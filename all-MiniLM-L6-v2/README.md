# Embedding Model Directory

This directory should contain the sentence-transformers all-MiniLM-L6-v2 model files.

## How to Obtain the Model

You have two options to populate this directory:

### Option 1: Download from Hugging Face

```bash
pip install sentence-transformers
python3 << PYEOF
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
model.save('./all-MiniLM-L6-v2')
PYEOF
```

### Option 2: Download Manually

1. Visit https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
2. Download all model files
3. Place them in this directory

## Required Files

The directory should contain:
- `config.json` - Model configuration
- `pytorch_model.bin` or `model.safetensors` - Model weights
- `tokenizer_config.json` - Tokenizer configuration
- `vocab.txt` - Vocabulary file
- `special_tokens_map.json` - Special tokens mapping
- Other supporting files from the model repository

## Verification

After populating this directory, you should have a structure like:
```
all-MiniLM-L6-v2/
├── config.json
├── pytorch_model.bin (or model.safetensors)
├── tokenizer_config.json
├── vocab.txt
├── special_tokens_map.json
└── ... (other model files)
```

## Why Local Models?

CANChat uses local models to:
- Enable offline operation
- Ensure consistent model versions across deployments
- Improve build reproducibility
- Faster container startup (no download on first run)
