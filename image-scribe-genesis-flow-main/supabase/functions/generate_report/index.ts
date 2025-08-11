import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const REPORT_SERVICE_URL = Deno.env.get("REPORT_SERVICE_URL")!;

const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405, headers: corsHeaders });
  }

  try {
    const { document_id } = await req.json();
    console.log('🔍 Edge function called with document_id:', document_id);
    
    if (!document_id) {
      console.error('❌ Missing document_id in request');
      return new Response("Missing document_id", { status: 400, headers: corsHeaders });
    }

    // Mark as processing
    console.log('📝 Marking document as processing:', document_id);
    await supabase.from("documents").update({ status: "processing" }).eq("id", document_id);

    // Fetch images with enriched metadata (images table → fallback to document_images)
    console.log('🖼️ Fetching images for document:', document_id);
    const { data: enrichedRows, error: enrichedErr } = await supabase
      .from("images")
      .select("url, angle, category, is_closeup, source, confidence")
      .eq("document_id", document_id);

    if (enrichedErr) {
      console.warn('⚠️ images table query failed, will attempt fallback:', enrichedErr);
    }

    let imagesPayload: Array<Record<string, unknown>> = [];
    if (enrichedRows && enrichedRows.length > 0) {
      imagesPayload = enrichedRows.map((r) => ({
        url: r.url,
        angle: r.angle ?? undefined,
        category: r.category ?? undefined,
        is_closeup: r.is_closeup ?? undefined,
        source: r.source ?? undefined,
        confidence: r.confidence ?? undefined,
      }));
      console.log('✅ Using enriched images from images table:', imagesPayload.length);
    } else {
      console.log('ℹ️ No enriched rows found in images; falling back to document_images');
      const { data: imageRows, error: imgErr } = await supabase
        .from("document_images")
        .select("image_url")
        .eq("document_id", document_id);
      if (imgErr) {
        console.error('❌ Failed to fetch fallback images:', imgErr);
        await supabase.from("documents").update({ status: "error" }).eq("id", document_id);
        return new Response("Failed to fetch images", { status: 500, headers: corsHeaders });
      }
      const signedUrls = imageRows?.map((r) => r.image_url) ?? [];
      console.log('🔗 Fallback signed URLs found:', signedUrls.length);
      if (!signedUrls.length) {
        console.error('❌ No images found for document:', document_id);
        await supabase.from("documents").update({ status: "error" }).eq("id", document_id);
        return new Response("No images found for document", { status: 400, headers: corsHeaders });
      }
      imagesPayload = signedUrls.map((url) => ({ url }));
    }

    // Call backend generator and return immediately
    const { data: docData } = await supabase.from("documents").select("*").eq("id", document_id).single();
    fetch(`${REPORT_SERVICE_URL}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document: {
          ...docData,
          images: imagesPayload,
        }
      })
    }).catch(console.error);

    return new Response(JSON.stringify({
      message: "Report generation started",
      document_id,
      status: "processing"
    }), {
      headers: { "Content-Type": "application/json", ...corsHeaders }
    });
  } catch (e) {
    console.error("Error:", e);
    return new Response("Internal error", { status: 500, headers: corsHeaders });
  }
});
