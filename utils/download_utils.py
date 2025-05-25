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
        'format': 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 
        'outtmpl': None, 
        'quiet': False,
        'noprogress': True,
        'nooverwrites': False, 
        'socket_timeout': 30,
        'retries': 3,
        'cookiefile': PTKConfig.cookies_path if hasattr(PTKConfig, 'cookies_path') else None,
        'noplaylist': True,
        'restrictfilenames': True,
        'merge_output_format': 'mp4', 
    }

    @classmethod
    def run(cls, url):
        if not cls.temporary_uploads or not os.path.isdir(cls.temporary_uploads):
            # Fallback to system default temp if not configured or invalid
            # However, this might still lead to cross-device issues if not on the same device as permanent_uploads
            effective_temp_dir_base = None 
            print(f"Warning: PTKConfig.temporary_upload_directory is not set or invalid. Using system default temp directory.")
        else:
            effective_temp_dir_base = cls.temporary_uploads

        video_temp_dir = tempfile.mkdtemp(prefix="media_dl_", dir=effective_temp_dir_base)
        
        # Set dynamic output template for yt-dlp
        # yt-dlp will replace '%(title)s' and '%(ext)s'
        cls.downloader_options['outtmpl'] = os.path.join(video_temp_dir, '%(title)s.%(ext)s')

        try:
            with yt_dlp.YoutubeDL(cls.downloader_options) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                downloaded_file_name_in_temp = os.path.basename(ydl.prepare_filename(info_dict))


            if not downloaded_file_name_in_temp or not os.path.exists(os.path.join(video_temp_dir, downloaded_file_name_in_temp)):
                downloaded_files_list = os.listdir(video_temp_dir)
                if not downloaded_files_list:
                    raise HTTPException(
                        status_code=400,
                        detail="No file was downloaded from the provided URL."
                    )
                # If primary name not found but other files exist, take the first one (assuming single video download)
                # This part might need more robust logic if multiple files/formats are expected
                downloaded_file_name_in_temp = downloaded_files_list[0]


            full_temp_path = os.path.join(video_temp_dir, downloaded_file_name_in_temp)
            media_uuid, upload_datetime, filename_cleaned, final_filepath, media_type = FileOperations.process_filename(downloaded_file_name_in_temp) #
            if not FileOperations.is_allowed_file(filename_cleaned): #
                shutil.rmtree(video_temp_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type: {os.path.splitext(downloaded_file_name_in_temp)[1]}. Only {FileOperations.allowed_extensions} are allowed."
                )
            if media_type == "video":
                FileOperations.probe_transcode(media_uuid, full_temp_path) #
            
            os.makedirs(os.path.dirname(final_filepath), exist_ok=True)

            try:
                shutil.move(full_temp_path, final_filepath)
            except OSError as e:
                if e.errno == 18: 
                    print(f"Cross-device link detected for {full_temp_path} to {final_filepath}. Copying and deleting.")
                    shutil.copy2(full_temp_path, final_filepath) 
                    os.remove(full_temp_path)
                else:
                    raise e
                
            finally:
                try:
                    shutil.rmtree(video_temp_dir)
                except Exception as e_cleanup:
                    print(f"Warning: Failed to remove temporary directory {video_temp_dir}: {e_cleanup}")

            return media_uuid, upload_datetime, filename_cleaned, final_filepath, media_type

        except yt_dlp.utils.DownloadError as e:
            if os.path.exists(video_temp_dir): 
                shutil.rmtree(video_temp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=400,
                detail=f"Download failed: {str(e)}"
            )
        except HTTPException: 
            if os.path.exists(video_temp_dir):
                shutil.rmtree(video_temp_dir, ignore_errors=True)
            raise
        except Exception as e:
            if os.path.exists(video_temp_dir): 
                shutil.rmtree(video_temp_dir, ignore_errors=True)
            print(f"An unexpected error occurred in VideoDownloader.run: {type(e).__name__} - {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred while processing the video." 
            )