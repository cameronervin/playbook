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

The `minio-bootstrap` service creates the configured local bucket used by
Playbook and applies bucket CORS so the frontend origin can POST direct-upload
form requests:

```text
playbook-bucket
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
S3_PUBLIC_ENDPOINT_URL=http://localhost:9000
S3_BUCKET_NAME=playbook-bucket
S3_ACCESS_KEY_ID=playbookminio
S3_SECRET_ACCESS_KEY=playbookminio123
S3_REGION=us-east-1
```

`S3_ENDPOINT_URL` is the container-internal endpoint used by backend and
KB-service processes. `S3_PUBLIC_ENDPOINT_URL` is only used when returning
browser direct-upload POST contracts, because the browser must reach MinIO
through the host port.

For a backend running directly on your host machine, use:

```env
S3_ENDPOINT_URL=http://localhost:9000
S3_PUBLIC_ENDPOINT_URL=http://localhost:9000
```

In production, omit `S3_ENDPOINT_URL` and provide real credentials (ideally via
a secrets manager / instance role).

## Create the Bucket

Compose creates buckets automatically. For standalone MinIO, use the MinIO
client:

```bash
docker run --rm --network host quay.io/minio/mc \
  sh -c 'mc alias set local http://localhost:9000 playbookminio playbookminio123 && \
  mc mb --ignore-existing local/playbook-bucket'
```

## Bucket CORS

Compose applies this automatically from `deploy/compose/local.yml`. For
standalone MinIO, configure CORS with the MinIO client:

```bash
cat > /tmp/playbook-cors.json <<'JSON'
[
  {
    "AllowedOrigins": ["http://localhost:3000"],
    "AllowedMethods": ["POST", "GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": [
      "ETag",
      "x-amz-checksum-crc32",
      "x-amz-checksum-crc32c",
      "x-amz-checksum-sha1",
      "x-amz-checksum-sha256"
    ],
    "MaxAgeSeconds": 3000
  }
]
JSON

docker run --rm --network host -v /tmp/playbook-cors.json:/tmp/playbook-cors.json quay.io/minio/mc \
  sh -c 'mc alias set local http://localhost:9000 playbookminio playbookminio123 && \
  mc cors set local/playbook-bucket /tmp/playbook-cors.json && \
  mc cors get local/playbook-bucket'
```

## Validate

```bash
# Check MinIO health
curl -f http://localhost:9000/minio/health/live

# Confirm bucket CORS
docker run --rm --network host quay.io/minio/mc \
  sh -c 'mc alias set local http://localhost:9000 playbookminio playbookminio123 && \
  mc cors get local/playbook-bucket'

# Open MinIO console
open http://localhost:9001
```

Manual direct-upload smoke after backend storage support is available:

1. Generate a presigned POST contract through `StorageProvider.create_presigned_post(...)`.
2. Submit a multipart form POST to the returned `url` with every returned
   `field` plus a `file` part.
3. Confirm `StorageProvider.get_object_metadata(...)` returns the expected
   content length, content type, ETag, and any checksum metadata exposed by
   MinIO.
4. Confirm `StorageProvider.verify_object(...)` returns `valid`.

## Reset

```bash
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml rm -sf minio minio-bootstrap
docker volume rm playbook_minio_data
```
