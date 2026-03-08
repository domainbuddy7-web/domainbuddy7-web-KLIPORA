# KLIPORA Mission Control API — deployable to Railway
FROM python:3.11-slim

WORKDIR /app

# Project root = /app (Infrastructure, Command_Center, Agents live here)
COPY . /app/

RUN pip install --no-cache-dir -r requirements.txt

# Railway sets PORT at runtime
ENV PORT=8000
EXPOSE 8000
ENV PYTHONPATH=/app

CMD sh -c 'uvicorn Command_Center.dashboard_api:app --host 0.0.0.0 --port ${PORT:-8000}'
