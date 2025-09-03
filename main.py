from fastapi import FastAPI, HTTPException, Query
import jobs  # imports jobs.py

app = FastAPI()

# Start background worker
jobs.start_worker()

@app.post("/jobs")
def create_job(job: dict):
    try:
        record = jobs.create_job(job)
        return {"job_id": record["job_id"], "status": record["status"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/jobs")
def list_jobs(status: str = Query(None, description="Filter by job status"),
              limit: int = Query(100, description="Max number of jobs to return")):
    return {"items": jobs.list_jobs(status=status, limit=limit)}


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = jobs.cancel_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "message": "job canceled successfully"}
