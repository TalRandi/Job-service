# Dockerfile for FastAPI app and worker
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Entrypoint will be set by docker-compose for each service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5001"]
