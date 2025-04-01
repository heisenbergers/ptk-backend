#!/bin/bash

docker run -d --gpus=all --rm -p 8000:8000 --name ptk-backend ptk-backend:0.1