
import { useState, useEffect, useCallback } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { History, Plus, FileText } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface Document {
  id: string;
  title: string;
  vin?: string;
  make?: string;
  model?: string;
  status: string;
  created_at: string;
}

interface HistorySidebarProps {
  onSelectDocument: (documentId: string | null) => void;
  selectedDocumentId: string | null;
  showOnlyReady?: boolean; // Filter to show only ready documents
}

const HistorySidebar = ({ onSelectDocument, selectedDocumentId, showOnlyReady = false }: HistorySidebarProps) => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  const fetchDocuments = useCallback(async () => {
    try {
      let query = supabase
        .from('documents')
        .select('id, title, vin, make, model, status, created_at')
        .order('created_at', { ascending: false });
      
      // Filter to only ready documents if requested
      if (showOnlyReady) {
        query = query.eq('status', 'ready');
      }

      const { data, error } = await query;
      if (error) throw error;
      
      console.log(`📋 Fetched ${data?.length || 0} documents${showOnlyReady ? ' (ready only)' : ''}`);
      setDocuments(data || []);
    } catch (error) {
      console.error('Error fetching documents:', error);
      toast({
        title: "Error",
        description: "Failed to load document history",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [toast, showOnlyReady]);

  useEffect(() => {
    fetchDocuments();
    
    // Subscribe to realtime updates for documents
    const channel = supabase
      .channel('documents-sidebar')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'documents' },
        () => {
          console.log('Document change detected, refetching...');
          // Refetch documents when any document changes
          fetchDocuments();
        }
      )
      .subscribe();

    // Also poll every 10 seconds as backup
    const pollInterval = setInterval(fetchDocuments, 10000);

    return () => {
      supabase.removeChannel(channel);
      clearInterval(pollInterval);
    };
  }, [fetchDocuments]);

  const handleNewDocument = () => {
    onSelectDocument(null);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready':
      case 'completed':
        return 'text-green-600';
      case 'processing':
        return 'text-blue-600';
      case 'error':
      case 'failed':
        return 'text-red-600';
      case 'draft':
        return 'text-gray-600';
      default:
        return 'text-gray-500';
    }
  };

  return (
    <div className="w-80 bg-white/80 backdrop-blur-sm border-r border-gray-200 h-full flex flex-col">
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <History className="h-5 w-5 text-gray-600" />
            <h2 className="font-semibold text-gray-900">Document History</h2>
          </div>
        </div>
        
        <Button
          onClick={handleNewDocument}
          className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Document
        </Button>
      </div>

      <ScrollArea className="flex-1 p-4">
        {loading ? (
          <div className="text-center text-gray-500 py-8">Loading...</div>
        ) : documents.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <FileText className="h-12 w-12 mx-auto mb-2 text-gray-300" />
            <p>No documents yet</p>
            <p className="text-sm">Create your first document to get started</p>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => (
              <Card
                key={doc.id}
                className={`cursor-pointer transition-all hover:shadow-md ${
                  selectedDocumentId === doc.id
                    ? 'ring-2 ring-blue-500 shadow-md'
                    : 'hover:bg-gray-50'
                }`}
                onClick={() => onSelectDocument(doc.id)}
              >
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium truncate">
                    {doc.title}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="space-y-1 text-xs text-gray-600">
                    {doc.vin && (
                      <p><span className="font-medium">VIN:</span> {doc.vin}</p>
                    )}
                    {(doc.make || doc.model) && (
                      <p>
                        <span className="font-medium">Vehicle:</span> {doc.make} {doc.model}
                      </p>
                    )}
                    <div className="flex justify-between items-center pt-2">
                      <span className={`font-medium ${getStatusColor(doc.status)}`}>
                        {doc.status.charAt(0).toUpperCase() + doc.status.slice(1)}
                      </span>
                      <span className="text-gray-400">
                        {formatDate(doc.created_at)}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
};

export default HistorySidebar;
