#!/bin/zsh
cd "$(dirname "$0")"
exec .build/venv/bin/python run.py
