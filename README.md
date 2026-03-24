# A Configurable Research Platform for Human-LLM Agent Collaboration

This repository presents a configurable research platform for conducting Human-LLM agent collaboration experiments from the paper **Through the Lens of Human-Human Collaboration: A Configurable Research Platform for Exploring Human-Agent Collaboration**.

The system supports multiple experiment paradigms, including ShapeFactory, DayTrader, EssayRanking, and WordGuessing, along with an Experiment Configuration Language (ECL) for custom experiment design.

![image](https://github.com/neuhai/human-agent-collab/blob/main/preview.gif)

This repository includes:
- `backend/`: Flask + Socket.IO backend (experiment logic, session management, database, MTurk APIs)
- `frontend/`: Vue 3 frontend (researcher dashboard, participant interface, annotation pages)
- `docker-compose.yml`: one-command local stack (Postgres + backend + frontend)
- `docker-compose.rds.yml`: deployment mode with external Postgres (e.g., AWS RDS)

---

## Table of Contents

- [A Configurable Research Platform for Human-LLM Agent Collaboration](#a-configurable-research-platform-for-human-llm-agent-collaboration)
  - [Table of Contents](#table-of-contents)
  - [Quick Start (Docker)](#quick-start-docker)
    - [Prerequisites](#prerequisites)
    - [1) Prepare environment variables](#1-prepare-environment-variables)
    - [2) Start full local stack (with bundled Postgres)](#2-start-full-local-stack-with-bundled-postgres)
    - [3) Use external Postgres (e.g., AWS RDS)](#3-use-external-postgres-eg-aws-rds)
  - [User Tutorials](#user-tutorials)
  - [MTurk Deployment Notes](#mturk-deployment-notes)
  - [Run from Source (Developer)](#run-from-source-developer)
    - [Backend](#backend)
    - [Frontend](#frontend)
  - [Configuration](#configuration)
    - [LLM Providers](#llm-providers)
    - [Database](#database)
    - [Storage / Annotation](#storage--annotation)
  - [Key Features](#key-features)
  - [Project Structure](#project-structure)
  - [Troubleshooting](#troubleshooting)
  - [Citation](#citation)

---

## Quick Start (Docker)

This path is for users who want to run the platform locally as quickly as possible.

### Prerequisites

- Docker Desktop installed and running
- A terminal (macOS Terminal, Linux shell, or PowerShell)

### 1) Prepare environment variables

From the repository root:

```bash
cp .env.example .env
```

Then edit `.env` and at least confirm:

- `FLASK_SECRET_KEY`
- LLM settings (`LLM_PROVIDER` + corresponding API key)
- Database settings (local Postgres or external DB)

> By default, `.env.example` uses `LLM_PROVIDER=mock`, which is useful for local testing without model API calls.

### 2) Start full local stack (with bundled Postgres)

```bash
docker compose up --build
```

After startup:
- Frontend: [http://localhost:8080](http://localhost:8080)
- Backend API: [http://localhost:5000](http://localhost:5000)
- Researcher Dashboard: [http://localhost:8080/researcher](http://localhost:8080/researcher)
- Participant Login: [http://localhost:8080/login](http://localhost:8080/login)

### 3) Use external Postgres (e.g., AWS RDS)

After setting `DATABASE_URL` or `PGHOST/PGUSER/PGPASSWORD/PGDATABASE` in `.env`:

```bash
docker compose -f docker-compose.rds.yml --env-file .env up --build
```

---

## User Tutorials

Detailed deployment guides:

- Local deployment with ngrok (development/sandbox friendly):  
  [`user_tutorial/run_locally.md`](./user_tutorial/run_locally.md)
- Cloud deployment (recommended for robust MTurk studies):  
  [`user_tutorial/run_on_cloud.md`](./user_tutorial/run_on_cloud.md)

---

## MTurk Deployment Notes

The backend includes MTurk management APIs (associate HIT, list assignments, approve/reject assignments).

Required environment variables:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` (typically `us-east-1`)
- `MTURK_ENVIRONMENT` (`sandbox` or `production`)

The backend automatically switches endpoint by environment:
- sandbox: `https://mturk-requester-sandbox.us-east-1.amazonaws.com`
- production: `https://mturk-requester.us-east-1.amazonaws.com`

> Before running real studies, deploy to a publicly reachable URL (cloud deployment or tunnel/proxy setup).

---

## Run from Source (Developer)

Use this path if you want to develop/debug backend and frontend directly.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.init_db
python app.py
```

Default backend URL: `http://localhost:5000`

### Frontend

```bash
cd frontend
corepack enable
yarn install
yarn dev
```

Frontend dev server is usually: `http://localhost:5173` (check Vite output).

---

## Configuration

### LLM Providers

Supported providers:
- Azure OpenAI (recommended)
- OpenAI
- Anthropic Claude
- Mock (testing)

Configured via environment variables (see `.env.example` and `backend/agent/README_LLM.md`):
- `LLM_PROVIDER` (`azure` / `openai` / `claude` / `mock`)
- `OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`
- `ANTHROPIC_API_KEY`

### Database

Two supported modes:
- **Bundled Postgres (`docker-compose.yml`)**
- **External Postgres/RDS (`docker-compose.rds.yml`)**

Application tables are created under schema `humanagent_collab` by default (override with `PGSCHEMA`).

### Storage / Annotation

If you enable S3-based uploads (screenshots, annotation assets, etc.), configure:
- `S3_BUCKET`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`

---

## Key Features

- Multiple experiment paradigms managed through the researcher dashboard
- Human-AI mixed collaboration within the same session
- Real-time state updates via Socket.IO (participants, status, timers)
- Experiment config upload and backend validation
- Resource upload support (PDF/image/text files)
- In-session and post-session annotation workflows
- MTurk workflow support (HIT association, assignment retrieval, approval/rejection)

---

## Project Structure

```text
HumanAgentCollab2026/
├── backend/
│   ├── app.py
│   ├── routes/                 # session / participant / mturk APIs
│   ├── agent/                  # agent runner + LLM client + prompts
│   ├── services/               # db, logging, timer, annotation, storage
│   ├── scripts/                # init_db, etc.
│   ├── database/               # SQL init scripts
│   ├── ecl_example/            # ECL sample configurations
│   └── uploads/                # uploaded assets (maps / essays)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   ├── services/
│   │   └── router/
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.rds.yml
└── .env.example
```

---

## Troubleshooting

- **Containers fail to start**
  - Ensure Docker Desktop is running
  - Check port conflicts on `5000`, `8080`, `5432`
- **Backend cannot connect to database**
  - Verify `DATABASE_URL` or `PG*` values are complete
  - For RDS, verify security group/network accessibility
- **LLM does not respond**
  - Confirm `LLM_PROVIDER` and provider keys match
  - Try `LLM_PROVIDER=mock` first to validate pipeline
- **MTurk API errors**
  - Verify `AWS_REGION` and `MTURK_ENVIRONMENT`
  - Verify IAM permissions and key validity

---

## Citation

```bibtex
@article{yao2025through,
  title={Through the Lens of Human-Human Collaboration: A Configurable Research Platform for Exploring Human-Agent Collaboration},
  author={Yao, Bingsheng and Chen, Jiaju and Chen, Chaoran and Wang, April and Li, Toby Jia-jun and Wang, Dakuo},
  journal={arXiv preprint arXiv:2509.18008},
  year={2025}
}
```
