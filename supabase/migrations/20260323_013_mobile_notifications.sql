alter table if exists public.profiles
  add column if not exists mobile_notifications_enabled boolean not null default true;

create table if not exists public.company_notifications (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.companies(id) on delete cascade,
  request_id uuid references public.requests(id) on delete cascade,
  request_code text,
  event_type text not null,
  title text not null,
  message text not null,
  tone text not null default 'info'
    check (tone in ('info', 'success', 'warning', 'danger', 'muted')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table if exists public.company_notifications
  add column if not exists company_id uuid references public.companies(id) on delete cascade;
alter table if exists public.company_notifications
  add column if not exists request_id uuid references public.requests(id) on delete cascade;
alter table if exists public.company_notifications
  add column if not exists request_code text;
alter table if exists public.company_notifications
  add column if not exists event_type text;
alter table if exists public.company_notifications
  add column if not exists title text;
alter table if exists public.company_notifications
  add column if not exists message text;
alter table if exists public.company_notifications
  add column if not exists tone text default 'info';
alter table if exists public.company_notifications
  add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table if exists public.company_notifications
  add column if not exists created_at timestamptz not null default now();

create index if not exists company_notifications_company_id_idx on public.company_notifications(company_id, created_at desc);
create index if not exists company_notifications_request_id_idx on public.company_notifications(request_id, created_at desc);

alter table public.company_notifications enable row level security;

drop policy if exists company_notifications_select_admin_or_same_company on public.company_notifications;
create policy company_notifications_select_admin_or_same_company
on public.company_notifications
for select
to authenticated
using (
  public.is_admin()
  or company_id = public.current_company_id()
  or company_id is null
);
