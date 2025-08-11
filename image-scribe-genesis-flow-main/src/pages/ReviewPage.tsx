import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import type { Tables } from "@/integrations/supabase/types";
import AngleReviewBoard from "@/components/AngleReviewBoard";
import type { ReviewImage } from "@/components/AngleBucketPanel";
import { BACKEND_BASE_URL, FUNCTIONS_BASE_URL } from "@/lib/config";

export default function ReviewPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const [initialImages, setInitialImages] = useState<{ url: string; id?: string; category?: "exterior" | "interior" | "document" }[]>([]);
  const [loading, setLoading] = useState(true);
  const [classifying, setClassifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmedImages, setConfirmedImages] = useState<ReviewImage[] | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genResult, setGenResult] = useState<{ status?: string } | null>(null);

  const backendBaseUrl = BACKEND_BASE_URL;
  const functionsBaseUrl = FUNCTIONS_BASE_URL;

  useEffect(() => {
    if (!documentId) return;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        // Prefer enriched images first (cast table name to bypass generated types until updated)
        type ImageRow = {
          url: string;
          angle: string | null;
          category: "exterior" | "interior" | "document" | null;
          is_closeup: boolean | null;
          source: string | null;
          confidence: number | null;
        };
        const sbAny = supabase as unknown as {
          from: (table: string) => {
            select: (cols: string) => {
              eq: (col: string, val: string) => Promise<{ data: ImageRow[] | null; error: unknown | null }>;
            };
          };
        };
        const { data: enriched, error: enrichedErr } = await sbAny
          .from("images")
          .select("url, angle, category, is_closeup, source, confidence")
          .eq("document_id", documentId);

        if (enrichedErr) {
          console.warn("images query failed, will fallback:", enrichedErr);
        }

        const hasEnriched = enriched && enriched.length > 0;
        if (hasEnriched) {
          const rows = enriched as ImageRow[];
          const mapped = rows.filter((r) => !!r.url).map((r) => ({ url: r.url, category: (r.category ?? "exterior") as "exterior" | "interior" | "document" }));
          setInitialImages(mapped);
          // Decide if we need background classification
          const unknownExterior = rows.filter((r) => (r.category ?? 'exterior') === 'exterior').filter((r) => !r.angle || r.angle === 'unknown').length;
          if (unknownExterior > 0 && backendBaseUrl) {
            setClassifying(true);
            // Fire-and-forget start
            try { await fetch(`${backendBaseUrl}/angles/classify/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ document_id: documentId }) }); } catch (e) { console.warn('angles/classify/start failed', e); }
            // Poll status until complete or timeout (~60s)
            const tStart = Date.now();
            const deadline = tStart + 60000;
            while (Date.now() < deadline) {
              try {
                const res = await fetch(`${backendBaseUrl}/angles/classify/status?document_id=${encodeURIComponent(documentId)}`);
                if (res.ok) {
                  const s = await res.json();
                  if (s && typeof s.unknown_exterior === 'number' && s.unknown_exterior === 0) {
                    break;
                  }
                }
              } catch (e) { /* tolerate transient poll errors */ }
              await new Promise(r => setTimeout(r, 1200));
            }
            // Re-fetch enriched rows
            try {
              const { data: enriched2 } = await sbAny
                .from("images")
                .select("url, angle, category, is_closeup, source, confidence")
                .eq("document_id", documentId);
              if (enriched2 && enriched2.length) {
                const rows2 = enriched2 as ImageRow[];
                setInitialImages(rows2.filter(r => !!r.url).map(r => ({ url: r.url, category: (r.category ?? 'exterior') as 'exterior' | 'interior' | 'document' })));
              }
            } catch (e) { console.warn('re-fetch enriched images failed', e); }
            setClassifying(false);
          }
          setLoading(false);
          return;
        }

        // Fallback to legacy document_images
        const { data: legacy, error: legacyErr } = await supabase
          .from("document_images")
          .select("image_url")
          .eq("document_id", documentId);
        if (legacyErr) throw legacyErr;
        const legacyRows = (legacy ?? []) as Pick<Tables<'document_images'>, 'image_url'>[];
        setInitialImages(legacyRows.map((r) => ({ url: r.image_url, category: "exterior" })));
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'Failed to load images';
        setError(msg);
      } finally {
        setLoading(false);
      }
    })();
  }, [documentId, backendBaseUrl]);

  const canGenerate = useMemo(() => {
    return !!confirmedImages && confirmedImages.length > 0;
  }, [confirmedImages]);

  const handleConfirm = (imgs: ReviewImage[]) => {
    setConfirmedImages(imgs);
  };

  const triggerGenerate = async () => {
    if (!documentId) return;
    if (!functionsBaseUrl) {
      alert("Missing FUNCTIONS_BASE_URL. Set VITE_SUPABASE_FUNCTIONS_URL in your env.");
      return;
    }
    try {
      setGenerating(true);
      setGenResult(null);
      const res = await fetch(`${functionsBaseUrl}/generate_report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: documentId }),
      });
      const data = await res.json().catch(() => ({}));
      setGenResult(data);
      if (!res.ok) {
        throw new Error(`Edge function returned ${res.status}`);
      }
      // Expect 202 queued
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to start generation';
      setError(msg);
    } finally {
      setGenerating(false);
    }
  };

  if (!documentId) return <div className="p-4">Missing documentId</div>;
  if (loading) return <div className="p-4">Loading images…</div>;
  if (classifying) return <div className="p-4">Classifying angles in background…</div>;
  if (error) return <div className="p-4 text-red-600">{error}</div>;

  return (
    <div className="p-4 space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Review Angles for Document {documentId}</h1>
        <p className="text-sm text-gray-500">Backend: {backendBaseUrl || "<not set>"} · Functions: {functionsBaseUrl || "<not set>"}</p>
      </div>

      <AngleReviewBoard
        documentId={documentId}
        backendBaseUrl={backendBaseUrl}
        initialImages={initialImages}
        onConfirm={handleConfirm}
        autoClassifyOnMount={false}
      />

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={!canGenerate || generating}
          onClick={triggerGenerate}
          className="px-3 py-2 rounded bg-blue-600 text-white disabled:opacity-50"
        >
          {generating ? "Starting…" : "Generate Report"}
        </button>
        {genResult && (
          <span className="text-sm text-gray-600">{genResult.status ? `Status: ${genResult.status}` : ""}</span>
        )}
      </div>
    </div>
  );
}
