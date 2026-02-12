#!/usr/bin/env bash
# Script to download required local models for CANChat Docker build

set -e

echo "=========================================="
echo "CANChat Model Download Script"
echo "=========================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but not installed."
    exit 1
fi

# Create directories if they don't exist
mkdir -p all-MiniLM-L6-v2
mkdir -p whisper

echo "Installing required Python packages..."
pip3 install --quiet sentence-transformers faster-whisper torch

echo ""
echo "=========================================="
echo "Downloading Embedding Model (all-MiniLM-L6-v2)"
echo "This may take a few minutes..."
echo "=========================================="

python3 << 'PYEOF'
from sentence_transformers import SentenceTransformer
import os

print("Downloading sentence-transformers model...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# Save to local directory
save_path = './all-MiniLM-L6-v2'
model.save(save_path)

print(f"✓ Embedding model saved to {save_path}")

# Verify files exist
required_files = ['config.json', 'tokenizer_config.json']
for file in required_files:
    file_path = os.path.join(save_path, file)
    if os.path.exists(file_path):
        print(f"  ✓ {file} found")
    else:
        print(f"  ✗ Warning: {file} not found")
PYEOF

echo ""
echo "=========================================="
echo "Downloading Whisper Model (base)"
echo "This may take a few minutes..."
echo "=========================================="

python3 << 'PYEOF'
from faster_whisper import WhisperModel
import os

print("Downloading Whisper base model...")
model = WhisperModel("base", device="cpu", compute_type="int8", download_root="./whisper")

print("✓ Whisper model downloaded to ./whisper/base/")

# Verify the model directory exists
model_dir = "./whisper/base"
if os.path.exists(model_dir):
    files = os.listdir(model_dir)
    print(f"  ✓ Model directory contains {len(files)} file(s)")
    for file in files[:5]:  # Show first 5 files
        print(f"    - {file}")
    if len(files) > 5:
        print(f"    ... and {len(files) - 5} more")
else:
    print(f"  ✗ Warning: Model directory not found at {model_dir}")
PYEOF

echo ""
echo "=========================================="
echo "Download Complete!"
echo "=========================================="
echo ""
echo "Model directories:"
echo "  ✓ ./all-MiniLM-L6-v2/ - Embedding model"
echo "  ✓ ./whisper/base/ - Whisper speech-to-text model"
echo ""
echo "You can now build the Docker image:"
echo "  docker-compose build"
echo "  # or"
echo "  docker build -t canchat:latest ."
echo ""
