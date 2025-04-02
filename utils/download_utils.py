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
    'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]',
    'outtmpl': None,
    'quiet': False,
    'noprogress': True,
    'nooverwrites': True,
    'socket_timeout': 30,
    'retries': 3, 
    'cookiefile':'cookies.txt', # please take from burner account
    'noplaylist': True,           
    'restrictfilenames': True
    }

    @classmethod
    def run(cls, url):

        video_temp_dir = tempfile.mkdtemp(prefix="media_dl_", dir=cls.temporary_uploads)
        cls.downloader_options["outtmpl"] = os.path.join(video_temp_dir, '%(title)s.%(ext)s')
        try:
            with yt_dlp.YoutubeDL(cls.downloader_options) as ydl:
                ydl.download(url)
                
            # 6) Validate downloaded files
            downloaded_files = os.listdir(video_temp_dir)
            if not downloaded_files:
                raise HTTPException(
                    status_code=400,
                    detail="No file was downloaded from the provided URL."
                )
            
            if len(downloaded_files) > 1:
                video_files = [f for f in downloaded_files if os.path.splitext(f)[1].lower() in ['.mp4', '.webm', '.mkv']]
                if len(video_files) != 1:
                    raise HTTPException(
                        status_code=400,
                        detail="Error: More than one video file downloaded, currently not supported"
                    )
                temp_file = video_files[0]
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
            shutil.rmtree(video_temp_dir, ignore_errors=True)
            
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

