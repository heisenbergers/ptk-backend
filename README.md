# PTK Backend

## Overview

PTK Backend is a FastAPI-based application designed for processing and analyzing video and image files. It allows users to upload media directly or provide a URL for download. The backend then processes these files, stores metadata in a SQLite database, and can perform AI-driven analysis (e.g., summarization, deepfake detection) on the media. The service is designed to be run as a Docker container.

## Features

* **Media Upload:** Upload video or image files directly to the server.
* **URL Download:** Download media from supported URLs (e.g., YouTube, Vimeo, Facebook).
* **File Processing:**
    * Sanitizes filenames.
    * Validates file types and MIME types.
    * Transcodes videos to H.265 (libx265) if necessary for model compatibility or size reduction.
* **Database Integration:** Uses SQLite to store records of processed media, including metadata, status, and analysis results.
* **AI-Powered Analysis:**
    * Generates summaries of video content using a Qwen2.5-VL model.
    * (Optional) Deepfake detection capabilities via Sensity.ai API (configurable).
* **Dockerized:** Designed to run as a Docker container with GPU support for model inference.
* **API Endpoints:** Provides a RESTful API for all functionalities.

## Setup and Installation

### Prerequisites

* Docker installed.
* NVIDIA GPU drivers installed (if using GPU acceleration for model inference).
* Access to a Docker Hub repository if using pre-built images (as suggested in the original `README.md`).

### Running with Docker (Local Build)

1.  **Build the Docker Image:**
    Navigate to the `ptk-backend` directory and run:
    ```bash
    docker build -t ptk-backend:<tag> .
    ```

2.  **Run the Docker Container:**
    The `run.sh` script provides an example command:
    ```bash
    #!/bin/bash
    docker run -d --gpus=all --rm -p 8000:8000 -e deepfake_config="False" --name ptk-backend ptk-backend:<tag>
    ```
    This command runs the container in detached mode (`-d`), enables all available GPUs (`--gpus=all`), removes the container when it exits (`--rm`), maps port 8000 of the host to port 8000 of the container (`-p 8000:8000`), and names the container `ptk-backend`.

### Running with Runpod (as per original README)

The original `README.md` provides instructions for deploying to Runpod:

1.  Login into RunPod's user console, and navigate to the templates (https://www.runpod.io/console/user/templates).
2.  Create a new template using the following parameters (remember to add credentials):
    * The image provided in the original README suggests using a pre-pushed Docker image from a private Docker Hub repository.
    * When adding credentials, enter the Docker API key into the password section, and leave the username empty.
    * Note that saved videos will not be persistent unless allocated to a persistent volume.
3.  Deploy the template as a pod from the deployment page (https://www.runpod.io/console/deploy).

### Dependencies

Python dependencies are listed in `requirements.txt`. These are installed within the Docker image during the build process.

Key dependencies include:
* FastAPI
* Uvicorn
* SQLAlchemy
* Transformers
* Torch
* yt-dlp
* ffmpeg-python

## Configuration

The application can be configured using environment variables.

### Environment Variables

* `deepfake_config`:
    * Description: Enables or disables deepfake detection.
    * Values: `"True"` or `"False"` (as a string).
    * Default: If not set, the application might raise an error or use a hardcoded default if `get_deepfake_config()` is modified. Currently, it expects the variable to be present.
* `system_prompt`:
    * Description: The system prompt used for the AI model during inference.
    * Values: A string containing the system prompt.
    * Default: A long, detailed fallback system prompt is defined in `config.py`.
* `user_prompt`:
    * Description: The user prompt used for the AI model during inference, instructing it on how to analyze the media.
    * Values: A string containing the user prompt.
    * Default: `"Analyse this security video footage objectively."`

### Other Configurations (Hardcoded in `config.py`)

The following configurations are currently hardcoded in `config.py` but could be externalized to environment variables if needed:

* `PTKConfig.permanent_upload_directory`: "storage/videos"
* `PTKConfig.temporary_upload_directory`: "/tmp/yt-dlp"
* `PTKConfig.temporary_transcoding_directory`: "/tmp/ffmpeg"
* `PTKConfig.download_resolution`: "480" (for yt-dlp)
* `PTKConfig.cookies_path`: 'cookies.txt' (for yt-dlp)
* `PTKConfig.model_checkpoint`: "Qwen2.5-VL-7B-Instruct" (Hugging Face model)
* `PTKConfig.quantization`: "4bit" (Model quantization: "4bit", "8bit", or "16bit")
* `PTKConfig.min_pixels`: 256\*28\*28 (Min pixels for model processor)
* `PTKConfig.max_pixels`: 1024\*28\*28 (Max pixels for model processor)
* `PTKConfig.max_video_size`: 150 (Max size of video in MB before transcoding attempt)

The SQLite database URL is also hardcoded in `utils/database_utils.py`:
* `DatabaseOperations.DATABASE_URL`: 'sqlite:///storage/case_videos.db'

## API Endpoints

The API is served at port 8000 (as per `run.sh`).

* **`GET /`**
    * Description: Root endpoint to check if the API is live.
    * Response: `{"message": "API is live."}`

* **`POST /uploadurl?url={url}`**
    * Description: Downloads a media file from the given URL, processes it, and creates a database record.
    * Query Parameter:
        * `url` (str, required): The URL of the media file.
    * Response: `ResponseModel` (JSON object with `media_uuid`, `report_time`, `deepfake`, `summary`, `status`).

* **`POST /upload/`**
    * Description: Uploads a media file, processes it, and creates a database record.
    * Request Body: `UploadFile` (multipart/form-data with the file).
    * Response: `ResponseModel`.

* **`DELETE /delete/{media_uuid}`**
    * Description: Deletes the specified media file from storage and its record from the database.
    * Path Parameter:
        * `media_uuid` (str, required): The UUID of the media to delete.
    * Response: `{"detail": "File with UUID {media_uuid} has been deleted"}`

* **`POST /predict/{media_uuid}`**
    * Description: Triggers AI model inference (summarization) for the specified media file. Updates the database record with the summary and "Completed" status.
    * Path Parameter:
        * `media_uuid` (str, required): The UUID of the media to analyze.
    * Response: `ResponseModel` with the summary and updated status.

* **`GET /query/{media_uuid}`**
    * Description: Retrieves the database record for the specified media file.
    * Path Parameter:
        * `media_uuid` (str, required): The UUID of the media to query.
    * Response: `ResponseModel` containing the media details.

## Project Structure