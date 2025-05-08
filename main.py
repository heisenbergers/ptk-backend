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

FileOperations.create_and_verify_folders([PTKConfig.permanent_upload_directory, PTKConfig.temporary_upload_directory, PTKConfig.temporary_transcoding_directory])
DatabaseOperations.initialise_db()
model, processor = ModelOperations.load_model_and_processor()

api_headers = {"Authorization": f"{os.getenv('SENSITY_API_KEY')}"}

### api functions ###
# initialising FastAPI
app = FastAPI()

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_methods=["*"],
                   allow_headers=["*"])

@app.get("/")
def read_root():
    return {"message":  "API is live."}


@app.post("/uploadurl")
async def parse_url(
    url: str = Query(...),
    db: Session = Depends(DatabaseOperations.get_db)
):
    try:
        FileOperations.url_security_check(url)
        media_uuid, upload_datetime, filename_cleaned, filepath, media_type = VideoDownloader.run(url=url)
        deepfake = FileOperations.deepfake_detection(filename_cleaned, filepath, api_headers)
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
    try:
        media_uuid, upload_datetime, filename_cleaned, filepath, media_type = FileOperations.upload(post_file)
        deepfake = FileOperations.deepfake_detection(filename_cleaned, filepath, api_headers)

        if not deepfake:
            # creates a db record
            DatabaseOperations.create_record(db=db,
                                            media_uuid=media_uuid,
                                            upload_datetime=upload_datetime,
                                            file_name=filename_cleaned,
                                            file_path=filepath,
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

    file_record = DatabaseOperations.retrieve_filerecord(db, media_uuid) 
    file_path = file_record.file_path
    FileOperations.delete(file_path)
    DatabaseOperations.delete_filerecord(db=db, media_uuid=media_uuid)

    return {"detail": f"File with UUID {media_uuid} has been deleted"}


@app.post("/predict/{media_uuid}")
async def predict(media_uuid: str, db: Session = Depends(DatabaseOperations.get_db)) -> ResponseModel:
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
        return ResponseModel(
                    media_uuid=media_uuid,
                    report_time=file_record.upload_datetime,
                    deepfake=None,
                    summary=None,
                    status="Failed"
                    )

        
# return the record from query.
@app.get("/query/{media_uuid}")
async def query(media_uuid: str, db: Session = Depends(DatabaseOperations.get_db)) -> ResponseModel:
    file_record = DatabaseOperations.retrieve_filerecord(db = db,
                                                         media_uuid = media_uuid)
    return ResponseModel(
                        media_uuid=media_uuid,
                        report_time=file_record.upload_datetime,
                        deepfake=file_record.deepfake,
                        summary=file_record.summary,
                        status="Completed"
                        )


if __name__ == '__main__':
    uvicorn.run("main:app", port=8080, host="127.0.0.1")
