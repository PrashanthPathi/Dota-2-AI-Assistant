# How to Run and Deploy from an External System

This guide explains how to set up, run locally, and deploy the **DOTA 2 AI Assistant (RealmMaster)** from any external workstation (macOS, Linux, or Windows WSL) using your GitHub repository.

---

## 1. Prerequisites on the External Machine

Ensure you have the following installed on your system:
- **Git**: `git --version`
- **Python 3.11+**: `python3 --version`
- **uv** (recommended Python package manager):
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Google Cloud SDK (`gcloud`)**: [Installation Guide](https://cloud.google.com/sdk/docs/install)

---

## 2. Clone the Repository

```bash
git clone https://github.com/PrashanthPathi/Dota-2-AI-Assistant.git
cd Dota-2-AI-Assistant
```

---

## 3. Authenticate with Google Cloud

The agent utilizes Vertex AI (Gemini model & Memory Bank), Cloud Firestore, and Cloud Storage. Authenticate your external machine with Google Cloud:

```bash
# 1. Authenticate user account and generate application default credentials
gcloud auth login
gcloud auth application-default login

# 2. Set your active Google Cloud project ID
gcloud config set project <YOUR_GCP_PROJECT_ID>
```

> [!NOTE]
> If setting up in a new personal Google Cloud project, ensure the required APIs are enabled:
> ```bash
> gcloud services enable aiplatform.googleapis.com firestore.googleapis.com storage.googleapis.com
> ```

---

## 4. Option A: Run the Local Agent Development Playground

The ADK Web Playground is the fastest way to interact with and test the agent directly in development:

```bash
# Install agent dependencies
uv sync

# Launch the ADK development environment
uv run adk web . --port 8000 --reload_agents
```

Open **`http://localhost:8000`** in your browser.

*(If you have a Vertex AI Memory Bank, you can also pass `--memory_service_uri=agentengine://<YOUR_MEMORY_BANK_ID>` to test cross-session memory).*

---

## 5. Option B: Run the Custom Chat Web Frontend

The custom frontend provides the branded dark-theme UI with character dialogue turns, example prompt chips, and A2UI card rendering.

### Step 5.1: Install Frontend Dependencies
```bash
cd frontend

python3 -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 5.2: Configure Environment Variables & Run
Set your deployed Agent Engine resource name and start the proxy server:

```bash
export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_ID>/locations/<REGION>/reasoningEngines/<ENGINE_ID>"
export AGENT_DIRECTORY="app"
export PORT=8080

python main.py
```

Open **`http://localhost:8080`** in your browser to interact with the full web UI.

---

## 6. Full Deployment to Production (Google Cloud)

### 6.1. Deploy Agent to Vertex AI Agent Platform
Install the `agents-cli` tool and deploy your reasoning engine:

```bash
# Install agents-cli
uv tool install google-agents-cli

# Optional: pass your Google Maps API key if utilizing geocoding tools
agents-cli deploy --update-env-vars "GOOGLE_MAPS_API_KEY=<YOUR_MAPS_KEY>"
```
*Take note of the Reasoning Engine resource name output by this command (`projects/.../locations/.../reasoningEngines/...`).*

### 6.2. Grant Required IAM Roles to the Agent Runtime Service Account
```bash
# Firestore access
gcloud projects add-iam-policy-binding <YOUR_PROJECT_ID> \
  --member="serviceAccount:service-<PROJECT_NUMBER>@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

# Cloud Storage bucket access for generated images
gcloud storage buckets add-iam-policy-binding gs://<YOUR_BUCKET_NAME> \
  --member="serviceAccount:service-<PROJECT_NUMBER>@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

### 6.3. Deploy Frontend to Cloud Run
Deploy the FastAPI proxy and chat interface container:

```bash
cd frontend

gcloud run deploy dota-ai-frontend \
  --source . \
  --region <YOUR_REGION> \
  --allow-unauthenticated \
  --set-env-vars "AGENT_ENGINE_RESOURCE_NAME=projects/<PROJECT_ID>/locations/<REGION>/reasoningEngines/<ENGINE_ID>,AGENT_DIRECTORY=app"
```

Grant Cloud Run's service account permission to invoke Vertex AI Agent Engine:

```bash
gcloud projects add-iam-policy-binding <YOUR_PROJECT_ID> \
  --member="serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

Your service will output a public HTTPS URL serving the full application.
