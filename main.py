### dependencies ###
from fastapi import FastAPI, UploadFile, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager # Import asynccontextmanager
from config import PTKConfig, ResponseModel
from utils import DatabaseOperations, ModelOperations, VideoDownloader, FileOperations # Ensure ModelOperations is here
from sqlalchemy.orm import Session
import uvicorn
import os
import torch # <--- IMPORT TORCH HERE

# --- Global variables for the model ---
# These will be defined at the module level and initialized to None.
# They will be populated during the application startup via the lifespan event.
llm = None
processor = None
sampling_params = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # The 'global' statement must come before any use or assignment
    # of these variables within this function.
    global llm, processor, sampling_params

    # Startup: Load the ML model and other resources
    print("Application startup: Loading model and initializing database...")
    FileOperations.create_and_verify_folders([
        PTKConfig.permanent_upload_directory,
        PTKConfig.temporary_upload_directory,
        PTKConfig.temporary_transcoding_directory
    ])
    DatabaseOperations.initialise_db()
    
    # Assign to the global variables
    llm, processor, sampling_params = ModelOperations.load_model_and_processor()
    print("Model loaded successfully.")
    
    yield # Application is now running

    # Shutdown: Clean up the ML models and release resources
    print("Application shutdown: Cleaning up model...")
    
    # Check if variables were loaded before trying to delete
    if llm is not None:
        del llm
        llm = None # Set back to None
    if processor is not None:
        del processor
        processor = None # Set back to None
    if sampling_params is not None:
        del sampling_params
        sampling_params = None # Set back to None
            
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("Model and resources cleaned up.")

# Initialising FastAPI with the lifespan event handler
app = FastAPI(lifespan=lifespan)

# Add Middleware (ensure this comes after app initialization)
app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_methods=["*"],
                   allow_headers=["*"])

### API functions ###

@app.get("/")
def read_root():
    return {"message": "API is live."}

@app.post("/uploadurl")
async def parse_url(
    url: str = Query(...),
    db: Session = Depends(DatabaseOperations.get_db)
):
    if not llm or not processor: # Check if model is ready
        return ResponseModel(media_uuid=None, report_time=None, deepfake=None, summary="Model not ready", status="Failed")
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
        print(f"Exception in /uploadurl: {e}")
        return ResponseModel(media_uuid=None,
                        report_time=None,
                        deepfake=None,
                        summary=str(e), # Include error message in summary for debugging
                        status="Failed")
        

@app.post("/upload/")
async def upload_file(post_file: UploadFile, db: Session = Depends(DatabaseOperations.get_db)) -> ResponseModel:
    if not llm or not processor: # Check if model is ready
        return ResponseModel(media_uuid=None, report_time=None, deepfake=None, summary="Model not ready", status="Failed")
    try:
        media_uuid, upload_datetime, filename_cleaned, filepath, media_type = FileOperations.upload(post_file)
        deepfake = PTKConfig.deepfake_config

        if not deepfake:
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
        print(f"Exception in /upload: {e}")
        return ResponseModel(media_uuid=None,
                        report_time=None,
                        deepfake=None,
                        summary=str(e),
                        status="Failed")

@app.delete("/delete/{media_uuid}")
async def delete_video(media_uuid: str, db: Session = Depends(DatabaseOperations.get_db)):
    try:
        file_record = DatabaseOperations.retrieve_filerecord(db, media_uuid)
        if file_record and hasattr(file_record, 'file_path') and file_record.file_path:
            FileOperations.delete(file_record.file_path)
            DatabaseOperations.delete_filerecord(db=db, media_uuid=media_uuid)
            return {"detail": f"File with UUID {media_uuid} has been deleted"}
        else:
            return {"detail": f"File record not found or file_path missing for UUID {media_uuid}"}, 404
    except Exception as e:
        print(f"Exception in /delete/{media_uuid}: {e}")
        return {"detail": f"Error deleting file with UUID {media_uuid}: {str(e)}"}, 500


@app.post("/predict/{media_uuid}")
async def predict(media_uuid: str, db: Session = Depends(DatabaseOperations.get_db)) -> ResponseModel:
    if not llm or not processor or not sampling_params: # Check if model components are ready
        return ResponseModel(media_uuid=media_uuid, report_time=None, deepfake=None, summary="Model not ready", status="Failed")
    
    file_record = DatabaseOperations.retrieve_filerecord(db, media_uuid)
    if not file_record:
        return ResponseModel(media_uuid=media_uuid, report_time=None, deepfake=None, summary="File record not found", status="Failed")

    try:
        summary = ModelOperations.inference(llm=llm,
                                            processor=processor,
                                            sampling_params=sampling_params,
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
        print(f"Exception in /predict/{media_uuid}: {e}")
        DatabaseOperations.update_filerecord(db=db,
                            media_uuid=media_uuid,
                            summary=str(e), # Store error in summary for inspection
                            deepfake=file_record.deepfake, # Use existing deepfake value
                            status="Failed")
        
        return ResponseModel(
                    media_uuid=media_uuid,
                    report_time=file_record.upload_datetime, # Use existing report time
                    deepfake=file_record.deepfake, # Use existing deepfake value
                    summary=str(e),
                    status="Failed"
                    )

        
@app.get("/query/{media_uuid}")
async def query(media_uuid: str, db: Session = Depends(DatabaseOperations.get_db)) -> ResponseModel:
    file_record = DatabaseOperations.retrieve_filerecord(db = db, media_uuid = media_uuid)
    if not file_record:
        return ResponseModel(media_uuid=media_uuid, report_time=None, deepfake=None, summary="File record not found", status="Failed")
    
    return ResponseModel(
                        media_uuid=media_uuid,
                        report_time=file_record.upload_datetime,
                        deepfake=file_record.deepfake,
                        summary=file_record.summary,
                        status=file_record.status
                        )

if __name__ == '__main__':
    uvicorn.run(app, port=8000, host="127.0.0.1")
