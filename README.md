# PTK Backend

## Overview

PTK Backend is a FastAPI-based application designed for processing and analyzing video and image files. It allows users to upload media directly or provide a URL for download. The backend then processes these files, stores metadata in a database (SQLite by default, configurable via environment variable), and can perform AI-driven analysis (e.g., summarization, optional deepfake detection) on the media. The service is designed to be run as a Docker container and initializes key components like directory structures, database connections, and AI models during its startup sequence using FastAPI's lifespan events.

## Features

* **Media Upload:** Upload video or image files directly to the server.
* **URL Download:** Download media from supported URLs (e.g., YouTube, Vimeo, Facebook).
* **File Processing:**
    * Sanitizes filenames.
    * Validates file types and MIME types.
    * Transcodes videos to H.265 (libx265) if necessary for model compatibility or size reduction, based on configurable parameters.
* **Database Integration:** Uses SQLAlchemy to interact with a database (default SQLite, configurable via `DATABASE_URL` environment variable) to store records of processed media, including metadata, status, and analysis results.
* **AI-Powered Analysis:**
    * Generates summaries of video content using a Qwen2.5-VL model (configurable model checkpoint and quantization).
    * Optional deepfake detection capabilities via Sensity.ai API (configurable via `DEEPFAKE_CONFIG` and requires `SENSITY_API_KEY`).
* **Dockerized:** Designed to run as a Docker container with GPU support for model inference.
* **API Endpoints:** Provides a RESTful API for all functionalities.
* **Configuration via Environment Variables:** Most operational parameters can be set using environment variables, with sensible defaults.
* **Lifespan Management:** Application setup (directory creation, DB initialization, model loading) and teardown are managed by FastAPI's lifespan events.

## Setup and Installation

### Prerequisites

* Docker installed.
* NVIDIA GPU drivers installed (if using GPU acceleration for model inference).
* Access to a Docker Hub repository if using pre-built images (as suggested in the original `README.md`).

### Running with Docker (Local Build)

1.  **Build the Docker Image:**
    Navigate to the `ptk-backend` directory and run:
    ```bash
    docker build -t ptk-backend:0.1 .
    ```

2.  **Set Environment Variables (Recommended):**
    Create a `.env` file in the `ptk-backend` directory or set environment variables in your shell before running. See the "Configuration" section for a list of variables. Example `.env` file:
    ```env
    DATABASE_URL=sqlite:///storage/case_videos.db
    DEEPFAKE_CONFIG=False
    # SENSITY_API_KEY=your_sensity_api_key_if_deepfake_is_true
    MODEL_CHECKPOINT=Qwen2.5-VL-7B-Instruct
    QUANTIZATION=4bit
    UVICORN_PORT=8000
    UVICORN_HOST=0.0.0.0
    ```

3.  **Run the Docker Container:**
    The `run.sh` script provides an example command:
    ```bash
    #!/bin/bash
    docker run -d --gpus=all --rm -p 8000:8000 --env-file .env --name ptk-backend ptk-backend:0.1
    ```
    This command runs the container in detached mode (`-d`), enables all available GPUs (`--gpus=all`), removes the container when it exits (`--rm`), maps port 8000 of the host to port 8000 of the container (as defined by `UVICORN_PORT` or its default in `main.py`), loads environment variables from `.env` (`--env-file .env`), and names the container `ptk-backend`.
    *Note: The port in `run.sh` (`-p 8000:8000`) should match the `UVICORN_PORT` you intend to use.*

### Running with Runpod (as per original README)

The original `README.md` provides instructions for deploying to Runpod:

1.  Login into RunPod's user console, and navigate to the templates (https://www.runpod.io/console/user/templates).
2.  Create a new template using your Docker image. You will need to configure environment variables within the Runpod template settings.
    * When adding credentials (if for a private Docker Hub repo), enter the Docker API key into the password section, and leave the username empty.
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

The application is configured primarily through environment variables. The `config.py` file defines these variables and their default fallback values.

### Environment Variables

* **`DATABASE_URL`**:
    * Description: The connection string for the database.
    * Default: `sqlite:///storage/case_videos.db`
    * Example for PostgreSQL: `postgresql://user:password@host:port/database`
* **`DEEPFAKE_CONFIG`**:
    * Description: Enables or disables deepfake detection.
    * Values: `"True"` or `"False"` (case-insensitive string).
    * Default: `"False"`
* **`SENSITY_API_KEY`**:
    * Description: API key for Sensity.ai, required if `DEEPFAKE_CONFIG` is `"True"`.
    * Default: Not set. Deepfake detection will be skipped or fail if this is not set when `DEEPFAKE_CONFIG` is true.
* **`SYSTEM_PROMPT`**:
    * Description: The system prompt used for the AI model during inference.
    * Default: A detailed security analysis prompt defined in `config.py`.
* **`USER_PROMPT`**:
    * Description: The user prompt used for the AI model during inference.
    * Default: `"Analyse this security video footage objectively."`
* **`PERMANENT_UPLOAD_DIRECTORY`**:
    * Description: Path to the directory for storing processed media files permanently.
    * Default: `storage/videos`
* **`TEMPORARY_UPLOAD_DIRECTORY`**:
    * Description: Path to the directory for temporary storage during URL downloads.
    * Default: `/tmp/yt-dlp`
* **`TEMPORARY_TRANSCODING_DIRECTORY`**:
    * Description: Path to the directory for temporary storage during video transcoding.
    * Default: `/tmp/ffmpeg`
* **`DOWNLOAD_RESOLUTION`**:
    * Description: Preferred download resolution for `yt-dlp` (e.g., "480", "720").
    * Default: `"480"`
* **`COOKIES_PATH`**:
    * Description: Path to a cookies file for `yt-dlp` (for sites requiring login).
    * Default: `cookies.txt`
* **`MODEL_CHECKPOINT`**:
    * Description: Hugging Face model checkpoint name or path for the Qwen2.5-VL model.
    * Default: `"Qwen2.5-VL-7B-Instruct"`
* **`QUANTIZATION`**:
    * Description: Model quantization setting.
    * Values: `"4bit"`, `"8bit"`, or `"16bit"` (for full precision).
    * Default: `"4bit"`
* **`MIN_PIXELS`**:
    * Description: Minimum number of pixels for image/video processing by the model.
    * Default: `200704` (equivalent to 256 \* 28 \* 28)
* **`MAX_PIXELS`**:
    * Description: Maximum number of pixels for image/video processing by the model.
    * Default: `802816` (equivalent to 1024 \* 28 \* 28)
* **`MAX_VIDEO_SIZE_MB`**:
    * Description: Maximum size of a video in MB before an attempt to transcode it for size reduction (also transcoded if codec is not H.264/H.265).
    * Default: `150`
* **`UVICORN_HOST`**:
    * Description: Host address for the Uvicorn server.
    * Default: `"127.0.0.1"` (when running `main.py` directly), typically `"0.0.0.0"` in Docker for external accessibility.
* **`UVICORN_PORT`**:
    * Description: Port for the Uvicorn server.
    * Default: `8000`
* **`UVICORN_LOG_LEVEL`**:
    * Description: Log level for Uvicorn.
    * Default: `info`
* **`UVICORN_RELOAD`**:
    * Description: Enable Uvicorn auto-reload (for development).
    * Values: `"True"` or `"False"`.
    * Default: `False`

## API Endpoints

The API is served at the host and port configured by `UVICORN_HOST` and `UVICORN_PORT` (defaults to `127.0.0.1:8000` if `main.py` is run directly, or `0.0.0.0:8000` in the typical Docker setup).

* **`GET /`**
    * Description: Root endpoint to check if the API is live.
    * Response: `{"message": "API is live."}`

* **`POST /uploadurl?url={url}`**
    * Description: Downloads a media file from the given URL, processes it, and creates a database record.
    * Query Parameter:
        * `url` (str, required): The URL of the media file.
    * Response: `ResponseModel` (JSON object with `media_uuid`, `report_time`, `deepfake` status, `summary`, `status`).

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
    * Description: Triggers AI model inference (summarization) for the specified media file. If deepfake detection is enabled and not yet performed, it will also be attempted. Updates the database record with the summary, deepfake status, and "Completed" status.
    * Path Parameter:
        * `media_uuid` (str, required): The UUID of the media to analyze.
    * Response: `ResponseModel` with the summary and updated status.

* **`GET /query/{media_uuid}`**
    * Description: Retrieves the database record for the specified media file.
    * Path Parameter:
        * `media_uuid` (str, required): The UUID of the media to query.
    * Response: `ResponseModel` containing the media details.

## Project Structure

ptk-backend/
├── .env.example        # Example environment file (Recommended to create .env)
├── config.py           # Application configuration, Pydantic models
├── main.py             # FastAPI application, API endpoints, lifespan events
├── requirements.txt    # Python dependencies
├── run.sh              # Script to run the Docker container
├── Dockerfile          # (Assumed) Dockerfile to build the image
├── storage/            # Default directory for persistent data if using SQLite
│   └── videos/         # Default permanent storage for media (see PERMANENT_UPLOAD_DIRECTORY)
│   └── case_videos.db  # Default SQLite database file (see DATABASE_URL)
├── tmp/                # Default directory for temporary files
│   ├── yt-dlp/         # Default temp storage for downloads (see TEMPORARY_UPLOAD_DIRECTORY)
│   └── ffmpeg/         # Default temp storage for transcoding (see TEMPORARY_TRANSCODING_DIRECTORY)
├── utils/              # Utility modules
│   ├── init.py

│   ├── database_utils.py # Database models and operations
│   ├── download_utils.py # URL downloading logic
│   ├── file_utils.py     # File operations, sanitization, transcoding
│   └── model_utils.py    # Model loading and inference logic
└── README.md           # This file


## Notes

* The system uses `yt-dlp` for downloading videos from URLs, which requires `ffmpeg` to be available in the environment for processing and merging formats. This is typically handled within the Docker image.
* The AI model (e.g., Qwen2.5-VL) and its processor are downloaded from Hugging Face hub to a cache location upon first run if not already present.
* Ensure that the directories specified by environment variables (e.g., `PERMANENT_UPLOAD_DIRECTORY`) are writable by the application. The application attempts to create these directories during startup if they don't exist.
* For deepfake detection using Sensity.ai, a valid `SENSITY_API_KEY` environment variable must be set, and `DEEPFAKE_CONFIG` must be `"True"`.
