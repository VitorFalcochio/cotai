create extension if not exists pgcrypto;

create or replace function public.set_current_timestamp_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.request_quotes (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null references public.requests(id) on delete cascade,
  status text not null default 'PENDING'
    check (status in ('PENDING','RECEIVED','QUOTING','DONE','ERROR')),
  source_summary text,
  response_text text,
  error_message text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists request_quotes_request_id_idx
  on public.request_quotes(request_id);

create index if not exists request_quotes_status_idx
  on public.request_quotes(status);

drop trigger if exists trg_request_quotes_set_updated_at on public.request_quotes;
create trigger trg_request_quotes_set_updated_at
before update on public.request_quotes
for each row
execute function public.set_current_timestamp_updated_at();

create table if not exists public.worker_processed_messages (
  id uuid primary key default gen_random_uuid(),
  message_id text not null unique,
  chat_id text,
  request_id uuid references public.requests(id) on delete set null,
  request_quote_id uuid references public.request_quotes(id) on delete set null,
  payload_hash text,
  processing_status text not null default 'PROCESSED'
    check (processing_status in ('PROCESSED','IGNORED','FAILED')),
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists worker_processed_messages_chat_id_idx
  on public.worker_processed_messages(chat_id);

create index if not exists worker_processed_messages_request_id_idx
  on public.worker_processed_messages(request_id);

create index if not exists worker_processed_messages_request_quote_id_idx
  on public.worker_processed_messages(request_quote_id);

alter table public.request_quotes enable row level security;
alter table public.worker_processed_messages enable row level security;

drop policy if exists request_quotes_select_same_company on public.request_quotes;
create policy request_quotes_select_same_company
on public.request_quotes
for select
to authenticated
using (
  exists (
    select 1
    from public.requests r
    where r.id = request_quotes.request_id
      and r.company_id = public.current_company_id()
  )
);

drop policy if exists request_quotes_insert_same_company on public.request_quotes;
create policy request_quotes_insert_same_company
on public.request_quotes
for insert
to authenticated
with check (
  exists (
    select 1
    from public.requests r
    where r.id = request_quotes.request_id
      and r.company_id = public.current_company_id()
  )
);

drop policy if exists request_quotes_update_same_company on public.request_quotes;
create policy request_quotes_update_same_company
on public.request_quotes
for update
to authenticated
using (
  exists (
    select 1
    from public.requests r
    where r.id = request_quotes.request_id
      and r.company_id = public.current_company_id()
  )
)
with check (
  exists (
    select 1
    from public.requests r
    where r.id = request_quotes.request_id
      and r.company_id = public.current_company_id()
  )
);

drop policy if exists worker_processed_messages_select_same_company on public.worker_processed_messages;
create policy worker_processed_messages_select_same_company
on public.worker_processed_messages
for select
to authenticated
using (
  request_id is not null
  and exists (
    select 1
    from public.requests r
    where r.id = worker_processed_messages.request_id
      and r.company_id = public.current_company_id()
  )
);

drop policy if exists worker_processed_messages_insert_same_company on public.worker_processed_messages;
create policy worker_processed_messages_insert_same_company
on public.worker_processed_messages
for insert
to authenticated
with check (
  request_id is not null
  and exists (
    select 1
    from public.requests r
    where r.id = worker_processed_messages.request_id
      and r.company_id = public.current_company_id()
  )
);
