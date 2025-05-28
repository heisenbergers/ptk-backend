### dependencies ###
from fastapi import FastAPI, UploadFile, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager # Added for lifespan
from config import settings, ResponseModel 
from utils import DatabaseOperations, ModelOperations, VideoDownloader, FileOperations
from sqlalchemy.orm import Session
# import random # No longer used
import uvicorn
# import torch # No longer directly used here, handled in ModelOperations
import os
# import time # No longer used

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup:
    print("INFO:     Starting up application...")
    print(f"INFO:     Permanent upload directory: {settings.permanent_upload_directory}")
    print(f"INFO:     Temporary upload directory: {settings.temporary_upload_directory}")
    print(f"INFO:     Temporary transcoding directory: {settings.temporary_transcoding_directory}")
    print(f"INFO:     Database URL: {DatabaseOperations.DATABASE_URL}")
    print(f"INFO:     Model Checkpoint: {settings.model_checkpoint}")
    print(f"INFO:     Quantization: {settings.quantization}")
    print(f"INFO:     Deepfake detection enabled: {settings.deepfake_config}")


    FileOperations.create_and_verify_folders([
        settings.permanent_upload_directory,
        settings.temporary_upload_directory,
        settings.temporary_transcoding_directory
    ])
    print("INFO:     Directories checked/created.")

    DatabaseOperations.initialise_db()
    print("INFO:     Database initialized.")

    print("INFO:     Loading model and processor...")
    model, processor = ModelOperations.load_model_and_processor(
        checkpoint=settings.model_checkpoint, 
        min_pixels=settings.min_pixels,       
        max_pixels=settings.max_pixels        
    )
    app.state.model = model
    app.state.processor = processor
    print("INFO:     Model and processor loaded.")
    print("INFO:     Application startup complete.")
    yield
    # Shutdown:
    print("INFO:     Shutting down application...")
    if hasattr(app.state, 'model'):
        del app.state.model
    if hasattr(app.state, 'processor'):
        del app.state.processor
    print("INFO:     Application shutdown complete.")


### api functions ###
# initialising FastAPI
app = FastAPI(lifespan=lifespan)

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_methods=["*"],
                   allow_headers=["*"])

@app.get("/")
def read_root():
    """Root endpoint for the API.

    Returns:
        dict: A message indicating the API is live.
    """
    return {"message":  "API is live."}


@app.post("/uploadurl")
async def parse_url(
    url: str = Query(...),
    db: Session = Depends(DatabaseOperations.get_db)
):
    """Downloads a video from a URL, processes it, and stores its metadata.

    Args:
        url (str): The URL of the video to download.
        db (Session, optional): SQLAlchemy session. Defaults to Depends(DatabaseOperations.get_db).

    Returns:
        ResponseModel: An object containing details of the uploaded video or failure status.
    """
    try:
        FileOperations.url_security_check(url)
        # Pass settings for directory paths to VideoDownloader.run if it needs them
        media_uuid, upload_datetime, filename_cleaned, filepath, media_type = VideoDownloader.run(url=url, config=settings) # Pass settings
        deepfake_enabled = settings.deepfake_config 

        if not deepfake_enabled: # Logic remains the same, just using settings
            DatabaseOperations.create_record(db=db,
                                media_uuid=media_uuid,
                                upload_datetime=upload_datetime,
                                file_name=filename_cleaned,
                                file_path=filepath,
                                deepfake=False,
                                source_url=url,
                                media_type=media_type,
                                status="Uploaded"
                                )
        else:
            DatabaseOperations.create_record(db=db,
                                media_uuid=media_uuid,
                                upload_datetime=upload_datetime,
                                file_name=filename_cleaned,
                                file_path=filepath,
                                deepfake=None, 
                                source_url=url,
                                media_type=media_type,
                                status="Uploaded" \
                                )

        return ResponseModel(media_uuid=media_uuid,
                    report_time=upload_datetime,
                    deepfake=None if deepfake_enabled else False, 
                    summary=None,
                    status="Uploaded") 

    except Exception as e:
        print(f"Exception: {e}")
        return ResponseModel(media_uuid=None,
                        report_time=None,
                        deepfake=None,
                        summary=None,
                        status="Failed")


@app.post("/upload/")
async def upload_file(post_file: UploadFile, db: Session = Depends(DatabaseOperations.get_db)) -> ResponseModel:
    """Uploads a video file, processes it, and stores its metadata.

    Args:
        post_file (UploadFile): The video file to upload.
        db (Session, optional): SQLAlchemy session. Defaults to Depends(DatabaseOperations.get_db).

    Returns:
        ResponseModel: An object containing details of the uploaded video or failure status.
    """
    try:
        media_uuid, upload_datetime, filename_cleaned, filepath, media_type = FileOperations.upload(post_file, config=settings) # Pass settings
        deepfake_enabled = settings.deepfake_config 

        initial_deepfake_status = None if deepfake_enabled else False

        # creates a db record
        DatabaseOperations.create_record(db=db,
                                        media_uuid=media_uuid,
                                        upload_datetime=upload_datetime,
                                        file_name=filename_cleaned,
                                        file_path=filepath,
                                        deepfake=initial_deepfake_status,
                                        source_url=None,
                                        media_type=media_type,
                                        status="Uploaded" 
                                        )

        return ResponseModel(media_uuid=media_uuid,
                                report_time=upload_datetime,
                                deepfake=initial_deepfake_status,
                                summary=None,
                                status="Uploaded")

    except Exception as e:
        print(f"Exception: {e}")
        return ResponseModel(media_uuid=None,
                        report_time=None,
                        deepfake=None,
                        summary=None,
                        status="Failed")

@app.delete("/delete/{media_uuid}")
async def delete_video(media_uuid: str, db: Session = Depends(DatabaseOperations.get_db)):
    """Deletes a video file and its record from the database.

    Args:
        media_uuid (str): The UUID of the media file to delete.
        db (Session, optional): SQLAlchemy session. Defaults to Depends(DatabaseOperations.get_db).

    Returns:
        dict: A message confirming the deletion.
    """

    file_record = DatabaseOperations.retrieve_filerecord(db, media_uuid)
    file_path = file_record.file_path
    FileOperations.delete(file_path)
    DatabaseOperations.delete_filerecord(db=db, media_uuid=media_uuid)

    return {"detail": f"File with UUID {media_uuid} has been deleted"}


@app.post("/predict/{media_uuid}")
async def predict(request: Request, media_uuid: str, db: Session = Depends(DatabaseOperations.get_db)) -> ResponseModel:
    """Generates a summary for a video using a machine learning model.

    Args:
        request (Request): The FastAPI request object to access app.state.
        media_uuid (str): The UUID of the media file to process.
        db (Session, optional): SQLAlchemy session. Defaults to Depends(DatabaseOperations.get_db).

    Returns:
        ResponseModel: An object containing the prediction details or failure status.
    """
    file_record = None 
    try:
        file_record = DatabaseOperations.retrieve_filerecord(db, media_uuid)
        model = request.app.state.model
        processor = request.app.state.processor

        summary = ModelOperations.inference(model=model,
                                            processor=processor,
                                            system_prompt=settings.system_prompt, 
                                            user_prompt=settings.user_prompt,     
                                            file_path = file_record.file_path)

        current_deepfake_status = file_record.deepfake
        if settings.deepfake_config and current_deepfake_status is None:
            sensity_api_key = os.getenv("SENSITY_API_KEY")
            if sensity_api_key:
                api_headers = {"Authorization": f"Bearer {sensity_api_key}"}
                try:
                    print(f"INFO:     Performing deepfake detection for {media_uuid}...")
                    current_deepfake_status = FileOperations.deepfake_detection(
                        file_name=file_record.file_name,
                        file_path=file_record.file_path,
                        api_headers=api_headers
                    )
                    print(f"INFO:     Deepfake detection for {media_uuid} result: {current_deepfake_status}")
                except Exception as df_exc:
                    print(f"ERROR:    Deepfake detection failed for {media_uuid}: {df_exc}")
                    current_deepfake_status = False 
            else:
                print("WARNING:  SENSITY_API_KEY not set. Skipping deepfake detection.")
                current_deepfake_status = False

        DatabaseOperations.update_filerecord(db=db,
                                    media_uuid=media_uuid,
                                    summary=summary,
                                    deepfake=current_deepfake_status, 
                                    status="Completed")

        return ResponseModel(
                        media_uuid=media_uuid,
                        report_time=file_record.upload_datetime,
                        deepfake=current_deepfake_status,
                        summary=summary,
                        status="Completed"
                        )

    except Exception as e:
        print(f"ERROR: Prediction failed for {media_uuid}: {e}")
        if file_record: # Check if file_record was retrieved before error
            DatabaseOperations.update_filerecord(db=db,
                                media_uuid=media_uuid,
                                summary=None,
                                deepfake=file_record.deepfake, # Keep original deepfake status on failure
                                status="Failed")

        return ResponseModel(
                    media_uuid=media_uuid,
                    report_time=file_record.upload_datetime if file_record else None,
                    deepfake=file_record.deepfake if file_record else None,
                    summary=None,
                    status="Failed"
                    )


# return the record from query.
@app.get("/query/{media_uuid}")
async def query(media_uuid: str, db: Session = Depends(DatabaseOperations.get_db)) -> ResponseModel:
    """Retrieves the record of a media file from the database.

    Args:
        media_uuid (str): The UUID of the media file to query.
        db (Session, optional): SQLAlchemy session. Defaults to Depends(DatabaseOperations.get_db).

    Returns:
        ResponseModel: An object containing the details of the queried media file.
    """
    file_record = DatabaseOperations.retrieve_filerecord(db = db,
                                                         media_uuid = media_uuid)
    return ResponseModel(
                        media_uuid=media_uuid,
                        report_time=file_record.upload_datetime,
                        deepfake=file_record.deepfake,
                        summary=file_record.summary,
                        status=file_record.status
                        )


if __name__ == '__main__':
    # Read UVICORN_HOST and UVICORN_PORT from environment variables, with defaults
    host = os.getenv("UVICORN_HOST", "127.0.0.1")
    port = int(os.getenv("UVICORN_PORT", "8000")) # Defaulted to 8000 as in run.sh
    log_level = os.getenv("UVICORN_LOG_LEVEL", "info")

    uvicorn.run("main:app", port=port, host=host, log_level=log_level, reload=True if os.getenv("UVICORN_RELOAD", "False").lower() == "true" else False)