import { useEffect, useRef, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Textarea } from "@/components/ui/textarea";
import Spinner from "@/components/ui/Spinner";
import { toast } from "@/components/ui/use-toast";

interface Props {
  documentId: string;
}

const ReportEditor = ({ documentId }: Props) => {
  const [jsonText, setJsonText] = useState<string>("{}");
  const [loading, setLoading] = useState(true);
  const saveTimer = useRef<NodeJS.Timeout | null>(null);

  // fetch initial JSON
  useEffect(() => {
    let canceled = false;
    (async () => {
      const { data, error } = await supabase
        .from("documents")
        .select("report_json, edited_report_json")
        .eq("id", documentId)
        .single();
      if (error || canceled) return;
      const src = (data?.edited_report_json ?? data?.report_json) || {};
      setJsonText(JSON.stringify(src, null, 2));
      setLoading(false);
    })();
    return () => {
      canceled = true;
    };
  }, [documentId]);

  // debounce save
  const scheduleSave = (newVal: string) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      try {
        const parsed = JSON.parse(newVal);
        const { error } = await supabase
          .from("documents")
          .update({ edited_report_json: parsed })
          .eq("id", documentId);
        if (error) throw error;
        toast({ title: "Saved", description: "Report updated" });
      } catch (e: any) {
        toast({ title: "Invalid JSON", description: e.message, variant: "destructive" });
      }
    }, 1200);
  };

  if (loading) return <Spinner />;

  return (
    <Textarea
      className="h-[500px] w-full font-mono text-xs"
      value={jsonText}
      onChange={(e) => {
        setJsonText(e.target.value);
        scheduleSave(e.target.value);
      }}
    />
  );
};

export default ReportEditor;
