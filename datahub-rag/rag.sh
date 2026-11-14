#!/bin/sh
# DataHub RAG launcher — the ONLY supported way to call rag.py: it forces
# the project .venv (system python fails on the sentence_transformers
# import) and offline HuggingFace mode (the model is already cached
# locally; the egress proxy must not be consulted for model files).
# Usage: rag.sh query "query text"   |   rag.sh status   |   rag.sh <args...>
cd "$(dirname "$0")" || exit 1
export HF_HUB_OFFLINE=1
exec ./.venv/bin/python rag.py "$@"
