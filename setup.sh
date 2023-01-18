#!/bin/bash

python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt --no-cache-dir

backend/manage.py migrate
backend/manage.py sync setup
