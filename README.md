# YDRP.chat

This repository is the monorepo for the YDRP.chat website — a policy chatbot for the Yale Department of Diagnostic Radiology. It lets staff search and access official departmental policies via a modern chat interface. Under the hood, a retrieval‑augmented generation (RAG) engine indexes policy documents and serves answers with accurate citations through an API; the Next.js UI provides a secure, responsive front‑end.

## Layout
- `ydrp_engine/`: Backend Engine (Python/FastAPI, MCP tools, DB + embeddings)
- `ydrp_ui/`: Frontend UI (Next.js/TypeScript, streaming chat interface)
- `run.sh`: Top‑level helper for starting/stopping services locally

Detailed documentation for each module is available in their respective README files under `ydrp_engine/` and `ydrp_ui/`.

## Working with run.sh
The `run.sh` script manages local development via tmux sessions. It can start the MCP server, the Agent API, the UI, and Cloudflare tunnels.

Commands
- `./run.sh start-all` — Start MCP, Agent API, UI, and Cloudflare tunnel (kills existing sessions first)
- `./run.sh start <name>` — Start one: `mcp | agent | ui | tunnel | tunnel-api`
- `./run.sh kill-all` — Kill all managed tmux sessions
- `./run.sh kill <name>` — Kill one session: `mcp | agent | ui | tunnel | tunnel-api`
- `./run.sh status` — Show tmux session status
- `./run.sh help` — Show usage and environment help

Environment variables (optional)
- Backend/MCP
  - `MCP_HOST` (default `0.0.0.0`), `MCP_PORT` (default `8001`)
  - `API_HOST` (default `0.0.0.0`), `API_PORT` (default `8000`)
- UI
  - `NEXT_PORT` (default `3000`)
  - `NEXT_PUBLIC_API_URL` (default `http://localhost:${API_PORT}`)
  - `NEXT_PUBLIC_ADMIN_MODE` (default `false`)
  - `NEXT_PUBLIC_TYPING_INDICATOR_DELAY_MS` (default `3000`)
- Cloudflare (optional)
  - `CLOUDFLARED_BIN` (binary name/path, default `cloudflared`)
  - `CF_TARGET` (default `http://localhost:${NEXT_PORT}`)
  - `CF_HOSTNAME` (default `ydrp.chat`)
  - `CF_TUNNEL_ID` or `CF_TUNNEL_NAME` (run a named tunnel if set)
  - `CF_CONFIG` (path to cloudflared config for named tunnels)
  - `CF_API_HOSTNAME` (default `api.ydrp.chat`), `CF_API_TARGET` (default `http://localhost:${API_PORT}`)
  - `CF_AUTOCONFIG_DNS` (default `true`, adds/updates DNS routes for hostnames when using a named tunnel)

Notes
- Named tunnel: If `CF_TUNNEL_ID` or `CF_TUNNEL_NAME` is provided, `run.sh` runs that tunnel and can auto‑configure DNS routes for `CF_HOSTNAME` and `CF_API_HOSTNAME` when `CF_AUTOCONFIG_DNS=true`.
- Secondary API tunnel: `./run.sh start tunnel-api` starts a second hostname → API mapping, only used when not using a named tunnel.
- UI → API URL: By default the UI calls the backend at `http://localhost:${API_PORT}`. Override with `NEXT_PUBLIC_API_URL` (e.g., a public API hostname).

Examples
```bash
# Start everything
./run.sh start-all

# Start single components
./run.sh start mcp
./run.sh start agent
./run.sh start ui
./run.sh start tunnel
./run.sh start tunnel-api

# Status and cleanup
./run.sh status
./run.sh kill ui
./run.sh kill-all
```

## Documentation
- Backend details: see `ydrp_engine/README.md`
- Frontend details: see `ydrp_ui/README.md`

## Contact
Pouria Rouzrokh, MD, MPH, MHPE — Diagnostic Radiology Resident
- Email: pouria.rouzrokh@yale.edu
- Homepage: https://pouriarouzrokh.com

Bardia (Bardīa) Khosravi, MD, MPH, MHPE — Diagnostic Radiology Resident
- Email: bardia.khosravi@yale.edu
- Homepage: https://brdkhsrv.com
