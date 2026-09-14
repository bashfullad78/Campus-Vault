# College Uploader

A college-specific academic PDF sharing platform with a virtual coin economy.
Students upload validated PDFs (**+10 coins**, capped 5 rewards/day) and spend
coins to download other students' notes (**−5 coins**). Modular monolith:
FastAPI + SQLAlchemy 2 + PostgreSQL + Alembic on the backend; React + Vite +
TypeScript + Tailwind v4 on the frontend.

Central security rule: identifying a resource never grants access to it.

---

## 1. Repository layout

```
backend/                   FastAPI app — 42/42 tests passing
├── main.py                app + restricted CORS (origins from CORS_ORIGINS env)
├── config.py              pydantic-settings; production refuses default SECRET_KEY
├── database.py            engine, SessionLocal (autoflush=False!)
├── models/                user, note, subject, rating, wallet, transaction
├── schemas/               auth, user, note, subject, wallet (never expose storage_key/file_hash)
├── routes/                auth, notes, coins, subjects
├── services/              auth_service, note_service, coin_service
├── storage/               interface.py (Protocol) + local.py + s3.py, get_storage() factory
├── utils/                 auth_helpers, dependencies, file_helpers, rate_limit
└── migrations/versions/   schema · subject seed · auth columns
frontend/                  React SPA — verified end-to-end
└── src/
    ├── api/               client.ts (fetch wrapper + single-flight refresh),
    │                      types.ts (mirrors backend schemas exactly), domain modules
    ├── components/        Layout/Nav, CoinChip, NoteCard, Pagination, guards
    ├── pages/             Login, Register, NotesList, NoteDetail, Upload, MyUploads, Wallet
    ├── lib/               format.ts, economy.ts (UI-copy constants)
    └── App.tsx            router + guards + QueryClientProvider
tests/                     pytest suite (conftest + auth/files/notes/wallet/storage)
```

## 2. Requirements

* Python 3.12 venv at `./venv`
* PostgreSQL at localhost:5432, db/user `college_uploader` — credentials in
  `.env` (copy `.env.example`; the DB role cannot CREATE DATABASE, so tests run
  against the dev DB)
* Node v24, npm 11 (frontend)

## 3. Backend

```bash
# one-time: apply migrations (schema + 10 seeded subjects)
./venv/bin/alembic upgrade head

# run (http://localhost:8000)
./venv/bin/uvicorn backend.main:app --reload
```

Tests — note the `python -m` form: there is no pytest config putting the
project root on `sys.path`, so plain `pytest` fails with
`ModuleNotFoundError: No module named 'backend'`:

```bash
./venv/bin/python -m pytest tests/ -v     # 42 tests, ~40s
```

Test isolation: all accounts are namespaced `v1test-<tag>@example.com`, wiped
per test (cascade); `storage/notes` is swept at session bounds; rate limiting
is disabled inside the suite.

### Storage backends (config-driven)

`STORAGE_BACKEND=local` (default) keeps files under `./STORAGE_DIR` — fine for
development. `STORAGE_BACKEND=s3` sends them to any S3-compatible store (AWS
S3, Cloudflare R2, Backblaze B2, MinIO) via `backend/storage/s3.py`: streaming
saves/reads (no full-file buffering in RAM), strict shared key validation,
and a boot check that proves credentials/bucket work at startup — a bad deploy
fails immediately, not at first upload. Required in production: free PaaS
disks are ephemeral, so local storage would lose every uploaded PDF on the
next redeploy while its DB rows survive. See `.env.example` for the S3_* vars.

### Design decisions worth knowing

* **Upload pipeline** (`note_service.create_note`): validate → dedup pre-check
  → storage.save → INSERT+flush → reward → commit. Concurrent-duplicate race
  is lost on commit → IntegrityError → file removed, 409 returned.
* **Coin engine** (`coin_service`): every mutation locks the wallet row
  (`SELECT … FOR UPDATE`), inserts the ledger row, then adjusts balance — all
  in the caller's transaction. Explicit `flush()` after the ledger insert is
  required under `autoflush=False`, or the daily-cap COUNT misses pending rows.
  A concurrency test proves 3 parallel 5-coin spends on a 10-coin wallet
  return exactly 2×200 + 1×409 — balance never negative.
* **Download** (`note_service.download_note`): charge before streaming, commit
  only after the file opens; missing file → rollback → user not billed.
  Self-download always free. Insufficient coins → 409.
* **Validation** (`utils/file_helpers`): size (413) → magic bytes → pypdf
  parse → page count → encryption → SHA-256, streamed once; cursor reset
  before returning. Identical files are rejected server-side (409) via the
  content hash — dedup is never trusted to the client.
* **Auth**: bcrypt + JWT (type claim: refresh can never authenticate as
  access). Logout bumps `users.token_invalid_before` (≤ second granularity,
  fail closed) and revokes *all* of a user's tokens globally.
* **Email dedup**: `normalized_email` (lowercase, strip +tags, gmail dots).
* **Rate limiting**: in-process sliding window on login/register/upload.
* **Soft delete**: notes leave every listing but coins already earned are
  kept — deletion is not exploitable to dodge the reward cap.

## 4. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

CORS on the backend is restricted to `http://localhost:5173` via
`CORS_ORIGINS` (`backend/config.py`); the Vite dev server is pinned to that
port. If Vite ever binds another port, update `CORS_ORIGINS`.

Design: coin-gold on slate, dark-first, quiet/utilitarian (Linear-clean) —
the coin economy is the visual identity. TanStack Query v5 for server state
(no Redux), react-router v7, hand-written types mirroring the backend schemas
(`NoteOut` excludes `storage_key`/`file_hash` client-side too).

### Frontend behavior notes (why things look the way they do)

* **Ownership** — the API exposes `owner_id` but no names and no `is_owner`
  flag; the client compares against `/auth/me` and shows "Uploaded {date}".
* **Reward feedback** — the upload response is silent about the daily cap, so
  the UI captures the balance before the upload and animates on the delta:
  `+10` → celebrate; unchanged → "cap reached (5/5) — no coins this time".
* **Daily-cap progress** — counted client-side from the ledger against **UTC**
  midnight, matching the server.
* **Downloads** — require an Authorization header, so they go through
  `fetch → blob → objectURL → click → revoke`, never a plain `<a href>`.
* **Token refresh** — one shared in-flight refresh promise; concurrent 401s
  queue behind it and retry exactly once. Tokens live in localStorage
  (XSS tradeoff documented in `frontend/src/api/client.ts`). Refresh TTL
  (7 days) is the hard session ceiling.
* **422 details** — FastAPI returns `detail` as a string or an array; both are
  flattened and shown verbatim in the UI.
* **No fake search** — the API has no search endpoint, so the UI offers
  subject filters and pagination instead of pretending.

## 5. Testing & verification

```bash
./venv/bin/python -m pytest tests/ -v     # backend: 42 tests, ~40s
./venv/bin/python scripts/smoke_test.py   # E2E: full user flow against a live server
cd frontend && npx tsc -b && npm run build  # frontend: typecheck + production build
cd frontend && npm run lint               # 0 warnings
```

The smoke test (local-only, `scripts/` is gitignored) boots the backend on
:8000 and walks the exact flow the React app performs, then shuts the server
down: health → register (409 on duplicate) → login (401 copy) → me → subjects
→ upload 201 (+10 balance, no internal fields in NoteOut) → duplicate 409 →
self-download free (PDF bytes, Content-Disposition) → 0-coin download 409 →
ledger row (+10 UPLOAD_REWARD) → delete → 404, balance unchanged → refresh
rotation → logout → global token revocation. 25/25 passing. It uses emails
namespaced `frontend-demo-*@example.com` so pytest cleanup (`v1test-*`) is
never disturbed.

## 6. Quick reference — API surface

Base URL: `http://localhost:8000` (no global prefix). Health: `GET /health`.
Error body is FastAPI `{detail}`; 422s return `detail` as an ARRAY.

```
POST /auth/register        201  {email, name, password} · 409 email exists
POST /auth/login           200  → {access_token, refresh_token}
POST /auth/refresh         200  (refresh token rotates)
POST /auth/logout          200  (revokes ALL tokens for the user)
GET  /auth/me              200

GET  /subjects             200  ?semester=1..10

POST /notes                201  multipart: subject_id, title, file, [chapter]
                                409 duplicate · 404 subject · 413 size · 422 invalid
GET  /notes                200  ?subject_id=&limit=&offset=
GET  /notes/my             200
GET  /notes/{id}           200
GET  /notes/{id}/download  200 stream · 409 insufficient coins (self: free)
DELETE /notes/{id}         200  (owner only → 403 otherwise)

GET  /coins/balance        200  {balance}
GET  /coins/transactions   200  ledger, newest first
```

Economy defaults (config-overridable): UPLOAD_REWARD=10, DOWNLOAD_COST=5,
DAILY_REWARD_CAP=5, MAX_FILE_SIZE_MB=25, pages 1–500, access token 30min,
refresh 7d.

## 7. Known limitations

* In-process rate limiter only (per-instance, resets on restart); a
  Redis-backed limiter is the natural next hardening step.
* Refresh rotation re-issues the pair but does **not** invalidate the old
  refresh token (no jti replay check) — tokens stay valid until logout bumps
  `token_invalid_before`. Cheap hardening win; the frontend already behaves
  correctly.
* ~~No object storage~~ **done**: `STORAGE_BACKEND=s3` streams files to any
  S3-compatible bucket (see §3). Multi-instance deploys are now unblocked,
  though the in-process rate limiter still assumes one instance.
* Logout revokes all of a user's tokens (global, not per-session).
* Ratings exist in the data model but have no API or UI yet; the subject
  catalog is read-only, seeded by migration.
