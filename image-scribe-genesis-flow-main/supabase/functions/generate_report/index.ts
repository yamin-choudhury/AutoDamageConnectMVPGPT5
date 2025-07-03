import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// Environment variables are injected automatically by the Supabase runtime
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const REPORT_SERVICE_URL = Deno.env.get("REPORT_SERVICE_URL")!; // e.g. https://damage-report-service.example.com

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

    // 1. Fetch the document with small retry loop to avoid race condition right after insert
    let doc: any = null;
    let attempts = 0;
    while (attempts < 3 && !doc) {
      const { data, error } = await supabase
        .from("documents")
        .select("*")
        .eq("id", document_id)
        .single();
      if (!error && data) {
        doc = data;
      } else {
        console.warn("Doc fetch attempt", attempts + 1, error);
        await new Promise((r) => setTimeout(r, 300));
      }
      attempts += 1;
    }

    if (!doc) {
      return new Response("Document not found", { status: 404, headers: corsHeaders });
    }

    // mark as processing AFTER we know the doc exists
    await supabase.from("documents").update({ status: "processing" }).eq("id", document_id);

    // fetch related images (if any) separately
    const { data: images } = await supabase
      .from("images")
      .select("url")
      .eq("document_id", document_id);

    const docWithImages = { ...doc, images: images || [] };

    // 3. Call the Python report service
    const backendResp = await fetch(`${REPORT_SERVICE_URL}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document: docWithImages,
      }),
    });

    if (!backendResp.ok) {
      console.error("Report service error", await backendResp.text());
      await supabase.from("documents").update({ status: "error" }).eq("id", document_id);
      return new Response("Report generation failed", { status: 502, headers: corsHeaders });
    }

    const { json_url, pdf_url } = await backendResp.json();

    // Fetch the generated JSON so we can store it inline for quick preview
    let reportJson: any = null;
    try {
      const jsonResp = await fetch(json_url);
      if (jsonResp.ok) {
        reportJson = await jsonResp.json();
      }
    } catch (_e) {
      // non-fatal, we’ll still store the URL
      console.warn("Unable to fetch JSON from", json_url);
    }

    // 4. Save data & set status ready
    await supabase
      .from("documents")
      .update({
        status: "ready",
        report_json: reportJson,
        report_json_url: json_url,
        report_pdf_url: pdf_url,
      })
      .eq("id", document_id);

    return new Response(JSON.stringify({ json_url, pdf_url }), {
      headers: { "Content-Type": "application/json", ...corsHeaders },
    });
  } catch (e) {
    console.error("Unhandled error", e);
    return new Response("Internal error", { status: 500, headers: corsHeaders });
  }
});
