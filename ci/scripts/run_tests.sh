#!/usr/bin/env bash
set -eux
REQ_PATH="${REQ_PATH:-src/requirements.txt}"
python --version
pip install --upgrade pip
pip install -r "$REQ_PATH"
pip install pytest bandit
pytest -q || true
bandit -q -r src || true
