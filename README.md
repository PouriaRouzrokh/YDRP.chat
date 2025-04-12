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

## High-Level Understanding of Chat Functionality

Here's how the different components work together to provide the chat functionality, focusing on the primary API flow with history:

### Entry Point (main.py -> Uvicorn -> api_main.py):

- When you run uv run main.py agent, it eventually starts the Uvicorn server.
- Uvicorn loads the FastAPI application defined in api_main.py.
- api_main.py sets up the overall FastAPI app, including CORS, lifespan events (startup/shutdown), and includes routers.

### API Request (routers/chat.py):

- The UI (or your testing tool) sends a POST request to /chat/stream.
- The request body matches the ChatRequest schema (schemas/chat.py), containing user_id, the message, and optionally a chat_id.
- FastAPI validates the request.
- The stream_chat function in routers/chat.py is called.
- It uses dependency injection (Depends) to get an instance of ChatService.

### Service Layer Orchestration (services/chat_service.py):

- The ChatService instance's process_user_message_stream method takes over. This is the core orchestrator.
- Database Interaction (Setup): It asynchronously opens a database session (get_async_session) and creates instances of ChatRepository and MessageRepository.

### History/Chat Management:

- If a chat_id is provided, it uses ChatRepository to find the chat and verify it belongs to the user_id. If found, it uses MessageRepository to load the recent message history for that chat.
- If no chat_id is provided, it uses ChatRepository to create a new chat session for the user_id, generating a title based on the first message. The new chat_id is stored.
- It immediately streams back a chat_info chunk containing the chat_id (either existing or new).
- Save User Message: It uses MessageRepository to save the current user message to the database, linked to the correct chat_id.
- Agent Input Formatting: It calls \_format_history_for_agent to convert the loaded database messages into a single string format suitable for the LLM, prepending it to the current user message. It applies basic length limits.
- Agent Initialization: It ensures the Agent instance (defined in agent/policy_agent.py) is initialized via get_agent(). This agent has the specific instructions, the configured OpenAI model (config.OPENAI.MODEL), and knows about the MCP server connection (managed by agent/mcp_connection.py).
- Run Agent: It calls Runner.run_streamed(agent, formatted_input). This starts the agent execution loop provided by the OpenAI Agents SDK.

### Agent Execution (SDK Runner & agent/policy_agent.py):

- The Runner sends the formatted input (history + message) to the configured LLM (e.g., gpt-4-turbo).
- The LLM processes the input based on the agent's instructions (in policy_agent.py).
- Tool Decision: Based on the instructions ("Use find_similar_chunks first..."), the LLM might decide to call a tool. It generates a tool call request.

### MCP Interaction:

- The Runner detects the tool call request.
- It looks at the agent.mcp_servers list (which contains the instance managed by agent/mcp_connection.py).
- It calls call_tool(tool_name, tool_args) on the MCPServerSse client instance.
- The MCPServerSse client sends the request over HTTP to your running MCP server process (mcp/server.py).

### MCP Server (mcp/server.py):

- Receives the request.
- Executes the corresponding tool function (find_similar_chunks or get_policy_from_ID).
- These tool functions interact with the database (PolicyRepository) to perform searches or lookups.
- The tool function returns its result to the MCP server process.
- The MCP server process sends the result back over HTTP to the MCPServerSse client.

### Agent Execution (cont.):

- The Runner receives the tool result from the MCPServerSse client.
- It sends the tool result back to the LLM for processing.
- The LLM uses the tool result to formulate its final text response.
- The Runner streams the LLM's response (text deltas) and information about tool calls/outputs back to the ChatService.

### Service Layer (Streaming & Saving):

- process_user_message_stream receives events from the Runner.
- It converts these events into StreamChunk objects (text deltas, tool call/output info, status).
- It yields these chunks to the router using the async generator pattern.
- It accumulates the full text of the assistant's response.
- After the stream ends: If the agent run was successful, it uses MessageRepository to save the accumulated assistant response text and any ToolUsage records (linking tool calls/outputs to the assistant message) to the database.

### API Response (routers/chat.py):

- The stream_chat function receives each yielded StreamChunk from the service.
- It formats the chunk as a Server-Sent Event (SSE) string (data: <json>\n\n).
- The StreamingResponse sends these SSE events back to the client/UI.

### Important Functions/Concepts:

- ChatService.process_user_message_stream: The main orchestrator coordinating DB interaction, agent execution, and streaming.
- create_policy_agent (agent/policy_agent.py): Defines the agent's "personality," instructions, model, and connection to tools (via MCP).
- Runner.run_streamed (SDK): Executes the agent, handles the LLM calls, tool calls, and provides the event stream.
- Repositories (ChatRepository, MessageRepository, PolicyRepository): Encapsulate all database logic, keeping the service layer cleaner.
- History Management: Loading past messages, formatting them for the LLM context, and saving new messages are crucial for conversation flow.
- Streaming (AsyncGenerator, StreamChunk, SSE): Enables real-time feedback to the user as the agent thinks and responds.
- MCP (mcp/server.py, agent/mcp_connection.py): Provides the mechanism for the agent to use external tools (your RAG functions).

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
