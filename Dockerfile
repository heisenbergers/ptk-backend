FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 AS compile-image
RUN apt-get update && apt install python3 -y
RUN apt install python3-pip -y
COPY requirements.txt .
RUN pip --default-timeout=1000 install --user -r requirements.txt
RUN pip install flash-attn --user --no-build-isolation

FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 AS build-image
COPY --from=compile-image /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
RUN apt-get update && apt install ffmpeg -y
RUN apt install python3 -y && apt install python3-pip -y 
WORKDIR /code
COPY ./utils ./utils
COPY ./config.py ./config.py
COPY ./main.py ./main.py
COPY ./Qwen2.5-VL-7B-Instruct ./Qwen2.5-VL-7B-Instruct
COPY ./cookies.txt ./cookies.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

