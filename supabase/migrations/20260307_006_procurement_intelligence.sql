create extension if not exists pgcrypto;

create table if not exists public.suppliers (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.companies(id) on delete cascade,
  name text not null,
  region text,
  city text,
  state text,
  contact_name text,
  contact_channel text,
  material_tags text[] not null default '{}'::text[],
  average_delivery_days integer,
  average_rating numeric,
  quote_participation_count integer not null default 0,
  average_price_score numeric,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table if exists public.suppliers add column if not exists company_id uuid references public.companies(id) on delete cascade;
alter table if exists public.suppliers add column if not exists name text;
alter table if exists public.suppliers add column if not exists region text;
alter table if exists public.suppliers add column if not exists city text;
alter table if exists public.suppliers add column if not exists state text;
alter table if exists public.suppliers add column if not exists contact_name text;
alter table if exists public.suppliers add column if not exists contact_channel text;
alter table if exists public.suppliers add column if not exists material_tags text[] not null default '{}'::text[];
alter table if exists public.suppliers add column if not exists average_delivery_days integer;
alter table if exists public.suppliers add column if not exists average_rating numeric;
alter table if exists public.suppliers add column if not exists quote_participation_count integer not null default 0;
alter table if exists public.suppliers add column if not exists average_price_score numeric;
alter table if exists public.suppliers add column if not exists status text not null default 'active';
alter table if exists public.suppliers add column if not exists created_at timestamptz not null default now();
alter table if exists public.suppliers add column if not exists updated_at timestamptz not null default now();

create index if not exists suppliers_company_id_idx on public.suppliers(company_id);
create index if not exists suppliers_name_idx on public.suppliers(name);
create index if not exists suppliers_status_idx on public.suppliers(status);

create table if not exists public.supplier_reviews (
  id uuid primary key default gen_random_uuid(),
  supplier_id uuid not null references public.suppliers(id) on delete cascade,
  request_id uuid references public.requests(id) on delete set null,
  company_id uuid references public.companies(id) on delete cascade,
  reviewer_user_id uuid references auth.users(id) on delete set null,
  price_rating integer,
  delivery_rating integer,
  service_rating integer,
  reliability_rating integer,
  comment text,
  created_at timestamptz not null default now()
);

create index if not exists supplier_reviews_supplier_id_idx on public.supplier_reviews(supplier_id);
create index if not exists supplier_reviews_request_id_idx on public.supplier_reviews(request_id);
create index if not exists supplier_reviews_company_id_idx on public.supplier_reviews(company_id);

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  name text not null,
  location text,
  stage text default 'planning',
  status text default 'active',
  notes text,
  created_by_user_id uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists projects_company_id_idx on public.projects(company_id);
create index if not exists projects_status_idx on public.projects(status);

create table if not exists public.project_materials (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  request_id uuid references public.requests(id) on delete set null,
  material_name text not null,
  category text,
  estimated_qty numeric,
  purchased_qty numeric,
  pending_qty numeric,
  status text default 'pending',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists project_materials_project_id_idx on public.project_materials(project_id);
create index if not exists project_materials_request_id_idx on public.project_materials(request_id);
create index if not exists project_materials_status_idx on public.project_materials(status);

alter table if exists public.requests
  add column if not exists project_id uuid references public.projects(id) on delete set null;

create index if not exists requests_project_id_idx on public.requests(project_id);

create table if not exists public.price_history (
  id uuid primary key default gen_random_uuid(),
  request_id uuid references public.requests(id) on delete set null,
  request_quote_id uuid references public.request_quotes(id) on delete set null,
  supplier_id uuid references public.suppliers(id) on delete set null,
  supplier_name text,
  item_name text not null,
  source_name text,
  price numeric,
  unit_price numeric,
  total_price numeric,
  captured_at timestamptz not null default now()
);

create index if not exists price_history_item_name_idx on public.price_history(item_name);
create index if not exists price_history_request_id_idx on public.price_history(request_id);
create index if not exists price_history_supplier_id_idx on public.price_history(supplier_id);
create index if not exists price_history_captured_at_idx on public.price_history(captured_at desc);

alter table if exists public.quote_results add column if not exists supplier_id uuid references public.suppliers(id) on delete set null;
alter table if exists public.quote_results add column if not exists unit_price numeric;
alter table if exists public.quote_results add column if not exists total_price numeric;
alter table if exists public.quote_results add column if not exists delivery_days integer;
alter table if exists public.quote_results add column if not exists delivery_label text;
alter table if exists public.quote_results add column if not exists origin_label text;
alter table if exists public.quote_results add column if not exists category text;
alter table if exists public.quote_results add column if not exists value_score numeric;
alter table if exists public.quote_results add column if not exists is_best_price boolean default false;
alter table if exists public.quote_results add column if not exists is_best_delivery boolean default false;
alter table if exists public.quote_results add column if not exists is_best_overall boolean default false;

create index if not exists quote_results_supplier_id_idx on public.quote_results(supplier_id);
create index if not exists quote_results_item_name_idx on public.quote_results(item_name);
