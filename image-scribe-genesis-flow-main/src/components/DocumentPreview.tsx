import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import Spinner from "@/components/ui/Spinner";
import { Button } from "@/components/ui/button";

interface Props {
  documentId: string | null;
}

type DocRow = {
  id: string;
  status: string;
  report_json: any | null;
  edited_report_json: any | null;
  report_pdf_url: string | null;
};

const DocumentPreview = ({ documentId }: Props) => {
  const [doc, setDoc] = useState<DocRow | null>(null);
  const [loading, setLoading] = useState(false);

  // Subscribe to realtime updates for this document
  useEffect(() => {
    if (!documentId) {
      setDoc(null);
      return;
    }
    setLoading(true);
    const channel = supabase
      .channel("doc-" + documentId)
      .on(
        "postgres_changes",
        { event: "UPDATE", schema: "public", table: "documents", filter: `id=eq.${documentId}` },
        (payload) => {
          setDoc(payload.new as DocRow);
        }
      )
      .subscribe();

    // Fetch the initial
    (async () => {
      const { data } = await supabase
        .from("documents")
        .select("id,status,report_json,edited_report_json,report_pdf_url")
        .eq("id", documentId)
        .single();
      setDoc(data as DocRow);
      setLoading(false);
    })();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [documentId]);

  if (!documentId) return <p className="text-gray-500">No document selected.</p>;
  if (loading || !doc) return <Spinner />;

  if (doc.status === "processing") {
    return (
      <div className="flex flex-col items-center justify-center space-y-2 text-gray-600">
        <Spinner />
        <p>Generating report…</p>
      </div>
    );
  }

  if (!doc.report_json) {
    return <p className="text-gray-500">Report not generated yet.</p>;
  }

  const overview = doc.report_json?.overview || [];
  return (
    <div className="space-y-4">
      {/* Very simple overview list */}
      <ul className="list-disc list-inside text-sm">
        {overview.map((item: any, idx: number) => (
          <li key={idx}>{item.part} – {item.severity}</li>
        ))}
      </ul>

      {doc.report_pdf_url && (
        <Button asChild className="w-full">
          <a href={doc.report_pdf_url} target="_blank" rel="noopener noreferrer">Download PDF</a>
        </Button>
      )}
      <Button className="w-full" onClick={async () => {
        const body = {
          document_id: doc.id,
          json: doc.edited_report_json ?? doc.report_json,
        };
        const res = await fetch(`${import.meta.env.VITE_REPORT_SERVICE_URL}/pdf-from-json`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (res.ok) {
          const { pdf_url } = await res.json();
          window.open(pdf_url, "_blank");
        }
      }}>Re-generate PDF</Button>
    </div>
  );
};

export default DocumentPreview;
