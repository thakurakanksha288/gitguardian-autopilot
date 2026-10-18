FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY receiver.py .
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:8081/health || exit 1
CMD ["python", "-m", "uvicorn", "receiver:app", "--host", "0.0.0.0", "--port", "8081"]
