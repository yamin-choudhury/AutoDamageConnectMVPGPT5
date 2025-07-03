-- Enable RLS and create select policy so that users only see their own documents
alter table documents enable row level security;

create policy if not exists "documents_owner_select"
  on documents
  for select
  using (auth.uid() = user_id);
