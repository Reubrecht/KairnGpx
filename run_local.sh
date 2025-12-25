#!/bin/bash
source .venv/bin/activate
uvicorn app.main:app --reload --env-file local.env --host 0.0.0.0 --port 8000
