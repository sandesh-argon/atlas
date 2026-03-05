# Public reproducibility container (no private infra assumptions)
FROM python:3.11-slim

WORKDIR /app

COPY environments/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY runtime /app/runtime
COPY pipeline /app/pipeline
COPY data /app/data
COPY docs /app/docs

EXPOSE 8000
CMD ["python", "/app/runtime/api/main.py"]
