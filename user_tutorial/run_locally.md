# Local Deployment with ngrok for MTurk Integration

This guide provides step-by-step instructions for running the human–agent collaboration platform on your **local machine** and exposing it to the internet using **ngrok**. This setup is ideal for:

* Development
* Internal testing
* **Small-scale or short-duration** experiments with Amazon Mechanical Turk (MTurk)

> ⚠️ For long-running or large-scale studies, we recommend using the **cloud deployment** option instead.

---

## Prerequisites

Before you begin, make sure you have the following:

* **Docker Desktop**
  Required to run the application containers.
  Download: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

* **ngrok**
  Used to expose your local server to the public internet.

  * Sign up for an account: [https://ngrok.com](https://ngrok.com)
  * Install the ngrok agent and add your authtoken:
    [https://dashboard.ngrok.com/get-started/setup](https://dashboard.ngrok.com/get-started/setup)

* **AWS Account**
  An active AWS account is required for MTurk.

* **MTurk Requester Account**
  You will need an MTurk Requester account to create and manage HITs:
  [https://requester.mturk.com](https://requester.mturk.com)

* **AWS Credentials with MTurk Permissions**
  An Access Key ID and Secret Access Key that can interact with MTurk (sandbox and/or production).

> 🔐 **Security note:** Keep your AWS keys and API keys private. Do **not** commit them to GitHub or share screenshots with keys visible.

---

## Step 1: Set Up the Application

The quickest way to set up the application is to use the one-line setup command.

1. **Open a terminal**

   * macOS / Linux: Terminal
   * Windows: PowerShell

2. **Run the appropriate command for your operating system**

   * **macOS or Linux:**

     ```bash
     curl -fsSL https://raw.githubusercontent.com/neuhai/human-agent-collab/main/deployment/quick-start.sh | bash
     ```

   * **Windows (PowerShell):**

     ```powershell
     irm https://raw.githubusercontent.com/neuhai/human-agent-collab/main/deployment/quick-start.ps1 | iex
     ```

3. **Navigate into the new directory**

   ```bash
   cd human-agent-collab-app
   ```

4. **Configure environment variables**

   Open the `.env` file in a text editor and fill in the required values:

   ```env
   # A secure password for the database
   POSTGRES_PASSWORD=your_super_secret_password

   # Your OpenAI API key
   OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

   # A secure random string for JWT
   JWT_SECRET=your_secure_random_string

   # --- AWS Configuration (for MTurk Integration) ---
   AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
   AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
   MTURK_REGION_NAME=us-east-1
   MTURK_ENVIRONMENT=sandbox  # Use 'sandbox' for testing, 'production' for live HITs
   ```

> ✅ **Recommended:** Start with `MTURK_ENVIRONMENT=sandbox` until you have fully tested the entire workflow.

> 🔐 Make sure `.env` is **ignored by Git** (via `.gitignore`) so that secrets are not committed.

---

## Step 2: Run the Application Locally

Once the `.env` file is configured, you can start the application using Docker:

```bash
docker compose up -d
```

* The first run may take a few minutes as Docker downloads the images.
* After the containers start, the application should be available at:

  ```text
  http://localhost
  ```

> ℹ️ If your setup uses a non-default port (e.g., `http://localhost:8080`), make a note of that—you’ll need it in the ngrok step.

---

## Step 3: Expose the Application with ngrok

To make your local application accessible to MTurk workers, you need to expose it to the internet.

1. **Open a new terminal window** (keep the one running Docker open).

2. **Start an ngrok tunnel**:

   ```bash
   ngrok http 80
   ```

   * If your application is running on a different local port (for example `http://localhost:8080`), use:

     ```bash
     ngrok http 8080
     ```

3. **Get the public URL**

   ngrok will display a URL such as:

   ```text
   https://random-string.ngrok.io
   ```

   This is the URL you will use in your MTurk HIT.

> ⚠️ **Important limitations:**
>
> * Your machine must stay **on and connected to the internet** for the entire duration of the experiment.
> * If you stop ngrok and restart it, the public URL may change (especially on the free plan). You will need to update your HIT if that happens.
> * All traffic passes through ngrok’s relay servers; check whether this is acceptable for your IRB and data policies.

---

## Step 4: Configure the MTurk HIT

When you create your HIT on the MTurk Requester website (Sandbox or Production), embed the ngrok URL so that each worker is linked to an experiment session.

1. **HIT Description and Link**

   In the HIT description / HTML content, include instructions and a link like this:

   ```html
   <p>Please click the link below to participate in the experiment:</p>
   <p>
     <a href="https://<your_ngrok_url>/login?workerId=${workerId}&assignmentId=${assignmentId}&hitId=${hitId}"
        target="_blank">
       Start Experiment
     </a>
   </p>
   ```

   Replace `<your_ngrok_url>` with the HTTPS URL from ngrok, for example:

   ```text
   https://random-string.ngrok.io
   ```

   The `${workerId}`, `${assignmentId}`, and `${hitId}` variables will be filled in by MTurk for each worker. The application uses these to associate sessions and assignments.

2. **Completion Code Instructions**

   At the end of the experiment, the application will display a **completion code** to the participant.

   In your HIT instructions, tell workers to:

   * Copy the completion code shown in the app.
   * Paste it back into the MTurk interface when submitting the HIT.

   This ensures that only workers who finish the experiment get approved.

---

## Step 5: Manage Assignments in the Researcher Dashboard

The Researcher Dashboard includes an **“MTurk Panel”** that lets you manage assignments for your HITs.

1. **Associate a HIT**

   In the MTurk Panel, enter the **HIT ID** associated with your current experiment session. Once linked, the platform will fetch assignment data from MTurk.

2. **View Assignments**

   After association, the panel will show a list of assignments, including status (Submitted, Approved, Rejected, etc.).

3. **Approve / Reject Work**

   You can approve or reject assignments directly from the panel based on:

   * Whether the participant completed the task.
   * Whether the completion code is valid.
   * Any additional quality checks you define.

   These actions are sent back to MTurk via the AWS API.

> ✅ **Suggested workflow:**
>
> 1. Run everything locally with ngrok and MTurk **Sandbox**.
> 2. Confirm that assignments, completion codes, and approvals work as expected.
> 3. For larger studies or longer-running experiments, switch to the **cloud deployment** option.
