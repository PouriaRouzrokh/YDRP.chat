# Yale Radiology Policies RAG Application (Engine) V0.2.0

## Project Overview

The Yale Radiology Policies RAG Application is a comprehensive system designed to make Yale Diagnostic Radiology departmental policies accessible and interactive through large language models (LLMs). The system leverages modern retrieval-augmented generation (RAG) techniques to provide accurate policy information to users through natural language interactions or direct API access.

It includes components for:

1.  **Data Collection:** Crawling Yale web sources, downloading documents, extracting text and images.
2.  **Processing & Classification:** Converting content to Markdown/Text, using LLMs to identify actual policies and extract titles.
3.  **Database Storage:** Storing policy metadata, text content, image references, user information, chat history (including archived status), and vector embeddings (using `pgvector`) in a PostgreSQL database.
4.  **Retrieval & Generation:** Providing tools (via MCP) for semantic search (RAG) over the policy data.
5.  **Agent Interaction:** Exposing a chat agent (via API or terminal) that uses the retrieval tools to answer user questions based on the indexed policies, with support for persistent chat history, user authentication, and chat management (rename, archive).

This repository contains the scripts for the core engine functionalities – everything apart from the user interface. The UI will be developed in a separate repository:

https://github.com/PouriaRouzrokh/YDRP_UI

## Technology Stack

### Backend

- **Python**: Core programming language (3.10+)
- **FastAPI**: Modern, high-performance web framework for building the API.
- **Uvicorn**: ASGI server to run the FastAPI application.
- **PostgreSQL + pgvector**: Relational database with vector storage capabilities for RAG.
- **SQLAlchemy**: ORM for database interactions (async via `asyncpg` driver).
- **Alembic** (Optional but Recommended): For database schema migrations.
- **OpenAI API**: For LLM generation (chat agent) and text embeddings.
- **Agents SDK (`openai/agentic-sdk-python`)**: Framework for building the agent logic and tool usage.
- **MCP (`modelcontextprotocol/mcp-python`)**: Protocol and library for exposing tools (RAG functions) to the agent via HTTP/SSE or stdio.
- **Asyncio**: For asynchronous programming, enabling efficient I/O operations.
- **Pydantic**: Data validation, settings management, and API schema definition.
- **JWT (`python-jose`)**: For creating and validating JSON Web Tokens for authentication.
- **Password Hashing (`passlib[bcrypt]`)**: For securely storing user passwords.
- **Typer**: CLI framework for `main.py`.
- **HTTPX**: Async HTTP client (used internally by SDKs).
- **Ruff**: Linter and formatter.
- **(Optional) Mistral API**: Used in data collection for potential OCR tasks.

### Data Collection and Processing

- **Selenium**: Web automation for crawling complex, Javascript-heavy sites.
- **Requests**: HTTP library for simpler web requests and document downloads.
- **PDF Processing Libraries**: Tools used internally by data collection scripts.
- **Markdown Processing**: Libraries like `markdownify` for converting HTML to Markdown.
- **Pandas**: Used for managing crawled data logs.

## System Architecture

```
┌─────────────────────────────────────┐
│                                     │
│ Frontend Service (e.g., Next.js)    │
│ [Typically Port: 3000]              │
│                                     │
└──────────────────┬──────────────────┘
                   │ (HTTP API Calls + SSE)
                   ▼
┌─────────────────────────────────────┐    ┌──────────────────────┐
│                                     │    │                      │
│ Backend API (FastAPI/Uvicorn)       │───>│ MCP Server           │
│ [Default Port: 8000]                │<───│ [Default Port: 8001] │
│                                     │    │                      │
│ - Auth Endpoints (/auth/token)      │    │ - RAG Tools          │
│ - Chat Endpoints (/chat/...)        │    │ - find_similar_chunks│
│ - Stream, List, History, Rename,    │    │ - get_policy_from_ID │
│   Archive, Unarchive, Archive All   │    │                      │
│ - Chat Service & History Mgmt       │    └──────────────────────┘
│ - Policy Agent Logic (Agents SDK)   │
│ - Database Repositories             │
│ - JWT Authentication                │
│                                     │
└──────────────────┬──────────────────┘
                   │ (SQLAlchemy Async + Migrations)
                   ▼
┌─────────────────────────────────────┐
│                                     │
│ PostgreSQL + pgvector Database      │
│ [Default Port: 5432]                │
│ (Stores Policies, Chunks, Users,    │
│ Chats [w/ archive status], Messages)│
└─────────────────────────────────────┘
                   ↑
                   │ (Data Pipeline via CLI)
                   │
┌─────────────────────────────────────┐
│                                     │
│ Data Collection & Processing        │
│ (Via main.py policy &               │
│ main.py database --populate)        │
│ - Crawler (Selenium/Requests)       │
│ - Scraper/Classifier (LLM)          │
│ - DB Populator (Embedding, Insert)  │
│ - User Seeding (from JSON)          │
│                                     │
└─────────────────────────────────────┘
```

## Setup and Installation

1.  **Prerequisites:**

    - Python 3.10+
    - PostgreSQL server (version compatible with `pgvector`) with the `pgvector` extension enabled within the target database.
    - `uv` (Python package manager): Recommended. Install via `pip install uv` or see official `uv` docs. (Or use `pip`).

2.  **Clone Repository:**

    ```bash
    git clone <repository_url>
    cd ydrp_engine
    ```

3.  **Create Virtual Environment (Recommended):**

    ```bash
    # Using uv
    uv venv .venv
    source .venv/bin/activate # Linux/macOS
    # .venv\Scripts\activate # Windows

    # Or using standard venv
    # python -m venv .venv
    # source .venv/bin/activate # Linux/macOS
    # .venv\Scripts\activate # Windows
    ```

4.  **Install Dependencies:**

    ```bash
    # Using uv (reads pyproject.toml)
    uv sync

    # Or using pip (if you have requirements.txt)
    # pip install -r requirements.txt
    ```

    _Note: Ensure your dependency file includes `fastapi[all]`, `openai`, `agents-sdk`, `mcp[cli]`, `sqlalchemy[asyncpg]`, `psycopg` (or `psycopg2-binary`), `pgvector-sqlalchemy`, `typer`, `python-dotenv`, `pandas`, `selenium`, `markdownify`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`, `ruff`, `alembic` (if using migrations)._

5.  **Configuration (`.env` file):**

    - Create a `.env` file in the project root (you can copy `.env.example` if provided).
    - Edit `.env` and provide **required** values:
      - `DATABASE_URL`: Your PostgreSQL connection string (e.g., `postgresql+asyncpg://pouria:@localhost:5432/ydrpolicy`). The user needs permissions to create databases and extensions.
      - `OPENAI_API_KEY`: Your OpenAI API key (used for embeddings and agent generation).
      - `JWT_SECRET`: **Crucially, change this to a strong, unique secret key.** Generate one using `python -c 'import secrets; print(secrets.token_hex(32))'`.
    - Optional:
      - `MISTRAL_API_KEY`: If used for OCR in data collection.
      - Adjust `JWT_EXPIRATION` (in minutes, default 30) in `config.py` if needed.

6.  **Create User Seed File (Required for Auth):**

    - Create an `auth` directory in the project root: `mkdir auth`
    - Create a file named `auth/users.json`.
    - Populate it with initial user(s) in JSON list format. **Use strong passwords!**
      ```json
      [
        {
          "email": "admin@example.com",
          "full_name": "Administrator",
          "password": "YOUR_SECURE_ADMIN_PASSWORD",
          "is_admin": true
        },
        {
          "email": "testuser@example.com",
          "full_name": "Test User",
          "password": "YOUR_SECURE_USER_PASSWORD",
          "is_admin": false
        }
      ]
      ```
    - _(Security Note: Storing plain passwords in JSON is insecure for production. This is for initial setup/development)._

7.  **Initialize Database:**
    - Ensure your PostgreSQL server is running.
    - **Using Alembic (Recommended):**
      - Initialize Alembic if you haven't: `alembic init alembic` (configure `alembic.ini` with your `DATABASE_URL`).
      - Generate the initial migration based on your models: `alembic revision --autogenerate -m "Initial schema"`
      - Apply the migration: `alembic upgrade head`
    - **OR Using `init_db` (for simpler setups/testing):**
      - Run the database initialization command. This creates the DB (if needed), enables `pgvector`, creates tables based on current models, and **seeds users** from `users.json`.
      ```bash
      # Create schema and seed users, but don't populate policies yet
      uv run main.py database --init --no-populate
      ```
      - **Note:** If you later change models, `init_db` will _not_ automatically migrate the schema. You would need to `--drop` and `--init` again, losing data, or manually alter the tables, or switch to Alembic.

## CLI Commands Reference (`main.py`)

Interact with the engine via `uv run main.py <command> [options]`.

_(Run `uv run main.py --help` for a full list)_

### 1. `database` Command

Manages the database schema, user seeding, and policy data population.

- **`uv run main.py database --init [--no-populate]`**

  - **Purpose:** Initializes the database structure (creating DB, extensions, tables based on **current** models) and seeds users from `auth/users.json`. Optionally populates policies. **WARNING:** Does not perform schema migrations on existing databases. Use Alembic for managing schema changes on existing databases.
  - **Actions:**
    - Connects to PostgreSQL, creates the database (if needed) and `vector` extension.
    - Creates all tables defined in `models.py` (if they don't exist).
    - Applies full-text search triggers.
    - Reads `auth/users.json`, hashes passwords, and inserts any users not already present in the DB based on email.
    - If `--no-populate` is **NOT** used (or if `--populate` is explicitly used later), it proceeds to populate policies (see below).
  - **Use Case:** First-time setup, resetting the schema (requires `--drop` first if DB exists), adding predefined users.

- **`uv run main.py database --populate`**

  - **Purpose:** Populates the database with new or updated policy data found in the processed data directory (`data/processed/scraped_policies/`). Implicitly runs `--init` actions if needed but focuses on data loading.
  - **Actions:**
    - Ensures DB schema exists (like `--init`, but safe to run if already initialized).
    - Scans `data/processed/scraped_policies/` for `<title>_<timestamp>` folders.
    - Compares found policies (by title and timestamp) with existing DB records.
    - Deletes older versions from the DB if a newer timestamped folder is found.
    - For new policies or newer versions: reads content, chunks text, generates embeddings (via OpenAI), and inserts `Policy`, `Image`, `PolicyChunk` records into the DB.
  - **Use Case:** Adding policies to the agent's knowledge base after they have been collected and processed by the `policy` command.

- **`uv run main.py database --drop [--force]`**

  - **Purpose:** **Permanently deletes** the entire application database.
  - **Actions:** Connects to PostgreSQL and executes `DROP DATABASE`.
  - **Options:** `--force` skips confirmation.
  - **Use Case:** Complete reset during development/testing. **Irreversible.**

- **Common Options:**
  - `--db-url <URL>`: Override the `DATABASE_URL` from `.env`.
  - `--no-populate`: (With `--init`) Explicitly skip the policy population step, only create schema and seed users.

### 2. `policy` Command

Manages the data collection/processing pipeline (filesystem operations) and database _removal_.

- **`uv run main.py policy --collect-all`**

  - **Purpose:** Runs the full data finding, downloading, processing, and classification pipeline. Prepares policy data folders on the filesystem. **Does NOT populate DB.**
  - **Actions:** Crawls sources, downloads/converts content (saving raw versions), classifies using LLM, extracts titles, creates structured folders (`<title>_<timestamp>`) in `data/processed/scraped_policies/`.
  - **Use Case:** Refreshing policy data from source. Needs `database --populate` afterwards.

- **`uv run main.py policy --collect-one --url <URL>`**

  - **Purpose:** Processes a single URL through the full pipeline. Prepares folder if identified as policy. **Does NOT populate DB.**
  - **Use Case:** Adding/testing a single known policy URL. Needs `database --populate` afterwards.

- **`uv run main.py policy --crawl-all`**

  - **Purpose:** Runs only the crawling stage (finding/downloading raw content).
  - **Actions:** Saves raw markdown/images, creates `crawled_policies_data.csv`. Does not classify or create processed folders.
  - **Use Case:** Refreshing raw data only.

- **`uv run main.py policy --scrape-all`**

  - **Purpose:** Runs only the classification/processing stage on existing raw data.
  - **Actions:** Reads CSV, analyzes raw files via LLM, creates structured processed folders. **Does NOT populate DB.**
  - **Use Case:** Classifying previously crawled data.

- **`uv run main.py policy --remove-id <ID> [--force]`** or **`uv run main.py policy --remove-title <TITLE> [--force]`**

  - **Purpose:** Removes a policy and its associated data (chunks, images) **from the database ONLY**.
  - **Actions:** Finds policy by ID or title in DB and deletes it. Logs the action. **Does NOT delete filesystem folders.**
  - **Use Case:** Removing outdated/incorrect policies from the agent's knowledge.

- **Common Options:**
  - `--reset-crawl`: (With `--collect-all` / `--crawl-all`) Clears crawler state.
  - `--resume-crawl`: (With `--collect-all` / `--crawl-all`) Resumes crawl from saved state.
  - `--force`: (With `--remove-*`) Skips confirmation prompt.
  - `--db-url <URL>`: (With `--remove-*`) Specifies DB URL for removal.

### 3. `mcp` Command

Manages the Model Context Protocol (MCP) server, which provides tools to the agent.

- **`uv run main.py mcp [--transport http]`** (or default)

  - **Purpose:** Starts MCP server using HTTP/SSE transport.
  - **Actions:** Runs Uvicorn on default port 8001, serving the MCP tools (`find_similar_chunks`, `get_policy_from_ID`) over SSE on the `/sse` endpoint.
  - **Use Case:** **Required** when running the agent in API mode (`main.py agent`). Run in a separate terminal.

- **`uv run main.py mcp --transport stdio [--no-log]`**

  - **Purpose:** Starts MCP server using standard input/output.
  - **Use Case:** Direct integration with stdio clients (less common).

- **Common Options:**
  - `--host <HOST>`: Set listen host for HTTP mode (default `0.0.0.0`).
  - `--port <PORT>`: Set listen port for HTTP mode (default `8001`).
  - `--no-log`: (With `stdio`) Disable logging to avoid protocol interference.

### 4. `agent` Command

Runs the chat agent application.

- **`uv run main.py agent`**

  - **Purpose:** Starts the main FastAPI web server for the agent API.
  - **Actions:** Runs Uvicorn on default port 8000, serving the API endpoints (including `/auth/token`, `/chat`, `/chat/stream`). Connects to the MCP server (if not disabled) when handling requests.
  - **Use Case:** Standard mode for running the backend service for the frontend UI. Requires MCP server running separately if tools are needed.

- **`uv run main.py agent --terminal`**

  - **Purpose:** Runs an interactive chat session directly in the terminal. Uses temporary session history.
  - **Actions:** Initializes agent, connects to MCP server (if not disabled), and provides a command-line chat prompt.
  - **Use Case:** Testing agent responses, instructions, and tool usage directly. Requires MCP server running separately if tools are needed.

- **Common Options:**
  - `--no-mcp`: Disable connection to and usage of the MCP server and its tools.
  - `--host <HOST>`: (API Mode) Set listen host for FastAPI (default `0.0.0.0`).
  - `--port <PORT>`: (API Mode) Set listen port for FastAPI (default `8000`).
  - `--workers <NUM>`: (API Mode) Set number of Uvicorn workers (default `1`).
  - `--log-level <LEVEL>`: Override default log level (e.g., `debug`).
  - `--trace`: Enable trace uploading to OpenAI platform (requires compatible SDK setup).

### Common Workflow Example

1.  **(First time) Create `auth/users.json` with initial users/passwords.**
2.  **(First time or after schema change) Init DB & Seed Users:**
    - Using Alembic: `alembic upgrade head` (assuming initialized and migrations generated)
    - Using `init_db`: `uv run main.py database --init --no-populate`
3.  **(Optional) Collect & Process Policy Data:** `uv run main.py policy --collect-all`
4.  **(Optional) Populate Policies into DB:** `uv run main.py database --populate`
5.  **Start MCP Server:** `uv run main.py mcp --transport http` (in Terminal 1)
6.  **Start Agent API Server:** `uv run main.py agent` (in Terminal 2)
7.  **Interact:** Use the frontend UI (pointing to `http://localhost:8000`) or the API docs (`http://localhost:8000/docs`).

## API Endpoints Summary

_(This is a high-level overview. See the Frontend Developer Guide or API docs `/docs` for details)._

- **`POST /auth/token`**: Login, get JWT.
- **`GET /chat`**: List user chats (active or archived via `?archived=true`).
- **`POST /chat/stream`**: Start/continue chat, stream responses.
- **`GET /chat/{chat_id}/messages`**: Get history for a chat.
- **`PATCH /chat/{chat_id}/rename`**: Rename a chat.
- **`PATCH /chat/{chat_id}/archive`**: Archive a chat.
- **`PATCH /chat/{chat_id}/unarchive`**: Unarchive a chat.
- **`POST /chat/archive-all`**: Archive all user's active chats.
- **`GET /auth/users/me`**: Get authenticated user details.

## Developer

Pouria Rouzrokh, MD, MPH, MHPE
Diagnostic Radiology Resident
Department of Radiolohy, Yale New Haven School of Medicine, Yale University, CT, USA
Homepage: https://pouria.ai

## Copyright

This package is the intellectual property of the Yale New Haven Medical School, Departments of Radiology.
