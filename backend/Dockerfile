FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/app /app/app
COPY prnu_core /app/prnu_core

ENV PYTHONPATH=/app

EXPOSE 8000
