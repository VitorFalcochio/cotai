alter table if exists public.projects add column if not exists source_thread_id uuid references public.chat_threads(id) on delete set null;
alter table if exists public.projects add column if not exists project_type text;
alter table if exists public.projects add column if not exists area_m2 numeric;
alter table if exists public.projects add column if not exists floors integer;
alter table if exists public.projects add column if not exists building_standard text;
alter table if exists public.projects add column if not exists foundation_type text;
alter table if exists public.projects add column if not exists roof_type text;
alter table if exists public.projects add column if not exists summary_estimated_total_cents bigint;
alter table if exists public.projects add column if not exists summary_estimated_total_display text;
alter table if exists public.projects add column if not exists current_phase_key text;
alter table if exists public.projects add column if not exists current_phase_title text;
alter table if exists public.projects add column if not exists metadata jsonb not null default '{}'::jsonb;

create index if not exists projects_source_thread_id_idx on public.projects(source_thread_id);
