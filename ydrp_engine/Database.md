### YDR Policy RAG – Database Details (Local Dev Instance)

This manual documents how to operate and inspect the PostgreSQL instance used by this project on this machine.

- Database: `ydrpolicy`
- User: `pr555` (local trust auth; no password required on localhost)
- Host/Port: `127.0.0.1:5432` (also reachable via `localhost:5432`)
- PostgreSQL binaries: `/home1/pr555/pgsql/bin`
- Data directory (PGDATA): `/home1/pr555/pgsql/data`
- Server log: `/home1/pr555/pgsql/data/server.log`
- PostgreSQL version (psql): 12.1

If you want shorter commands, consider exporting this to your shell session:

```bash
export PATH="/home1/pr555/pgsql/bin:$PATH"
export PGHOST=127.0.0.1
export PGPORT=5432
```

### 1) Start/Stop/Restart/Status/Logs

- Start (listen on 127.0.0.1:5432):
```bash
/home1/pr555/pgsql/bin/pg_ctl -D /home1/pr555/pgsql/data \
  -l /home1/pr555/pgsql/data/server.log \
  -o "-h 127.0.0.1 -p 5432" start
```

- Stop (fast):
```bash
/home1/pr555/pgsql/bin/pg_ctl -D /home1/pr555/pgsql/data stop -m fast
```

- Restart:
```bash
/home1/pr555/pgsql/bin/pg_ctl -D /home1/pr555/pgsql/data restart \
  -o "-h 127.0.0.1 -p 5432"
```

- Status:
```bash
/home1/pr555/pgsql/bin/pg_ctl -D /home1/pr555/pgsql/data status || true
/home1/pr555/pgsql/bin/pg_isready -h 127.0.0.1 -p 5432
```

- Tail logs:
```bash
tail -f /home1/pr555/pgsql/data/server.log
```

### 2) Connect with psql

- Connect to `ydrpolicy` as `pr555`:
```bash
/home1/pr555/pgsql/bin/psql -h 127.0.0.1 -p 5432 -U pr555 -d ydrpolicy
```

- One-off SQL:
```bash
/home1/pr555/pgsql/bin/psql -h 127.0.0.1 -p 5432 -d ydrpolicy -c "SELECT now();"
```

- Quick sanity check:
```bash
/home1/pr555/pgsql/bin/psql -h 127.0.0.1 -p 5432 -d ydrpolicy -Atqc "SELECT current_user, current_database();"
```

### 3) Schema overview (ORM tables)

The app defines these main tables (from SQLAlchemy models):

- `users`
- `policies`
- `policy_chunks`
- `images`
- `chats`
- `messages`
- `tool_usage`
- `policy_updates`

There are triggers maintaining full-text search vectors on `policies` and `policy_chunks` and vector indexes on `policy_chunks.embedding` (requires the `vector` extension if installed).

### 4) Discovering schema and metadata in psql

Run these inside psql (`\` commands are psql meta-commands):

- List databases: `\l`
- Connect to DB: `\c ydrpolicy`
- List tables: `\dt`
- Describe a table (columns, indexes, triggers): `\d policies` or `\d+ policies`
- List indexes: `\di`
- Show search_path and current user: `SHOW search_path; SELECT current_user;`

### 5) Common data queries (read-only)

- Count rows:
```sql
SELECT COUNT(*) FROM policies;
SELECT COUNT(*) FROM policy_chunks;
```

- Sample few rows:
```sql
SELECT id, title, created_at FROM policies ORDER BY id LIMIT 5;
SELECT id, policy_id, chunk_index, left(content, 120) AS snippet FROM policy_chunks ORDER BY id LIMIT 5;
```

- Find by id:
```sql
SELECT * FROM policies WHERE id = 1;
```

### 6) Common write operations (use with care)

Note: Foreign keys exist between `policies` → `policy_chunks`/`images`, `users` → `chats` → `messages` → `tool_usage`. Deleting a parent may cascade depending on each FK's `ondelete`.

- Insert a user:
```sql
INSERT INTO users (email, password_hash, full_name, is_admin)
VALUES ('user@example.com', 'REPLACE_WITH_HASH', 'Test User', false)
RETURNING id;
```

- Insert a minimal policy (text fields required):
```sql
INSERT INTO policies (title, markdown_content, text_content, policy_metadata)
VALUES ('Example Policy', '# Title\nBody', 'Body', '{}'::jsonb)
RETURNING id;
```

- Insert a chunk for a policy:
```sql
INSERT INTO policy_chunks (policy_id, chunk_index, content, chunk_metadata)
VALUES (/* policy_id */ 1, 0, 'First chunk text', '{}'::jsonb)
RETURNING id;
```

- Update a row:
```sql
UPDATE policies SET description = 'Updated description', updated_at = now()
WHERE id = 1;
```

- Delete one row by id:
```sql
DELETE FROM policies WHERE id = 1;
```

### 7) Extensions and indexes

- Check installed extensions in the DB:
```sql
SELECT name, default_version, installed_version FROM pg_available_extensions
ORDER BY name;
```

- Create `vector` extension (if available and not already installed):
```sql
CREATE EXTENSION IF NOT EXISTS vector SCHEMA public;
```

- Reindex a table:
```sql
REINDEX TABLE policy_chunks;
```

- See triggers on a table:
```sql
\d policies
\d policy_chunks
```

### 8) Backup and restore

- Backup the `ydrpolicy` DB:
```bash
/home1/pr555/pgsql/bin/pg_dump -h 127.0.0.1 -p 5432 -U pr555 -d ydrpolicy -Fc \
  -f /home1/pr555/ydrpolicy_$(date +%Y%m%d_%H%M%S).dump
```

- Restore into a fresh DB:
```bash
/home1/pr555/pgsql/bin/createdb -h 127.0.0.1 -p 5432 -U pr555 ydrpolicy_restored
/home1/pr555/pgsql/bin/pg_restore -h 127.0.0.1 -p 5432 -U pr555 -d ydrpolicy_restored \
  /path/to/ydrpolicy_YYYYMMDD_HHMMSS.dump
```

### 9) Managing roles (only if needed)

Local trust auth allows any local user to connect as `pr555`. If you need to recreate the role:

```bash
/home1/pr555/pgsql/bin/psql -h 127.0.0.1 -p 5432 -d postgres -c \
  "DO $$BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pr555') THEN
     CREATE ROLE pr555 LOGIN SUPERUSER CREATEDB CREATEROLE;
   END IF; END$$;"
```

### 10) Project-specific DB lifecycle via CLI

Run these from inside `ydrp_engine` using `uv`:

```bash
cd /home1/pr555/Projects/YDRP-RAG/ydrp_engine

# Initialize schema, seed users, and populate from processed TXT (requires DB running)
uv run python main.py database --init --populate

# Initialize schema only (no population)
uv run python main.py database --init

# Drop database (DANGEROUS; irreversible). Add --force to skip confirmation.
uv run python main.py database --drop --force
```

Notes:
- Population may attempt to compute embeddings using OpenAI. Ensure `OPENAI_API_KEY` is set if you need embeddings.
- Even if embeddings fail, schema/tables and core records will still be created.

### 11) Troubleshooting

- Check if server is accepting connections:
```bash
/home1/pr555/pgsql/bin/pg_isready -h 127.0.0.1 -p 5432
```

- Nothing on 5432? Start the server (see Section 1). If another process uses 5432:
```bash
ss -ltnp '( sport = :5432 )'
```

- Cannot connect with `psql`: verify host/port/user/db and that `/home1/pr555/pgsql/data/pg_hba.conf` allows local trust (then reload):
```bash
/home1/pr555/pgsql/bin/pg_ctl -D /home1/pr555/pgsql/data reload
```

- Inspect server logs:
```bash
tail -n 200 /home1/pr555/pgsql/data/server.log
```

- Ensure DB URL used by the app (default): `postgresql+asyncpg://pr555:@localhost:5432/ydrpolicy`.

### 12) Current state (as configured now)

- Server is running on `127.0.0.1:5432` and accepting connections.
- Database `ydrpolicy` exists and is accessible as user `pr555`.
- Record counts example:
```bash
/home1/pr555/pgsql/bin/psql -h 127.0.0.1 -p 5432 -d ydrpolicy -Atqc "SELECT COUNT(*) FROM policies;"
```

This manual is tailored to this repository and machine paths. If you relocate the installation, update the paths accordingly.


