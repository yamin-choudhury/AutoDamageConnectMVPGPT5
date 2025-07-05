
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import DocumentPreview from "@/components/DocumentPreview";
import { User } from "@supabase/supabase-js";
import { User as UserIcon } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import Spinner from "@/components/ui/Spinner";
import ImageUploader from "@/components/ImageUploader";
import HistorySidebar from "@/components/HistorySidebar";
import VehicleInfoForm from "@/components/VehicleInfoForm";

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
  const [currentDocument, setCurrentDocument] = useState<any>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [docStatus, setDocStatus] = useState<string | null>(null);
  const { toast } = useToast();

  // show success/error when docStatus changes
  useEffect(() => {
    if (docStatus === 'ready') {
      toast({ title: 'Report ready', description: 'Damage report has been generated.' });
      setIsGenerating(false);
    } else if (docStatus === 'error') {
      toast({ title: 'Generation failed', variant: 'destructive' });
      setIsGenerating(false);
    }
  }, [docStatus, toast]);

  // Real-time subscription for document status updates
  useEffect(() => {
    if (!selectedDocumentId) {
      setDocStatus(null);
      return;
    }

    // Check actual database status first
    const checkDatabaseStatus = async () => {
      const { data, error } = await supabase
        .from('documents')
        .select('id, status, created_at')
        .eq('id', selectedDocumentId)
        .single();
      
      console.log('🔍 Database status check:', { data, error });
      if (data) {
        console.log('  - Actual DB status:', data.status);
        console.log('  - Current docStatus state:', docStatus);
        
        // If DB shows ready but state is wrong, fix it immediately
        if (data.status === 'ready' && docStatus !== 'ready') {
          console.log('🚑 FIXING STATE MISMATCH: DB is ready but state is', docStatus);
          setDocStatus('ready');
          setIsGenerating(false);
        }
      }
    };
    
    checkDatabaseStatus();
    
    // Set up real-time listener for this document
    const channel = supabase
      .channel("dashboard-doc-" + selectedDocumentId)
      .on(
        "postgres_changes",
        { 
          event: "UPDATE", 
          schema: "public", 
          table: "documents", 
          filter: `id=eq.${selectedDocumentId}` 
        },
        (payload) => {
          console.log('🎯 Dashboard real-time update received!');
          console.log('  - Previous status:', docStatus);
          console.log('  - New status:', payload.new.status);
          console.log('  - Was generating:', isGenerating);
          
          setDocStatus(payload.new.status);
          setIsGenerating(false); // Clear generating state on any status change
          
          console.log('  - Updated states: docStatus ->', payload.new.status, ', isGenerating -> false');
        }
      )
      .subscribe();
      
    // Backup: Check database status every 3 seconds
    const statusCheck = setInterval(checkDatabaseStatus, 3000);

    return () => {
      supabase.removeChannel(channel);
    };
  }, [selectedDocumentId]);

  useEffect(() => {
    if (selectedDocumentId) {
      fetchDocument(selectedDocumentId);
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
  }, [selectedDocumentId]);

  const fetchDocument = async (documentId: string) => {
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
  };

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
                  Document Generator
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
                <CardTitle className="text-2xl">
                  {selectedDocumentId ? 'Edit Document' : 'Create New Document'}
                </CardTitle>
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
                <ImageUploader documentId={selectedDocumentId} onDocumentCreated={setSelectedDocumentId} />
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
                  disabled={isGenerating || docStatus==='processing' }
                  variant={isGenerating || docStatus==='processing' ? 'secondary' : 'outline'}
                  onClick={async () => {
                     setIsGenerating(true);
                     const docId = await saveDocument();
                     if (!docId) { setIsGenerating(false); return; }
                     const { data: { session } } = await supabase.auth.getSession();
                     const { error } = await supabase.functions.invoke('generate_report', {
                       headers: { Authorization: `Bearer ${session?.access_token || supabase['supabaseKey']}` },
                       body: { document_id: docId },
                     });
                     if (error) {
                       setIsGenerating(false);
                       toast({ title:'Error', description:'Report generation failed', variant:'destructive' });
                     } else {
                       setDocStatus('processing');
                       toast({ title:'Generating', description:'Report generation started' });
                     }
                   }}
                  className="border border-gray-300 px-6"
                >
                  Generate Report
                </Button>
              )}
            </div>
          </div>
        </main>
       </div>

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
