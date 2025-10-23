# A Configurable Research Platform for Human-LLM Agent Collaboration

We present a configurable research platform for conducting Human-LLM agent collaboration experiments. The system supports multiple experiment paradigms, including ShapeFactory, DayTrader, EssayRanking, and WordGuessing, along with an Experiment Configuration Language (ECL) for custom experiment design.

## Table of Contents

- [System Requirements](#system-requirements)
- [Installation & Setup](#installation--setup)
- [Running Locally](#running-locally)
- [Automated Setup Issues](#automated-setup-issues)
- [Customization](#customization)
- [Development](#development)

## System Requirements
- **Python**: 3.10 or higher
- **Node.js (for frontend management)**: 20.19.0+ or 22.12.0+
- **PostgreSQL (for database management)**: 13 or higher
- **npm/yarn**: Node.js package manager
- **Git**: For version control (recommended)
- **uv**: Modern Python package manager (recommended)

## Installation & Setup

### 1. Quick Setup

For the fastest setup experience, use our automated setup script:

#### Step 1: Clone this repository

On your local machine, clone this repository using the following command:

```bash
git clone https://github.com/neuhai/human-agent-collab.git
cd human-agent-collab
```

#### Step 2: Create Environment Configuration

##### 1. Create .env file **in the backend** containing the following information:

```bash
DATABASE_URL=postgresql://'username':@localhost:5432/shape_factory_research
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=Database name (default: shape_factory_research)
DATABASE_USER=Your PostgreSQL username
DATABASE_PASSWORD=Your PostgreSQL password  

# OpenAI API Key
OPENAI_API_KEY= Your OpenAI API key for AI functionality

# WebSocket Configuration
WS_PORT=8001

AGENT_LLM_MODE=function
```

**Note**: Please make sure to enter your database name, username, password, and openai api key.

**Important**: If you already have a postgresql database on your local machine, you can use the same username and password.

##### 2. Create .env file **in the vue-app (frontend)** containing the following information:

````bash
VITE_BACKEND_URL=http://localhost:5002
# You can update the backend URL
````

#### Step 3: Run Automated Setup
```bash
# Make the script executable (if not already)
chmod +x setup.sh

# Run the automated setup
./setup.sh
```

The script will automatically:
- Check all prerequisites (Python, Node.js, PostgreSQL)
- Create virtual environment and install Python dependencies
- Set up PostgreSQL database using your configuration
- Initialize database schema
- Install frontend dependencies
- Build the frontend for production
- Generate secure JWT secrets

#### Step 4: Start the Application
```bash
# Terminal 1 - Backend Server
cd backend && python app.py

# Terminal 2 - Frontend Development Server  
cd vue-app && npm run dev
```

**Access Points:**

* **Participant Login**: http://localhost:3000/login

- **Participant Interface**: http://localhost:3000/participant
- **Researcher Dashboard**: http://localhost:3000/researcher
- **API Endpoints**: http://localhost:5002/api/*

---

### 2. Manual Setup (Alternative)

If you prefer manual setup or need to customize the installation:

#### 2.1 Database Setup

##### Install PostgreSQL
- **macOS**: `brew install postgresql`
- **Ubuntu/Debian**: `sudo apt install postgresql postgresql-contrib`
- **Windows**: Download from [postgresql.org](https://www.postgresql.org/download/)

##### Start PostgreSQL Service
```bash
# macOS (with Homebrew)
brew services start postgresql

# Ubuntu/Debian
sudo systemctl start postgresql

# Windows: Start PostgreSQL service from Services panel
```

##### Create Database and User
```bash
# Connect to PostgreSQL as superuser
psql -U postgres

# Create database and user (replace with your desired credentials)
CREATE DATABASE shape_factory_research;
CREATE USER your_username WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE shape_factory_research TO your_username;
\q
```

##### Initialize Database Schema
```bash
# Import the schema (make sure to use the same credentials as above)
psql -U your_username -d shape_factory_research -f backend/database/schema.sql
```

**Important**: Remember the database credentials you create here - you'll need them for your `.env` file in the next step.

#### 2.2 Backend Setup

##### Using uv (Recommended)
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

##### Using pip
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install core dependencies
pip install -r backend/requirements.txt

# Optional: Install analysis dependencies (for data analysis scripts)
pip install -r backend/requirements-analysis.txt
```

##### Environment Configuration

1. At backend, add the following configuration to your `.env` file:

```bash
# Database Configuration
DATABASE_URL=postgresql://your_username:your_password@localhost:5432/shape_factory_research
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=shape_factory_research
DATABASE_USER=your_username
DATABASE_PASSWORD=your_password

# JWT Configuration
JWT_SECRET=your-super-secret-jwt-key-change-in-production

# OpenAI Configuration (for AI agents) - REQUIRED for AI functionality
OPENAI_API_KEY=your_openai_api_key_here

# Server Configuration
FLASK_ENV=development
FLASK_DEBUG=True
```

**Note**: Replace the placeholder values with your actual database credentials and OpenAI API key. Without the `.env` file, the application will not start properly.

#### 2.3 Frontend Setup

At frontend, add the following configuration to your `.env` file:

```bash
VITE_BACKEND_URL=http://localhost:5002
# You can update the backend URL
```

Then, run the following commands:

```bash
# Navigate to Vue app directory
cd vue-app

# Install dependencies
npm install
# or
yarn install
```

## Running Locally

> **Tip**: If you used the automated setup script, you can skip to the "Start the Application" section below.

### Development Mode

#### 1. Start Backend Server
```bash
# From project root
cd backend
python app.py
```
The backend will start on `http://localhost:5002`

#### 2. Start Frontend Development Server
```bash
# From vue-app directory
cd vue-app
npm run dev
# or
yarn dev
```
The frontend will start on `http://localhost:3000`




### Automated Setup Issues

#### Common Problems and Solutions

**1. ".env file not found" Error**
```bash
# Make sure you've created the .env file
cp env.template .env
# Edit the file with your actual values
nano .env
```

**2. "Missing required fields" Error**
- Ensure all required fields are set in your `.env` file:
  - `DATABASE_USER`
  - `DATABASE_PASSWORD` 
  - `DATABASE_NAME`
  - `OPENAI_API_KEY`
- Make sure `OPENAI_API_KEY` is not the placeholder value

**3. PostgreSQL Connection Issues**
```bash
# Check if PostgreSQL is running
brew services list | grep postgresql  # macOS
sudo systemctl status postgresql     # Linux

# Start PostgreSQL if needed
brew services start postgresql       # macOS
sudo systemctl start postgresql      # Linux
```

**4. Permission Denied on setup.sh**
```bash
# Make the script executable
chmod +x setup.sh
```

**5. Python/Node.js Version Issues**
- Ensure you have Python 3.12+ and Node.js 20.19.0+
- Use `python3 --version` and `node --version` to check

**6. Database Already Exists**
- The script will ask if you want to recreate the database
- Choose 'y' to recreate or 'N' to use existing database

### Manual Recovery Steps

If the automated setup fails, you can complete the setup manually:

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install Python dependencies
pip install -r backend/requirements.txt

# 3. Set up database manually
psql -U postgres -c "CREATE DATABASE your_database_name;"
psql -U your_username -d your_database_name -f backend/database/schema.sql

# 4. Install frontend dependencies
cd vue-app && npm install && cd ..

# 5. Build frontend
cd vue-app && npm run build && cd ..
```



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
