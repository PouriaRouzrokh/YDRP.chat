# YDRP Monorepo

This repository houses both the YDRP Engine and YDRP UI in a single Git repository at the project root.

## Layout
- ydrp_engine/: Backend Engine
- ydrp_ui/: Frontend UI
- commit_log.md: Consolidated human-written change log for Engine and UI
- run.sh: Top-level utility script used during development

## Using commit_log.md
- The consolidated log merges the previous Engine/UI logs.
- Headings include only date/time, not numeric commit counters.
- To add a new note:
  - Edit commit_log.md
  - Add a dated section under the appropriate area
  - Keep bullets short and clear

Example entry:


## Viewing run.sh history
- See history for run.sh:
commit ba6a5dfe19bb130e8ea38b22c21fd13d84a06486
Author: Pouria Rouzrokh <po.rouzrokh@gmail.com>
Date:   Mon Aug 11 17:37:35 2025 -0400

    chore(repo): add root project files
- Show a specific revision of run.sh:

- Diff run.sh between two commits:


## Contributing
- Work directly under ydrp_engine/ and ydrp_ui/ and commit to the root repository.
- Standard Git branch/PR workflows apply.
