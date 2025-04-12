# Commit History

## commit 12 (4/12/2025 - 15:02)

Added the base scripts for chat and fastapi but no tests ran yet.

## commit 11 (4/12/2025 - 14:33)

Created files for incorporating the chat agent.

## commit 10 (4/12/2025 - 13:00)

Removed archive folder from the ydrpolicy 

## commit 9 (4/11/2025 - 09:16)

Debugged the MCP server setup and made sure it works fine with claude.

## commit 8 (4/11/2025 - 00:48)

Wrote the primary version of the mcp server

## commit 7 (4/9/2025 - 21:38)

Optimized the database functionalities and testing"

## commit 6 (3/30/2025 - 07:38)

Debugged the base path in the config files.

## commit 5 (3/30/2025 - 06:25)

- Ensured all DB operations match the new data collection scripts.
- Ensured all test scripts for DB operations are up to date.
- Added the Image table.
- Updated and shortened the README.md file.

## commit 4 (3/30/2025 - 03:31)

- Naming convention of files saved by crawler and scraper are now clearer.
- The saved processed markdown files are now not parsed by the scraper LLM, but directly copied from the raw files.
- The associated imaging with the markdown files are also saved in the processed scraped folder.
- There now exists a collect_one and a collect_all functionality for handing addition of single-url and multi-url policies, respectively.
- The logging mechanism is now more error-proof. 

## commit 3 (3/29/2025 - 17:57)

- Debugged some of the current scripts.
- Moved the mcp folder inside the backend.
- Ensured the migrations are saved in the data folder.

## commit 2 (3/26/2025 - 01:36)

- Updated project specification to be more detailed.
- Updated the project database code base to match the new project specifications.
- Added the primary codes for handling new policy addition through the database, backend, and the FastAPI servers, though these need to be completed and verified later.
- Split the database test scripts into smaller scripts.
- Added text-based search in addition to the RAG-search and hybrid-search to the datbase operations.
- All database scripts and functionalities are yet to be tested. 

## commit 1 (3/25/2025 - 12:33)

- Added commit.py file. 
  - It should handle commit levelling appropriately!

## commit 0 (3/25/2025 - 12:25)

- Started commit logging in `commit_log.md`.
- At this commit:
  - Data Collection works smoothly.
  - The Database scripts have been added but not tested.
