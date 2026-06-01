# Storage Infrastructure — Stubs & Extension Guide

File storage behind a provider interface. The scaffold ships one real
implementation: S3 (via boto3), which also targets LocalStack and AWS profiles.

## Pattern

```
StorageProvider (ABC)        ← provider.py
   └── S3StorageProvider     ← s3_client.py  (boto3, LocalStack/AWS)

_StorageManager singleton    ← factory.py
get_storage_provider()       ← factory.py  (lazy singleton)
get_storage_provider_dependency() ← factory.py (FastAPI Depends)
cleanup_storage_provider()   ← factory.py  (shutdown)
reset_storage_provider()     ← factory.py  (test reset)

key construction             ← paths.py
```

Unlike the LLM/KB factories, storage uses a manager-object singleton rather
than `@lru_cache`, because the boto3 client needs an explicit `.close()` on
shutdown.

## Configuration

| Setting             | Local (LocalStack)            | Production AWS S3        |
|---------------------|-------------------------------|--------------------------|
| `S3_ENDPOINT_URL`   | `http://localstack:4566`      | unset / None             |
| `S3_ACCESS_KEY_ID`  | `test`                        | unset (use profile/IAM)  |
| `S3_SECRET_ACCESS_KEY` | `test`                     | unset (use profile/IAM)  |
| `AWS_PROFILE`       | unset                         | optional profile name    |
| `S3_BUCKET_NAME`    | `scaffold-bucket`             | your bucket              |

## Adding a new backend (e.g. local filesystem, GCS, Azure Blob)

1. Implement `StorageProvider` (e.g. `FilesystemStorageProvider`).
2. Add a mode setting if you want it switchable (e.g. `STORAGE_MODE`), then
   convert `factory.py` to the StrEnum + factory pattern used by the LLM/KB
   factories. Otherwise just swap the class instantiated in `_StorageManager`.
3. Keep `_run_sync` semantics: any blocking client call must be dispatched to a
   thread executor with a timeout so the event loop is never blocked.

## Key construction

All S3 keys are built in `paths.py`. Replace the `examples/...` prefixes with
your real entity hierarchy. Use `generated_file_key()` for versioned files and
`generated_file_key_static()` for overwrite-in-place files.
