# Yale Radiology Policies RAG Application (Engine)

## Project Overview

The Yale Radiology Policies RAG Application is a comprehensive system designed to make Yale Diagnostic Radiology departmental policies accessible and interactive through large language models (LLMs). The system leverages modern retrieval-augmented generation (RAG) techniques to provide accurate policy information to users through natural language interactions or direct API access. It includes components for collecting policies from Yale sources, processing them into a structured database with vector embeddings, and providing interfaces for querying this information. This repository contains the scripts for the core functionalities of the application (a.k.a. engine) - referring to all functionalities apart from the UI. The UI will be developed in a separate repository.

## Modes of Operation (CLI Interface)

The primary interaction with the project's engine functionalities (data collection, database management, server processes) is through the main Command Line Interface (CLI) accessible via `python -m ydrpolicy.main`. The CLI provides the following modes:

### 1. `policy` Mode

Manages the data collection pipeline (finding, downloading, processing policy files) and handles the removal of individual policies from the database.

- **`policy collect-all`**: Runs the full data collection pipeline. It crawls starting points (like the Yale Radiology intranet), downloads potential policy documents/pages, converts them to Markdown/Text, uses an LLM to classify them and extract titles, and saves structured results ( `content.md`, `content.txt`, `img-*.*`) into timestamped folders named `<policy_title>_<timestamp>` within `data/processed/`. This _prepares_ policies but doesn't add them to the database.
- **`policy collect-one --url <URL>`**: Performs the full collection pipeline (download, process, classify, structure files) for a single specified URL, saving the result to `data/processed/` if it's identified as a policy. Does not add to the database.
- **`policy crawl-all`**: Runs only the crawling part - finding, downloading, and saving raw content (Markdown, images) to `data/raw/` and creating `crawled_policies_data.csv`. Does not classify or populate `data/processed/`.
- **`policy scrape-all`**: Runs only the scraping/classification part. It reads `crawled_policies_data.csv`, processes the corresponding raw files from `data/raw/` using an LLM, and creates the structured folders in `data/processed/` for those identified as policies.
- **`policy remove --id <ID>` / `policy remove --title <TITLE>`**: Removes a _single policy_ and its associated data (chunks, images, embeddings) _from the database_. It identifies the policy by its database ID or exact title. Requires confirmation unless `--force` is used. **Note:** This does _not_ delete the corresponding folder from the `data/processed/` filesystem.

### 2. `database` Mode

Manages the PostgreSQL database itself, including schema setup and data ingestion from the processed files.

- **`database init [--no-populate]`**: Initializes a new database environment. It connects to PostgreSQL, creates the database if it doesn't exist, creates the necessary `vector` extension, creates all tables based on `models.py` using SQLAlchemy's `create_all`, and applies search vector triggers. **Crucially**, if `--no-populate` is _not_ used, it then scans the `data/processed/` directory. For any policy folder (`<title>_<timestamp>`) where the `<title>` doesn't already exist in the database's `policies` table, it reads `content.md`, `content.txt`, finds `img-*.*` files, creates the corresponding `Policy`, `Image`, and `PolicyChunk` records, generates embeddings for the chunks (using the configured embedding service, e.g., OpenAI), and inserts everything into the database. This command is safe to re-run; it will only populate _new_ policies found in `data/processed/`.
- **`database remove [--force]`**: Completely **DROPS** the entire application database from the PostgreSQL server, deleting all tables, data, and schema. **This is irreversible.** Requires confirmation unless `--force` is used.

### 3. `mcp` Mode (Placeholder)

Intended for managing the MCP (Model Context Protocol) server, which would provide specialized retrieval tools (RAG, keyword search) for LLMs.

- **`mcp start`**: (Not Implemented) Placeholder command to start the MCP server.

### 4. `agent` Mode (Placeholder)

Intended for interacting with the core chat agent functionality directly (e.g., for testing or specific integrations).

- **`agent chat`**: (Not Implemented) Placeholder command to start an interactive chat session via the CLI.

## System Architecture

```
┌─────────────────────────────────────┐
│                                     │
│  Frontend Service (Next.js)         │
│  [Port: 3000]                       │
│                                     │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│                                     │
│  Backend API (FastAPI)              │
│  [Port: 8000]                       │
│                                     │
│  - Database Models & Migrations     │
│  - Chat Agent API (/api/chat)       │
│  - Policy Management                │
│  - Authentication                   │
│                                     │
└──────────────────┬──────────────────┘
          │                 │
          │                 ▼
          │        ┌─────────────────────┐
          │        │                     │
          │        │  MCP Server         │
          │        │  [Port: 8001]       │
          │        │                     │
          │        │  - RAG Tools        │
          │        │  - Keyword Search   │
          │        │  - Hybrid Search    │
          │        │                     │
          │        └─────────────────────┘
          │
          ▼
┌─────────────────────────────────────┐
│                                     │
│  PostgreSQL + pgvector               │
│  [Port: 5432]                       │
│                                     │
└─────────────────────────────────────┘

     ↑
     │ (Data Pipeline)
     │
┌─────────────────────────────────────┐
│                                     │
│  Data Collection                    │
│  - Yale Intranet Crawler            │
│  - Policy Content Scraper           │
│  - LLM-powered Extractor            │
│                                     │
└─────────────────────────────────────┘
```

## Technology Stack

### Backend

- **FastAPI**: Modern, high-performance web framework for building APIs with Python
- **PostgreSQL + pgvector**: Relational database with vector storage capabilities
- **SQLAlchemy**: ORM for database interactions
- **OpenAI API**: For LLM capabilities (embedding and generation)
- **Google Gemini API**: Alternative LLM provider
- **MCP Protocol**: For tool integration with LLMs
- **Async Programming**: Leveraging Python's asyncio for high concurrency
- **Pydantic**: Data validation and settings management
- **JWT**: For authentication and session management

### Data Collection and Processing

- **Selenium**: Web automation for crawling complex sites
- **Requests**: HTTP library for simpler web requests
- **PDF Processing**: Libraries for extracting text from PDFs
- **Markdown Processing**: Tools for converting and standardizing content
