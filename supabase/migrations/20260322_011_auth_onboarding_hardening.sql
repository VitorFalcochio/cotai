create extension if not exists unaccent;

alter table if exists public.companies add column if not exists slug text;
alter table if exists public.companies add column if not exists legal_name text;
alter table if exists public.companies add column if not exists tax_id text;
alter table if exists public.companies add column if not exists settings jsonb not null default '{}'::jsonb;

alter table if exists public.billing_subscriptions add column if not exists metadata jsonb not null default '{}'::jsonb;

create or replace function public.normalize_company_slug(value text)
returns text
language plpgsql
immutable
as $$
declare
  cleaned text;
begin
  cleaned := lower(unaccent(coalesce(value, '')));
  cleaned := regexp_replace(cleaned, '[^a-z0-9]+', '-', 'g');
  cleaned := regexp_replace(cleaned, '(^-+|-+$)', '', 'g');
  cleaned := regexp_replace(cleaned, '-{2,}', '-', 'g');
  if cleaned = '' then
    cleaned := 'empresa';
  end if;
  return cleaned;
end;
$$;

create or replace function public.generate_unique_company_slug(base_name text, preferred_company_id uuid default null)
returns text
language plpgsql
volatile
as $$
declare
  base_slug text;
  candidate text;
  suffix integer := 1;
begin
  base_slug := public.normalize_company_slug(base_name);
  candidate := base_slug;

  while exists (
    select 1
    from public.companies c
    where c.slug = candidate
      and (preferred_company_id is null or c.id <> preferred_company_id)
  ) loop
    suffix := suffix + 1;
    candidate := base_slug || '-' || suffix::text;
  end loop;

  return candidate;
end;
$$;

update public.companies
set slug = public.generate_unique_company_slug(name, id)
where coalesce(slug, '') = '';

create unique index if not exists companies_slug_key on public.companies(slug);

do $$
begin
  if exists (
    select 1
    from pg_constraint
    where conname = 'companies_plan_check'
  ) then
    alter table public.companies drop constraint companies_plan_check;
  end if;

  alter table public.companies
    add constraint companies_plan_check
    check (plan in ('starter', 'silver', 'gold', 'diamond'));
exception
  when duplicate_object then
    null;
end $$;

do $$
begin
  if exists (
    select 1
    from pg_constraint
    where conname = 'billing_subscriptions_plan_check'
  ) then
    alter table public.billing_subscriptions drop constraint billing_subscriptions_plan_check;
  end if;

  alter table public.billing_subscriptions
    add constraint billing_subscriptions_plan_check
    check (plan in ('starter', 'silver', 'gold', 'diamond'));
exception
  when duplicate_object then
    null;
end $$;

update public.companies
set plan = case lower(coalesce(plan, ''))
  when '' then 'starter'
  when 'trial' then 'starter'
  else lower(plan)
end
where lower(coalesce(plan, '')) not in ('starter', 'silver', 'gold', 'diamond');

update public.billing_subscriptions
set plan = case lower(coalesce(plan, ''))
  when '' then 'starter'
  when 'trial' then 'starter'
  else lower(plan)
end
where lower(coalesce(plan, '')) not in ('starter', 'silver', 'gold', 'diamond');

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  requested_company_name text;
  effective_full_name text;
  existing_profile public.profiles%rowtype;
  target_company_id uuid;
  created_company_id uuid;
  normalized_plan text;
  role_to_apply text;
begin
  requested_company_name := nullif(trim(coalesce(new.raw_user_meta_data ->> 'company_name', '')), '');
  effective_full_name := coalesce(
    nullif(trim(new.raw_user_meta_data ->> 'full_name'), ''),
    requested_company_name,
    split_part(new.email, '@', 1)
  );

  select *
  into existing_profile
  from public.profiles
  where id = new.id;

  target_company_id := existing_profile.company_id;
  normalized_plan := lower(coalesce(existing_profile.plan, '', new.raw_user_meta_data ->> 'plan', 'starter'));
  if normalized_plan not in ('starter', 'silver', 'gold', 'diamond') then
    normalized_plan := 'starter';
  end if;

  if target_company_id is null and requested_company_name is not null then
    insert into public.companies (
      name,
      slug,
      plan,
      status,
      owner_user_id,
      settings,
      created_at,
      updated_at
    )
    values (
      requested_company_name,
      public.generate_unique_company_slug(requested_company_name),
      normalized_plan,
      'trial',
      new.id,
      '{}'::jsonb,
      now(),
      now()
    )
    returning id into created_company_id;

    target_company_id := created_company_id;
  end if;

  role_to_apply := case
    when created_company_id is not null then 'owner'
    when coalesce(existing_profile.role, '') in ('member', 'admin', 'owner') then existing_profile.role
    else 'member'
  end;

  insert into public.profiles (
    id,
    email,
    full_name,
    company_name,
    company_id,
    role,
    status,
    plan,
    created_at,
    updated_at
  )
  values (
    new.id,
    new.email,
    effective_full_name,
    requested_company_name,
    target_company_id,
    role_to_apply,
    'active',
    normalized_plan,
    now(),
    now()
  )
  on conflict (id) do update
  set email = excluded.email,
      full_name = coalesce(nullif(public.profiles.full_name, ''), excluded.full_name),
      company_name = coalesce(nullif(public.profiles.company_name, ''), excluded.company_name),
      company_id = coalesce(public.profiles.company_id, excluded.company_id),
      plan = coalesce(nullif(public.profiles.plan, ''), excluded.plan),
      role = case
        when public.profiles.role in ('member', 'admin', 'owner') then public.profiles.role
        else excluded.role
      end,
      status = coalesce(nullif(public.profiles.status, ''), excluded.status),
      updated_at = now();

  if created_company_id is not null then
    insert into public.billing_subscriptions (
      company_id,
      plan,
      status,
      monthly_amount,
      mrr,
      amount_cents,
      metadata,
      created_at,
      updated_at
    )
    values (
      created_company_id,
      normalized_plan,
      'trial',
      0,
      0,
      0,
      jsonb_build_object('source', 'auth_onboarding'),
      now(),
      now()
    )
    on conflict do nothing;
  end if;

  return new;
end;
$$;
