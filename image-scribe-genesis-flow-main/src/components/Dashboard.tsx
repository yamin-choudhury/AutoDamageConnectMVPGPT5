
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import DocumentPreview from "@/components/DocumentPreview";
import { User } from "@supabase/supabase-js";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { User as UserIcon } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import Spinner from "@/components/ui/Spinner";
import ImageUploader from "@/components/ImageUploader";
import HistorySidebar from "@/components/HistorySidebar";
import VehicleInfoForm from "@/components/VehicleInfoForm";
import AngleReviewBoard from "@/components/AngleReviewBoard";
import type { ReviewImage } from "@/components/AngleBucketPanel";
import { BACKEND_BASE_URL } from "@/lib/config";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface DashboardProps {
  user: User;
  onLogout: () => void;
}

interface VehicleInfo {
  vin: string;
  registrationPlate: string;
  make: string;
  model: string;
  year: string;
  trimBodyStyle: string;
}

interface DocumentRow {
  id: string;
  status?: string | null;
  created_at?: string | null;
  title?: string | null;
  vin?: string | null;
  registration_plate?: string | null;
  make?: string | null;
  model?: string | null;
  year?: string | null;
  trim_body_style?: string | null;
}

const Dashboard = ({ user, onLogout }: DashboardProps) => {
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [vehicleInfo, setVehicleInfo] = useState<VehicleInfo>({
    vin: '',
    registrationPlate: '',
    make: '',
    model: '',
    year: '',
    trimBodyStyle: '',
  });
  const [currentDocument, setCurrentDocument] = useState<DocumentRow | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [docStatus, setDocStatus] = useState<string | null>(null);
  const { toast } = useToast();
  const navigate = useNavigate();
  const [anglesReady, setAnglesReady] = useState<boolean | null>(null);
  const [angleClassifying, setAngleClassifying] = useState(false);
  const [angleTotals, setAngleTotals] = useState<{ total_exterior: number; unknown_exterior: number } | null>(null);
  // Realtime channel for images updates (one per selected document)
  const [imagesChannel, setImagesChannel] = useState<RealtimeChannel | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewImages, setReviewImages] = useState<{ url: string; id?: string; category?: "exterior" | "interior" | "document" }[]>([]);
  const [statusErrorCount, setStatusErrorCount] = useState(0);
  const backendBaseUrl = BACKEND_BASE_URL;

  // Helper minimal Supabase typed interfaces to avoid 'any'
  type SBSelectResult<T> = Promise<{ data: T[] | null; error: unknown | null }>;
  type SBFromSelect<T> = { select: (cols: string) => { eq: (col: string, val: string) => SBSelectResult<T> } };
  type SBClient = { from: <T = unknown>(table: string) => SBFromSelect<T> };
  const sbTyped = supabase as unknown as SBClient;

  // Helper to refresh server-computed angle totals and update UI state
  const refreshStatus = useCallback(async (docId: string) => {
    if (!backendBaseUrl) return;
    try {
      const res = await fetch(`${backendBaseUrl}/angles/classify/status?document_id=${encodeURIComponent(docId)}`);
      if (!res.ok) { setStatusErrorCount((c) => c + 1); return; }
      setStatusErrorCount(0);
      const s = await res.json();
      const totals = { total_exterior: s.total_exterior ?? 0, unknown_exterior: s.unknown_exterior ?? 0 };
      setAngleTotals(totals);
      // update readiness locally from totals (no DB roundtrip)
      if (totals.total_exterior > 0) setAnglesReady(totals.unknown_exterior === 0);
      if (totals.unknown_exterior === 0 && totals.total_exterior > 0) setAngleClassifying(false);
    } catch {
      setStatusErrorCount((c) => c + 1);
    }
  }, [backendBaseUrl]);

  // Check if angle review is complete for this document
  const checkAnglesComplete = useCallback(async (documentId: string): Promise<boolean> => {
    try {
      // Prefer enriched public.images; fall back logic: if none exist yet, consider not ready
      type ImgRow = { id?: string; category: 'exterior'|'interior'|'document'|null; angle: string | null };
      const { data: imgs, error } = await (sbTyped as unknown as { from: <T=ImgRow>(t: string) => SBFromSelect<T> })
        .from<ImgRow>('images')
        .select('id, category, angle')
        .eq('document_id', documentId);

      if (error) throw error;
      if (!imgs || imgs.length === 0) { setAnglesReady(false); return false; }

      const exterior = (imgs as ImgRow[]).filter((i) => (i.category ?? 'exterior') === 'exterior');
      if (exterior.length === 0) { setAnglesReady(false); return false; }

      const hasUnlabeled = exterior.some((i) => !i.angle || i.angle === 'unknown');
      setAnglesReady(!hasUnlabeled);
      return !hasUnlabeled;
    } catch (e) {
      console.error('Angle completeness check failed:', e);
      setAnglesReady(false);
      return false;
    }
  }, [sbTyped]);

  // Start background angle classification for a document (Realtime will push updates)
  const startAngleClassification = useCallback(async (docId: string) => {
    if (!backendBaseUrl) return;
    try {
      setAngleClassifying(true);
      // best-effort start
      await fetch(`${backendBaseUrl}/angles/classify/start`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ document_id: docId })
      }).catch((e) => { console.warn('angles/classify/start error', e); });
      // initial status fetch to seed UI; realtime events will drive subsequent updates
      await refreshStatus(docId);
    } catch (e) {
      console.warn('startAngleClassification failed', e);
      setAngleClassifying(false);
    }
  }, [backendBaseUrl, refreshStatus]);

  const retryAnglePolling = useCallback(async () => {
    if (!selectedDocumentId || !backendBaseUrl) return;
    setStatusErrorCount(0);
    await startAngleClassification(selectedDocumentId);
  }, [selectedDocumentId, backendBaseUrl, startAngleClassification]);

  // Cleanup realtime channel on unmount
  useEffect(() => {
    return () => { if (imagesChannel) { try { supabase.removeChannel(imagesChannel); } catch { /* ignore */ } } };
  }, [imagesChannel]);

  // On document selection, subscribe to realtime updates and fetch initial status
  useEffect(() => {
    const docId = selectedDocumentId;
    if (!docId || !backendBaseUrl) return;
    (async () => {
      // tear down existing channel
      if (imagesChannel) { try { supabase.removeChannel(imagesChannel); } catch { /* ignore */ } setImagesChannel(null); }
      // create new realtime subscription for this document
      const ch = supabase.channel(`images-${docId}`) as unknown as RealtimeChannel;
      ch.on('postgres_changes', { event: '*', schema: 'public', table: 'images', filter: `document_id=eq.${docId}` }, async (_payload: unknown) => {
        // whenever an image row changes, refresh totals
        await refreshStatus(docId);
      });
      await ch.subscribe();
      setImagesChannel(ch);
      // initial status fetch
      await refreshStatus(docId);
    })();
  }, [selectedDocumentId, backendBaseUrl, imagesChannel, refreshStatus]);

  useEffect(() => {
    const run = async () => {
      if (!selectedDocumentId) { setAnglesReady(null); return; }
      await checkAnglesComplete(selectedDocumentId);
    };
    void run();
  }, [selectedDocumentId, checkAnglesComplete]);

  const fetchDocument = useCallback(async (documentId: string) => {
    try {
      const { data, error } = await supabase
        .from('documents')
        .select('*')
        .eq('id', documentId)
        .single();

      if (error) throw error;

      setCurrentDocument(data);
      setVehicleInfo({
        vin: data.vin || '',
        registrationPlate: data.registration_plate || '',
        make: data.make || '',
        model: data.model || '',
        year: data.year || '',
        trimBodyStyle: data.trim_body_style || '',
      });
    } catch (error) {
      console.error('Error fetching document:', error);
      toast({
        title: "Error",
        description: "Failed to load document",
        variant: "destructive",
      });
    }
  }, [toast]);

  useEffect(() => {
    if (selectedDocumentId) {
      void fetchDocument(selectedDocumentId);
    } else {
      // Reset form for new document
      setVehicleInfo({
        vin: '',
        registrationPlate: '',
        make: '',
        model: '',
        year: '',
        trimBodyStyle: '',
      });
      setCurrentDocument(null);
    }
  }, [selectedDocumentId, fetchDocument]);

  const saveDocument = async (): Promise<string | null> => {
    try {
      if (selectedDocumentId) {
        // Update existing document
        const { error } = await supabase
          .from('documents')
          .update({
            vin: vehicleInfo.vin || null,
            registration_plate: vehicleInfo.registrationPlate || null,
            make: vehicleInfo.make || null,
            model: vehicleInfo.model || null,
            year: vehicleInfo.year || null,
            trim_body_style: vehicleInfo.trimBodyStyle || null,
            updated_at: new Date().toISOString(),
          })
          .eq('id', selectedDocumentId);

        if (error) throw error;
        return selectedDocumentId;
      } else {
        // Create new document
        const { data, error } = await supabase
          .from('documents')
          .insert({
            user_id: user.id,
            title: generateDocumentTitle(),
            vin: vehicleInfo.vin || null,
            registration_plate: vehicleInfo.registrationPlate || null,
            make: vehicleInfo.make || null,
            model: vehicleInfo.model || null,
            year: vehicleInfo.year || null,
            trim_body_style: vehicleInfo.trimBodyStyle || null,
          })
          .select()
          .single();

        if (error) throw error;
        setSelectedDocumentId(data.id);
        return data.id;
      }

      toast({
        title: "Success",
        description: "Document saved successfully",
      });
      return selectedDocumentId || null;
    } catch (error) {
      console.error('Error saving document:', error);
      toast({
        title: "Error",
        description: "Failed to save document",
        variant: "destructive",
      });
      return null;
    }
  };

  const generateDocumentTitle = () => {
    const parts = [vehicleInfo.make, vehicleInfo.model, vehicleInfo.year].filter(Boolean);
    return parts.length > 0 ? parts.join(' ') + ' Report' : 'Untitled Document';
  };

  // Check if we should show full-screen report
  const showFullscreenReport = selectedDocumentId && (docStatus === 'ready' || currentDocument?.status === 'ready');
  
  if (showFullscreenReport) {
    return (
      <div className="min-h-screen bg-gray-50 flex">
        {/* History Sidebar - Only Ready Documents */}
        <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Ready Reports</h2>
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => {
                  setSelectedDocumentId(null);
                  setDocStatus(null);
                  setIsGenerating(false);
                }}
              >
                ← Dashboard
              </Button>
            </div>
          </div>
          
          <div className="flex-1 overflow-auto">
            <HistorySidebar 
              onSelectDocument={(docId) => {
                setSelectedDocumentId(docId);
                setDocStatus('ready'); // Assume ready since we're filtering
              }}
              selectedDocumentId={selectedDocumentId}
              showOnlyReady={true} // New prop to filter only ready docs
            />
          </div>
          
          <div className="p-4 border-t border-gray-200">
            <div className="flex items-center space-x-2">
              <UserIcon className="h-5 w-5 text-gray-400" />
              <Button variant="outline" size="sm" onClick={onLogout}>Logout</Button>
            </div>
          </div>
        </div>
        
        {/* Full-screen report content */}
        <div className="flex-1 bg-white">
          <div className="bg-white border-b border-gray-200 px-6 py-4">
            <div className="flex justify-between items-center">
              <h1 className="text-xl font-bold text-gray-900">Vehicle Damage Report</h1>
              <span className="text-sm text-green-600 font-medium">✅ Report Ready</span>
            </div>
          </div>
          
          <div className="h-[calc(100vh-80px)] overflow-auto">
            <DocumentPreview documentId={selectedDocumentId} />
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 flex">
      {/* History Sidebar */}
      <HistorySidebar 
        onSelectDocument={setSelectedDocumentId}
        selectedDocumentId={selectedDocumentId}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center space-x-3">
                <h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  AutoDamageConnect
                </h1>
                {selectedDocumentId && (
                  <span className="text-sm text-gray-500">
                    • Editing: {currentDocument?.title || 'Loading...'}
                  </span>
                )}
              </div>
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2 text-sm text-gray-600">
                  <UserIcon size={16} />
                  <span>{user?.email}</span>
                </div>
                <Button onClick={onLogout} size="sm" className="border border-gray-300">
                  Logout
                </Button>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Welcome Section */}
            <Card className="shadow-lg border-0 bg-white/80 backdrop-blur-sm">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <CardTitle className="text-2xl">
                    {selectedDocumentId ? 'Edit Document' : 'Create New Document'}
                  </CardTitle>
                  {selectedDocumentId && (
                    <div className="mt-1">
                      {angleClassifying ? (
                        <span className="inline-flex items-center rounded-full px-2 py-1 bg-blue-50 text-blue-700 border border-blue-200 text-xs">
                          Angles {angleTotals ? `${Math.max(0, (angleTotals.total_exterior - angleTotals.unknown_exterior))}/${angleTotals.total_exterior}` : '…'}
                        </span>
                      ) : anglesReady === true ? (
                        <span className="inline-flex items-center rounded-full px-2 py-1 bg-green-50 text-green-700 border border-green-200 text-xs">
                          Angles ready
                        </span>
                      ) : null}
                    </div>
                  )}
                </div>
                <p className="text-gray-600">
                  {selectedDocumentId 
                    ? 'Update vehicle information and images for this document.'
                    : 'Fill in vehicle details and upload images to generate an intelligent document.'
                  }
                </p>
              </CardHeader>
            </Card>

            {/* Column 1: Forms */}
            <VehicleInfoForm 
              vehicleInfo={vehicleInfo}
              onVehicleInfoChange={setVehicleInfo}
            />

            {/* Upload Section */}
            <Card className="shadow-lg border-0 bg-white/80 backdrop-blur-sm">
              <CardHeader>
                <CardTitle className="text-xl">Upload Images</CardTitle>
                <p className="text-gray-600">
                  Select or drag and drop multiple images of the vehicle.
                </p>
              </CardHeader>
              <CardContent>
                <ImageUploader 
                  documentId={selectedDocumentId} 
                  onDocumentCreated={setSelectedDocumentId}
                  onUploadFinished={async ({ documentId }) => {
                    toast({ title: 'Classifying angles…', description: 'We are calculating image angles in the background.' });
                    await startAngleClassification(documentId);
                  }}
                />

                {/* Angle classification progress */}
                {selectedDocumentId && angleClassifying && (
                  <div className="mt-4 p-3 rounded-md bg-blue-50 border border-blue-200">
                    <div className="flex items-center justify-between text-sm text-blue-800">
                      <span>Calculating angles…</span>
                      <span>
                        {angleTotals ? `${Math.max(0, (angleTotals.total_exterior - angleTotals.unknown_exterior))}/${angleTotals.total_exterior}` : ''}
                      </span>
                    </div>
                    <Progress className="mt-2" value={angleTotals && angleTotals.total_exterior > 0 ? ((angleTotals.total_exterior - angleTotals.unknown_exterior) / angleTotals.total_exterior) * 100 : 0} />
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Preview Panel */}
            <Card className="shadow-lg border-0 bg-white/80 backdrop-blur-sm">
              <CardHeader>
                <CardTitle className="text-xl">Document Preview</CardTitle>
              </CardHeader>
              <CardContent>
                {selectedDocumentId ? (
                  <DocumentPreview documentId={selectedDocumentId} />
                ) : (
                  <p className="text-gray-500">Save a document to enable preview.</p>
                )}
              </CardContent>
            </Card>

            {/* Action Buttons */}
            <div className="flex flex-col lg:flex-row justify-end gap-4">
              <Button
                onClick={saveDocument}
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 px-6"
              >
                {selectedDocumentId ? 'Update' : 'Save'}
              </Button>
              {selectedDocumentId && (
                <Button
                  variant="outline"
                  onClick={async () => {
                    const docId = await saveDocument();
                    if (!docId) {
                      toast({ title: 'Error', description: 'Please save the document first', variant: 'destructive' });
                      return;
                    }
                    // load images for dialog with fallback to legacy table
                    try {
                      type ImageRow = { url: string; angle: string | null; category: 'exterior'|'interior'|'document'|null; is_closeup?: boolean|null; source?: string|null; confidence?: number|null };
                      const { data: enriched } = await sbTyped
                        .from<ImageRow>('images')
                        .select('url, angle, category, is_closeup, source, confidence')
                        .eq('document_id', docId);

                      if (enriched && enriched.length > 0) {
                        const mapped = enriched
                          .filter(r => !!r.url)
                          .map(r => ({ url: r.url, category: (r.category ?? 'exterior') as 'exterior'|'interior'|'document' }));
                        setReviewImages(mapped);

                        // if unknown exterior remain, kick/resume background classification & polling
                        const unknownExterior = enriched
                          .filter(r => (r.category ?? 'exterior') === 'exterior')
                          .filter(r => !r.angle || r.angle === 'unknown').length;
                        if (unknownExterior > 0 && backendBaseUrl && !angleClassifying) {
                          await startAngleClassification(docId);
                        }
                      } else {
                        // fallback to legacy document_images
                        const { data: legacy, error: legacyErr } = await supabase
                          .from('document_images')
                          .select('image_url')
                          .eq('document_id', docId);
                        if (legacyErr) { console.warn('legacy images query failed', legacyErr); }
                        const mappedLegacy = (legacy || []).map((r: { image_url: string }) => ({ url: r.image_url, category: 'exterior' as const }));
                        setReviewImages(mappedLegacy);
                      }
                    } catch (e) { console.warn('load images for review failed', e); }
                    setReviewOpen(true);
                  }}
                  className="border border-gray-300 px-6"
                >
                  {angleTotals ? `Review Angles (${Math.max(0, (angleTotals.total_exterior - angleTotals.unknown_exterior))}/${angleTotals.total_exterior})` : 'Review Angles'}
                </Button>
              )}
              {selectedDocumentId && (
                <Button
                  disabled={isGenerating || docStatus==='processing' || anglesReady === false }
                  variant={isGenerating || docStatus==='processing' || anglesReady === false ? 'secondary' : 'outline'}
                  onClick={async () => {
                    setIsGenerating(true);
                    try {
                      // Enforce staged flow: angles must be reviewed and complete
                      const ready = await checkAnglesComplete(selectedDocumentId);
                      if (!ready) {
                        setIsGenerating(false);
                        toast({ title:'Review required', description:'Complete angle review for all exterior images before generating.', variant:'destructive' });
                        navigate(`/review/${selectedDocumentId}`);
                        return;
                      }
                      console.log('Starting report generation...');
                      const docId = await saveDocument();
                      console.log('Document ID from saveDocument:', docId);
                      
                      if (!docId) { 
                        console.error('No document ID returned from saveDocument');
                        setIsGenerating(false); 
                        toast({ title:'Error', description:'Failed to save document before generating report', variant:'destructive' });
                        return; 
                      }
                      
                      const { data: { session } } = await supabase.auth.getSession();
                      console.log('Session:', session ? 'Valid' : 'None');
                      
                      console.log('Calling generate_report edge function with docId:', docId);
                      const { data, error } = await supabase.functions.invoke('generate_report', {
                        headers: { Authorization: `Bearer ${session?.access_token || supabase['supabaseKey']}` },
                        body: { document_id: docId },
                      });
                      
                      if (error) {
                        console.error('Generate report error:', error);
                        setIsGenerating(false);
                        toast({ title:'Error', description: `Report generation failed: ${error.message || 'Unknown error'}`, variant:'destructive' });
                      } else {
                        console.log('Generate report success:', data);
                        setIsGenerating(false); // Edge function returns immediately now
                        setDocStatus('processing');
                        toast({ title:'Success', description: data?.message || 'Report generation started' });
                      }
                    } catch (err) {
                      console.error('Unexpected error in generate report:', err);
                      setIsGenerating(false);
                      toast({ title:'Error', description: 'Unexpected error occurred', variant:'destructive' });
                    }
                  }}
                  className="border border-gray-300 px-6"
                >
                  Generate Report
                </Button>
              )}
              {/* Helper hint about stages */}
              {selectedDocumentId && anglesReady === false && (
                <div className="text-sm text-gray-500 self-center">Review angles to enable Generate.</div>
              )}
            </div>
          </div>
        </main>
       </div>

       {/* Angle Review Dialog encapsulated in dashboard */}
       <Dialog open={reviewOpen} onOpenChange={setReviewOpen}>
         <DialogContent className="max-w-5xl w-[96vw]">
           <DialogHeader>
             <DialogTitle>Review Angles</DialogTitle>
           </DialogHeader>
            {selectedDocumentId ? (
              <div className="space-y-4">
                {angleClassifying && (
                  <div className="p-3 rounded-md bg-blue-50 border border-blue-200">
                    <div className="flex items-center justify-between text-sm text-blue-800">
                      <span>Calculating angles…</span>
                      <span>
                        {angleTotals ? `${Math.max(0, (angleTotals.total_exterior - angleTotals.unknown_exterior))}/${angleTotals.total_exterior}` : ''}
                      </span>
                    </div>
                    <Progress className="mt-2" value={angleTotals && angleTotals.total_exterior > 0 ? ((angleTotals.total_exterior - angleTotals.unknown_exterior) / angleTotals.total_exterior) * 100 : 0} />
                  </div>
                )}
                {statusErrorCount >= 3 && (angleTotals?.unknown_exterior ?? 0) > 0 && (
                  <div className="p-3 rounded-md bg-amber-50 border border-amber-200 flex items-center justify-between text-amber-800 text-sm">
                    <span>Having trouble updating classification status.</span>
                    <button onClick={retryAnglePolling} className="px-2 py-1 text-xs rounded bg-amber-600 text-white hover:bg-amber-700">Retry</button>
                  </div>
                )}
                {reviewImages.length === 0 && (
                  <div className="text-sm text-gray-500">Loading images…</div>
                )}
                <AngleReviewBoard
                  documentId={selectedDocumentId}
                  backendBaseUrl={backendBaseUrl || ''}
                  initialImages={reviewImages}
                  onConfirm={(imgs: ReviewImage[]) => {
                   setReviewOpen(false);
                   setAnglesReady(true);
                   toast({ title: 'Angles saved', description: 'All exterior images are labeled.' });
                 }}
                 autoClassifyOnMount={false}
                />
                <div className="text-xs text-gray-500">Prefer a full page? <button className="underline" onClick={() => { setReviewOpen(false); if (selectedDocumentId) navigate(`/review/${selectedDocumentId}`); }}>Open Review Page</button></div>
              </div>
            ) : (
              <div className="text-sm text-gray-600">Save or select a document to review angles.</div>
            )}
         </DialogContent>
       </Dialog>

       {/* Only show overlay if NOT in fullscreen report mode */}
       {!showFullscreenReport && (isGenerating || docStatus==='processing') && (
         <div className="fixed inset-0 bg-black/40 flex flex-col items-center justify-center z-50 space-y-4">
           <Spinner />
           <p className="text-white text-lg">Generating report…</p>
         </div>
       )}
     </div>
   );
};

export default Dashboard;
