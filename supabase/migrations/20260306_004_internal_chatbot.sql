create extension if not exists pgcrypto;

create table if not exists public.chat_threads (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  company_id uuid references public.companies(id) on delete set null,
  title text not null,
  status text not null default 'DRAFT'
    check (status in ('DRAFT', 'AWAITING_CONFIRMATION', 'PROCESSING', 'DONE', 'ERROR', 'ARCHIVED')),
  request_id uuid references public.requests(id) on delete set null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.chat_threads(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table if exists public.requests add column if not exists chat_thread_id uuid references public.chat_threads(id) on delete set null;
alter table if exists public.requests add column if not exists requested_by_user_id uuid references auth.users(id) on delete set null;
alter table if exists public.chat_threads add column if not exists metadata jsonb not null default '{}'::jsonb;

create index if not exists chat_threads_user_id_idx on public.chat_threads(user_id);
create index if not exists chat_threads_company_id_idx on public.chat_threads(company_id);
create index if not exists chat_threads_request_id_idx on public.chat_threads(request_id);
create index if not exists chat_messages_thread_id_idx on public.chat_messages(thread_id);
create index if not exists requests_chat_thread_id_idx on public.requests(chat_thread_id);
create index if not exists requests_requested_by_user_id_idx on public.requests(requested_by_user_id);

alter table public.chat_threads enable row level security;
alter table public.chat_messages enable row level security;

create or replace function public.set_current_timestamp_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_chat_threads_set_updated_at on public.chat_threads;
create trigger trg_chat_threads_set_updated_at
before update on public.chat_threads
for each row
execute function public.set_current_timestamp_updated_at();

do $$
begin
  if exists (
    select 1 from pg_constraint where conname = 'requests_status_check'
  ) then
    alter table public.requests drop constraint requests_status_check;
  end if;

  alter table public.requests
    add constraint requests_status_check
    check (status in (
      'NEW', 'RECEIVED', 'QUOTING', 'DONE', 'ERROR',
      'DRAFT', 'AWAITING_CONFIRMATION', 'PENDING_QUOTE', 'PROCESSING'
    ));
exception
  when duplicate_object then null;
end $$;

drop policy if exists chat_threads_select_own on public.chat_threads;
create policy chat_threads_select_own
on public.chat_threads
for select
to authenticated
using (auth.uid() = user_id or public.is_admin());

drop policy if exists chat_threads_insert_own on public.chat_threads;
create policy chat_threads_insert_own
on public.chat_threads
for insert
to authenticated
with check (auth.uid() = user_id or public.is_admin());

drop policy if exists chat_threads_update_own on public.chat_threads;
create policy chat_threads_update_own
on public.chat_threads
for update
to authenticated
using (auth.uid() = user_id or public.is_admin())
with check (auth.uid() = user_id or public.is_admin());

drop policy if exists chat_messages_select_thread on public.chat_messages;
create policy chat_messages_select_thread
on public.chat_messages
for select
to authenticated
using (
  exists (
    select 1
    from public.chat_threads t
    where t.id = chat_messages.thread_id
      and (t.user_id = auth.uid() or public.is_admin())
  )
);

drop policy if exists chat_messages_insert_thread on public.chat_messages;
create policy chat_messages_insert_thread
on public.chat_messages
for insert
to authenticated
with check (
  exists (
    select 1
    from public.chat_threads t
    where t.id = chat_messages.thread_id
      and (t.user_id = auth.uid() or public.is_admin())
  )
);
