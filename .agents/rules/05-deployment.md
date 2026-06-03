# Deployment Rules

## Structure
```
deploy/
├── docker/      # Dockerfiles, nginx config
├── envs/        # Environment-specific .env files
├── compose/     # Docker Compose files (base + overrides)
└── scripts/     # Deployment and maintenance scripts
```

## Environment Files
| File | Purpose | Commit? |
|------|---------|---------|
| `.env.local` | Local development | ✅ Yes |
| `.env.dev` | Development server | ✅ Yes (with placeholders) |
| `.env.test` | Staging/QA | ✅ Yes (with placeholders) |
| `.env.prod.example` | Production template | ✅ Yes |
| `.env.prod` | Real production values | 🚫 Never |

## Compose Pattern
- `base.yml` → Shared service definitions
- `<env>.yml` → Environment-specific overrides

```bash
# Usage
docker compose -f base.yml -f local.yml up
# Or use deploy script
./deploy/scripts/deploy.sh local|dev|test|prod
```

## DO
- Use base.yml + environment override pattern
- Keep secrets as `${PLACEHOLDER}` in committed files
- Use AWS Secrets Manager / Vault for production
- Add health checks on all services
- Set resource limits in staging/production
- Use deploy script for consistent deployments

## DON'T
- Commit real `.env.prod` file
- Hardcode credentials in compose files
- Expose database ports in production
- Skip health checks
- Deploy without resource limits

## Environment Differences
| Setting | Local | Dev | Test | Prod |
|---------|-------|-----|------|------|
| DEBUG | true | true | false | false |
| LOG_LEVEL | DEBUG | DEBUG | INFO | WARNING |
| Replicas | 1 | 1 | 2 | 3+ |
| Volumes | bind mounts | none | none | none |
| DB ports | exposed | exposed | internal | internal |
| Secrets | .env file | .env file | .env file | secrets manager |

## Commands
```bash
# Deploy to environment
./deploy/scripts/deploy.sh local|dev|test|prod

# With options
./deploy/scripts/deploy.sh dev --build --logs

# Stop services
./deploy/scripts/deploy.sh prod --down

# View logs
cd deploy/compose && docker compose -f base.yml -f local.yml logs -f backend
```
