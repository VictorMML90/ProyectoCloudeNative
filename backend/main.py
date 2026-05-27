import os
import json
import uuid
import asyncio
import boto3
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import redis.asyncio as aioredis
 
app = FastAPI()
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
 
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
AWS_REGION  = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET   = os.getenv("S3_BUCKET")
 
s3 = boto3.client("s3", region_name=AWS_REGION)
 
def get_redis():
    return aioredis.from_url(f"redis://{REDIS_HOST}:6379", decode_responses=True)
 
 
# 1. Signed POST para que el frontend suba directo a S3
@app.get("/presign")
async def presign(filename: str):
    key = f"originals/{uuid.uuid4()}_{filename}"
    data = s3.generate_presigned_post(
        Bucket=S3_BUCKET,
        Key=key,
        ExpiresIn=300,
    )
    return {"url": data["url"], "fields": data["fields"], "key": key}
 
 
# 2. Encolar job
@app.post("/jobs")
async def create_job(
    s3_key: str = Form(...),
    filters: str = Form(...),
):
    job_id = str(uuid.uuid4())
    r = get_redis()
    job = {
        "id":      job_id,
        "s3_key":  s3_key,
        "filters": filters,
        "status":  "pendiente",
        "result":  "",
    }
    await r.set(f"job:{job_id}", json.dumps(job))
    await r.lpush("jobs_queue", job_id)
    await r.aclose()
    return {"job_id": job_id}
 
 
# 3. SSE: estado en tiempo real
@app.get("/status/{job_id}")
async def job_status(job_id: str):
    async def event_stream():
        r = get_redis()
        try:
            while True:
                raw = await r.get(f"job:{job_id}")
                if raw:
                    job = json.loads(raw)
                    yield f"data: {json.dumps(job)}\n\n"
                    if job["status"] in ("completada", "error"):
                        break
                await asyncio.sleep(1)
        finally:
            await r.aclose()
    return StreamingResponse(event_stream(), media_type="text/event-stream")
 
 
# 4. Listar todos los jobs
@app.get("/jobs")
async def list_jobs():
    r = get_redis()
    keys = await r.keys("job:*")
    jobs = []
    for key in keys:
        raw = await r.get(key)
        if raw:
            jobs.append(json.loads(raw))
    await r.aclose()
    return jobs
 
 
# 5 descargar el resultado
@app.get("/download/{job_id}")
async def download_url(job_id: str):
    r = get_redis()
    raw = await r.get(f"job:{job_id}")
    await r.aclose()
    if not raw:
        return JSONResponse({"error": "job no encontrado"}, status_code=404)
    job = json.loads(raw)
    if not job.get("result"):
        return JSONResponse({"error": "aún no hay resultado"}, status_code=400)
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": job["result"]},
        ExpiresIn=600,
    )
    return {"url": url}
