# Cloud Deployment for MTurk Integration

This guide explains how to deploy the platform to a cloud environment for reliable MTurk experiments.

This option is recommended for:
- Medium/large-scale studies
- Longer-running experiments
- Better uptime and operational stability

> We strongly recommend validating your workflow in MTurk Sandbox first.

---

## Prerequisites

Prepare the following:

- **Docker Desktop** (for local image build/testing)  
  [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

- **Container registry** (to host images), e.g.:
  - [Google Artifact Registry](https://cloud.google.com/artifact-registry)
  - [Azure Container Registry](https://azure.microsoft.com/en-us/products/container-registry/)
  - [Amazon ECR](https://aws.amazon.com/ecr/)

- **Cloud provider account** (Cloud Run, Azure Container Apps, ECS, etc.)

- **Managed PostgreSQL** (recommended), e.g. RDS / Cloud SQL / Azure Database for PostgreSQL

- **AWS account + MTurk Requester account**  
  [https://requester.mturk.com](https://requester.mturk.com)

- **AWS credentials with MTurk permissions**

> Security: keep all secrets in cloud secret managers or environment variable systems, not in Git.

---

## Step 1: Build and Push Images

1. Clone repo:

```bash
git clone <your-repo-url>
cd HumanAgentCollab2026
```

2. Log in to your registry:

```bash
docker login <your_registry_url>
```

3. Build and tag backend/frontend images:

```bash
docker build -t <registry>/humanagent-backend:latest ./backend
docker build -t <registry>/humanagent-frontend:latest ./frontend
```

4. Push images:

```bash
docker push <registry>/humanagent-backend:latest
docker push <registry>/humanagent-frontend:latest
```

---

## Step 2: Choose a Cloud Runtime

You can deploy using any service that supports containerized web apps.

Common options:
- **Google Cloud Run** (simple managed deployment)
- **Azure Container Apps** (managed multi-container option)
- **AWS ECS/Fargate** (if your infra is AWS-centric)

Deployment target should include:
- One backend service (Flask/Socket.IO)
- One frontend service (Nginx static + API proxy)
- External managed Postgres (recommended)

> This repository also includes `docker-compose.rds.yml` as a reference topology for external-DB mode.
>
> Important: frontend Nginx currently proxies API/WebSocket traffic to `http://backend:5000` (see `frontend/nginx.conf`).
> If your cloud platform uses a different backend hostname, you must update `frontend/nginx.conf` and rebuild/push the frontend image.

---

## Step 3: Configure Environment Variables

Set these for the **backend** service:

```env
FLASK_SECRET_KEY=replace_with_secure_value

# LLM
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxx

# Database (recommended: full URL)
DATABASE_URL=postgresql://<user>:<password>@<db-host>:5432/<db-name>
PGSCHEMA=humanagent_collab

# MTurk / AWS
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
AWS_REGION=us-east-1
MTURK_ENVIRONMENT=sandbox

# Optional ports
BACKEND_PORT=5000
FRONTEND_PORT=8080
```

If you do not use `DATABASE_URL`, configure `PGUSER/PGPASSWORD/PGHOST/PGPORT/PGDATABASE` instead.

---

## Step 4: Initialize Database Schema

Before opening to participants, initialize DB tables once:

```bash
cd backend
python -m scripts.init_db
```

In containerized cloud environments, this is usually done by:
- one-off task/job, or
- startup command in backend service (already included in backend Dockerfile)

---

## Step 5: Validate Public Endpoints

After deployment, verify:
- Frontend URL loads (`https://<your-domain>/`)
- Researcher page loads (`/researcher`)
- Participant login loads (`/login`)
- Backend health/basic API reachable (for example `/api/experiments`)

Also verify websocket behavior (real-time updates) works through your load balancer/proxy settings.

---

## Step 6: Configure MTurk HIT Link

In your HIT content:

```html
<p>Please click the link below to participate:</p>
<p>
  <a href="https://<your_public_url>/login?workerId=${workerId}&assignmentId=${assignmentId}&hitId=${hitId}" target="_blank">
    Start Experiment
  </a>
</p>
```

Replace `<your_public_url>` with your cloud HTTPS URL.

Keep completion-code instructions in the HIT so workers submit valid completion evidence.

---

## Step 7: Operate via Researcher Dashboard

Inside MTurk panel:
1. Associate HIT ID with the session.
2. Fetch assignments.
3. Approve/reject based on completion and quality checks.

Suggested rollout:
1. Cloud deploy + internal QA
2. MTurk Sandbox pilot
3. Small production pilot
4. Full production launch

---

## Reliability and Security Recommendations

- Use managed Postgres instead of local container Postgres in production.
- Use strong `FLASK_SECRET_KEY`.
- Rotate and scope AWS credentials to least privilege.
- Enable HTTPS-only access and restrict admin/researcher access.
- Monitor logs (`backend/logs`) and set alerts for API failures.
- Keep `MTURK_ENVIRONMENT=sandbox` until end-to-end validation is complete.
