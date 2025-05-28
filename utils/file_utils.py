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
        """Replaces any non-permitted characters in the filename with underscores.

        Args:
            filename (str): The original filename.

        Returns:
            str: The sanitized filename containing only alphanumerical characters and ("_",".","-").
        """
        filename = os.path.basename(filename)  # remove path traversal
        filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)  # allow only safe chars
        return filename

    @classmethod
    def is_allowed_file(cls, filename: str) -> bool:
        """Checks if the file extension is in the list of allowed extensions.

        Args:
            filename (str): The name of the file.

        Returns:
            bool: True if the file extension is allowed, False otherwise.
        """
        ext = os.path.splitext(filename)[1].lower()
        return ext in cls.allowed_extensions


    @staticmethod
    def probe_transcode(media_uuid, file_path):
        """Probes a video file for its codec and size, and transcodes it to H.265 (libx265)
        if the codec is not H.264/H.265 or if the size exceeds the configured maximum.
        This is essential for compatibility with Qwen2.5VL via decord.

        Args:
            media_uuid (str): UUID for the temporary file if transcoding is needed.
            file_path (str): Path of the original video file. The original file will be
                             replaced by the transcoded version if transcoding occurs.

        Raises:
            subprocess.CalledProcessError: If ffprobe or ffmpeg commands fail.
        """
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
                    'ffmpeg',  # Hardware acceleration using NVDEC
                    '-i', file_path,
                    '-c:v', 'libx265',
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
        """Creates directories if they do not already exist.

        Args:
            directories (list): A list of directory paths to create.
        """
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    @classmethod
    def process_filename(cls, filename):
        """Generates metadata for a given filename, including UUID, upload datetime,
        sanitized filename, full file path, and media type.

        Args:
            filename (str): The original name of the file.

        Returns:
            tuple: A tuple containing:
                - media_uuid (str): A unique identifier for the media.
                - upload_datetime (str): The current datetime in 'Asia/Singapore' timezone.
                - filename_cleaned (str): The sanitized filename, prefixed with the media_uuid.
                - file_path (str): The full path to where the file will be stored.
                - media_type (str): "video" or "image" based on the file extension.
        """
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
        """Performs security checks on a given URL.

        Checks include:
        1. Preventing access to local/internal networks.
        2. Ensuring the domain is in the list of permitted hosts.

        Args:
            url (str): The URL to check.

        Raises:
            HTTPException: If the URL fails any security check (e.g., local access, non-permitted domain).
        """
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
        """Handles the file upload process.

        This includes sanitizing the filename, checking for allowed file types and MIME types,
        saving the file to the permanent upload directory, and transcoding if it's a video.

        Args:
            post_file (UploadFile): The file uploaded via a POST request.

        Raises:
            HTTPException: If the file type or MIME type is invalid, or if an error occurs during saving or transcoding.

        Returns:
            tuple: A tuple containing:
                - media_uuid (str): UUID of the uploaded media.
                - upload_datetime (str): Datetime of the upload.
                - filename_cleaned (str): Sanitized name of the uploaded file.
                - filepath (str): Path where the file is saved.
                - media_type (str): Type of the media ("video" or "image").
        """
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
        """Deletes a file from the filesystem.

        Args:
            file_path (str): The path to the file to be deleted.

        Raises:
            HTTPException: If an error occurs during file deletion (excluding FileNotFoundError).
        """
        try:
            os.remove(file_path)

        except FileNotFoundError:
            print(f"Warning: File {file_path} not found on disk.")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An error occurred while deleting the file: {str(e)}")

    @staticmethod
    def sensity_post(file_name, file_path, api_headers):
        """Sends a video file to the Sensity AI API for face manipulation detection.

        Args:
            file_name (str): The name of the file.
            file_path (str): The path to the video file.
            api_headers (dict): Headers for the Sensity API request, including authorization.

        Raises:
            FileNotFoundError: If the video file is not found at file_path.
            requests.exceptions.RequestException: If an error occurs during the API request.
            ValueError: If the API response is not successful or cannot be decoded, or if 'report_id' is missing.
            KeyError: If 'report_id' is missing in the API response.


        Returns:
            str: The task ID (report_id) from the Sensity API response.
        """
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
        """Polls the Sensity AI API for the result of a face manipulation detection task.

        Args:
            task_id (str): The task ID (report_id) obtained from `sensity_post`.
            api_headers (dict): Headers for the Sensity API request, including authorization.
            interval (int, optional): Polling interval in seconds. Defaults to 5.
            timeout (int, optional): Timeout in seconds for polling. Defaults to 500.

        Raises:
            requests.exceptions.RequestException: If an error occurs during an API request.
            KeyError: If the API response is missing expected keys ('status' or 'result').
            TimeoutError: If the polling times out before the task is completed.

        Returns:
            dict: The 'result' dictionary from the Sensity API response when the task is completed.
        """
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
        """Performs deepfake detection on a video file using the Sensity AI API.

        This function posts the video for analysis and then polls for the result.

        Args:
            file_name (str): The name of the file.
            file_path (str): The path to the video file.
            api_headers (dict): Headers for the Sensity API request, including authorization.

        Returns:
            bool: True if the video is classified as "fake", False if "real" or "no_faces".
                  Prints a warning and returns False for unconfigured classifications.
        """
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