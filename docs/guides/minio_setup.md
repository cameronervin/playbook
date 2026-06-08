# Local S3-Compatible Storage Setup (MinIO)

> Develop against an S3-compatible object store locally with MinIO, so you
> don't need a real AWS account. The same boto3 client points at MinIO in local
> development and real S3 in production — only the endpoint and credentials
> change.

## Option A — Compose

MinIO is included in `deploy/compose/local.yml` with the S3 API on port `9000`
and the web console on port `9001`:

```bash
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml up -d minio minio-bootstrap
```

The `minio-bootstrap` service creates the local buckets used by Playbook:

```text
playbook-bucket
kb-documents
```

## Option B — Standalone container

```bash
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -v minio_data:/data \
  -e MINIO_ROOT_USER=playbookminio \
  -e MINIO_ROOT_PASSWORD=playbookminio123 \
  quay.io/minio/minio server /data --console-address ":9001"
```

## Environment

For services running inside Docker Compose, point the backend at MinIO with:

```env
S3_ENDPOINT_URL=http://minio:9000
S3_BUCKET_NAME=playbook-bucket
S3_ACCESS_KEY_ID=playbookminio
S3_SECRET_ACCESS_KEY=playbookminio123
S3_REGION=us-east-1
```

For a backend running directly on your host machine, use:

```env
S3_ENDPOINT_URL=http://localhost:9000
```

In production, omit `S3_ENDPOINT_URL` and provide real credentials (ideally via
a secrets manager / instance role).

## Create the Bucket

Compose creates buckets automatically. For standalone MinIO, use the MinIO
client:

```bash
docker run --rm --network host quay.io/minio/mc \
  sh -c 'mc alias set local http://localhost:9000 playbookminio playbookminio123 && \
  mc mb --ignore-existing local/playbook-bucket && \
  mc mb --ignore-existing local/kb-documents'
```

## Validate

```bash
# Check MinIO health
curl -f http://localhost:9000/minio/health/live

# Open MinIO console
open http://localhost:9001
```

## Reset

```bash
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml rm -sf minio minio-bootstrap
docker volume rm playbook_minio_data
```
