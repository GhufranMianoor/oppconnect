#!/usr/bin/env bash
# Render (or any similar platform) runs this during deploy.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
