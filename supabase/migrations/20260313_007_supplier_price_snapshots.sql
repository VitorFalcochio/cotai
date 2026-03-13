create extension if not exists pgcrypto;

create table if not exists public.supplier_price_snapshots (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references public.companies(id) on delete cascade,
  item_name text not null,
  normalized_item_name text not null,
  query text not null,
  provider text not null,
  source_name text not null,
  supplier_name text not null,
  supplier_id uuid references public.suppliers(id) on delete set null,
  title text not null,
  price numeric,
  unit_price numeric,
  currency text not null default 'BRL',
  delivery_days integer,
  delivery_label text,
  result_url text,
  metadata jsonb not null default '{}'::jsonb,
  captured_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists supplier_price_snapshots_company_id_idx on public.supplier_price_snapshots(company_id);
create index if not exists supplier_price_snapshots_item_name_idx on public.supplier_price_snapshots(item_name);
create index if not exists supplier_price_snapshots_normalized_item_name_idx on public.supplier_price_snapshots(normalized_item_name);
create index if not exists supplier_price_snapshots_provider_idx on public.supplier_price_snapshots(provider);
create index if not exists supplier_price_snapshots_captured_at_idx on public.supplier_price_snapshots(captured_at desc);

alter table public.supplier_price_snapshots enable row level security;

drop policy if exists supplier_price_snapshots_select_admin_or_same_company on public.supplier_price_snapshots;
create policy supplier_price_snapshots_select_admin_or_same_company
on public.supplier_price_snapshots
for select
to authenticated
using (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
      and (
        p.role = 'admin'
        or p.company_id = supplier_price_snapshots.company_id
      )
  )
);

drop policy if exists supplier_price_snapshots_insert_admin on public.supplier_price_snapshots;
create policy supplier_price_snapshots_insert_admin
on public.supplier_price_snapshots
for insert
to authenticated
with check (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
      and p.role = 'admin'
  )
);

drop policy if exists supplier_price_snapshots_update_admin on public.supplier_price_snapshots;
create policy supplier_price_snapshots_update_admin
on public.supplier_price_snapshots
for update
to authenticated
using (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
      and p.role = 'admin'
  )
)
with check (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
      and p.role = 'admin'
  )
);

drop policy if exists supplier_price_snapshots_delete_admin on public.supplier_price_snapshots;
create policy supplier_price_snapshots_delete_admin
on public.supplier_price_snapshots
for delete
to authenticated
using (
  exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
      and p.role = 'admin'
  )
);
