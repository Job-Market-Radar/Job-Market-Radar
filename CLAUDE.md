# Job Market Radar

A platform that fetches tech job postings daily, extracts skills with an LLM, and matches a CV to jobs.
Built in 7 days by two people who are here to **learn**:

- **Cloud engineer (Huthifa):** `infra/`, `.github/workflows/`, Docker, AWS, monitoring.
- **AI engineer (koopticon):** `ai/`, `dashboard/`, extraction, embeddings, matching, evaluation.
- **Shared:** `api/`, `docs/contract.md`.

The interface between the two halves is `docs/contract.md`. Read it before touching the database or the API.

## How to work with us (most important)

We are learning. The goal is that we understand everything in this repo, not that it gets written fast.

1. **Explain before writing.** Before you write code, explain the concept and the approach in a few sentences, then wait.
2. **Don't write whole files unless asked.** Prefer pointing at what to change, or writing small pieces.
3. **Boilerplate is fine.** Config files, Dockerfiles we've already written once, test scaffolding, repetitive Terraform blocks: go ahead when asked.
4. **Review, don't rubber-stamp.** When we ask for a review, point out real problems, including security and cost.
5. **Never run anything we can't explain.** Especially `terraform apply`, `terraform destroy`, and anything touching IAM. Show the command and explain it; we run it.

## AWS rules

- Account uses AWS's new experience (Builder ID sign-in, no IAM users). Home Region is **eu-north-1** (Stockholm); everything goes there.
- Free plan with credits. Never create anything that bills by the hour without saying so first (NAT gateways, load balancers, RDS, public IPv4 addresses).
- Never use or ask for root credentials or long-term access keys. Local CLI access is via `aws login`.
- Every resource is created through Terraform in `infra/`, tagged `project = "job-market-radar"` and `owner = "<name>"`.

## Deployment (how changes reach AWS)

- **Merging to `main` deploys.** `.github/workflows/deploy.yml` builds the `api`, `fetcher` and `ai` images,
  tags them with the short commit SHA, pushes them to ECR, runs `terraform apply`, and waits for ECS to be stable.
- **PRs that touch `infra/` get a `terraform plan` comment** (`.github/workflows/terraform-plan.yml`). Read it before approving.
- **Don't run `terraform apply` from a laptop.** CI applies. Locally, only plan:
```powershell
  git pull
  aws login
  cd infra
  terraform plan -var "image_tag=$(git rev-parse --short origin/main)"
```
- GitHub Actions uses AWS through OIDC (no stored keys): role `jmr-gha-plan` (read-only, PRs only) and
  `jmr-gha-deploy` (admin, pushes to `main` only).
- The fetcher runs every day at **07:00 Europe/Istanbul** (EventBridge Scheduler `jmr-fetcher-daily`).

## Infrastructure

- State: S3 bucket `jmr-tfstate-885069197789`, key `main/terraform.tfstate`, locking with `use_lockfile`.
  `infra/bootstrap/` created that bucket and keeps local state; don't touch it.
- Modules in `infra/modules/`:
  - `network`: VPC, subnets, routes
  - `data`: S3 raw bucket, RDS Postgres, secrets
  - `registry`: ECR repositories (`jmr-api`, `jmr-fetcher`, `jmr-ai`; immutable tags)
  - `ecs`: cluster, task definitions, IAM roles, load balancer, security groups, services, daily schedule
  - `cicd`: GitHub OIDC provider and the plan/deploy roles
- One variable, `image_tag` (no default): the short commit SHA of the images to deploy.
- Load balancer routes `/jobs`, `/jobs/*`, `/stats/*`, `/match-cv` to the AI service (`jmr-ai`); everything else to the API (`jmr-api`).
- App URL: `terraform output app_url`. Logs: CloudWatch `/ecs/jmr-api`, `/ecs/jmr-ai`, `/ecs/jmr-fetcher`.

## Configuration

- Locally, code gets `DATABASE_URL` (from docker-compose).
- On AWS (ECS), code gets `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` instead, because the RDS password
  lives in its own secret. Code must work with either. `GEMINI_API_KEY` is set in both.
- Secrets Manager values must be **plain text** (not key/value JSON) and have no trailing spaces or newlines.
- Code that opens files must build paths from `__file__`, not from the repo root: inside the containers the
  `ai/` folder is `/app`.

## Repo layout

```
api/          FastAPI service (shared). Tests in api/tests/
ai/           Fetcher, cleaning, extraction, embeddings, matching, AI service, evaluation (ai/eval/). Tests: ai/test_*.py
dashboard/    Streamlit app (Day 6)
infra/        Terraform: bootstrap/ (state bucket) and modules/
docs/         contract.md — the shared interface
.github/      CI, Terraform plan and Deploy workflows
```

## Commands

```bash
# Local stack (Postgres + API; add --profile ai for the fetcher)
docker compose up --build
docker compose --profile ai up --build

# Lint (CI runs this on the whole repo)
ruff check .
ruff check --fix .

# Tests
cd api && python -m pytest
cd ai && python -m pytest
```

## Conventions

- **Never commit to `main` directly.** Branch, push, open a PR. CI (`test`, `test-ai`, `build`) must pass and the other person approves.
- **Branch names:** `cloud/<topic>`, `ai/<topic>`, `chore/<topic>`.
- **Run `ruff check --fix .` before pushing.** CI lints everything, including `ai/`.
- **Add files by name, not `git add .`**
- **Files are UTF-8 without BOM, LF line endings.** On Windows, don't create files with PowerShell's `>`; it writes UTF-16.
- **`.gitignore` patterns without a leading `/` match at any depth.** `data/` once hid `infra/modules/data/`.
  Anchor root-only folders: `/data/`.
- **Secrets live in `.env` (gitignored) locally and in AWS Secrets Manager in the cloud.** Never commit `.env`, keys, `.pem` files or Terraform state.
- **If you change a table, an endpoint or an environment variable, update `docs/contract.md` in the same PR.**
- **Log the full error message, not just the status code.** "API error 400" alone cost us an hour.
