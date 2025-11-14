# Cloud Deployment for MTurk Integration

This guide provides step-by-step instructions for deploying the human–agent collaboration platform to a cloud provider using a **Docker offload** strategy. This setup is recommended for a **scalable and robust environment** when running experiments with Amazon Mechanical Turk (MTurk).

> 💡 **Tip:** We strongly recommend starting with the **MTurk Sandbox** and a test deployment before launching any production HITs.

---

## Prerequisites

Before you begin, make sure you have the following:

* **Docker Desktop**
  Required to build and push the application images.
  Download: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

* **Container Registry**
  A container registry to host your Docker images, such as:

  * [Google Container Registry / Artifact Registry](https://cloud.google.com/container-registry)
  * [Azure Container Registry](https://azure.microsoft.com/en-us/services/container-registry/)

* **Cloud Provider Account**
  An account with a cloud provider that supports Docker Compose or multi-container deployments, such as:

  * [Google Cloud](https://cloud.google.com/)
  * [Microsoft Azure](https://azure.microsoft.com/)

* **AWS Account**
  An active AWS account is required for MTurk.

* **MTurk Requester Account**
  You will need an MTurk Requester account to create and manage HITs:
  [https://requester.mturk.com](https://requester.mturk.com)

* **AWS Credentials with MTurk Permissions**
  An **Access Key ID** and **Secret Access Key** that have permission to interact with MTurk (either sandbox or production).

> ⚠️ **Security note:** Treat all API keys and secrets as sensitive information. Do **not** commit them to Git or share them in screenshots.

---

## Step 1: Build and Push Docker Images

1. **Clone the Repository**

   ```bash
   git clone https://github.com/neuhai/human-agent-collab.git
   cd human-agent-collab
   ```

2. **Log In to Your Container Registry**

   ```bash
   docker login <your_registry_url>
   ```

   Examples:

   * GCP: `docker login gcr.io`
   * Azure: `docker login <your_registry_name>.azurecr.io`

3. **Build and Push the Images**

   Use the provided production Docker Compose file to build and push the images. Replace `<your_registry_username>` (or registry path) as needed.

   ```bash
   docker-compose -f deployment/docker-compose.prod.yml build
   docker-compose -f deployment/docker-compose.prod.yml push
   ```

   > ℹ️ You may need to update the `image` fields in `deployment/docker-compose.prod.yml` so they include your registry and namespace, for example:
   >
   > ```yaml
   > image: <your_registry_url>/<your_registry_username>/human-agent-backend:latest
   > ```

---

## Step 2: Deploy with Docker Compose in the Cloud

We recommend using a cloud provider that supports Docker Compose-based multi-container deployments (“Docker offload”). This allows you to keep using the existing `docker-compose` configuration.

### Option A: Google Cloud Run

Google Cloud Run supports deploying multi-container applications. Follow the official documentation to deploy from a `docker-compose.yml` file or equivalent configuration:

* [https://cloud.google.com/run/docs/deploying-multi-container](https://cloud.google.com/run/docs/deploying-multi-container)

You will typically:

1. Create a new Cloud Run service (or services) using the images you pushed.
2. Configure the exposed port to match the backend container (e.g., 8000 or 8080).
3. Set environment variables in the service configuration (see Step 3).
4. Enable HTTPS and obtain the public URL.

### Option B: Azure Container Apps

Azure Container Apps also supports deployments from Docker Compose or multi-container setups. See:

* [https://learn.microsoft.com/en-us/azure/container-apps/docker-compose-cli-dev-env](https://learn.microsoft.com/en-us/azure/container-apps/docker-compose-cli-dev-env)

Typical steps:

1. Create an Azure Container Apps environment.
2. Deploy your `docker-compose` definition and map services to Container Apps.
3. Configure environment variables for the backend app.
4. Expose the HTTP endpoint and note down the public URL.

> 💡 If you are new to these platforms, we recommend starting with **a single backend + frontend** configuration, verify that the app loads, and then connect MTurk.

---

## Step 3: Configure Environment Variables

In your cloud provider’s console or deployment configuration, set the following **environment variables for the backend service** (and any other service that needs them):

* `POSTGRES_PASSWORD`
  A strong password for your PostgreSQL database.

* `OPENAI_API_KEY`
  Your OpenAI API key.

* `JWT_SECRET`
  A secure random string used to sign JSON Web Tokens.

* `AWS_ACCESS_KEY_ID`
  Your AWS access key ID for MTurk.

* `AWS_SECRET_ACCESS_KEY`
  Your AWS secret access key for MTurk.

* `MTURK_ENVIRONMENT`

  * Use `sandbox` for testing with MTurk Sandbox.
  * Use `production` for live HITs on the real MTurk marketplace.

> ⚠️ **Important:**
>
> * Only use `MTURK_ENVIRONMENT=production` after you have fully tested the workflow in `sandbox`.
> * Store keys only in the cloud provider’s secret manager / environment variable system, not in the code repository.

If your setup uses an **external managed database** (e.g., Cloud SQL, Azure Database for PostgreSQL), also configure:

* `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_DB`

and make sure your cloud services can reach the database.

---

## Step 4: Configure the MTurk HIT

When creating a HIT (either in **Sandbox** or **Production**), you must embed the public URL of your deployed application and pass MTurk identifiers to the app.

1. **HIT Description and External Link**

   In the HIT design / HTML section, include a link like this:

   ```html
   <p>Please click the link below to participate in the experiment:</p>
   <p>
     <a href="https://<your_public_url>/login?workerId=${workerId}&assignmentId=${assignmentId}&hitId=${hitId}"
        target="_blank">
       Start Experiment
     </a>
   </p>
   ```

   Replace `<your_public_url>` with the HTTPS URL given by your cloud provider (Cloud Run / Container Apps, etc.).

   The platform will automatically replace `${workerId}`, `${assignmentId}`, and `${hitId}` with the correct values for each worker. The application uses these parameters to link each session to a specific MTurk assignment.

2. **Completion Code Workflow**

   At the end of the experiment, the application will display a **completion code** to the participant.

   In your HIT instructions, clearly state that:

   * Participants must **copy the completion code** from the web app.
   * They must **paste it back into the MTurk interface** and submit the HIT.
   * Only submissions with a valid completion code will be approved.

   This ensures that only participants who actually complete the task are credited.

---

## Step 5: Manage Assignments in the Researcher Dashboard

The platform includes a **Researcher Dashboard** with an **“MTurk Panel”** to help you manage assignments associated with your experiments.

1. **Associate a HIT**

   In the MTurk Panel, enter the **HIT ID** corresponding to your deployed experiment session. Once associated, the platform will fetch and display assignments for that HIT.

2. **View Assignments**

   After the HIT ID is linked, the panel shows a list of all assignments with their status (e.g., Submitted, Approved, Rejected).

3. **Approve or Reject Work**

   You can approve or reject assignments directly from the MTurk Panel based on:

   * Whether the participant completed the task.
   * Whether the completion code is valid.
   * Any additional quality checks you have defined.

   Changes made here are propagated back to MTurk through the AWS API.

> ✅ Recommended workflow:
>
> 1. Deploy to cloud and verify locally.
> 2. Run a **small pilot** on MTurk Sandbox.
> 3. Check data and assignment handling in the MTurk Panel.
> 4. Only then switch `MTURK_ENVIRONMENT` to `production` and launch live HITs.

