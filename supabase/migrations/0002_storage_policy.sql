-- Storage retention policy (ratified April 2026):
--
-- We keep only the processed 4D model long-term. The user's original
-- uploaded video is transient: it exists in the `videos` bucket just long
-- enough for the worker to download it, then is deleted once the .splat
-- pipeline succeeds.
--
-- `source_video_path` therefore holds a storage key while the memory is
-- in flight (uploading -> scanning -> processing) and is nulled out by
-- the worker on success (see echoes_pipeline.build_completion_update).
-- A non-null value on a `ready` memory is a bug: the cleanup step failed
-- and the video in storage is orphaned.

comment on column public.memories.source_video_path is
  'Transient storage key for the uploaded video. Set on insert; cleared when the memory reaches status=ready and the underlying object is deleted from the `videos` bucket. Never set on ready memories — if it is, the source video is leaked in storage.';

comment on column public.memories.splat_path is
  'Storage key in the `splats` bucket. Points at manifest.json for 4D memories or at a single .splat for 3D. The canonical long-term artifact.';

-- Safety net: reject any update that tries to set source_video_path
-- on a ready memory. Keeps the invariant above honest.
create or replace function public.enforce_source_video_cleared_on_ready()
returns trigger
language plpgsql
as $$
begin
  if new.status = 'ready' and new.source_video_path is not null then
    raise exception
      'source_video_path must be null on ready memories (storage retention policy)';
  end if;
  return new;
end;
$$;

drop trigger if exists memories_enforce_source_cleared on public.memories;
create trigger memories_enforce_source_cleared
  before insert or update on public.memories
  for each row execute function public.enforce_source_video_cleared_on_ready();
