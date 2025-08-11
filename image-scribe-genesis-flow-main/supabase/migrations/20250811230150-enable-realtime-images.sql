-- Enable Supabase Realtime for images (and legacy document_images) tables in an idempotent way
-- This ensures frontend can subscribe to per-document updates without polling.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
    -- Add public.images if not already in publication
    IF NOT EXISTS (
      SELECT 1 FROM pg_publication_tables
      WHERE pubname = 'supabase_realtime'
        AND schemaname = 'public'
        AND tablename = 'images'
    ) THEN
      ALTER PUBLICATION supabase_realtime ADD TABLE public.images;
    END IF;

    -- Optionally add legacy table for debugging/compatibility
    IF NOT EXISTS (
      SELECT 1 FROM pg_publication_tables
      WHERE pubname = 'supabase_realtime'
        AND schemaname = 'public'
        AND tablename = 'document_images'
    ) THEN
      ALTER PUBLICATION supabase_realtime ADD TABLE public.document_images;
    END IF;
  END IF;
END $$;

-- Ensure robust change payloads for updates/deletes
ALTER TABLE IF EXISTS public.images REPLICA IDENTITY FULL;
ALTER TABLE IF EXISTS public.document_images REPLICA IDENTITY FULL;
