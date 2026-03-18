do $$
begin
  update public.companies
  set plan = case lower(coalesce(plan, ''))
    when 'prata' then 'silver'
    when 'ouro' then 'gold'
    when 'diamante' then 'diamond'
    else coalesce(plan, 'silver')
  end
  where plan is distinct from case lower(coalesce(plan, ''))
    when 'prata' then 'silver'
    when 'ouro' then 'gold'
    when 'diamante' then 'diamond'
    else coalesce(plan, 'silver')
  end;

  update public.profiles
  set plan = case lower(coalesce(plan, ''))
    when 'prata' then 'silver'
    when 'ouro' then 'gold'
    when 'diamante' then 'diamond'
    else coalesce(plan, 'silver')
  end
  where plan is not null
    and plan is distinct from case lower(coalesce(plan, ''))
      when 'prata' then 'silver'
      when 'ouro' then 'gold'
      when 'diamante' then 'diamond'
      else coalesce(plan, 'silver')
    end;

  update public.billing_subscriptions
  set plan = case lower(coalesce(plan, ''))
    when 'prata' then 'silver'
    when 'ouro' then 'gold'
    when 'diamante' then 'diamond'
    else coalesce(plan, 'silver')
  end
  where plan is distinct from case lower(coalesce(plan, ''))
    when 'prata' then 'silver'
    when 'ouro' then 'gold'
    when 'diamante' then 'diamond'
    else coalesce(plan, 'silver')
  end;
end $$;

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
    check (plan in ('silver', 'gold', 'diamond'));
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
    check (plan in ('silver', 'gold', 'diamond'));
exception
  when duplicate_object then
    null;
end $$;

update public.billing_subscriptions
set
  monthly_amount = case lower(coalesce(plan, 'silver'))
    when 'silver' then 89
    when 'gold' then 189
    when 'diamond' then 499
    else monthly_amount
  end,
  mrr = case lower(coalesce(plan, 'silver'))
    when 'silver' then 89
    when 'gold' then 189
    when 'diamond' then 499
    else mrr
  end,
  amount_cents = case lower(coalesce(plan, 'silver'))
    when 'silver' then 8900
    when 'gold' then 18900
    when 'diamond' then 49900
    else amount_cents
  end
where coalesce(monthly_amount, 0) = 0
   or coalesce(mrr, 0) = 0
   or coalesce(amount_cents, 0) = 0;

drop policy if exists billing_subscriptions_insert_admin_only on public.billing_subscriptions;
create policy billing_subscriptions_insert_admin_only
on public.billing_subscriptions
for insert
to authenticated
with check (public.is_admin());
