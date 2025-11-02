FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# OS deps for lxml/trafilatura
RUN apt-get update && apt-get install -y \
    build-essential libxml2-dev libxslt1.1 libxslt1-dev libffi-dev curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# IMPORTANT: use the dynamic $PORT that Render provides
# Use a shell form so $PORT expands at runtime
CMD bash -lc 'uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}'
