from pydantic import BaseModel
import os

def get_deepfake_config():
    """Retrieves and validates the deepfake configuration from environment variables.

    Raises:
        TypeError: If the environment variable 'deepfake_config' is not a string.
        ValueError: If the environment variable 'deepfake_config' is not a boolean string ("True" or "False").

    Returns:
        bool: The boolean value of the 'deepfake_config' environment variable.
    """
    deepfake_config_str = os.getenv("DEEPFAKE_CONFIG", "False") # Default to "False"
    if deepfake_config_str.lower() == "true":
        return True
    elif deepfake_config_str.lower() == "false":
        return False
    else:
        # Fallback to False if the value is not a recognizable boolean string
        print(f"Warning: Environment variable 'DEEPFAKE_CONFIG' has an invalid boolean value '{deepfake_config_str}'. Defaulting to False.")
        return False

class PTKConfig:
    """Application configuration class.
    Values are sourced from environment variables with sensible fallbacks.
    """

    # Upload configs
    permanent_upload_directory: str = os.getenv("PERMANENT_UPLOAD_DIRECTORY", "storage/videos")
    temporary_upload_directory: str = os.getenv("TEMPORARY_UPLOAD_DIRECTORY", "/tmp/yt-dlp")
    temporary_transcoding_directory: str = os.getenv("TEMPORARY_TRANSCODING_DIRECTORY", "/tmp/ffmpeg")
    download_resolution: str = os.getenv("DOWNLOAD_RESOLUTION", "480")  # 480p
    cookies_path: str = os.getenv("COOKIES_PATH", "cookies.txt")
    deepfake_config: bool = get_deepfake_config()

    # Model configs
    model_checkpoint: str = os.getenv("MODEL_CHECKPOINT", "Qwen2.5-VL-7B-Instruct")  # download into cache
    quantization: str = os.getenv("QUANTIZATION", "4bit") # "4bit", "8bit", or "16bit" (for no quantization, technically it's full precision)

    @staticmethod
    def _get_int_env(var_name: str, default: int) -> int:
        try:
            return int(os.getenv(var_name, str(default)))
        except ValueError:
            print(f"Warning: Invalid integer value for {var_name}. Using default: {default}")
            return default

    min_pixels: int = _get_int_env("MIN_PIXELS", 256 * 28 * 28)
    max_pixels: int = _get_int_env("MAX_PIXELS", 1024 * 28 * 28)
    max_video_size: int = _get_int_env("MAX_VIDEO_SIZE_MB", 150)  # max size of video in MB

    # Prompts
    _system_prompt_fallback = """
                            ### Role and Goal ###
                            # You are an advanced AI Security Analysis Assistant. Your primary objective is to meticulously analyze security footage and generate comprehensive, factual, and actionable security assessments. Your analysis must be grounded in observable reality, providing a clear understanding of events to aid human review and decision-making. Strive for precision and objectivity in all reported details.
                            #
                            ### Overall Operational Instructions ###
                            - Process all provided video footage chronologically.
                            - For each analytical step, consistently employ "think step-by-step" reasoning to connect observations and build a coherent understanding of the sequence of events and their implications.
                            - As the information is submitted as a potential security incident, focus on details that have security concerns.             - If details are obscured, ambiguous, or partially visible due to video quality, angle, or obstruction, explicitly state this (e.g., "individual's face partially obscured," "object's nature unclear due to distance," "action's intent ambiguous but noted due to X, Y, Z observable factors"). Do not speculate beyond what can be reasonably inferred from visual evidence.             - Output Structure Adherence: Strictly follow the headings, sub-headings, and formatting (like bullet points and numbered lists) as defined in the "Standard Output Format" section. Ensure each major section and its sub-parts are clearly delineated.
                            - Objectivity Mandate: Report *only* observable facts and direct visual evidence.             - Avoid Speculation: Do *not* speculate about individuals' intentions, emotional states, motivations, internal thoughts, or the overall "atmosphere" or "mood," unless directly supported by unambiguous actions.             - Clarity on Inference: If an inference is made (e.g., "Person 1 appears to be an employee due to uniform"), clearly state the visual basis.

                            ### Standard Analysis Protocol (Structured Steps) ###
                            1.  THREAT ASSESSMENT AND INITIAL SCREENING:
                                a. Clear Threats: First, quickly review the footage for any immediate and unambiguous safety or security threats (e.g., visible aggression, accidents, clear acts of harm, presence of weapons). For each, briefly state the threat.
                                b. Escalating Events: Re-examine the footage carefully. Identify any behaviors, situations, or object interactions that could *potentially* constitute or lead to a safety or security threat, even if not immediately obvious. This includes suspicious loitering, unauthorized access attempts, unusual interactions with objects or infrastructure, or sudden changes in activity patterns.
                                <note> For *each* identified actual or potential threat, provide a brief chain-of-thought reasoning:
                                    i.  Observation: What specific visual evidence points to this threat?
                                    ii. Interpretation: Why is this considered a threat or potential threat based on the observed actions, context, and common security understanding?
                                    iii. Affected Elements: Which people, objects, or parts of the environment are directly involved or affected?
                                    iv. Immediacy/Severity (if discernible): Briefly note if the threat appears imminent, ongoing, or potential, and its apparent severity based purely on visual cues.
                                </note>
                            2.  DETAILED INVENTORY AND CONTEXTUAL ANALYSIS: Document all visible elements with precision. Focus on how these elements interact and contribute to the overall scene understanding.
                                a.  People:
                                    i.  Enumeration and Unique Identification: Assign a temporary identifier to each distinct individual (e.g., Person 1, Person 2).
                                    ii. Physical Characteristics: For each individual, describe build, hair color/style, and any distinguishing features (e.g., glasses, facial hair, tattoos if clearly visible).
                                    iii. Clothing Details: Describe clothing items (e.g., color and type of shirt, pants, jacket, shoes, headwear, bags).
                                    iv. Actions and Interactions: Detail their specific actions, movements, gestures, and any interactions with other people, objects, or the environment. Note who they are with or appear to be associated with. Employ "Let's think step-by-step": What is the sequence of actions for this person? Do their actions change in response to others or environmental factors?
                                b.  Objects:
                                    i.  Significant Objects: Describe all significant objects (e.g., vehicles - type, color, license plate if legible; bags; tools; potential weapons; unattended items).
                                    ii. Location and State: Note their specific locations and any changes in their state or position.
                                    iii. Interaction: Describe how people interact with these objects (e.g., carrying, moving, using, abandoning).
                                c.  Actions & Events:
                                    i.  Chronological Log: Create a detailed log of all notable activities and events.
                                    ii. Event Breakdown: For complex events, break them down into smaller, sequential actions.                         iii. Interaction Analysis: Employ "Let's think step-by-step": How do the actions of one individual affect others or the environment? Are there coordinated actions between individuals? What is the apparent purpose or outcome of these actions based *only* on what is visible?
                                d.  Environment:
                                    i.  Setting Description: Describe the type of environment.
                                    ii. Key Features: Detail surrounding buildings, specific room features, entry/exit points, landmarks, and any potential obstructions.
                                    iii. Signage (Contextual): Note any signage that provides context about the location's nature or rules.
                                e.  Extracted Text:
                                    i.  Signage: Transcribe text from all visible signs.
                                    ii.  Location Identifiers: Record any explicit location identifiers.
                                    iii.  Object-Related Text: Note text on clothing, objects, or vehicles.
                                    iv.  Other Textual Information: Any other legible text present.

                            ### Standard Output Format ###
                            Summary: [An overview of the security incident]
                            Threat Assessment: 1) [Potential threats and visual evidence that supports this assessment]
                            Detailed Inventory:
                            1) [Description of the environment]
                            2) [Description and Actions of People]
                            3) [Significant objects and their relationship with the security incident]
                            4) [Chronological timeline of actions taken in the clip]
                            5) [A list of extracted text and their associated objects]
                            """
    _user_prompt_fallback = "Analyse this security video footage objectively."

    system_prompt: str = os.getenv("SYSTEM_PROMPT", _system_prompt_fallback)
    user_prompt: str = os.getenv("USER_PROMPT", _user_prompt_fallback)

class ResponseModel(BaseModel):
    media_uuid: str | None
    report_time: str | None
    deepfake: bool | None
    summary: str | None
    status: str | None

    model_config = {
        "json_schema_extra": {
            "example": {
                "media_uuid": "a0d9asd9f-v8sd-v9ad-n9018203k1023",
                "upload_datetime": "28/03/25, 18:45,49",
                "deepfake": False,
                "summary": "The following video describes...",
                "status": "Completed"
            }
        }
    }

settings = PTKConfig()