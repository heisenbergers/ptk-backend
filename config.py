from pydantic import BaseModel

class PTKConfig:
    #upload configs
    permanent_upload_directory = "storage/videos"
    temporary_upload_directory = "/tmp/yt-dlp"
    temporary_transcoding_directory = "/tmp/ffmpeg"
    download_resolution = "480" #480p
    cookies_path = '/code/cookies.txt'

    #model configs
    model_checkpoint = "Qwen2.5-VL-7B-Instruct" #download into cache
    quantization = "4bit" # Use "16bit" if AWQ/GPTQ, use "4bit" or "8bit" if using BitsAndBytes
    max_video_size = 150 # max size of video in MB

    #prompts
    system_prompt = "You are a professional analyst at a law enforcement agency, with advanced vision capabilities and visual reasoning skills"
    user_prompt = """  Analyze the provided security video footage and deliver a comprehensive assessment following these structured steps:

    1. THREAT ASSESSMENT: Carefully examine the video to identify any potential safety or security threats present in the footage.

    2. DETAILED INVENTORY: Document all visible elements with precision:
    - People: Record each individual, their physical characteristics, clothing details, and movements
    - Objects: Describe significant objects, their locations, and any interaction with people
    - Actions: Chronologically list all notable activities occurring in the footage
    - Environment: Describe the surrounding buildings, landmarks, or any potential signage that may indicate location

    3. TEXT EXTRACTION: Identify and record all visible text including:
    - Timestamps and chronological indicators
    - Signage (street signs, business names, warning notices)
    - Location identifiers (addresses, landmarks, GPS coordinates)
    - Any other textual information present in the footage

    4. FACTUAL REPORTING: Maintain strict objectivity by reporting only observable facts. Do not speculate about intentions, atmosphere, mood, or make subjective assessments about the context.

    You must only respond in the following format:
    Summary:
    Description of People: 
    Objects Involved:
    Environment:
    Chronology of Events:
    Extracted Text:
    """


class ResponseModel(BaseModel):
    media_uuid: str | None
    report_time: str | None
    deepfake: bool | None
    summary: str | None
    status: str
    
    model_config= { "json_schema_extra":{
                                    "example": {
                                                "media_uuid": "a0d9asd9f-v8sd-v9ad-n9018203k1023",
                                                "upload_datetime": "28/03/25, 18:45,49",
                                                "deepfake": False,
                                                "summary": "The following video describes...",
                                                "status": "Completed"
                                                }
                                        }
                    }

