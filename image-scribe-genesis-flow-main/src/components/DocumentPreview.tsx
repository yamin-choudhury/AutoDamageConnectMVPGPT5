import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import Spinner from "@/components/ui/Spinner";
import { Button } from "@/components/ui/button";
import ReportViewer from "@/components/ReportViewer";
import { useToast } from "@/hooks/use-toast";

interface Props {
  documentId: string | null;
}

type DocRow = {
  id: string;
  status: string;
  report_json: any;
  report_pdf_url: string | null;
};

const DocumentPreview = ({ documentId }: Props) => {
  const [doc, setDoc] = useState<DocRow | null>(null);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  // Subscribe to realtime updates for this document
  useEffect(() => {
    if (!documentId) {
      setDoc(null);
      return;
    }
    
    setLoading(true);
    
    // Fetch initial document data
    const fetchDocument = async () => {
      const { data, error } = await supabase
        .from("documents")
        .select("id,status,report_pdf_url,report_json")
        .eq("id", documentId)
        .single();
      
      console.log('DocumentPreview fetch result:', { data, error, documentId });
      
      if (data) {
        setDoc(data as DocRow);
      }
      setLoading(false);
    };
    
    fetchDocument();
    
    // Set up real-time subscription
    const channel = supabase
      .channel("doc-updates-" + documentId)
      .on(
        "postgres_changes",
        { 
          event: "UPDATE", 
          schema: "public", 
          table: "documents", 
          filter: `id=eq.${documentId}` 
        },
        (payload) => {
          console.log('🔔 Real-time update received:', payload.new);
          setDoc(payload.new as DocRow);
          
          // Show toast notification when status changes to ready
          if (payload.new.status === 'ready') {
            console.log('✅ Document is now ready!');
            toast({
              title: "Report Ready! 🎉",
              description: "Your damage report has been generated and is ready to view.",
              variant: "default",
            });
          }
        }
      )
      .subscribe();
    
    // Also poll every 5 seconds as backup for critical status changes
    const pollInterval = setInterval(() => {
      console.log('🔄 Polling for document updates...');
      fetchDocument();
    }, 5000);

    return () => {
      supabase.removeChannel(channel);
      clearInterval(pollInterval);
    };
  }, [documentId, toast]);

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

  console.log('DocumentPreview render check:', { 
    status: doc.status, 
    has_pdf: !!doc.report_pdf_url, 
    has_json: !!doc.report_json,
    report_json_preview: doc.report_json ? 'has data' : 'null/undefined'
  });

  if (doc.status === "ready" && (doc.report_pdf_url || doc.report_json)) {
    console.log('Showing ReportViewer for documentId:', documentId);
    // Report is ready - show in-app viewer with download capability
    return <ReportViewer documentId={documentId} />;
  }

  // Fallback for other statuses
  return (
    <div className="text-center space-y-4">
      <p className="text-gray-500">Status: {doc.status}</p>
      {doc.status === "draft" && (
        <p className="text-sm">Upload images and generate your report.</p>
      )}
      {doc.status === "error" && (
        <p className="text-sm text-red-600">Report generation failed. Please try again.</p>
      )}
    </div>
  );
};

export default DocumentPreview;
