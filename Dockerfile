FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install uv && uv sync

COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini .

ENV PYTHONPATH=/app

EXPOSE 8000
