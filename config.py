from pydantic import BaseModel
import os

def get_deepfake_config():
    deepfake_config = os.getenv("deepfake_config") 
    if not isinstance(deepfake_config, str):
        raise TypeError(f"Expected a string, but received type {type(deepfake_config).__name__}")
    
    if "True" in deepfake_config:
        return True
    elif "False" in deepfake_config:
        return False
    else:
        raise ValueError("Environment variable 'deepfake_config' must be a boolean value")

class PTKConfig:
    
    #upload configs
    permanent_upload_directory = "storage/videos"
    temporary_upload_directory = "/tmp/yt-dlp"
    temporary_transcoding_directory = "/tmp/ffmpeg"
    download_resolution = "480" #480p
    cookies_path = 'cookies.txt'
    deepfake_config = get_deepfake_config()

    #model configs
    model_checkpoint = "Qwen2.5-VL-7B-Instruct" #download into cache
    quantization = "4bit" # Use "16bit" if AWQ/GPTQ, use "4bit" or "8bit" if using BitsAndBytes
    max_video_size = 150 # max size of video in MB

    #prompts
    system_prompt = """
            Role: You are an advanced AI Security Analyst. Your objective is to analyze security footage and generate comprehensive and factual security assessments. Your analysis must be grounded in observable reality, providing a clear understanding of events to aid human review and decision-making. Be precise and objective in all reported details.

            General Principles and Guidelines:
            - Process all provided video footage chronologically.
            - For each analytical step, consistently employ "think step-by-step" reasoning to connect observations and build a coherent understanding of the sequence of events and their implications.
            - Prioritize information most relevant to safety and security.
            - If details are obscured, ambiguous, or partially visible due to video quality, angle, or obstruction, explicitly state this (e.g., "individual's face partially obscured," "object's nature unclear due to distance," "action's intent ambiguous but noted due to X, Y, Z observable factors"). Do not speculate beyond what can be reasonably inferred from visual evidence.
            - Output Structure Adherence: Do not respond in markdown formatting. Strictly follow the headings, sub-headings, and formatting as defined in the "Standard Output Format" section. Ensure each major section and its sub-parts are clearly delineated. 
            - Avoid Speculation: Do not speculate about individuals' intentions, emotional states, motivations, internal thoughts, or the overall "atmosphere" or "mood," unless directly supported by unambiguous actions.
            - Clarity on Inference: If an inference is made (e.g., "Person 1 appears to be an employee due to uniform"), clearly state the visual basis.
            """
    user_prompt = """
            Analyze the provided security video footage and deliver a comprehensive assessment following these structured steps:

            1. THREAT ASSESSMENT: Review the footage for any immediate and unambiguous safety or security threats (e.g., visible aggression, accidents, clear acts of harm, presence of weapons).

            2. DETAILED INVENTORY: Document all visible elements with precision:
            - People: Record each individual, their physical characteristics, clothing details, and movements
            - Objects: Describe significant objects, their locations, and any interaction with people
            - Actions: Chronologically list all notable activities occurring in the footage
            - Environment: Highlight buildings, room features, landmarks, or any noticable environmental features. If possible, highlight potential signs that may provide context for a location.

            3. TEXT EXTRACTION: Identify and record all visible text including:
            - Timestamps and chronological indicators
            - Signage (street signs, business names, warning notices)
            - Location identifiers (addresses, landmarks, GPS coordinates)
            - Any other textual information present in the footage

            4. FACTUAL REPORTING: Maintain strict objectivity by reporting only observable facts. Do not speculate about intentions, atmosphere, mood, or make subjective assessments about the context.

            You must only respond in the following format:
            Summary:
            Environment:
            Description of People: 
            Objects Involved:
            Chronology of Events:
            Extracted Text:
            """


class ResponseModel(BaseModel):
    media_uuid: str | None
    report_time: str | None
    deepfake: bool | None
    summary: str | None
    status: str | None
    
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

