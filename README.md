# Echoes

4D personal memory vault. Upload a 15–45s video, walk inside the resulting
Gaussian splat scene, rewind and share.

## Repo layout

```
echoes/
  web/           Next.js 16 App Router + TypeScript + Tailwind + R3F
  processing/    Local Python worker (RTX 5080) — gsplat pipeline
  supabase/      SQL migrations + storage RLS
```

## Month 1 status

| Area                    | Status |
| ----------------------- | ------ |
| Next.js scaffold        | done   |
| Supabase clients + RLS  | done   |
| `memories` table schema | done   |
| Video validator         | done (TDD) |
| Share-link tokens       | done (TDD) |
| Status state machine    | done (TDD) |
| Frame index (4D)        | done (TDD) |
| Landing + auth (magic link) | done |
| Upload page (drag & drop) | done |
| Dashboard               | done |
| Memory detail + viewer  | done |
| Public share page `/s/[token]` | done |
| Python gsplat worker    | skeleton done (swap in 4D pipeline) |

## Getting started

### 1. Supabase

Create a Supabase project. In the SQL editor:

```sql
-- run supabase/migrations/0001_init.sql
-- then create storage buckets: videos, splats, thumbnails (all private except thumbnails)
-- then run supabase/storage.sql
```

### 2. Web app

```bash
cd web
cp .env.example .env.local    # fill in SUPABASE creds
npm install
npm run dev
```

- `npm test` — Vitest unit tests (40/40 passing)
- `npm run typecheck` — TypeScript strict

### 3. Local processing worker

See `processing/README.md`. Requires PyTorch + CUDA + gsplat + ffmpeg.

```bash
cd processing
cp .env.example .env
python echoes_pipeline.py
```

## Architecture

```
User → /new ──▶ Supabase Storage (videos bucket, private RLS)
                │
                ▼
         memories.status = uploading → scanning
                │
                ▼
  Python worker on RTX 5080 polls "scanning"
                │
                ├─ Hive safety check (optional)
                ├─ ffmpeg → frames
                ├─ gsplat training
                └─ upload .splat → splats bucket
                │
                ▼
         memories.status = ready
                │
                ▼
  Web viewer (R3F + drei Splat) via signed URL
```

## Testing philosophy

Pure logic (validators, state machines, token generation, frame index search)
is test-first with Vitest. UI / framework integration is driven from typed
Supabase client + manual verification in the dev server.
