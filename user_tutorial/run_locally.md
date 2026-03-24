# Local Deployment with ngrok for MTurk Integration

This guide explains how to run the platform on your **local machine** and expose it to the internet with **ngrok** for MTurk-based studies.

Use this setup for:
- Development
- Internal testing
- Small-scale / short-duration MTurk pilots

> For long-running or large-scale studies, use cloud deployment instead.

---

## Prerequisites

Before you begin, make sure you have:

- **Docker Desktop**  
  Install: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

- **ngrok account + agent**  
  Sign up: [https://ngrok.com](https://ngrok.com)  
  Setup guide: [https://dashboard.ngrok.com/get-started/setup](https://dashboard.ngrok.com/get-started/setup)

- **AWS account**

- **MTurk Requester account**  
  [https://requester.mturk.com](https://requester.mturk.com)

- **AWS credentials** with MTurk permissions (sandbox and/or production)

> Security: never commit `.env` files or expose keys in screenshots.

---

## Step 1: Prepare the Application

1. Clone the repository:

```bash
git clone <your-repo-url>
cd HumanAgentCollab2026
```

2. Create your environment file:

```bash
cp .env.example .env
```

3. Edit `.env` and set at least:

```env
# Flask
FLASK_SECRET_KEY=replace_with_a_secure_value

# LLM
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx

# Database (local compose default)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change_me
POSTGRES_DB=humanagent
POSTGRES_PORT=5432

# App schema
PGSCHEMA=humanagent_collab

# MTurk + AWS
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
AWS_REGION=us-east-1
MTURK_ENVIRONMENT=sandbox
```

> Start with `MTURK_ENVIRONMENT=sandbox` until your full flow is verified.

---

## Step 2: Start the App Locally

Run from project root:

```bash
docker compose up --build -d
```

By default, services are available at:
- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:5000`

Researcher/participant pages:
- `http://localhost:8080/researcher`
- `http://localhost:8080/login`

---

## Step 3: Expose Local App with ngrok

In a new terminal:

```bash
ngrok http 8080
```

ngrok will output a public HTTPS URL such as:

```text
https://abc12345.ngrok-free.app
```

Use this URL in your MTurk HIT external link.

Important notes:
- Your computer must stay online while the HIT is active.
- Free ngrok URLs may change when restarted.
- If URL changes, update your MTurk task link.

---

## Step 4: Configure MTurk HIT Link

In your HIT HTML/instructions, include:

```html
<p>Please click the link below to participate:</p>
<p>
  <a href="https://<your_ngrok_url>/login?workerId=${workerId}&assignmentId=${assignmentId}&hitId=${hitId}" target="_blank">
    Start Experiment
  </a>
</p>
```

Replace `<your_ngrok_url>` with your ngrok HTTPS host.

The query params (`workerId`, `assignmentId`, `hitId`) let the platform map workers and assignments correctly.

---

## Step 5: Manage Assignments in Researcher Dashboard

1. Open `Researcher Dashboard` → MTurk panel.
2. Associate the HIT by entering the HIT ID.
3. Pull assignment list (Submitted / Approved / Rejected).
4. Approve or reject assignments from the dashboard.

Recommended workflow:
1. Run full test in MTurk Sandbox.
2. Verify assignment retrieval + completion-code flow.
3. Move to production only after end-to-end validation.

---

## Common Issues

- **Cannot fetch MTurk assignments**
  - Check `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `MTURK_ENVIRONMENT`
- **Workers cannot open experiment link**
  - Check ngrok process is still running
  - Confirm you tunneled the frontend port (`8080` by default)
- **Backend startup/database errors**
  - Check `.env` values for Postgres and schema
  - Re-run `docker compose up --build`
