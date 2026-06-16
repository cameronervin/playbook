# Self-Hosted LiteLLM

Playbook runs LiteLLM as its own gateway container so backend chat, KB
embeddings, and eval traffic do not hold direct provider API keys.

## What LiteLLM Owns

| Item | Location |
|------|----------|
| Proxy image | `deploy/docker/Dockerfile.litellm` |
| Model aliases | `deploy/litellm/config.yaml` |
| Local LiteLLM secrets | `deploy/envs/.env.litellm.local` |
| LiteLLM DB | `LITELLM_DATABASE_URL` |

Configured aliases:

- `playbook-chat` for backend chat and eval judge calls. Local defaults route
  to `openai/gpt-5.4`.
- `playbook-fast` for cheaper/faster future chat tasks. Local defaults route
  to `openai/gpt-5.4-mini`.
- `playbook-embed` for KB-service embeddings. Local defaults route to
  `openai/text-embedding-3-small`.

Provider API keys belong only in the LiteLLM env/secrets. For the local OpenAI
defaults, set:

```env
OPENAI_API_KEY=...
OPENAI_API_BASE=https://us.api.openai.com/v1
```

`OPENAI_API_BASE` must match the OpenAI regional hostname for the project that
owns the key. If OpenAI returns an incorrect regional hostname error, update this
value and rebuild or restart the LiteLLM container so `deploy/litellm/config.yaml`
is reloaded.

Add other provider keys, such as `ANTHROPIC_API_KEY`, only if you intentionally
configure aliases for those providers.

Backend and KB-service should only receive scoped LiteLLM virtual keys.

## Keys

`LITELLM_MASTER_KEY` is the LiteLLM admin key. Use it to log into the UI and
create, rotate, or revoke virtual keys. Do not use it as a production runtime
key for backend or KB-service.

`LITELLM_SALT_KEY` is used by LiteLLM for encrypted stored credentials. Keep it
secret, stable, and backed up. Do not rotate it after storing credentials in
LiteLLM.

Provision two virtual keys:

| Service | Models |
|---------|--------|
| Backend | `playbook-chat`, `playbook-fast` |
| KB-service | `playbook-embed`, `playbook-fast` |

Set them here:

```env
# deploy/envs/.env.local or prod secret
LITELLM_API_KEY=<backend-virtual-key>

# deploy/envs/.env.kb-service.local or prod secret
LITELLM_API_KEY=<kb-service-virtual-key>
```

## Local Startup

```bash
cp deploy/envs/.env.litellm.local.example deploy/envs/.env.litellm.local
./deploy/scripts/deploy.sh local --build
```

Verify:

```bash
curl http://localhost:4000/health/liveliness
curl http://localhost:4000/health/readiness
```

Generate keys from `http://localhost:4000/ui`, or use the API:

```bash
source deploy/envs/.env.litellm.local

curl -s -X POST "http://localhost:4000/key/generate" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key_alias":"playbook-backend-local","models":["playbook-chat","playbook-fast"],"metadata":{"service":"backend","environment":"local"}}'

curl -s -X POST "http://localhost:4000/key/generate" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key_alias":"playbook-kb-local","models":["playbook-embed","playbook-fast"],"metadata":{"service":"kb-service","environment":"local"}}'
```

After writing generated keys into the app env files, restart app services:

```bash
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml up -d --force-recreate backend kb-api kb-worker-cpu kb-worker-io
```

## Production Notes

- Use a separate LiteLLM database or database user.
- Keep the LiteLLM DB and proxy on private networking.
- Store `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY`, provider keys, and virtual keys
  in a secrets manager.
- Generate backend and KB-service virtual keys during provisioning/deploy, then
  inject those keys into the services.
- Do not give backend or KB-service the master key.

Keys survive LiteLLM container restarts because they are stored in the LiteLLM
database. They must be regenerated only if the LiteLLM DB is deleted, volumes are
wiped, or you intentionally rotate/revoke them.

## Security Posture

The LiteLLM DB is sensitive because it stores virtual key records, usage/spend
data, budgets, and related metadata. Protect it like application credentials:

- no public DB exposure,
- least-privilege DB user,
- encrypted backups,
- scoped virtual keys per service,
- budgets and rate limits per key,
- regular LiteLLM updates.

This is safer than putting provider keys directly in every app service because a
leaked virtual key can be revoked, budget-limited, and model-scoped without
rotating Anthropic or OpenAI provider credentials.
