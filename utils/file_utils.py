import re
import uuid
import os
import ffmpeg
from urllib.parse import urlparse
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil
from fastapi import HTTPException
from config import PTKConfig
from typing import Union
import time
import requests


class FileOperations:
    allowed_video_extensions = {".mp4", ".avi", ".mov", ".mkv"}
    allowed_image_extensions = {".png", ".jpg", ".tif"}
    allowed_extensions = allowed_image_extensions | allowed_video_extensions
    allowed_mime_types = {"video/mp4", "video/x-msvideo", "video/quicktime", "video/x-matroska"}
    permitted_hosts = {'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
            'facebook.com', 'fb.com', 'instagram.com', 'twitter.com',
            'x.com', 'reddit.com', 'tiktok.com'}

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
        ''' Probes a file for its codec, and transcodes it to libx264 if it is not already in that codec. 

        Essential for passing it into Qwen2.5VL via decord. A temporary file is created before replacing the original file, because ffmpeg does not allow in-place replacement

        Args:
            media_uuid (str): uuid generated during the file upload, which is only used to create a temporary file
            filepath (str): the file path of the original video. this will be replaced immediately with the temporary file 
        '''
        try:
            video_info = ffmpeg.probe(file_path)
            codec = video_info['streams'][0]['codec_name']
            size = float(video_info['format']['size']) / (1024 * 1024)
            if (codec != Union["h264","h265"]) or (size > PTKConfig.max_video_size):
                print("Video processing failed, transcoding video ...")
                temp_filepath = f"{media_uuid}_temp.mp4" # the use of a temporary filepath is necessary because ffmpeg does not allow overwrites
                ffmpeg.input(file_path).output(
                                                temp_filepath,
                                                vcodec='libx265',
                                                acodec='aac',
                                                audio_bitrate='32k',
                                                video_bitrate='400k',
                                                preset='fast',
                                                crf=28,
                                                vf='scale=640:-2',
                                                r=24
                                                ).run(overwrite_output=True)
                
                os.replace(temp_filepath, file_path)


        except ffmpeg.Error as e:
            print('stdout:', e.stdout.decode('utf8'))
            print('stderr:', e.stderr.decode('utf8'))
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
    def sensity_post(file_record, headers):
        url = "https://api.sensity.ai/tasks/face_manipulation"
        data = {"explain": True}
        files = {"file": (f"{file_record.file_name}", open(f"{file_record.file_path}", "rb"), "video/mp4")}
        task_id, post_success = requests.post(url, headers=headers, data=data, files=files).json()
        return task_id, post_success

    @staticmethod
    def sensity_polling(task_id, headers, interval=5, timeout=300):
        url = f"https://api.sensity.ai/tasks/face_manipulation/{task_id}"
        end_time = time.time() + timeout
        completed = False
        while time.time() < end_time and completed == False:
            try:
                response = requests.get(url, headers=headers).json()
                if response["status"] == "completed":
                    completed = True
                    return response["result"]
            except requests.exceptions.RequestException:
                pass
            time.sleep(interval)
        raise TimeoutError("Polling timed out")
