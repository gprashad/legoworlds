-- Lego Worlds — Supabase Schema Migration
-- Run this in the Supabase SQL Editor

-- Profiles (extends Supabase Auth users)
create table profiles (
  id uuid references auth.users primary key,
  display_name text not null,
  role text default 'creator',  -- 'creator' or 'admin'
  phone_number text,
  created_at timestamptz default now()
);

-- Scenes
create table scenes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) not null,
  title text not null default 'Untitled Scene',
  backstory text,
  status text not null default 'draft',
  director_name text default 'Jackson',
  movie_style text default 'cinematic',
  music_mood text default 'auto',
  scene_bible jsonb,
  screenplay jsonb,
  screenplay_feedback text,
  screenplay_version int default 0,
  voiceover_url text,
  final_video_url text,
  final_video_duration_seconds int,
  published_platforms jsonb default '[]',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Scene media (photos, videos)
create table scene_media (
  id uuid primary key default gen_random_uuid(),
  scene_id uuid references scenes(id) on delete cascade not null,
  file_url text not null,
  file_type text not null,  -- 'photo' or 'video'
  file_name text,
  file_size_bytes int,
  sort_order int default 0,
  source text default 'upload',  -- 'upload', 'email', 'sms'
  created_at timestamptz default now()
);

-- Jobs (pipeline tracking)
create table jobs (
  id uuid primary key default gen_random_uuid(),
  scene_id uuid references scenes(id) not null,
  status text not null default 'pending',
  current_stage text,
  progress_pct int default 0,
  stages_completed jsonb default '[]',
  error text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz default now()
);

-- Enable RLS
alter table profiles enable row level security;
alter table scenes enable row level security;
alter table scene_media enable row level security;
alter table jobs enable row level security;

-- RLS Policies

-- Profiles: users can read/update their own profile
create policy "Users read own profile" on profiles
  for select using (auth.uid() = id);
create policy "Users update own profile" on profiles
  for update using (auth.uid() = id);

-- Scenes: users see/manage only their own scenes
create policy "Users see own scenes" on scenes
  for select using (auth.uid() = user_id);
create policy "Users insert own scenes" on scenes
  for insert with check (auth.uid() = user_id);
create policy "Users update own scenes" on scenes
  for update using (auth.uid() = user_id);
create policy "Users delete own scenes" on scenes
  for delete using (auth.uid() = user_id);

-- Scene media: users manage media for their own scenes
create policy "Users see own media" on scene_media
  for select using (scene_id in (select id from scenes where user_id = auth.uid()));
create policy "Users insert own media" on scene_media
  for insert with check (scene_id in (select id from scenes where user_id = auth.uid()));
create policy "Users update own media" on scene_media
  for update using (scene_id in (select id from scenes where user_id = auth.uid()));
create policy "Users delete own media" on scene_media
  for delete using (scene_id in (select id from scenes where user_id = auth.uid()));

-- Jobs: users see jobs for their own scenes
create policy "Users see own jobs" on jobs
  for select using (scene_id in (select id from scenes where user_id = auth.uid()));

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', 'Builder'));
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Auto-update updated_at on scenes
create or replace function public.update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger scenes_updated_at
  before update on scenes
  for each row execute procedure public.update_updated_at();

-- Storage bucket (run separately or via Supabase dashboard)
-- insert into storage.buckets (id, name, public) values ('legoworlds', 'legoworlds', false);

-- Storage policies
-- Users upload to their own scene folders
create policy "Users upload to own scenes" on storage.objects for insert
to authenticated with check (
  bucket_id = 'legoworlds'
  and (storage.foldername(name))[1] = 'scenes'
  and exists (select 1 from scenes where id::text = (storage.foldername(name))[2] and user_id = auth.uid())
);

-- Users read their own scene files
create policy "Users read own scenes" on storage.objects for select
to authenticated using (
  bucket_id = 'legoworlds'
  and (storage.foldername(name))[1] = 'scenes'
  and exists (select 1 from scenes where id::text = (storage.foldername(name))[2] and user_id = auth.uid())
);

-- Users delete their own scene files
create policy "Users delete own scenes" on storage.objects for delete
to authenticated using (
  bucket_id = 'legoworlds'
  and (storage.foldername(name))[1] = 'scenes'
  and exists (select 1 from scenes where id::text = (storage.foldername(name))[2] and user_id = auth.uid())
);
