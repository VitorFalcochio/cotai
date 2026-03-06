create extension if not exists pgcrypto;

create table if not exists public.admin_audit_logs (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.companies(id) on delete set null,
  actor_id uuid references auth.users(id) on delete set null,
  actor_email text,
  event_type text not null default 'admin_action',
  description text not null,
  metadata jsonb,
  created_at timestamptz not null default now()
);

alter table if exists public.admin_audit_logs add column if not exists company_id uuid references public.companies(id) on delete set null;
alter table if exists public.admin_audit_logs add column if not exists actor_id uuid references auth.users(id) on delete set null;
alter table if exists public.admin_audit_logs add column if not exists actor_email text;
alter table if exists public.admin_audit_logs add column if not exists event_type text default 'admin_action';
alter table if exists public.admin_audit_logs add column if not exists description text;
alter table if exists public.admin_audit_logs add column if not exists metadata jsonb;
alter table if exists public.admin_audit_logs add column if not exists created_at timestamptz not null default now();

create index if not exists admin_audit_logs_company_id_idx
  on public.admin_audit_logs(company_id);

create index if not exists admin_audit_logs_actor_id_idx
  on public.admin_audit_logs(actor_id);

create index if not exists admin_audit_logs_event_type_idx
  on public.admin_audit_logs(event_type);

create index if not exists admin_audit_logs_created_at_idx
  on public.admin_audit_logs(created_at desc);

create or replace function public.log_admin_event(
  p_company_id uuid,
  p_event_type text,
  p_description text,
  p_metadata jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
begin
  insert into public.admin_audit_logs (
    company_id,
    actor_id,
    actor_email,
    event_type,
    description,
    metadata
  )
  values (
    p_company_id,
    auth.uid(),
    (select email from auth.users where id = auth.uid()),
    coalesce(nullif(trim(p_event_type), ''), 'admin_action'),
    p_description,
    coalesce(p_metadata, '{}'::jsonb)
  )
  returning id into v_id;

  return v_id;
end;
$$;

alter table public.admin_audit_logs enable row level security;

drop policy if exists admin_audit_logs_select_admin_only on public.admin_audit_logs;
create policy admin_audit_logs_select_admin_only
on public.admin_audit_logs
for select
to authenticated
using (public.is_admin());

drop policy if exists admin_audit_logs_insert_admin_only on public.admin_audit_logs;
create policy admin_audit_logs_insert_admin_only
on public.admin_audit_logs
for insert
to authenticated
with check (public.is_admin());
