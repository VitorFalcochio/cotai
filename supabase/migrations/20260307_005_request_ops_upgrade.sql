alter table if exists public.requests
  add column if not exists priority text default 'MEDIUM';

alter table if exists public.requests
  add column if not exists sla_due_at timestamptz;

alter table if exists public.requests
  add column if not exists approval_required boolean not null default false;

alter table if exists public.requests
  add column if not exists approval_status text default 'NOT_REQUIRED';

alter table if exists public.requests
  add column if not exists approved_at timestamptz;

alter table if exists public.requests
  add column if not exists approved_by_user_id uuid references auth.users(id) on delete set null;

alter table if exists public.requests
  add column if not exists duplicate_of_request_id uuid references public.requests(id) on delete set null;

alter table if exists public.requests
  add column if not exists duplicate_score numeric;

create index if not exists requests_priority_idx on public.requests(priority);
create index if not exists requests_sla_due_at_idx on public.requests(sla_due_at desc);
create index if not exists requests_approval_status_idx on public.requests(approval_status);
create index if not exists requests_duplicate_of_request_id_idx on public.requests(duplicate_of_request_id);
