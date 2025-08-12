# YDRP Monorepo Commit Log

This file consolidates commit logs from the Engine and UI sub-projects.

### 8/12/2025 - 21:45

- Backend (DB population): Now prefers `data/import.csv` for URL/origin metadata with fallback to legacy `data/PDF/import.csv`. Logs which path is used. File updated: `ydrpolicy/backend/database/init_db.py`.
- UI (Chat): Increased default/unfocused visibility of the chat input border while keeping focused state intact. File updated: `ydrp_ui/src/components/chat/chat-input.tsx`.
- Data handling (local ops, not tracked by git due to `.gitignore`):
  - Copied PDFs from `temp/` and `temp1/` into `ydrp_engine/data/PDF/` and generated `import.csv` with appropriate URLs (`policies & SOPs`, `trainee-resources`, `resident-resources`).
  - Moved `import.csv` to `ydrp_engine/data/import.csv` per new loader behavior; normalized all CSV filenames to include `.pdf`.
  - Archive of PDF files completed as of Aug 11, 2025.

### 8/12/2025 - 12:00

- Switched primary PDF text extraction to PyMuPDF to preserve hyperlinks; added PyPDF fallback.
- Implemented `extract_pdf_markdown_with_links` in `ydrpolicy/data_collection/processors/pdf_processor.py` and refactored callers to reuse it.
- Updated:
  - `pdf_processor.pdf_file_to_markdown`
  - `document_processor.convert_pdf_to_markdown`
  - `ingest_local_files._write_processed_txt`
- Added `pymupdf` to dependency list and installed via `uv add pymupdf`.
- Result: TXT/MD outputs now include clickable links formatted as `[text](URL)` while preserving non-linked text.

### 8/11/2025 - 20:00

- Local-only ingestion overhaul finalized; removed crawl/scrape flows.
- PyPDF is the sole PDF processor; removed all Mistral API usage.
- New ingestion CLI supports single file and CSV modes with overwrite logic.
- Simplified data layout to `data/PDF/` and `data/TXT/` (txt only).
- DB population reads `TXT/*.txt` and maps metadata from `PDF/import.csv`.
- Agent prompt updated to: output HTML, hide titles/origin by default, return one reference link, and name files only when downloads are requested.
- MCP `find_similar_chunks` tool returns `policy_url` and `origin_type` for internal use.
- Chat streaming: backend adds HTML formatting fallback and debug prints; emits `html_chunk`/`html` structures.
- UI: render sanitized HTML, enable list styling, and add visual spacing between streamed chunks.
- Fixed CSV appending for import list and cleaned old data folders.
- Chat rendering refined for agent HTML output:
  - Sanitize while preserving class and data attributes used by streamed chunks.
  - Render sanitized HTML directly inside `div.chat-html`.
  - Tailwind/typography list styles enabled; bullets and spacing visible.
  - Added spacing between streamed chunks using `.html-chunk-sep` and `[data-chunk="1"]`.

### 8/09/2025 - 12:44  

- Renamed CLI flags for policy commands for consistency:
  - `--collect-all` → `--collect-all-urls`, `--collect-one` → `--collect-one-url`
  - `--crawl-all` → `--crawl-all-urls`, added `--crawl-one-url`
  - `--scrape-all` → `--scrape-all-urls`
  - Split `--ingest-pdfs` into process-only: `--ingest-all-pdfs`, `--ingest-one-pdf`
- Separated processing from DB population:
  - New process-only local PDF module `ydrpolicy/data_collection/ingest_local_pdfs.py`
  - Renamed URLs collector to `ydrpolicy/data_collection/collect_policy_urls.py`
  - `database --populate` now loads from BOTH `processed/scraped_policies/` and `processed/local_policies/`
- Removed old redundant local-PDF DB ingestion path from `init_db.py`
- Added `LOCAL_POLICIES_DIR` and `SOURCE_POLICIES_DIR` to data collection config
- Updated `README.md` with new commands and flows; adjusted examples and module names
- Verified end-to-end:
  - Dropped and re-initialized DB (users re-seeded)
  - Processed 35 local PDFs; populated DB with 35 policies and embeddings

### 8/08/2025 - 18:10

- Made user email handling case-insensitive for authentication while keeping password verification case-sensitive.
- Normalized emails to lowercase during user seeding to avoid case-variant duplicates and ensure consistent lookups.
- Re-initialized the database without policy population to seed users from `auth/users.json`.

### 8/08/2025 - 17:45

- Added local PDF ingestion pipeline and CLI (`policy --ingest-pdfs`) with options for `--pdfs-dir`, `--rebuild-db`, and `--global-link`.
- Moved processors to `ydrpolicy/data_collection/processors` (shared by crawl and local); updated imports across the codebase.
- Implemented OCR attempt via Mistral with fallback to PyPDF for local files; ensured processed outputs are saved under `data/processed/local_policies/` and appended to `processed_policies_log.csv`.
- Preserved users on database rebuild; cleaned processed folders and log when requested.
- Updated agent system prompt to cite titles and include a global link for local policies.
- Updated `README.md` with comprehensive CLI instructions (including uv and new commands).
- Created `AI_Docs/checkpoint_2/signout-checkpoint_2.md` and referenced it in checkpoint_1 sign-out.
- Started commit logging in `commit_log.md`.
- At this commit:
  - Data Collection works smoothly.
  - The Database scripts have been added but not tested.

### 4/23/2025 - 05:30

deployed on claudflare

### 4/22/2025 - 05:26

changed the database settings to server side

### 4/22/2025 - 04:09

Tested server git connection

### 4/21/2025 - 22:32

Updated system prompt

### 4/21/2025 - 20:54

Removed data and users from git.
Debugged handling of duplicated errors during initalization of the database.

### 4/16/2025 - 01:35

Updated the readme file.

### 4/15/2025 - 17:59

Applied black to all files.

### 4/15/2025 - 17:59

Updated collected_scripts.md

### 4/15/2025 - 17:58

Added rename and archive mechanisms.
Updated readme and frontend guidelines.
Copied the system_prompt to a separate file and improved it.

### 4/14/2025 - 15:40

Added for for_frontend_dev.md

### 4/14/2025 - 14:48

updated readme.md

### 4/14/2025 - 14:44

Updated the readme.md
Added a for_frontend_dev.md
Applied black to all scripts.

### 4/14/2025 - 14:35

Added authentication mechanism.

### 4/14/2025 - 13:27

Added get apis for chats and messages.

### 4/14/2025 - 03:09

Ensured the agent is working fine in api mode.

### 4/14/2025 - 02:18

Debugged running the agent sdk with mcp servers in the http mode. 
All scripts now work fine in the terminal mode. FastAPI mode remains untested.

### 4/13/2025 - 09:36

- Ensured the agent runs fine in the terminal mode.
- Reformatted all codes using black.

### 4/13/2025 - 00:29

Applied black to certain files

### 4/13/2025 - 00:10

- Debugged the logging issues.
- Switched from litellm to openai in pdf processing
- added back the remove-policy functionality to main.py

### 4/12/2025 - 20:34

Removed the code for removing rich handler from mcp server.

### 4/12/2025 - 20:30

Debugged the logging mechanism for the data collection scripts

### 4/12/2025 - 17:13

Switched to default logging through Python. Added no logging option to main.py

### 4/12/2025 - 16:28

Improved the logging mechanism.

### 4/12/2025 - 15:47

Made sure that the we are using the OpenAI agentic SDK runner functionalities to handle chat history

### 4/12/2025 - 15:22

Updated the README.md to add "High-Level Understanding of Chat Functionality"

### 4/12/2025 - 15:02

Added the base scripts for chat and fastapi but no tests ran yet.

### 4/12/2025 - 14:33

Created files for incorporating the chat agent.

### 4/12/2025 - 13:00

Removed archive folder from the ydrpolicy 

### 4/11/2025 - 09:16

Debugged the MCP server setup and made sure it works fine with claude.

### 4/11/2025 - 00:48

Wrote the primary version of the mcp server

### 4/9/2025 - 21:38

Optimized the database functionalities and testing"

### 3/30/2025 - 07:38

Debugged the base path in the config files.

### 3/30/2025 - 06:25

- Ensured all DB operations match the new data collection scripts.
- Ensured all test scripts for DB operations are up to date.
- Added the Image table.
- Updated and shortened the README.md file.

### 3/30/2025 - 03:31

- Naming convention of files saved by crawler and scraper are now clearer.
- The saved processed markdown files are now not parsed by the scraper LLM, but directly copied from the raw files.
- The associated imaging with the markdown files are also saved in the processed scraped folder.
- There now exists a collect_one and a collect_all functionality for handing addition of single-url and multi-url policies, respectively.
- The logging mechanism is now more error-proof. 

### 3/29/2025 - 17:57

- Debugged some of the current scripts.
- Moved the mcp folder inside the backend.
- Ensured the migrations are saved in the data folder.

### 3/26/2025 - 01:36

- Updated project specification to be more detailed.
- Updated the project database code base to match the new project specifications.
- Added the primary codes for handling new policy addition through the database, backend, and the FastAPI servers, though these need to be completed and verified later.
- Split the database test scripts into smaller scripts.
- Added text-based search in addition to the RAG-search and hybrid-search to the datbase operations.
- All database scripts and functionalities are yet to be tested. 

### 3/25/2025 - 12:33

- Added commit.py file. 
  - It should handle commit levelling appropriately!

