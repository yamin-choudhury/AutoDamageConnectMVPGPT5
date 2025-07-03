import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { Storage } from "npm:@google-cloud/storage@6";

const PROJECT_ID = Deno.env.get("GCS_PROJECT_ID")!;
const BUCKET = Deno.env.get("GCS_BUCKET")!;
const CLIENT_EMAIL = Deno.env.get("GCS_CLIENT_EMAIL")!;
const PRIVATE_KEY = (Deno.env.get("GCS_PRIVATE_KEY") || "").replace(/\\n/g, "\n");

const storage = new Storage({
  projectId: PROJECT_ID,
  credentials: {
    client_email: CLIENT_EMAIL,
    private_key: PRIVATE_KEY,
  },
});
const bucket = storage.bucket(BUCKET);

const corsHeaders: Record<string, string> = {
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
    const { key, contentType = "application/octet-stream" } = await req.json();
    if (!key || typeof key !== "string") {
      return new Response("Missing key", { status: 400, headers: corsHeaders });
    }

    const file = bucket.file(key);
    const [url] = await file.getSignedUrl({
      version: "v4",
      action: "write",
      expires: Date.now() + 15 * 60 * 1000,
      contentType,
    });

    const publicUrl = `https://storage.googleapis.com/${BUCKET}/${key}`;

    return new Response(JSON.stringify({ url, publicUrl }), {
      headers: { "Content-Type": "application/json", ...corsHeaders },
    });
  } catch (e) {
    console.error("GCS presign error", e);
    return new Response("Error generating URL", { status: 500, headers: corsHeaders });
  }
});
