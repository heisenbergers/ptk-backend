# Upload configurations
import shutil
import tempfile
import yt_dlp
import os
from fastapi import HTTPException
from .file_utils import FileOperations
from config import PTKConfig

class VideoDownloader:
    permanent_uploads = PTKConfig.permanent_upload_directory
    temporary_uploads = PTKConfig.temporary_upload_directory
    downloader_options = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': None,
        'quiet': False,
        'noprogress': True,
        'nooverwrites': True,
        'socket_timeout': 30,
        'retries': 3,
        'cookiefile': PTKConfig.cookies_path, # please take from burner account
        'noplaylist': True,
        'restrictfilenames': True,
        'merge_output_format': 'mp4', # Ensure final output is mp4
    }

    @classmethod
    def run(cls, url):
        """Downloads a video from a given URL, processes it, and saves it.

        Args:
            url (str): The URL of the video to download.

        Raises:
            HTTPException: If the download fails, no file is downloaded,
                           multiple files are downloaded, the downloaded file is not MP4,
                           or an invalid file type is detected.

        Returns:
            tuple: A tuple containing:
                - media_uuid (str): UUID of the downloaded media.
                - upload_datetime (str): Datetime of the download.
                - filename_cleaned (str): Sanitized name of the downloaded file.
                - filepath (str): Path where the file is saved.
                - media_type (str): Type of the media ("video" or "image").
        """

        video_temp_dir = tempfile.mkdtemp(prefix="media_dl_", dir=cls.temporary_uploads)
        cls.downloader_options["outtmpl"] = os.path.join(video_temp_dir, '%(title)s.%(ext)s')
        try:
            with yt_dlp.YoutubeDL(cls.downloader_options) as ydl:
                ydl.download([url])

            # 6) Validate downloaded files
            downloaded_files = os.listdir(video_temp_dir)
            if not downloaded_files:
                raise HTTPException(
                    status_code=400,
                    detail="No file was downloaded from the provided URL."
                )

            if len(downloaded_files) > 1:
                video_files = [f for f in downloaded_files if os.path.splitext(f)[1].lower() in ['.mp4']]
                if len(video_files) != 1:
                    raise HTTPException(
                        status_code=400,
                        detail="Error: More than one MP4 video file downloaded, or no MP4 video found when multiple files were present."
                    )
                temp_file = video_files[0]
            elif len(downloaded_files) == 1 and os.path.splitext(downloaded_files[0])[1].lower() != '.mp4':
                raise HTTPException(
                    status_code=400,
                    detail="Error: Downloaded video is not in MP4 format."
                )
            else:
                temp_file = downloaded_files[0]

            full_temp_path = os.path.join(video_temp_dir, temp_file)
            media_uuid, upload_datetime, filename_cleaned, filepath, media_type = FileOperations.process_filename(full_temp_path)
            if not FileOperations.is_allowed_file(filename_cleaned):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid file. Only image/video files are allowed."
                )
            if media_type == "video":
                FileOperations.probe_transcode(media_uuid, full_temp_path)

            # 8) Move downloaded file from temp dir to final path
            os.replace(full_temp_path, filepath)
            try:
                shutil.rmtree(video_temp_dir)
            except Exception as e_cleanup:
                print(f"Warning: Failed to remove temporary directory {video_temp_dir}: {e_cleanup}") # Or use proper logging


            return media_uuid, upload_datetime, filename_cleaned, filepath, media_type

        except yt_dlp.utils.DownloadError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Download failed: {str(e)}"
            )

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )