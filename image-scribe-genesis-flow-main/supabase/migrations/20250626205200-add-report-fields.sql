-- Add status, report_json, report_pdf_url to documents and create images table
alter table public.documents
  add column if not exists status text not null default 'draft' check (status in ('draft','processing','ready','error')),
  add column if not exists report_json jsonb,
  add column if not exists report_pdf_url text;

create table if not exists public.images (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  storage_path text not null,
  created_at timestamptz default now()
);

-- Enable realtime on documents
alter publication supabase_realtime add table public.documents;
