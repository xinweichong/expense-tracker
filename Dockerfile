FROM python:3.12-slim

WORKDIR /app

# Install Node.js for React build
RUN apt-get update && apt-get install -y curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/
COPY config.example.yaml config.example.yaml

# Build React SPA
WORKDIR /app/src/web/frontend
RUN npm ci && npm run build

WORKDIR /app

RUN mkdir -p logs /data

CMD ["python3", "src/main.py"]
