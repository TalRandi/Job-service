import time
import threading
import sqlite3
import json
import os
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid

# SQLite setup
DB_PATH = os.getenv("DB_PATH", "jobs.db")
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "3"))  # configurable concurrency limit

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            type TEXT,
            payload TEXT,
            status TEXT,
            result TEXT,
            retry_count INTEGER DEFAULT 0,
            locked_by TEXT DEFAULT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------- Job operations ---------------- #

def create_job(job: dict):
    if "type" not in job:
        raise ValueError("Missing job type")

    job_type = job["type"].lower()
    payload = job.get("payload", {})

    conn = get_conn()
    c = conn.cursor()

    # --- check for duplicate ---
    c.execute("SELECT * FROM jobs WHERE type = ? AND payload = ?", 
              (job_type, json.dumps(payload, sort_keys=True)))
    existing = c.fetchone()
    if existing:
        conn.close()
        job = dict(existing)
        job["payload"] = json.loads(job["payload"])
        job["result"] = json.loads(job["result"]) if job["result"] else None
        return job

    # --- create new job ---
    job_id = str(uuid4())
    status = "queued"
    result = None

    c.execute(
        "INSERT INTO jobs (job_id, type, payload, status, result) VALUES (?, ?, ?, ?, ?)",
        (job_id, job_type, json.dumps(payload, sort_keys=True), status, json.dumps(result))
    )
    conn.commit()
    c.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    row = c.fetchone()
    conn.close()

    job = dict(row)
    job["payload"] = json.loads(job["payload"])
    job["result"] = json.loads(job["result"]) if job["result"] else None
    return job

def get_job(job_id: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    row = c.fetchone()
    conn.close()
    if row:
        job = dict(row)
        job["payload"] = json.loads(job["payload"])
        job["result"] = json.loads(job["result"]) if job["result"] else None
        return job
    return None

def list_jobs(status: str = None, limit: int = 100):
    conn = get_conn()
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM jobs WHERE status = ? LIMIT ?", (status, limit))
    else:
        c.execute("SELECT * FROM jobs LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()

    jobs_list = []
    for row in rows:
        job = dict(row)
        job["payload"] = json.loads(job["payload"])
        job["result"] = json.loads(job["result"]) if job["result"] else None
        jobs_list.append(job)
    return jobs_list

def cancel_job(job_id: str):
    job = get_job(job_id)
    if not job:
        return None
    if job["status"] in ("succeeded", "failed", "canceled"):
        return job
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE jobs SET status = ? WHERE job_id = ?", ("canceled", job_id))
    conn.commit()
    conn.close()
    job["status"] = "canceled"
    return job

# ---------------- Worker logic ---------------- #

def run_job(job):
    import json
    import time

    job_id = job["job_id"]
    conn = get_conn()
    c = conn.cursor()

    # check if job is locked by this worker
    c.execute("SELECT locked_by FROM jobs WHERE job_id=?", (job_id,))
    row = c.fetchone()
    if not row or row["locked_by"] != WORKER_ID:
        conn.close()
        return  # someone else is taking the job

    try:
        # mark as running
        c.execute("UPDATE jobs SET status=? WHERE job_id=?", ("running", job_id))
        conn.commit()

        payload = json.loads(job["payload"])
        result = None

        if job["type"] == "sleep":
            seconds = payload.get("seconds", 1)
            time.sleep(seconds)
            result = {"slept": seconds}

        elif job["type"] == "analyze":
            filename = payload.get("filename")
            patterns = payload.get("patterns", [])
            if not filename:
                raise ValueError("Missing filename in payload")
            counts = {}
            with open(filename, "r", encoding="utf-8") as f:
                text = f.read()
                for pat in patterns:
                    counts[pat] = text.count(pat)
            result = {"counts": counts}

        else:
            result = {"info": f"job type not implemented: {job['type']}"}

        # mark as succeeded
        c.execute(
            "UPDATE jobs SET status=?, result=? WHERE job_id=?",
            ("succeeded", json.dumps(result), job_id)
        )
        conn.commit()

    except Exception as e:
        retry_count = job.get("retry_count", 0)
        if retry_count < 1:
            # small backoff before retry
            time.sleep(2)
            # update retry_count
            c.execute(
                "UPDATE jobs SET retry_count=? WHERE job_id=?",
                (retry_count + 1, job_id)
            )
            conn.commit()
            # fetch fresh job data
            c.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
            fresh_job = dict(c.fetchone())
            fresh_job["payload"] = json.loads(fresh_job["payload"])
            run_job(fresh_job)  # retry once
        else:
            # mark as failed
            c.execute(
                "UPDATE jobs SET status=?, result=? WHERE job_id=?",
                ("failed", json.dumps({"error": str(e)}), job_id)
            )
            conn.commit()

    finally:
        conn.close()

WORKER_ID = str(uuid.uuid4()) 

def worker_loop():
    executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENCY)
    while True:
        conn = get_conn()
        c = conn.cursor()
        c.execute("BEGIN;")

        # choose jobs that are queued and not locked
        c.execute(
            "SELECT * FROM jobs WHERE status='queued' AND locked_by IS NULL LIMIT ?",
            (MAX_CONCURRENCY,)
        )
        jobs_to_run = c.fetchall()
        job_ids = [job["job_id"] for job in jobs_to_run]

        # lock them with locked_by
        if job_ids:
            c.execute(
                "UPDATE jobs SET locked_by=? WHERE job_id IN ({seq})".format(
                    seq=','.join('?'*len(job_ids))
                ),
                [WORKER_ID, *job_ids]
            )
        conn.commit()
        conn.close()

        futures = []
        for row in jobs_to_run:
            job = dict(row)
            futures.append(executor.submit(run_job, job))

        for f in as_completed(futures):
            pass

        time.sleep(1)

def start_worker():
    threading.Thread(target=worker_loop, daemon=True).start()
