# A Configurable Research Platform for Human-LLM Agent Collaboration

This repository present of a configurable research platform for conducting Human-LLM agent collaboration experiments from the paper **Through the Lens of Human-Human Collaboration: A Configurable Research Platform for Exploring Human-Agent Collaboration**.

The system supports multiple experiment paradigms, including ShapeFactory, DayTrader, EssayRanking, and WordGuessing, along with an Experiment Configuration Language (ECL) for custom experiment design.

![image](https://github.com/neuhai/human-agent-collab/blob/main/preview.gif)

## Table of Contents

- [Quickest Start for Users](#-quickest-start-for-users)
- [Developer Guide: Running from Source](#developer-guide-running-from-source)
- [Customization](#customization)
- [Development](#development)
- [Trouble Shooting](#trouble-shooting)
- [Citation](#citation)

## Quickest Start for Users

This method is for users who just want to run the application. It uses a one-line command to automatically set up all necessary configuration files.

**Prerequisites:**
- Docker Desktop installed.
- A command-line terminal (like Terminal on macOS/Linux or PowerShell/WSL on Windows).

### One-Line Setup Command

Copy and paste the command for your operating system into a terminal and press Enter.

**For macOS or Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/neuhai/human-agent-collab/main/quick-start.sh | bash
```

**For Windows (in PowerShell):**
```powershell
irm https://raw.githubusercontent.com/neuhai/human-agent-collab/main/quick-start.ps1 | iex
```

This command will automatically set up all necessary files and guide you through the next steps.

### Managing the Application

After the initial setup, you can easily start, stop, and manage the application. You can use either the command line or the Docker Desktop graphical interface.

---
#### **Option 1: Using the Command Line**

Navigate into the `human-agent-collab-app` directory in your terminal and use the following commands.

**To Start the Application:**
If the application is stopped, restart it with:
```bash
docker compose up -d
```
*(Note: On older systems, you might need to use `docker-compose` instead of `docker compose`)*

**To Stop the Application:**
To stop all running services, use:
```bash
docker compose down
```
This command will stop and remove the containers, but **your database data will be preserved**.

**To Update to the Latest Version:**
To pull the newest versions of the application images from the registry, run:
```bash
docker compose pull
```
After updating, you can start the application again with `docker compose up -d`.

---
#### **Option 2: Using Docker Desktop (GUI)**

If you prefer a graphical interface, you can manage the application directly from Docker Desktop.

1.  **Open Docker Desktop.**
2.  Go to the **"Containers"** section in the left sidebar.
3.  You will see a container group (also called a "Compose stack") named **`human-agent-collab-app`**. This group contains the three services: `frontend`, `backend`, and `postgres`.

**To Stop the Application:**
- Click the **stop button** (■) next to the `human-agent-collab-app` group.

**To Start the Application:**
- Click the **start button** (▶) next to the `human-agent-collab-app` group.

**To Delete the Application:**
- Click the **delete button** (🗑️) to stop and remove the containers. This is equivalent to the `docker compose down` command and **will not delete your data**.

---

## Developer Guide: Running from Source

This section is for developers who want to contribute to the project.

### **Option 1: Using VS Code Dev Containers (Recommended)**

This is the best way to ensure a fully consistent development environment. It uses the [VS Code Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) to automatically build and configure your entire development environment inside Docker.

**Prerequisites:**
- **VS Code** with the **Dev Containers** extension installed.
- **Docker Desktop** installed and running.

**Getting Started:**
1.  **Clone the repository**: `git clone https://github.com/neuhai/human-agent-collab.git`
2.  **Open the folder in VS Code**.
3.  A pop-up will appear in the bottom-right corner saying: "Folder contains a Dev Container configuration file. Reopen in Container?".
4.  Click **"Reopen in Container"**.

That's it! VS Code will now automatically build the dev images, start all services (`backend`, `frontend`, `postgres`), install the recommended extensions inside the container, and connect your VS Code window to the `backend` service. Your terminal, debugger, and all tools will be running inside the fully configured container.

---
### **Option 2: Manual Docker Compose Workflow**

If you are not using VS Code or prefer a manual setup, you can follow the steps below. The only prerequisite is to have **Git** and **Docker Desktop** installed.

#### **Development Mode**

This is the primary way to work on the project. It uses development containers with features like hot-reloading, where your local source code is directly mounted into the containers.

#### 1. Clone the Repository
```bash
git clone https://github.com/neuhai/human-agent-collab.git
cd human-agent-collab
```

#### 2. Create Environment File
Copy the development environment template.
```bash
cp .env.dev.template .env
```
Edit the `.env` file and set your `POSTGRES_PASSWORD` and `OPENAI_API_KEY`.

#### 3. Build and Run
Use `docker-compose` to build and start the services in the background. This command will build the `dev` images.
```bash
docker-compose -f docker-compose.dev.yml up --build -d
```

#### 4. Access the Services
- **Frontend (with hot-reload)**: **http://localhost:3000**
- **Backend API**: **http://localhost:5002**

For more detailed commands (viewing logs, accessing container shells, etc.), please refer to the `README.docker-dev.md` file.

---

#### **Production Mode (from Source)**

This method is for developers who need to build and test the production images locally from the source code.

#### 1. Clone the Repository
If you haven't already, clone the repository.
```bash
git clone https://github.com/neuhai/human-agent-collab.git
cd human-agent-collab
```

#### 2. Create Environment File
Copy the production environment template. This file will hold your secret credentials.
```bash
cp .env.prod.template .env.prod
```
Now, edit the `.env.prod` file and set the required values.

#### 3. Build and Run
Use the automated deployment script to build and start all services using the `prod` Dockerfiles.
```bash
# On Linux/macOS (you may need to make it executable first)
chmod +x deploy-prod.sh
./deploy-prod.sh

# On Windows (using Git Bash or WSL)
./deploy-prod.sh
```

#### 4. Access the Application
Once the script finishes, the application will be available at:
- **URL**: **http://localhost**



## Customization

### Custom Agents

The platform supports AI agents powered by OpenAI's GPT models. To create custom agents with specific behaviors, you'll need to write custom prompts that define how the agent should behave in your experiment.

#### Agent Prompt Customization

**Location**: Agent prompts are stored in `backend/prompts/`
- `shapefactory_agent_prompt.txt` - Default ShapeFactory agent behavior
- `daytrader_agent_prompt.txt` - DayTrader experiment agent behavior
- `essayranking_agent_prompt.txt` - EssayRanking experiment agent behavior
- `wordguessing_guesser_prompt.txt` - WordGuessing guesser agent behavior
- `wordguessing_hinter_prompt.txt` - WordGuessing hinter agent behavior

#### Creating Custom Agent Prompts

1. **Create a new prompt file**:
```bash
# Navigate to prompts directory
cd backend/prompts

# Create your custom prompt file
touch my_custom_agent_prompt.txt
```
2. **Integrate with your experiment**:
- Reference your custom prompt in your ECL configuration
- Update the agent initialization code to use your prompt file
- Test thoroughly to ensure the agent behaves as intended

**Important**: Custom prompts require careful design to ensure agents behave appropriately and don't break experiment integrity. Consider testing with human participants before running full experiments.

### Customization with ECL

The Experiment Configuration Language (ECL) allows you to define custom experimental paradigms declaratively without modifying the core codebase.

#### Sample ECL File

A sample ECL configuration file is provided in the project root:
- **File**: `sample_ecl.yaml`

You can use this file as a template to create your own custom experiments. The sample includes examples of all major ECL features.

#### Creating Custom Experiments

##### 1. Define Your ECL Configuration

Create a new `.yaml` file in the project root using the provided sample:

```bash
# Copy the sample ECL file to create your own experiment
cp sample_ecl.yaml my_experiment.yaml

# Edit the new file with your experiment logic
nano my_experiment.yaml
# or use your preferred text editor
```

##### 2. Key ECL Components

**Types**: Define data types with constraints
```yaml
types:
  Currency: { kind: scalar, base: number, min: 0, max: 1000 }
  Status: { kind: enum, values: [active, inactive, completed] }
  Player: { kind: ref, of: Participant }
```

**Objects**: Define experiment entities
```yaml
objects:
  Participant:
    key: id
    attrs:
      id: { type: ID, required: true }
      money: { type: Currency, default: 100 }
      status: { type: Status, default: "active" }
```

**Actions**: Define what participants can do
```yaml
actions:
  TransferMoney:
    input:
      recipient: { type: Player, required: true }
      amount: { type: Currency, required: true }
    preconditions:
      - "Participant.money(actor.id) >= input.amount"
    effects:
      - dec: "Participant.money(actor.id)"
        by: "input.amount"
      - inc: "Participant.money(input.recipient)"
        by: "input.amount"
```

**Views**: Define the participant interface
```yaml
views:
  modules:
    - id: wallet
      label: "My Wallet"
      bindings:
        - { label: "Balance", path: "Participant.money" }
    
    - id: transfer
      label: "Transfer Money"
      bindings:
        - label: "Recipient"
          control: "select"
          options: "Participant.id"
          bind_to: "$local.recipient"
        - label: "Amount"
          control: "number"
          min: 0
          max: "Participant.money(actor.id)"
          bind_to: "$local.amount"
        - label: "Transfer"
          action: "TransferMoney"
          inputs:
            - { name: "recipient", from: "$local.recipient" }
            - { name: "amount", from: "$local.amount" }
```

##### 3. Advanced ECL Features

**Conditional Visibility**
```yaml
- id: admin_panel
  label: "Admin Panel"
  visible_if: "Participant.role(actor.id) == 'admin'"
```

**Communication Levels**
```yaml
- id: chat
  label: "Chat"
  communication_level: "group_chat"  # or "direct_message", "broadcast"
```

**Complex Expressions**
```yaml
effects:
  - compute: "total_contributions"
    expr: "sum(filter(Contribution, it.type == 'group').amount)"
  - set: "Session.total_contrib"
    to: "total_contributions"
```

#### Using Custom ECL Experiments

##### 1. Upload ECL Configuration

Via Researcher Dashboard:
1. Go to `http://localhost:3000/researcher`
2. Navigate to "Experiment Selection"
3. Upload your `.yaml` file

##### 2. ECL Validation

The system automatically validates ECL configurations for:
- Syntax correctness
- Type consistency
- Reference integrity
- Action preconditions/effects
- View bindings



## Development

### Project Structure

```
ShapeFactory_MCP/
├── backend/                 # Flask backend
│   ├── app.py              # Main Flask application
│   ├── game_engine.py      # Core game logic
│   ├── agent_runner.py     # AI agent management
│   ├── ecl_parser.py       # ECL configuration parser
│   ├── ecl_action_engine.py # ECL action execution
│   ├── ecl_ui_generator.py # ECL UI generation
│   ├── database/           # Database schemas and migrations
│   └── prompts/           # AI agent prompts
├── vue-app/               # Vue.js frontend
│   ├── src/
│   │   ├── components/    # Vue components
│   │   ├── views/        # Page views
│   │   ├── stores/       # State management
│   │   └── services/     # API services
│   └── dist/             # Built frontend
├── Analysis/             # Data analysis scripts
└── sample_ecl.yaml      # Example ECL configuration
```

### Adding New Experiment Types

#### 1. Backend Integration

Create a new game engine class:

```python
# backend/my_experiment_engine.py
from game_engine import GameEngine

class MyExperimentEngine(GameEngine):
    def __init__(self, session_id, config):
        super().__init__(session_id, config)
        self.experiment_type = "my_experiment"
    
    def initialize_session(self):
        # Initialize your experiment
        pass
    
    def process_participant_action(self, participant_id, action_data):
        # Handle participant actions
        pass
```

#### 2. Register in Game Engine Factory

```python
# backend/game_engine_factory.py
from my_experiment_engine import MyExperimentEngine

class GameEngineFactory:
    @staticmethod
    def create_engine(experiment_type, session_id, config):
        if experiment_type == "my_experiment":
            return MyExperimentEngine(session_id, config)
        # ... other engines
```

#### 3. Frontend Components

Create Vue components for your experiment:

```vue
<!-- vue-app/src/components/MyExperimentInterface.vue -->
<template>
  <div class="my-experiment">
    <!-- Your experiment UI -->
  </div>
</template>

<script>
export default {
  name: 'MyExperimentInterface',
  // Component logic
}
</script>
```

### Database Migrations

For schema changes, create migration scripts:

```python
# backend/migrate.py
def run_migration():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            ALTER TABLE participants 
            ADD COLUMN new_field VARCHAR(50);
        """)
        conn.commit()
```

### Trouble Shooting

If you encounter issues, please refer to the `README.docker-dev.md` for detailed troubleshooting steps related to the Docker environment. Common issues often involve port conflicts or incorrect environment variable settings.

## Citation
```
@article{yao2025through,
  title={Through the Lens of Human-Human Collaboration: A Configurable Research Platform for Exploring Human-Agent Collaboration},
  author={Yao, Bingsheng and Chen, Jiaju and Chen, Chaoran and Wang, April and Li, Toby Jia-jun and Wang, Dakuo},
  journal={arXiv preprint arXiv:2509.18008},
  year={2025}
}
```
