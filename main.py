### dependencies ###
from fastapi import FastAPI, responses, UploadFile, Depends, Query
from config import PTKConfig, ResponseModel
from utils import DatabaseOperations, ModelOperations, VideoDownloader, FileOperations
from sqlalchemy.orm import Session
import random
import uvicorn

FileOperations.create_and_verify_folders([PTKConfig.permanent_upload_directory, PTKConfig.temporary_upload_directory])
DatabaseOperations.initialise_db()
model, processor = ModelOperations.load_model_and_processor()

### api functions ###
# initialising FastAPI
app = FastAPI()

@app.get("/")
def read_root():
    return {"message":  "API is live."
                        "/upload: endpoint to upload image or video; returns UUID"
                        "/uploadurl: endpoint to upload an image or video url; returns UUID"
                        "/delete/: endpoint to delete video; receives UUID, to trigger if user decides not to process video"
                        "/predict/: endpoint to generate summary; receives UUID"
                        }


@app.post("/uploadurl")
async def parse_url(
    url: str = Query(...),
    db: Session = Depends(DatabaseOperations.get_db)
):
    try:
        FileOperations.url_security_check(url)
        media_uuid, upload_datetime, filename_cleaned, filepath, media_type = VideoDownloader.run(url=url)
        DatabaseOperations.create_record(db=db,
                                        media_uuid=media_uuid,
                                        upload_datetime=upload_datetime,
                                        file_name=filename_cleaned,
                                        file_path=filepath,
                                        source_url=url,
                                        media_type=media_type,
                                        status="Uploaded"
                                        )        
        return ResponseModel(media_uuid=media_uuid,
                             report_time=upload_datetime,
                             deepfake=None,
                             summary=None,
                             status="Uploaded")
    except Exception as e:
        print(f"Exception: {e}")
        


@app.post("/upload/")
async def upload_file(post_file: UploadFile, db: Session = Depends(DatabaseOperations.get_db)) -> ResponseModel:
    # cleaning of filenames to prevent injection
    media_uuid, upload_datetime, filename_cleaned, filepath, media_type = FileOperations.upload(post_file)

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
    #PYDANTIC class
    return ResponseModel(media_uuid=media_uuid,
                             report_time=upload_datetime,
                             deepfake=None,
                             summary=None,
                             status="Uploaded")

@app.delete("/delete/{media_uuid}")
async def delete_video(media_uuid: str, db: Session = Depends(DatabaseOperations.get_db)):

    file_record = DatabaseOperations.retrieve_filerecord(db, media_uuid) 
    file_path = file_record.file_path
    FileOperations.delete(file_path)
    DatabaseOperations.delete_filerecord(db=db, media_uuid=media_uuid)

    return {"detail": f"File with UUID {media_uuid} has been deleted"}


@app.post("/predict/{media_uuid}")
async def predict(media_uuid: str, db: Session = Depends(DatabaseOperations.get_db)) -> ResponseModel:
    # to put in config
    file_record = DatabaseOperations.retrieve_filerecord(db, media_uuid)

    # docs :: https://docs.sensity.ai/#tag/Face-manipulation 

    # headers = {"Authorization": f"{os.getenv("SENSITY_API_KEY")}"}
    # task_id, post_success = FileOperations.sensity_post(file_record, headers)
    # deepfake_task_response = FileOperations.sensity_polling(task_id, headers)
    # deepfake = deepfake_task_response["class_name"]
    # deepfake_probability = deepfake_task_response["class_probability"]
    
    # if deepfake == True: 
        # summary = ModelOperations.inference(model=model,
        #                                    processor=processor,
        #                                    system_prompt=PTKConfig.system_prompt,
        #                                    user_prompt=PTKConfig.user_prompt,
        #                                    file_path = file_record.file_path,)

    # elif deepfake == False:
        # summary = None

    # return ResponseModel(
    #                    media_uuid=media_uuid,
    #                    report_time=file_record.upload_datetime,
    #                    deepfake=deepfake,
    #                    deepfake_probability=deepfake_probability
    #                    summary=predicted_summary
    #                    )  
    #       
    # else:
    #     return ResponseModel(
    #                    media_uuid=media_uuid,
    #                    report_time=file_record.upload_datetime,
    #                    deepfake=deepfake,
    #                    deepfake_probability=deepfake_probability
    #                    summary=None
    #                    )
    
    ### Placeholder ###
    deepfake_probability = random.random()
    deepfake= deepfake_probability > 0.7
    ### Placeholder ###
    if deepfake == False:
        try:
            summary = ModelOperations.inference(model=model,
                                                        processor=processor,
                                                        system_prompt=PTKConfig.system_prompt,
                                                        user_prompt=PTKConfig.user_prompt,
                                                        file_path = file_record.file_path,)
        except Exception as e:
            raise(e)

    elif deepfake == True:
        summary = None

    DatabaseOperations.update_filerecord(db=db,
                                        media_uuid=media_uuid,
                                        summary=summary,
                                        deepfake=deepfake,
                                        deepfake_probability=deepfake_probability,
                                        status="Completed")
    
    return ResponseModel(
                        media_uuid=media_uuid,
                        report_time=file_record.upload_datetime,
                        deepfake=deepfake,
                        summary=summary,
                        status="Completed"
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
