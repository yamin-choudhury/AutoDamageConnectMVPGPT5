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
    if (!document_id) {
      return new Response("Missing document_id", { status: 400, headers: corsHeaders });
    }

    // Mark as processing
    await supabase.from("documents").update({ status: "processing" }).eq("id", document_id);

    // Fetch images
    const { data: imageRows, error: imgErr } = await supabase
      .from("document_images")
      .select("image_url")
      .eq("document_id", document_id);
    
    if (imgErr) {
      await supabase.from("documents").update({ status: "error" }).eq("id", document_id);
      return new Response("Failed to fetch images", { status: 500, headers: corsHeaders });
    }

    const signedUrls = imageRows?.map(r => r.image_url) ?? [];
    if (!signedUrls.length) {
      await supabase.from("documents").update({ status: "error" }).eq("id", document_id);
      return new Response("No images", { status: 400, headers: corsHeaders });
    }

    // Call Railway and return immediately
    fetch(`${REPORT_SERVICE_URL}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document: {
          ...(await supabase.from("documents").select("*").eq("id", document_id).single()).data,
          images: signedUrls.map((url) => ({ url }))
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
