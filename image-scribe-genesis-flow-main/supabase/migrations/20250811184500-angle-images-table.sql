-- Images table for angle review metadata
-- idempotent-ish migration: create table if not exists; add columns/indexes if missing

-- 1) Create table if missing
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema='public' AND table_name='images'
  ) THEN
    CREATE TABLE public.images (
      id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
      document_id UUID NOT NULL REFERENCES public.documents ON DELETE CASCADE,
      url TEXT NOT NULL,
      angle TEXT,
      category TEXT,
      is_closeup BOOLEAN NOT NULL DEFAULT FALSE,
      source TEXT,
      confidence DOUBLE PRECISION,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
  END IF;
END $$;

-- 2) Add columns if missing
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='images' AND column_name='angle') THEN
    ALTER TABLE public.images ADD COLUMN angle TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='images' AND column_name='category') THEN
    ALTER TABLE public.images ADD COLUMN category TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='images' AND column_name='is_closeup') THEN
    ALTER TABLE public.images ADD COLUMN is_closeup BOOLEAN NOT NULL DEFAULT FALSE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='images' AND column_name='source') THEN
    ALTER TABLE public.images ADD COLUMN source TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='images' AND column_name='confidence') THEN
    ALTER TABLE public.images ADD COLUMN confidence DOUBLE PRECISION;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='images' AND column_name='updated_at') THEN
    ALTER TABLE public.images ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
  END IF;
END $$;

-- 3) Unique index for upserts
CREATE UNIQUE INDEX IF NOT EXISTS images_document_id_url_uniq ON public.images(document_id, url);

-- 4) Angle index (exterior only)
CREATE INDEX IF NOT EXISTS images_document_id_angle_exterior_idx 
  ON public.images(document_id, angle) 
  WHERE category = 'exterior';

-- 5) Enable RLS and add policies similar to document_images
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='images'
  ) THEN
    -- table missing, nothing else to do here
    RETURN;
  END IF;
  
  EXECUTE 'ALTER TABLE public.images ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN others THEN NULL;
END $$;

-- Policies
DO $$
BEGIN
  -- SELECT policy
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='images' AND policyname='Users can view images of their own documents (images)'
  ) THEN
    CREATE POLICY "Users can view images of their own documents (images)"
      ON public.images
      FOR SELECT
      USING (EXISTS (
        SELECT 1 FROM public.documents 
        WHERE documents.id = images.document_id
        AND documents.user_id = auth.uid()
      ));
  END IF;

  -- INSERT policy
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='images' AND policyname='Users can create images for their own documents (images)'
  ) THEN
    CREATE POLICY "Users can create images for their own documents (images)"
      ON public.images
      FOR INSERT
      WITH CHECK (EXISTS (
        SELECT 1 FROM public.documents 
        WHERE documents.id = images.document_id
        AND documents.user_id = auth.uid()
      ));
  END IF;

  -- UPDATE policy
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='images' AND policyname='Users can update images for their own documents (images)'
  ) THEN
    CREATE POLICY "Users can update images for their own documents (images)"
      ON public.images
      FOR UPDATE
      USING (EXISTS (
        SELECT 1 FROM public.documents 
        WHERE documents.id = images.document_id
        AND documents.user_id = auth.uid()
      ));
  END IF;

  -- DELETE policy
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='images' AND policyname='Users can delete images of their own documents (images)'
  ) THEN
    CREATE POLICY "Users can delete images of their own documents (images)"
      ON public.images
      FOR DELETE
      USING (EXISTS (
        SELECT 1 FROM public.documents 
        WHERE documents.id = images.document_id
        AND documents.user_id = auth.uid()
      ));
  END IF;
END $$;
