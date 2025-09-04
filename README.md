<div dir="ltr">

# Job Service

A backend service that accepts jobs, runs them in parallel with a configurable concurrency limit, and allows clients to query their status and results.

---

## Features
- Submit jobs of type `analyze` or `sleep`.
- Query job status and result while running or after completion.
- Configurable concurrency limit for workers.
- Automatic retry for failed jobs.
- REST API built with FastAPI.
- Scalable deployment with Docker Swarm (2 replicas of listener).

---

### Clone the repository

```bash
git clone https://github.com/TalRandi/Job-service.git
cd Job-service
```

## Build the services:
```bash
docker compose build
```

## Requirements
- Docker  
- Docker Compose  
- Python 3.12+ (for local development)  
---

## Setup and Run
## Running in Docker Swarm (with 2 replicas)
## Initialize Docker Swarm (only once per machine):
```bash
docker swarm init
```

## Deploy the stack:
```bash
CONCURRENCY_LIMIT=5 docker stack deploy -c docker-compose.yml jobstack
```
(CONCURRENCY_LIMIT can be changed. Default value is 3)

## Check services:
```bash
docker service ls
```

## Check that the listener has 2 replicas running:
```bash
docker service ps jobstack_listener
```

### Run the service
```bash
 docker compose up
```

The listener will be available at http://localhost:5000
The worker will automatically start and process jobs from the database.

# API Endpoints

# --------------------------------------------------------- #
### 1. Submit a Sleep Job
```bash
curl -X POST http://localhost:5000/jobs \
  -H "Content-Type: application/json" \
  -d '{
        "type": "sleep",
        "payload": { "seconds": 5 }
      }'
```
#### Response (queued):
{ "job_id": "123e4567-e89b-12d3-a456-426614174000", "status": "queued" }


# --------------------------------------------------------- #
### 2. Submit an Analyze Job with a log file
```bash
curl -X POST http://localhost:5000/jobs \
  -F "type=analyze" \
  -F "payload={\"patterns\": [\"ERROR\",\"WARN\"]}" \
  -F "filename=@example.log"
```
#### Response:
{ "job_id": "abcd1234-5678-90ef-ghij-1234567890kl", "status": "queued" }

# --------------------------------------------------------- #
### 3. Get Job Status
```bash
curl -X GET http://localhost:5000/jobs/{job_id}
```
#### Response:
{
  "job_id": "{job_id}",
  "status": "running",
  "result": null
}

# --------------------------------------------------------- #
### 4. List Jobs
```bash
curl -X GET http://localhost:5000/jobs
```

#### List Jobs filtered by status, with limit of 50.
```bash
curl -X GET "http://localhost:5000/jobs?status=running&limit=50"
```
#### Response:
{
  "items": [
    { "job_id": "...", "status": "running", "result": null, "payload": {...} }
  ],
  "limit": 50
}


# --------------------------------------------------------- #
### 6. Cancel a Job
```bash
curl -X POST http://localhost:5000/jobs/{job_id}/cancel
```
#### Response:

{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "job canceled successfully"
}




## Running Tests

Automated tests are provided in the `tests/` folder using **pytest** and **FastAPI TestClient**.  

### Prerequisites
Make sure you have a Python virtual environment set up:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

From the root of the project, run:

```bash
pytest -v tests/
```





## Remarks

- Emphasis was placed on **code readability** and consistent coding style.
- The project structure is clearly separated into files (`main.py` for the API, `jobs.py` for the core logic) to ensure clean separation of concerns.
- Support for running multiple listener replicas with **load balancing** via Docker Swarm.
- A dedicated **worker service** with a configurable concurrency limit.
- Prevention of **race conditions** by introducing a `locked_by` mechanism in SQLite.
- Full job lifecycle management, including: `queued`, `running`, `succeeded`, `failed`, and `canceled`.
- Error handling with a single retry attempt (with backoff).
- Persistent storage of job data through a shared volume (`jobs-data`).