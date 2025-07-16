import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
);

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
    return new Response("Method not allowed", { 
      status: 405, 
      headers: corsHeaders 
    });
  }

  try {
    const { document_id, json_url, pdf_url, report_json } = await req.json();
    
    if (!document_id || !json_url || !pdf_url) {
      return new Response("Missing required fields", {
        status: 400,
        headers: corsHeaders,
      });
    }

    console.log(`📥 Webhook received for document ${document_id}`);
    console.log(`   JSON URL: ${json_url}`);
    console.log(`   PDF URL: ${pdf_url}`);

    // Update document with report data
    const { error } = await supabase
      .from("documents")
      .update({
        status: "ready",
        report_json: report_json, // Store the actual JSON content
        report_json_url: json_url,
        report_pdf_url: pdf_url,
        updated_at: new Date().toISOString(),
      })
      .eq("id", document_id);

    if (error) {
      console.error("Database update error:", error);
      throw error;
    }

    console.log(`✅ Report ${document_id} marked as ready`);
    
    return new Response(JSON.stringify({ success: true }), {
      headers: { "Content-Type": "application/json", ...corsHeaders },
    });
    
  } catch (error) {
    console.error("Webhook error:", error);
    return new Response(JSON.stringify({ error: "Internal server error" }), {
      status: 500,
      headers: { "Content-Type": "application/json", ...corsHeaders },
    });
  }
});
