import os
import json
import uuid
import io
import redis
import boto3
from PIL import Image, ImageFilter, ImageOps

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
AWS_REGION  = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET   = os.getenv("S3_BUCKET")

r  = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
s3 = boto3.client("s3", region_name=AWS_REGION)


def update_status(job_id, status, result=""):
    raw = r.get(f"job:{job_id}")
    if not raw:
        return
    job = json.loads(raw)
    job["status"] = status
    job["result"] = result
    r.set(f"job:{job_id}", json.dumps(job))


def download_image(key):
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return Image.open(io.BytesIO(obj["Body"].read())).convert("RGB")


def upload_image(img, key, fmt="JPEG"):
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=buf, ContentType=f"image/{fmt.lower()}")


def apply_filters(img, filters):
    ext = "JPEG"
    for f in filters:
        if f == "grayscale":
            img = ImageOps.grayscale(img).convert("RGB")
        elif f == "blur":
            img = img.filter(ImageFilter.GaussianBlur(radius=4))
        elif f == "sharpen":
            img = img.filter(ImageFilter.SHARPEN)
        elif f == "resize":
            img = img.resize((800, 600), Image.LANCZOS)
        elif f == "thumbnail":
            img = img.copy()
            img.thumbnail((200, 200), Image.LANCZOS)
        elif f == "sepia":
            gray = ImageOps.grayscale(img)
            img = Image.merge("RGB", [
                gray.point(lambda p: min(255, int(p * 1.1))),
                gray.point(lambda p: min(255, int(p * 0.9))),
                gray.point(lambda p: min(255, int(p * 0.7))),
            ])
        elif f == "png":
            ext = "PNG"
    return img, ext


def process_job(job_id):
    raw = r.get(f"job:{job_id}")
    if not raw:
        return
    job = json.loads(raw)
    filters = json.loads(job["filters"])

    print(f"[worker] Procesando {job_id} | filtros: {filters}")
    update_status(job_id, "en proceso")

    try:
        img = download_image(job["s3_key"])
        img, ext = apply_filters(img, filters)
        result_key = f"processed/{uuid.uuid4()}.{ext.lower()}"
        upload_image(img, result_key, ext)
        update_status(job_id, "completada", result_key)
        print(f"[worker] Completado {job_id} → {result_key}")
    except Exception as e:
        print(f"[worker] Error {job_id}: {e}")
        update_status(job_id, "error")


print("[worker] Listo, esperando jobs...")
while True:
    result = r.brpop("jobs_queue", timeout=5)
    if result:
        _, job_id = result
        process_job(job_id)
