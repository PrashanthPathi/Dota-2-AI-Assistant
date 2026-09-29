# RealmMaster · DOTA 2 & Tabletop AI Companion

RealmMaster is an agent-first tabletop RPG companion and game-mastering assistant built with Google's **Agent Development Kit (ADK)** and powered by **Gemini 2.5 Flash** (`gemini-2.5-flash`). It helps players and Game Masters manage campaigns, roll polyhedral dice, query live monster statistics, track character inventories, explore equipment/spells, generate magical item illustrations, locate tabletop hobby venues, and run simulations inside a secure code sandbox.

---

## 🛠️ Implemented Capabilities & Google Cloud Services

The agent logic in `app/agent.py` implements and wires the following Google Cloud and external integrations:

### 1. Cross-Session Long-Term Memory (Memory Bank)
- **Service**: Vertex AI Agent Engine Memory Bank (`PreloadMemoryTool` & `generate_memories_callback`).
- **Functionality**: Automatically extracts facts, character profile details, campaign choices, and preferences across sessions and preloads relevant memories at the beginning of each conversation turn.

### 2. Structured Storage & Inventory (Cloud Firestore)
- **Service**: Google Cloud Firestore (`equipment_and_spells` and `character_inventories` collections).
- **Tools**:
  - `list_items(item_type)`: Browses weapons, armor, potions, and spell scrolls stored in Firestore.
  - `search_item(name)`: Searches the equipment database by name or ID.
  - `create_or_update_item(...)`: Dynamically writes new custom magical items or spells to the database.
  - `manage_inventory(character_name, action, ...)`: Updates character inventories, tracks item quantities, and handles gold balance additions/deductions.

### 3. Image Generation & Media Asset Storage
- **Models & Storage**: `gemini-3.1-flash-lite-image` on Vertex AI + Google Cloud Storage.
- **Tool**:
  - `generate_item_image(prompt, item_name)`: Creates illustrations of weapons, potions, or loot, saves them as session artifacts, and uploads them to a Cloud Storage bucket with public URLs.

### 4. Live Bestiary Lookup
- **Integration**: D&D 5e SRD Public API.
- **Tool**:
  - `search_bestiary(monster_name)`: Fetches live stats, Armor Class, Hit Points, Challenge Rating, speeds, and legendary actions for creatures and monsters.

### 5. Tabletop Dice Roller
- **Tool**:
  - `roll_dice(dice)`: Parses polyhedral dice notation (e.g., `1d20+5`, `8d6`, `2d4-1`), computes individual roll breakdowns, and calculates final totals.

### 6. Geospatial & Hobby Store Discovery (Google Maps APIs)
- **Services**: Google Maps Geocoding API & Google Places API (New).
- **Tools**:
  - `geocode_address(address)`: Converts addresses and city names into latitude/longitude coordinates.
  - `find_nearby_places(place_type, latitude, longitude)`: Finds local gaming venues, hobby shops, cafes, and bookstores within a designated radius.

### 7. Isolated Code Execution (Code Sandbox)
- **Service**: Vertex AI Agent Engine Sandbox (`AgentEngineSandboxCodeExecutor`).
- **Capability**: Safely executes Python code blocks to calculate dice probability distributions, simulate combat turns, or analyze math.

### 8. Agent-First UI (A2UI)
- **Specification**: A2UI Schema v0.8 Basic Catalog (`a2ui.schema.manager.A2uiSchemaManager`).
- **Callback**: Custom `after_model_callback` (`a2ui_callback`) that translates structured JSON responses into interactive visual cards, rows, columns, badges, and inline images in the web frontend.

---

## 📋 Status of Planned Capabilities

- [x] **Polyhedral Dice Roller** (`roll_dice`) — *Implemented*
- [x] **Character Inventory & Gold Tracking** (`manage_inventory` on Firestore) — *Implemented*
- [x] **Item & Spell Catalog** (`list_items`, `search_item`, `create_or_update_item` on Firestore) — *Implemented*
- [x] **Live 5e Bestiary Lookup** (`search_bestiary`) — *Implemented*
- [x] **Item Artwork Generation** (`generate_item_image` via Imagen + Cloud Storage) — *Implemented*
- [x] **Real-World Game Store Finder** (`geocode_address`, `find_nearby_places` via Google Maps) — *Implemented*
- [x] **Code Sandbox Calculations** (`AgentEngineSandboxCodeExecutor`) — *Implemented*
- [x] **Long-Term Memory Bank** (`PreloadMemoryTool` + `add_session_to_memory`) — *Implemented*
- [x] **A2UI Rich Card Rendering** (`a2ui_callback`) — *Implemented*
- [ ] **Full Automated Initiative Turn Tracker** — *Planned, not yet implemented*
- [ ] **Multi-Character Party Campaign Sheet Sync** — *Planned, not yet implemented*

---

## 🏗️ Project Structure

```
realm-master/
├── app/
│   ├── agent.py               # Core ADK agent, tools, callbacks, and sandbox executor
│   ├── a2ui_utils.py          # A2UI response formatter and callback hook
│   ├── fast_api_app.py        # FastAPI server backend
│   └── app_utils/             # A2A and Reasoning Engine adapters
├── frontend/                  # Custom chat web frontend
│   ├── main.py                # FastAPI reverse proxy communicating over A2A protocol
│   ├── static/
│   │   └── index.html         # Dialogue layout, prompt chips, and A2UI card renderer
│   ├── Dockerfile             # Production container definition
│   └── requirements.txt       # Frontend dependencies
├── agents-cli-manifest.yaml   # Agent specification manifest
├── deployment_metadata.json   # Deployment tracking metadata
└── pyproject.toml             # Python package dependencies
```

---

## 🚀 Running Locally

### Prerequisites
- Python 3.11+
- `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Google Cloud SDK (`gcloud`) authenticated with your Google Cloud project

### 1. Authenticate with Google Cloud
Ensure your local environment has credentials for Vertex AI, Firestore, and Cloud Storage:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project <YOUR_PROJECT_ID>
```

### 2. Run the Agent Locally (ADK Web Playground)
To test the agent with live memory services:

```bash
uv run adk web . --port 8000 --reload_agents --memory_service_uri=agentengine://<YOUR_MEMORY_BANK_ID>
```

### 3. Run the Custom Chat Frontend
The frontend connects to the deployed Agent Platform runtime over the A2A protocol:

```bash
cd frontend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_ID>/locations/<REGION>/reasoningEngines/<ENGINE_ID>"
export AGENT_DIRECTORY="app"
export PORT=8080

python main.py
```

Open a browser to your configured local port (e.g. `http://localhost:8080`) to interact with the agent.

---

## 🚢 Deployment

### Deploy Agent to Agent Platform
Deploy the reasoning engine directly using `agents-cli`:

```bash
agents-cli deploy --update-env-vars "GOOGLE_MAPS_API_KEY=<YOUR_KEY>"
```

### Deploy Frontend to Cloud Run
Build and run the frontend proxy container on Cloud Run:

```bash
cd frontend
gcloud run deploy realm-master-frontend \
  --source . \
  --region <YOUR_REGION> \
  --allow-unauthenticated \
  --set-env-vars "AGENT_ENGINE_RESOURCE_NAME=projects/<PROJECT_ID>/locations/<REGION>/reasoningEngines/<ENGINE_ID>,AGENT_DIRECTORY=app"
```

Grant the Cloud Run service account permission to call the agent:

```bash
gcloud projects add-iam-policy-binding <YOUR_PROJECT_ID> \
  --member="serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```
