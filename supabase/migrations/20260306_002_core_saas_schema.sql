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

create table if not exists public.companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  plan text not null default 'prata',
  status text not null default 'active'
    check (status in ('active', 'inactive', 'blocked', 'trial')),
  owner_user_id uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table if exists public.companies add column if not exists name text;
alter table if exists public.companies add column if not exists plan text default 'prata';
alter table if exists public.companies add column if not exists status text default 'active';
alter table if exists public.companies add column if not exists owner_user_id uuid references auth.users(id) on delete set null;
alter table if exists public.companies add column if not exists created_at timestamptz not null default now();
alter table if exists public.companies add column if not exists updated_at timestamptz not null default now();

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  full_name text,
  company_name text,
  company_id uuid references public.companies(id) on delete set null,
  role text not null default 'member'
    check (role in ('member', 'admin', 'owner')),
  status text not null default 'active'
    check (status in ('active', 'inactive', 'blocked')),
  plan text,
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table if exists public.profiles add column if not exists email text;
alter table if exists public.profiles add column if not exists full_name text;
alter table if exists public.profiles add column if not exists company_name text;
alter table if exists public.profiles add column if not exists company_id uuid references public.companies(id) on delete set null;
alter table if exists public.profiles add column if not exists role text default 'member';
alter table if exists public.profiles add column if not exists status text default 'active';
alter table if exists public.profiles add column if not exists plan text;
alter table if exists public.profiles add column if not exists last_login_at timestamptz;
alter table if exists public.profiles add column if not exists created_at timestamptz not null default now();
alter table if exists public.profiles add column if not exists updated_at timestamptz not null default now();

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'profiles_role_check'
  ) then
    alter table public.profiles
      add constraint profiles_role_check
      check (role in ('member', 'admin', 'owner'));
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'profiles_status_check'
  ) then
    alter table public.profiles
      add constraint profiles_status_check
      check (status in ('active', 'inactive', 'blocked'));
  end if;
end $$;

create table if not exists public.requests (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.companies(id) on delete set null,
  request_code text unique,
  customer_name text,
  delivery_mode text,
  delivery_location text,
  notes text,
  status text not null default 'NEW'
    check (status in ('NEW', 'RECEIVED', 'QUOTING', 'DONE', 'ERROR')),
  source_channel text,
  origin_chat_id text,
  last_error text,
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table if exists public.requests add column if not exists company_id uuid references public.companies(id) on delete set null;
alter table if exists public.requests add column if not exists request_code text;
alter table if exists public.requests add column if not exists customer_name text;
alter table if exists public.requests add column if not exists delivery_mode text;
alter table if exists public.requests add column if not exists delivery_location text;
alter table if exists public.requests add column if not exists notes text;
alter table if exists public.requests add column if not exists status text default 'NEW';
alter table if exists public.requests add column if not exists source_channel text;
alter table if exists public.requests add column if not exists origin_chat_id text;
alter table if exists public.requests add column if not exists last_error text;
alter table if exists public.requests add column if not exists processed_at timestamptz;
alter table if exists public.requests add column if not exists created_at timestamptz not null default now();
alter table if exists public.requests add column if not exists updated_at timestamptz not null default now();

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'requests_status_check'
  ) then
    alter table public.requests
      add constraint requests_status_check
      check (status in ('NEW', 'RECEIVED', 'QUOTING', 'DONE', 'ERROR'));
  end if;
end $$;

create unique index if not exists requests_request_code_key on public.requests(request_code);

create table if not exists public.request_items (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null references public.requests(id) on delete cascade,
  item_name text,
  description text,
  line_number integer,
  created_at timestamptz not null default now()
);

alter table if exists public.request_items add column if not exists request_id uuid references public.requests(id) on delete cascade;
alter table if exists public.request_items add column if not exists item_name text;
alter table if exists public.request_items add column if not exists description text;
alter table if exists public.request_items add column if not exists line_number integer;
alter table if exists public.request_items add column if not exists created_at timestamptz not null default now();

create table if not exists public.quote_results (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null references public.requests(id) on delete cascade,
  request_quote_id uuid,
  item_name text,
  title text,
  supplier text,
  supplier_name text,
  price numeric(12,2),
  link text,
  result_url text,
  source text,
  source_name text,
  position integer,
  raw_payload jsonb,
  created_at timestamptz not null default now()
);

alter table if exists public.quote_results add column if not exists request_id uuid references public.requests(id) on delete cascade;
alter table if exists public.quote_results add column if not exists request_quote_id uuid;
alter table if exists public.quote_results add column if not exists item_name text;
alter table if exists public.quote_results add column if not exists title text;
alter table if exists public.quote_results add column if not exists supplier text;
alter table if exists public.quote_results add column if not exists supplier_name text;
alter table if exists public.quote_results add column if not exists price numeric(12,2);
alter table if exists public.quote_results add column if not exists link text;
alter table if exists public.quote_results add column if not exists result_url text;
alter table if exists public.quote_results add column if not exists source text;
alter table if exists public.quote_results add column if not exists source_name text;
alter table if exists public.quote_results add column if not exists position integer;
alter table if exists public.quote_results add column if not exists raw_payload jsonb;
alter table if exists public.quote_results add column if not exists created_at timestamptz not null default now();

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'quote_results_request_quote_id_fkey'
  ) then
    alter table public.quote_results
      add constraint quote_results_request_quote_id_fkey
      foreign key (request_quote_id)
      references public.request_quotes(id)
      on delete cascade;
  end if;
exception
  when undefined_table then
    null;
end $$;

create table if not exists public.request_quotes (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null references public.requests(id) on delete cascade,
  status text not null default 'PENDING'
    check (status in ('PENDING', 'RECEIVED', 'QUOTING', 'DONE', 'ERROR')),
  source_summary text,
  response_text text,
  error_message text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table if exists public.request_quotes add column if not exists request_id uuid references public.requests(id) on delete cascade;
alter table if exists public.request_quotes add column if not exists status text default 'PENDING';
alter table if exists public.request_quotes add column if not exists source_summary text;
alter table if exists public.request_quotes add column if not exists response_text text;
alter table if exists public.request_quotes add column if not exists error_message text;
alter table if exists public.request_quotes add column if not exists started_at timestamptz;
alter table if exists public.request_quotes add column if not exists finished_at timestamptz;
alter table if exists public.request_quotes add column if not exists created_at timestamptz not null default now();
alter table if exists public.request_quotes add column if not exists updated_at timestamptz not null default now();

create table if not exists public.worker_processed_messages (
  id uuid primary key default gen_random_uuid(),
  message_id text not null unique,
  chat_id text,
  request_id uuid references public.requests(id) on delete set null,
  request_quote_id uuid references public.request_quotes(id) on delete set null,
  payload_hash text,
  processing_status text not null default 'PROCESSED'
    check (processing_status in ('PROCESSED', 'IGNORED', 'FAILED')),
  notes text,
  created_at timestamptz not null default now()
);

alter table if exists public.worker_processed_messages add column if not exists message_id text;
alter table if exists public.worker_processed_messages add column if not exists chat_id text;
alter table if exists public.worker_processed_messages add column if not exists request_id uuid references public.requests(id) on delete set null;
alter table if exists public.worker_processed_messages add column if not exists request_quote_id uuid references public.request_quotes(id) on delete set null;
alter table if exists public.worker_processed_messages add column if not exists payload_hash text;
alter table if exists public.worker_processed_messages add column if not exists processing_status text default 'PROCESSED';
alter table if exists public.worker_processed_messages add column if not exists notes text;
alter table if exists public.worker_processed_messages add column if not exists created_at timestamptz not null default now();

create table if not exists public.worker_heartbeats (
  id uuid primary key default gen_random_uuid(),
  worker_name text not null default 'cotai-worker',
  status text not null default 'online'
    check (status in ('online', 'offline', 'degraded')),
  details jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.billing_subscriptions (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  plan text not null default 'prata',
  status text not null default 'active'
    check (status in ('active', 'inactive', 'trial', 'cancelled', 'past_due', 'upgraded', 'downgraded')),
  mrr numeric(12,2),
  monthly_amount numeric(12,2),
  amount_cents integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table if exists public.billing_subscriptions add column if not exists company_id uuid references public.companies(id) on delete cascade;
alter table if exists public.billing_subscriptions add column if not exists plan text default 'prata';
alter table if exists public.billing_subscriptions add column if not exists status text default 'active';
alter table if exists public.billing_subscriptions add column if not exists mrr numeric(12,2);
alter table if exists public.billing_subscriptions add column if not exists monthly_amount numeric(12,2);
alter table if exists public.billing_subscriptions add column if not exists amount_cents integer;
alter table if exists public.billing_subscriptions add column if not exists created_at timestamptz not null default now();
alter table if exists public.billing_subscriptions add column if not exists updated_at timestamptz not null default now();

create index if not exists companies_owner_user_id_idx on public.companies(owner_user_id);
create index if not exists profiles_company_id_idx on public.profiles(company_id);
create index if not exists requests_company_id_idx on public.requests(company_id);
create index if not exists request_items_request_id_idx on public.request_items(request_id);
create index if not exists quote_results_request_id_idx on public.quote_results(request_id);
create index if not exists quote_results_request_quote_id_idx on public.quote_results(request_quote_id);
create index if not exists request_quotes_request_id_idx on public.request_quotes(request_id);
create index if not exists worker_processed_messages_chat_id_idx on public.worker_processed_messages(chat_id);
create index if not exists worker_processed_messages_request_id_idx on public.worker_processed_messages(request_id);
create index if not exists worker_heartbeats_created_at_idx on public.worker_heartbeats(created_at desc);
create index if not exists billing_subscriptions_company_id_idx on public.billing_subscriptions(company_id);

drop trigger if exists trg_companies_set_updated_at on public.companies;
create trigger trg_companies_set_updated_at
before update on public.companies
for each row execute function public.set_current_timestamp_updated_at();

drop trigger if exists trg_profiles_set_updated_at on public.profiles;
create trigger trg_profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_current_timestamp_updated_at();

drop trigger if exists trg_requests_set_updated_at on public.requests;
create trigger trg_requests_set_updated_at
before update on public.requests
for each row execute function public.set_current_timestamp_updated_at();

drop trigger if exists trg_request_quotes_set_updated_at on public.request_quotes;
create trigger trg_request_quotes_set_updated_at
before update on public.request_quotes
for each row execute function public.set_current_timestamp_updated_at();

drop trigger if exists trg_billing_subscriptions_set_updated_at on public.billing_subscriptions;
create trigger trg_billing_subscriptions_set_updated_at
before update on public.billing_subscriptions
for each row execute function public.set_current_timestamp_updated_at();

create or replace function public.current_company_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select p.company_id
  from public.profiles p
  where p.id = auth.uid()
  limit 1
$$;

create or replace function public.current_user_role()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select p.role
  from public.profiles p
  where p.id = auth.uid()
  limit 1
$$;

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(public.current_user_role() in ('admin', 'owner'), false)
$$;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (
    id,
    email,
    full_name,
    company_name,
    role,
    status,
    created_at,
    updated_at
  )
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'company_name', split_part(new.email, '@', 1)),
    new.raw_user_meta_data ->> 'company_name',
    'member',
    'active',
    now(),
    now()
  )
  on conflict (id) do update
  set email = excluded.email,
      full_name = coalesce(public.profiles.full_name, excluded.full_name),
      company_name = coalesce(public.profiles.company_name, excluded.company_name),
      updated_at = now();

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

alter table public.companies enable row level security;
alter table public.profiles enable row level security;
alter table public.requests enable row level security;
alter table public.request_items enable row level security;
alter table public.quote_results enable row level security;
alter table public.request_quotes enable row level security;
alter table public.worker_processed_messages enable row level security;
alter table public.worker_heartbeats enable row level security;
alter table public.billing_subscriptions enable row level security;

drop policy if exists companies_select_admin_or_same_company on public.companies;
create policy companies_select_admin_or_same_company
on public.companies
for select
to authenticated
using (
  public.is_admin()
  or id = public.current_company_id()
);

drop policy if exists companies_update_admin_only on public.companies;
create policy companies_update_admin_only
on public.companies
for update
to authenticated
using (public.is_admin())
with check (public.is_admin());

drop policy if exists profiles_select_own_or_admin on public.profiles;
create policy profiles_select_own_or_admin
on public.profiles
for select
to authenticated
using (
  public.is_admin()
  or id = auth.uid()
  or company_id = public.current_company_id()
);

drop policy if exists profiles_update_own_or_admin on public.profiles;
create policy profiles_update_own_or_admin
on public.profiles
for update
to authenticated
using (
  public.is_admin()
  or id = auth.uid()
)
with check (
  public.is_admin()
  or id = auth.uid()
);

drop policy if exists requests_select_admin_or_same_company on public.requests;
create policy requests_select_admin_or_same_company
on public.requests
for select
to authenticated
using (
  public.is_admin()
  or company_id = public.current_company_id()
  or company_id is null
);

drop policy if exists requests_insert_admin_or_same_company on public.requests;
create policy requests_insert_admin_or_same_company
on public.requests
for insert
to authenticated
with check (
  public.is_admin()
  or company_id = public.current_company_id()
  or company_id is null
);

drop policy if exists requests_update_admin_or_same_company on public.requests;
create policy requests_update_admin_or_same_company
on public.requests
for update
to authenticated
using (
  public.is_admin()
  or company_id = public.current_company_id()
  or company_id is null
)
with check (
  public.is_admin()
  or company_id = public.current_company_id()
  or company_id is null
);

drop policy if exists request_items_select_admin_or_same_company on public.request_items;
create policy request_items_select_admin_or_same_company
on public.request_items
for select
to authenticated
using (
  public.is_admin()
  or exists (
    select 1
    from public.requests r
    where r.id = request_items.request_id
      and (
        r.company_id = public.current_company_id()
        or r.company_id is null
      )
  )
);

drop policy if exists request_items_insert_admin_or_same_company on public.request_items;
create policy request_items_insert_admin_or_same_company
on public.request_items
for insert
to authenticated
with check (
  public.is_admin()
  or exists (
    select 1
    from public.requests r
    where r.id = request_items.request_id
      and (
        r.company_id = public.current_company_id()
        or r.company_id is null
      )
  )
);

drop policy if exists quote_results_select_admin_or_same_company on public.quote_results;
create policy quote_results_select_admin_or_same_company
on public.quote_results
for select
to authenticated
using (
  public.is_admin()
  or exists (
    select 1
    from public.requests r
    where r.id = quote_results.request_id
      and (
        r.company_id = public.current_company_id()
        or r.company_id is null
      )
  )
);

drop policy if exists request_quotes_select_admin_or_same_company on public.request_quotes;
create policy request_quotes_select_admin_or_same_company
on public.request_quotes
for select
to authenticated
using (
  public.is_admin()
  or exists (
    select 1
    from public.requests r
    where r.id = request_quotes.request_id
      and (
        r.company_id = public.current_company_id()
        or r.company_id is null
      )
  )
);

drop policy if exists worker_processed_messages_select_admin_or_same_company on public.worker_processed_messages;
create policy worker_processed_messages_select_admin_or_same_company
on public.worker_processed_messages
for select
to authenticated
using (
  public.is_admin()
  or (
    request_id is not null
    and exists (
      select 1
      from public.requests r
      where r.id = worker_processed_messages.request_id
        and (
          r.company_id = public.current_company_id()
          or r.company_id is null
        )
    )
  )
);

drop policy if exists billing_subscriptions_select_admin_or_same_company on public.billing_subscriptions;
create policy billing_subscriptions_select_admin_or_same_company
on public.billing_subscriptions
for select
to authenticated
using (
  public.is_admin()
  or company_id = public.current_company_id()
);

drop policy if exists billing_subscriptions_update_admin_only on public.billing_subscriptions;
create policy billing_subscriptions_update_admin_only
on public.billing_subscriptions
for update
to authenticated
using (public.is_admin())
with check (public.is_admin());

drop policy if exists worker_heartbeats_select_admin_only on public.worker_heartbeats;
create policy worker_heartbeats_select_admin_only
on public.worker_heartbeats
for select
to authenticated
using (public.is_admin());
