FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/
COPY config.example.yaml config.example.yaml

RUN mkdir -p logs /data

CMD ["python3", "src/main.py"]
