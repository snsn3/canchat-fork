# CANChat Docker Setup Guide

This guide explains how to properly set up and build CANChat with local models.

## Overview

CANChat uses **local models** for offline operation and consistent deployments. Before building the Docker image, you must download the required models.

## Quick Start

### 1. Download Models

Run the provided script to automatically download all required models:

```bash
./download-models.sh
```

This will download:
- **Embedding Model**: sentence-transformers/all-MiniLM-L6-v2 (~90MB)
- **Whisper Model**: base (~150MB)

### 2. Build Docker Image

After models are downloaded:

```bash
# Using docker-compose
docker-compose build

# Or using docker directly
docker build -t canchat:latest .
```

### 3. Run CANChat

```bash
# Using docker-compose
docker-compose up -d

# Or using docker directly
docker run -d \
  -p 3000:8080 \
  -v open-webui:/app/backend/data \
  --name canchat \
  --restart always \
  canchat:latest
```

## Manual Model Download

If you prefer to download models manually or the script doesn't work:

### Embedding Model (all-MiniLM-L6-v2)

```bash
pip install sentence-transformers
python3 << EOF
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
model.save('./all-MiniLM-L6-v2')
EOF
```

### Whisper Model (base)

```bash
pip install faster-whisper
python3 << EOF
from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8", download_root="./whisper")
EOF
```

## Directory Structure

After downloading models, your directory should look like:

```
canchat-fork/
├── all-MiniLM-L6-v2/          # Embedding model
│   ├── config.json
│   ├── pytorch_model.bin
│   ├── tokenizer_config.json
│   └── ... (other model files)
├── whisper/                   # Whisper models
│   └── base/                  # Default base model
│       ├── model.bin
│       ├── config.json
│       └── ... (other model files)
├── Dockerfile
├── docker-compose.yaml
└── download-models.sh
```

## Why Local Models?

CANChat uses local models to provide:

1. **Offline Operation**: No internet required after build
2. **Consistent Versions**: Same model across all deployments
3. **Faster Startup**: No download on first run
4. **Air-Gapped Support**: Works in secure/isolated environments
5. **Reproducible Builds**: Exact same models every time

## Model Sizes and Requirements

| Model | Type | Size | Purpose |
|-------|------|------|---------|
| all-MiniLM-L6-v2 | Embedding | ~90MB | RAG (Retrieval Augmented Generation) |
| Whisper base | Speech-to-Text | ~150MB | Voice transcription |

**Total**: ~240MB of model files

## Changing Models

### Use a Different Embedding Model

Edit the Dockerfile and update the source directory name:

```dockerfile
# Change this line
COPY ./all-MiniLM-L6-v2 /app/backend/data/cache/embedding/models/all-MiniLM-L6-v2

# To your model directory, e.g.:
COPY ./my-custom-model /app/backend/data/cache/embedding/models/my-custom-model

# Also update the ENV variable:
ENV RAG_EMBEDDING_MODEL=/app/backend/data/cache/embedding/models/my-custom-model
```

### Use a Different Whisper Model Size

Download a different size to the whisper directory:

```bash
# For small model (better accuracy)
python3 << EOF
from faster_whisper import WhisperModel
model = WhisperModel("small", device="cpu", compute_type="int8", download_root="./whisper")
EOF
```

Then update the Dockerfile ENV:

```dockerfile
ENV WHISPER_MODEL=small
```

## Troubleshooting

### "Error: COPY failed: file not found"

This means the model directories don't exist or are empty. Run `./download-models.sh` first.

### "No space left on device"

The models require about 240MB of disk space. Free up space and try again.

### Models download slowly

The download speed depends on your internet connection. The script shows progress.

### Python errors during model download

Ensure you have Python 3.8+ installed:
```bash
python3 --version
```

Install pip if needed:
```bash
sudo apt-get install python3-pip  # Debian/Ubuntu
# or
brew install python3             # macOS
```

## Language Support

CANChat includes full bilingual support:

- **French (fr-CA)**: Complete UI translation
- **English (en-GB)**: Default language

Both languages have 1432+ translation keys covering all UI elements.

## Additional Resources

- [Open WebUI Documentation](https://docs.openwebui.com/)
- [Sentence Transformers Models](https://huggingface.co/sentence-transformers)
- [Whisper Models](https://github.com/openai/whisper)

## Getting Help

If you encounter issues:

1. Check that models are downloaded: `ls -la all-MiniLM-L6-v2/ whisper/base/`
2. Verify Docker is running: `docker --version`
3. Check Docker logs: `docker-compose logs`
4. Open an issue on GitHub with error details
