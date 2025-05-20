import re
import uuid
import os
import json
import subprocess
from urllib.parse import urlparse
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil
from fastapi import HTTPException
from config import PTKConfig
import time
import requests


class FileOperations:
    allowed_video_extensions = {".mp4", ".avi", ".mov", ".mkv"}
    allowed_image_extensions = {".png", ".jpg", ".tif"}
    allowed_extensions = allowed_image_extensions | allowed_video_extensions
    allowed_mime_types = {"video/mp4", "video/x-msvideo", "video/quicktime", "video/x-matroska"}
    permitted_hosts = {'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
            'facebook.com', 'fb.com', 'instagram.com', 'twitter.com',
            'x.com', 'reddit.com', 'tiktok.com', 'm.youtube.com', 'm.facebook.com'}

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        ''' Replaces any non-permitted characters in the filename with underscores 

        Args:
            filename (str): upload filename in a string

        Returns:
            filename (str): string only containing alphanumerical + ("_",".","-") characters
        '''
        filename = os.path.basename(filename)  # remove path traversal
        filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)  # allow only safe chars
        return filename

    @classmethod
    def is_allowed_file(cls, filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in cls.allowed_extensions


    @staticmethod
    def probe_transcode(media_uuid, file_path):
        '''Probes a file for its codec, and transcodes it to libx265 if needed.
        Essential for passing it into Qwen2.5VL via decord.
        
        Args:
            media_uuid (str): uuid for the temporary file
            file_path (str): path of the original video to be replaced
        '''
        try:
            # Probe the video using ffprobe
            probe_cmd = [
                'ffprobe', 
                '-v', 'verbose', 
                '-print_format', 'json', 
                '-show_format', 
                '-show_streams', 
                file_path
            ]
            
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            video_info = json.loads(probe_result.stdout)
            
            codec = video_info['streams'][0]['codec_name']
            size = float(video_info['format']['size']) / (1024 * 1024)
            
            if (codec not in ["h264", "h265", "hevc"]) or (size > PTKConfig.max_video_size):
                print("Video processing failed, transcoding video ...")
                temp_filepath = f"{PTKConfig.temporary_transcoding_directory}/{media_uuid}_temp.mp4"
                
                # Transcode command with NVDEC hardware acceleration
                transcode_cmd = [
                    'ffmpeg',
                    '-hwaccel', 'cuda',  # Hardware acceleration using NVDEC
                    '-i', file_path,
                    '-c:v', 'hevc_nvenc',
                    '-c:a', 'aac',
                    '-b:a', '32k',
                    '-b:v', '400k',
                    '-preset', 'fast',
                    '-crf', '28',
                    '-vf', 'scale=640:-2',
                    '-r', '24',
                    '-y',  # Equivalent to overwrite_output=True
                    temp_filepath
                ]
                
                subprocess.run(transcode_cmd, check=True)
                os.replace(temp_filepath, file_path)
                
        except subprocess.CalledProcessError as e:
            print('stdout:', e.stdout)
            print('stderr:', e.stderr)
            raise e
        else:
            pass


    @staticmethod
    def create_and_verify_folders(directories:list):
        """Creates directories if they do not exist.

        Args:
            directories (list): List of directories to confirm and verify
        """
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    @classmethod
    def process_filename(cls, filename):
            ''' Function to create the attributes required for database entry

            Args:

            Returns: 
            
            '''
            media_uuid = str(uuid.uuid1())
            upload_datetime = datetime.now(ZoneInfo('Asia/Singapore')).strftime(r"%d/%m/%y, %H:%M,%S")
            filename_cleaned = cls.sanitize_filename(filename)
            filename_cleaned = f"{media_uuid}_{filename_cleaned}"
            file_path = os.path.join(PTKConfig.permanent_upload_directory, filename_cleaned)
            ext = os.path.splitext(filename)[1].lower()
            if ext in cls.allowed_video_extensions:
                media_type = "video"
            elif ext in cls.allowed_image_extensions:
                media_type = "image"

            return media_uuid, upload_datetime, filename_cleaned, file_path, media_type

    @classmethod
    def url_security_check(cls, url):
        parsed_url = urlparse(url)
        # 1) Prevent access to local/internal networks.
        if not parsed_url.netloc or parsed_url.netloc in [
            "localhost", "127.0.0.1", "0.0.0.0",
            "::1", "internal", "intranet", "local"
        ]:
            raise HTTPException(
                status_code=400,
                detail="Access to local or internal networks not allowed"
            )
        # 2) Check if domain is permitted.
        domain = parsed_url.netloc.lstrip("www.")
        if domain not in cls.permitted_hosts:
            raise HTTPException(
                status_code=400,
                detail=f"Domain '{domain}' is not permitted."
            )

    @classmethod
    def upload(cls, post_file):
        filename = post_file.filename
        media_uuid, upload_datetime, filename_cleaned, filepath, media_type = cls.process_filename(filename)

        if not cls.is_allowed_file(filename_cleaned) :
            raise HTTPException(status_code=400, detail="Invalid file. Only image/video files are allowed.")
        
        if post_file.content_type not in cls.allowed_mime_types:
            raise HTTPException(status_code=400, detail="MIME Headers are invalid")

        # copy the uploaded file to the uploads folder, streaming the input
        try:
            with open(filepath,"wb") as buffer:
                shutil.copyfileobj(post_file.file, buffer)

            if media_type == "video":
                cls.probe_transcode(media_uuid, filepath)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return media_uuid, upload_datetime, filename_cleaned, filepath, media_type

    @staticmethod
    def delete(file_path):
        try:
            os.remove(file_path)

        except FileNotFoundError:
            print(f"Warning: File {file_path} not found on disk.")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An error occurred while deleting the file: {str(e)}")
    
    @staticmethod
    def sensity_post(file_name, file_path, api_headers):
        url = "https://api.sensity.ai/tasks/face_manipulation"
        data = {"explain": True}
        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_name, f, "video/mp4")}
                response = requests.post(url, headers=api_headers, data=data, files=files)
                response.raise_for_status()
                try:
                    response_json = response.json()
                    if "report_id" in response_json:
                        task_id = response_json["report_id"]
                        if response_json.get("success") is True:
                            return task_id
                        else:
                            raise ValueError("API request was not successful")
                    else:
                        raise KeyError("Missing 'report_id' in the API response.")
                except ValueError:
                    raise ValueError("Failed to decode JSON response from the API.")
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found at: {file_path}")
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Error during API request: {e}")

    
    @staticmethod
    def sensity_polling(task_id, api_headers, interval=5, timeout=500):
        url = f"https://api.sensity.ai/tasks/face_manipulation/{task_id}"
        end_time = time.time() + timeout

        while time.time() < end_time:
            try:
                response = requests.get(url, headers=api_headers)
                response.raise_for_status()
                response_json = response.json()
                if "status" in response_json:
                    if response_json["status"] == "completed":
                        if "result" in response_json:
                            return response_json["result"]
                        else:
                            raise KeyError("Missing 'result' key in the API response.")
                time.sleep(interval)
            except requests.exceptions.RequestException as e:
                print(f"Error during API request: {e}")
                time.sleep(interval) 
            except KeyError as e:
                print(f"Error parsing API response: {e}")
                raise 

        raise TimeoutError(f"Polling for task {task_id} timed out after {timeout} seconds.")

    @staticmethod
    def deepfake_detection(file_name, file_path, api_headers):
        task_id = FileOperations.sensity_post(file_name, file_path, api_headers)
        deepfake_task_response = FileOperations.sensity_polling(task_id, api_headers)
        print(deepfake_task_response)
        deepfake_classification = deepfake_task_response["class_name"]
        if deepfake_classification == "fake":
            return True
        elif deepfake_classification in ["real", "no_faces"]:
            return False
        else:
            print(f"Warning: Unconfigured deepfake classification '{deepfake_classification}'")
            return False