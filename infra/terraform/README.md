# Infrastructure — Terraform (GCP)

Provisions the full AppArt Agent stack on Google Cloud Platform.

## What gets created

| Resource | Service | Purpose |
|----------|---------|---------|
| Cloud Run (frontend) | `appart-frontend` | Next.js app with Better Auth |
| Cloud Run (backend) | `appart-backend` | FastAPI + Gemini |
| Cloud Run Job | `db-migrate` | Alembic migrations |
| Cloud SQL | PostgreSQL 15 | Primary database |
| Memorystore | Redis 7 | Caching |
| Cloud Storage | 2 buckets | Documents & photos |
| Secret Manager | 6 secrets | DB password, JWT, Better Auth, Logfire, OAuth |
| VPC + Connector | Private networking | Cloud SQL & Redis access |
| Load Balancer | Global HTTPS LB | SSL + routing (apex/www -> frontend, api.* -> backend) |
| Certificate Manager | Managed SSL | Auto-renewed certificates |
| Cloud DNS | Managed zone | DNS records |
| Artifact Registry | Docker repo | Container images |

## Quick start

```bash
# 1. Authenticate
gcloud auth application-default login

# 2. Configure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project ID, domain, etc.

# 3. Initialize (local state)
terraform init

# 4. Review & apply
terraform plan
terraform apply
```

## Remote state (team usage)

```bash
# First time — creates a GCS bucket for state
./scripts/setup-remote-state.sh <PROJECT_ID>
terraform init -backend-config=backend.hcl -migrate-state

# Joining existing team
cp backend.hcl.example backend.hcl
# Edit backend.hcl with your bucket name
terraform init -backend-config=backend.hcl
```

## Key variables

| Variable | Required | Description |
|----------|----------|-------------|
| `project_id` | Yes | GCP project ID |
| `region` | No | GCP region (default: `europe-west1`) |
| `domain` | No | Custom domain (e.g. `appartagent.com`) |
| `logfire_token` | No | Logfire observability token |
| `google_oauth_client_id` | No | Google OAuth client ID (enables Google sign-in) |
| `google_oauth_client_secret` | No | Google OAuth client secret |

See `terraform.tfvars.example` for all options with descriptions.

## Optional features

**Google OAuth** — Leave `google_oauth_client_id` and `google_oauth_client_secret` empty to disable.
Email/password authentication works without it. When set, Terraform creates secret versions and
injects the credentials into the frontend Cloud Run service.

**Logfire** — Leave `logfire_token` empty to disable. The backend `LOGFIRE_TOKEN` and `LOGFIRE_ENABLED`
env vars are only injected when the token is provided.

**Custom domain** — Leave `domain` empty to use Cloud Run URLs directly.
When set, a load balancer with managed SSL certificates is provisioned.

## DNS notes

Terraform manages these DNS records:

- `appartagent.com` (A) -> load balancer IP
- `www.appartagent.com` (A) -> load balancer IP
- `api.appartagent.com` (A) -> load balancer IP
- `_acme-challenge.*` (CNAME) -> certificate validation

Any records you add manually (MX, TXT, SPF, etc.) are **not touched** by Terraform.

## Files

```text
infra/terraform/
  main.tf                   # All resources
  backend.tf                # Remote state backend config
  backend.hcl.example       # Template for GCS state bucket
  terraform.tfvars.example  # Template for variables
  scripts/
    setup-remote-state.sh   # Creates GCS bucket for remote state
```

## Cost estimate

| Setup | Approximate monthly cost |
|-------|--------------------------|
| Minimal (scale-to-zero, db-f1-micro, BASIC redis) | ~$50 |
| Production (min_instances=1, db-custom-2-4096, STANDARD_HA redis) | ~$200-250 |
