alter table if exists public.suppliers
  add column if not exists address_line text,
  add column if not exists postal_code text,
  add column if not exists latitude numeric,
  add column if not exists longitude numeric;

create index if not exists suppliers_city_state_idx on public.suppliers(city, state);
