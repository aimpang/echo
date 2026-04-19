-- Echoes: initial schema
-- Run against your Supabase project via the SQL editor or CLI.

create extension if not exists "pgcrypto";

create type memory_status as enum (
  'uploading',
  'scanning',
  'processing',
  'ready',
  'upload_failed',
  'rejected',
  'processing_failed'
);

create type memory_privacy as enum ('private', 'link');

create table if not exists public.memories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 120),
  description text check (description is null or char_length(description) <= 2000),
  captured_at timestamptz,
  status memory_status not null default 'uploading',
  privacy memory_privacy not null default 'private',
  share_token text unique,
  source_video_path text,
  splat_path text,
  thumbnail_path text,
  duration_seconds numeric(6, 2),
  size_bytes bigint,
  safety_flag text,
  safety_checked_at timestamptz,
  processing_started_at timestamptz,
  processing_completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists memories_user_id_created_at_idx
  on public.memories (user_id, created_at desc);

create index if not exists memories_share_token_idx
  on public.memories (share_token)
  where share_token is not null;

-- Keep updated_at fresh
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists memories_set_updated_at on public.memories;
create trigger memories_set_updated_at
  before update on public.memories
  for each row execute function public.set_updated_at();

-- Row Level Security
alter table public.memories enable row level security;

drop policy if exists "memories_owner_select" on public.memories;
create policy "memories_owner_select" on public.memories
  for select using (auth.uid() = user_id);

drop policy if exists "memories_public_link_select" on public.memories;
create policy "memories_public_link_select" on public.memories
  for select using (privacy = 'link' and share_token is not null);

drop policy if exists "memories_owner_insert" on public.memories;
create policy "memories_owner_insert" on public.memories
  for insert with check (auth.uid() = user_id);

drop policy if exists "memories_owner_update" on public.memories;
create policy "memories_owner_update" on public.memories
  for update using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "memories_owner_delete" on public.memories;
create policy "memories_owner_delete" on public.memories
  for delete using (auth.uid() = user_id);

-- Storage buckets: create via dashboard or CLI
-- 1. `videos` (private) — user-uploaded source videos
-- 2. `splats` (private) — processed 4DGS artifacts, signed URLs for viewing
-- 3. `thumbnails` (public) — small preview images
