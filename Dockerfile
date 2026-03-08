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

# Use start script so port is read from env and logs are clear
CMD ["python", "start_api.py"]
