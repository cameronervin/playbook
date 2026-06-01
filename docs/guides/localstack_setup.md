# Local S3 Setup (LocalStack)

> Develop against an S3-compatible store locally with
> [LocalStack](https://github.com/localstack/localstack), so you don't need a
> real AWS account. The same boto3 client points at LocalStack in dev and real
> S3 in production — only the endpoint and credentials change.

## Option A — Compose

LocalStack is included in `deploy/compose/local.yml` (S3 service on port
`4566`):

```bash
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml up -d localstack
```

## Option B — Standalone container

```bash
docker run -d \
  --name localstack \
  -e SERVICES=s3 \
  -p 4566:4566 \
  localstack/localstack:latest
```

## Environment

Point the backend at LocalStack in `.env`:

```
S3_ENDPOINT_URL=http://localhost:4566
S3_BUCKET=app-bucket
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_REGION=us-east-1
```

In production, omit `S3_ENDPOINT_URL` and provide real credentials (ideally via
a secrets manager / instance role).

## Create the Bucket

```bash
aws --endpoint-url=http://localhost:4566 s3 mb s3://app-bucket
```

(Requires the AWS CLI. Alternatively the backend can create the bucket on
startup if you wire that in.)

## Validate

```bash
# List buckets
aws --endpoint-url=http://localhost:4566 s3 ls

# Check LocalStack health
curl http://localhost:4566/_localstack/health
```

## Reset

```bash
docker rm -f localstack
```
