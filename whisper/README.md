# Whisper Model Directory

This directory should contain the Whisper speech-to-text model files.

## How to Obtain the Model

You have two options to populate this directory:

### Option 1: Download Using faster-whisper

```bash
pip install faster-whisper
python3 << PYEOF
from faster_whisper import WhisperModel

# Download the base model (default)
model = WhisperModel("base", device="cpu", compute_type="int8", download_root="./whisper")
print("Model downloaded to ./whisper/base/")
PYEOF
```

### Option 2: Download Using whisper Python package

```bash
pip install openai-whisper
python3 << PYEOF
import whisper
import os

# Download base model
model = whisper.load_model("base", download_root="./whisper")
print("Model downloaded successfully")
PYEOF
```

## Supported Model Sizes

Whisper comes in different sizes. The default is `base`, but you can use:
- `tiny` - Fastest, least accurate (~75MB)
- `base` - Good balance (default) (~150MB)
- `small` - Better accuracy (~500MB)
- `medium` - High accuracy (~1.5GB)
- `large` - Best accuracy (~3GB)

To use a different size, download it to the appropriate subdirectory (e.g., `whisper/small/`) and update the `WHISPER_MODEL` environment variable in your Docker configuration.

## Required Structure

After downloading, you should have:
```
whisper/
└── base/          (or tiny, small, medium, large)
    ├── model.bin
    ├── config.json
    └── ... (other model files)
```

## Configuration

The model size is configured via the `WHISPER_MODEL` environment variable in the Dockerfile (default: `base`).

## Why Local Models?

CANChat uses local Whisper models to:
- Enable offline speech-to-text functionality
- Ensure consistent model versions
- Improve build reproducibility
- Faster container startup (no download on first run)
- Support enterprise/air-gapped deployments
