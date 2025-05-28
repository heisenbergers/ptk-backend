### dependencies ###
from fastapi import FastAPI, UploadFile, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from config import PTKConfig, ResponseModel
from utils import DatabaseOperations, ModelOperations, VideoDownloader, FileOperations
from sqlalchemy.orm import Session
import random
import uvicorn
import torch
import os
import time

FileOperations.create_and_verify_folders([PTKConfig.permanent_upload_directory, PTKConfig.temporary_upload_directory, PTKConfig.temporary_transcoding_directory])
DatabaseOperations.initialise_db()
model, processor = ModelOperations.load_model_and_processor()

### api functions ###
# initialising FastAPI
app = FastAPI()

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
        media_uuid, upload_datetime, filename_cleaned, filepath, media_type = VideoDownloader.run(url=url)
        deepfake = PTKConfig.deepfake_config

        if not deepfake:
            DatabaseOperations.create_record(db=db,
                                media_uuid=media_uuid,
                                upload_datetime=upload_datetime,
                                file_name=filename_cleaned,
                                file_path=filepath,
                                deepfake=deepfake,
                                source_url=url,
                                media_type=media_type,
                                status="Uploaded"
                                )

        return ResponseModel(media_uuid=media_uuid,
                    report_time=upload_datetime,
                    deepfake=deepfake,
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
        media_uuid, upload_datetime, filename_cleaned, filepath, media_type = FileOperations.upload(post_file)
        deepfake = PTKConfig.deepfake_config

        if not deepfake:
            # creates a db record
            DatabaseOperations.create_record(db=db,
                                            media_uuid=media_uuid,
                                            upload_datetime=upload_datetime,
                                            file_name=filename_cleaned,
                                            file_path=filepath,
                                            deepfake=deepfake,
                                            source_url=None,
                                            media_type=media_type,
                                            status="Uploaded"
                                            )

        return ResponseModel(media_uuid=media_uuid,
                                report_time=upload_datetime,
                                deepfake=deepfake,
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
async def predict(media_uuid: str, db: Session = Depends(DatabaseOperations.get_db)) -> ResponseModel:
    """Generates a summary for a video using a machine learning model.

    Args:
        media_uuid (str): The UUID of the media file to process.
        db (Session, optional): SQLAlchemy session. Defaults to Depends(DatabaseOperations.get_db).

    Returns:
        ResponseModel: An object containing the prediction details or failure status.
    """
    try:
        file_record = DatabaseOperations.retrieve_filerecord(db, media_uuid)
        summary = ModelOperations.inference(model=model,
                                            processor=processor,
                                            system_prompt=PTKConfig.system_prompt,
                                            user_prompt=PTKConfig.user_prompt,
                                            file_path = file_record.file_path,)

        DatabaseOperations.update_filerecord(db=db,
                                    media_uuid=media_uuid,
                                    summary=summary,
                                    deepfake=file_record.deepfake,
                                    status="Completed")

        return ResponseModel(
                        media_uuid=media_uuid,
                        report_time=file_record.upload_datetime,
                        deepfake=file_record.deepfake,
                        summary=summary,
                        status="Completed"
                        )

    except Exception as e:
        print(e)

        DatabaseOperations.update_filerecord(db=db,
                            media_uuid=media_uuid,
                            summary=None,
                            deepfake=file_record.deepfake,
                            status="Failed")

        return ResponseModel(
                    media_uuid=media_uuid,
                    report_time=None,
                    deepfake=None,
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
    uvicorn.run("main:app", port=8080, host="127.0.0.1")