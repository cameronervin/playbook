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
Playbook:

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

## Browser CORS

Local Compose configures MinIO's global CORS allowlist with
`MINIO_API_CORS_ALLOW_ORIGIN=http://localhost:3000` by default. The bootstrap
container only creates the bucket; it does not apply bucket-level CORS rules.
This keeps local setup aligned with MinIO's documented global CORS setting and
avoids brittle XML bootstrapping in `mc cors set`.

Validate the frontend origin before browser direct-upload smoke:

```bash
curl -i -X OPTIONS http://localhost:9000/playbook-bucket \
  -H 'Origin: http://localhost:3000' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type'
```

The response should include `Access-Control-Allow-Origin:
http://localhost:3000` and `Access-Control-Allow-Methods: POST`.

For production AWS S3 or an S3-compatible service that requires bucket CORS
configuration, configure the equivalent POST/GET/HEAD CORS policy through that
provider's supported control plane. MinIO also supports bucket CORS through
`mc cors set`, but that command expects S3 CORS XML.

## Validate

```bash
# Check MinIO health
curl -f http://localhost:9000/minio/health/live

# Confirm browser preflight
curl -i -X OPTIONS http://localhost:9000/playbook-bucket \
  -H 'Origin: http://localhost:3000' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type'

# Open MinIO console
open http://localhost:9001
```

Manual direct-upload smoke for the implemented route path:

1. Start the backend with `S3_ENDPOINT_URL` pointing at MinIO and
   `S3_PUBLIC_ENDPOINT_URL=http://localhost:9000` so browser upload contracts
   use the host-reachable endpoint.
2. Create an upload intent through either
   `POST /api/v1/admin/kb/documents` or
   `POST /api/v1/conversations/{conversation_id}/files`.
3. Submit a multipart form POST to the returned `upload.url` with every
   returned `upload.fields` entry plus a final `file` part.
4. Call the matching `upload-complete` endpoint with the returned
   `upload_request_id`.
5. Confirm backend completion verifies MinIO object metadata and transitions the
   resource to `uploaded`; the backend worker should then move it to
   `processing`/`extracting` and eventually `ready` or `failed` after KB-service
   ingestion.

If the browser POST fails before reaching backend completion, re-check bucket
CORS, the frontend origin, and `S3_PUBLIC_ENDPOINT_URL`.

## Reset

```bash
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml rm -sf minio minio-bootstrap
docker volume rm playbook_minio_data
```
