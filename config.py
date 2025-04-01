from pydantic import BaseModel

class PTKConfig:
    #upload configs
    permanent_upload_directory = "storage/videos"
    temporary_upload_directory = "/tmp/yt-dlp"
    download_resolution = "480" #480p

    #model configs
    model_checkpoint = "Qwen2.5-VL-7B-Instruct" #download into cache
    quantization = "4bit" # Use "16bit" if AWQ/GPTQ, use "4bit" or "8bit" if using BitsAndBytes
    max_video_size = 50 # max size of video in MB

    #prompts
    system_prompt = "You are a professional analyst at a law enforcement agency, with advanced vision capabilities and visual reasoning skills"
    user_prompt = """
    Analyze the provided security video footage and deliver a comprehensive assessment following these structured steps:

    1. THREAT ASSESSMENT: Carefully examine the video to identify any potential safety or security threats present in the footage.

    2. DETAILED INVENTORY: Document all visible elements with precision:
    - People: Record each individual, their physical characteristics, clothing details, and movements
    - Objects: Catalog all significant items, their locations, and any interaction with people
    - Actions: Chronologically list all notable activities occurring in the footage

    3. TEXT EXTRACTION: Identify and record all visible text including:
    - Timestamps and chronological indicators
    - Signage (street signs, business names, warning notices)
    - Location identifiers (addresses, landmarks, GPS coordinates)
    - Any other textual information present in the footage

    4. FACTUAL REPORTING: Maintain strict objectivity by reporting only observable facts. Do not speculate about intentions, atmosphere, mood, or make subjective assessments about the context.

    Provide your analysis in the following JSON format:

    {
    "persons": [
    {
        "id": "person_1",
        "physical_description": "Gender, approximate age, height, build, distinguishing features",
        "clothing": "Detailed description of attire including colors, styles, and accessories",
        "actions": ["List of chronological actions taken by this person"]
        },
        {
        "id": "person_2",
        "physical_description": "Gender, approximate age, height, build, distinguishing features",
        "clothing": "Detailed description of attire including colors, styles, and accessories",
        "actions": ["List of chronological actions taken by this person"]
        }
    ],
    "objects": [
    {
        "id": "object_1",
        "physical_description": "Describe the shape, colour, and type of object"
        },
        {
        "id": "object_2",
        "physical_description": "Describe the shape, colour, and type of object",
        }
    ],
    "location": {
        "setting_type": "Indoor/outdoor classification",
        "structures": ["Buildings, infrastructure, architectural elements"],
        "environmental_features": ["Natural elements, weather conditions, lighting"],
        "identifiable_markers": ["Landmarks, street signs, business names"]
    },
    "incidents": [
        {
        "time_marker": "Timestamp or relative time indicator",
        "description": "Detailed account of potentially concerning event",
        "involved_elements": ["References to relevant people_ids and objects"]
        }
    ],
    "text_elements": [
        {
        "content": "Exact text as it appears",
        "location": "Where in the frame the text appears",
        "context": "What object/surface contains this text"
        }
    ],
    "summary": "Concise factual overview of the entire video footage focusing on security-relevant observations"
    }
    """


class ResponseModel(BaseModel):
    media_uuid: str
    report_time: str
    deepfake: bool | None
    summary: str | None
    status: str
    
    model_config= { "json_schema_extra":{
                                    "example": {
                                                "media_uuid": "a0d9asd9f-v8sd-v9ad-n9018203k1023",
                                                "upload_datetime": "28/03/25, 18:45,49",
                                                "deepfake": False,
                                                "summary": "The following video describes..."
                                                }
                                        }
                    }

