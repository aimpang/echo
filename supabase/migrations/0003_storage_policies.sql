-- Storage bucket RLS for Echoes
-- Run after buckets `videos`, `splats`, `thumbnails` are created in the dashboard.

-- Videos bucket: owner-only
drop policy if exists "videos_owner_select" on storage.objects;
create policy "videos_owner_select" on storage.objects
  for select using (
    bucket_id = 'videos'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "videos_owner_insert" on storage.objects;
create policy "videos_owner_insert" on storage.objects
  for insert with check (
    bucket_id = 'videos'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "videos_owner_delete" on storage.objects;
create policy "videos_owner_delete" on storage.objects
  for delete using (
    bucket_id = 'videos'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- Splats bucket: owner-only read (shared via signed URLs)
drop policy if exists "splats_owner_select" on storage.objects;
create policy "splats_owner_select" on storage.objects
  for select using (
    bucket_id = 'splats'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- Thumbnails bucket: public read, owner write
drop policy if exists "thumbnails_public_select" on storage.objects;
create policy "thumbnails_public_select" on storage.objects
  for select using (bucket_id = 'thumbnails');
