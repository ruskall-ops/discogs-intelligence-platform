#!/bin/zsh
cd "$(dirname "$0")"
python3 -m pip install --user -e .
python3 app.py
