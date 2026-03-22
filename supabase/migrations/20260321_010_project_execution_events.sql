create table if not exists public.project_events (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  request_id uuid references public.requests(id) on delete set null,
  event_type text not null,
  material_name text,
  quantity numeric,
  stage_label text,
  supplier_name text,
  note text,
  impact_level text not null default 'info',
  created_by_user_id uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);

create index if not exists project_events_project_id_idx on public.project_events(project_id);
create index if not exists project_events_request_id_idx on public.project_events(request_id);
create index if not exists project_events_event_type_idx on public.project_events(event_type);
create index if not exists project_events_created_at_idx on public.project_events(created_at desc);

alter table if exists public.project_materials add column if not exists received_qty numeric;
alter table if exists public.project_materials add column if not exists consumed_qty numeric;
alter table if exists public.project_materials add column if not exists supplier_name text;
alter table if exists public.project_materials add column if not exists last_event_type text;
alter table if exists public.project_materials add column if not exists last_event_note text;
alter table if exists public.project_materials add column if not exists last_event_at timestamptz;
