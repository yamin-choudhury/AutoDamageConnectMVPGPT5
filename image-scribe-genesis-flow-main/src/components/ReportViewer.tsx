import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { supabase } from '../integrations/supabase/client';
import html2pdf from 'html2pdf.js';
import { Button } from './ui/button';
import { toast } from '@/hooks/use-toast';

interface DamageReport {
  vehicle: {
    make: string;
    model: string;
    year: string;
  };
  damaged_parts: Array<{
    name: string;
    category: string;
    location: string;
    damage_type: string;
    severity: string;
    image: string;
    box_id: number;
    bbox_px: {
      x: number;
      y: number;
      w: number;
      h: number;
    };
    repair_method: string;
    description: string;
    notes: string;
  }>;
  // Optional: parts that did not meet union/verification thresholds but are plausible and kept for assessor review
  potential_parts?: Array<{
    name: string;
    category?: string;
    location?: string;
    damage_type?: string;
    severity?: string;
    image?: string;
    box_id?: number;
    bbox_px?: {
      x: number;
      y: number;
      w: number;
      h: number;
    };
    repair_method?: string;
    description?: string;
    notes?: string;
    reason?: string; // e.g., "insufficient_votes", "verification_failed"
  }>;
  repair_parts: Array<{
    category: string;
    name: string;
    oem_only: boolean;
    sub_components: string[];
    labour_hours: number;
    paint_hours: number;
  }>;
  summary: {
    overall_severity: string;
    repair_complexity: string;
    safety_impacted: boolean;
    total_estimated_hours: number;
    comments: string;
  };
  _config?: Record<string, any>;
}

interface ReportViewerProps {
  documentId: string;
}

const ReportViewer: React.FC<ReportViewerProps> = ({ documentId }) => {
  const [report, setReport] = useState<DamageReport | null>(null);
  const [images, setImages] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [generatingPDF, setGeneratingPDF] = useState(false);

  // Helpers for uniqueness by canonical key (name + location)
  type Part = DamageReport['damaged_parts'][number];
  type PotentialPart = NonNullable<DamageReport['potential_parts']>[number];
  type AnyPart = Part | PotentialPart;

  const makeKey = useCallback((p: AnyPart) => {
    const name = (p?.name || '').toString().trim().toLowerCase();
    const loc = (p?.location || '').toString().trim().toLowerCase();
    return `${name}|${loc}`;
  }, []);

  const dedupeParts = useCallback((parts: ReadonlyArray<AnyPart> | undefined | null): AnyPart[] => {
    const out: AnyPart[] = [];
    const seen = new Set<string>();
    for (const p of parts || []) {
      const k = makeKey(p);
      if (!seen.has(k)) {
        seen.add(k);
        out.push(p);
      }
    }
    return out;
  }, [makeKey]);

  const definitiveParts = useMemo<Part[]>(() => (dedupeParts(report?.damaged_parts || []) as Part[]), [report?.damaged_parts, dedupeParts]);
  const potentialParts = useMemo<PotentialPart[]>(() => {
    const pot = (dedupeParts(report?.potential_parts || []) as PotentialPart[]);
    const defKeys = new Set(definitiveParts.map(makeKey));
    return pot.filter((p) => !defKeys.has(makeKey(p)));
  }, [report?.potential_parts, definitiveParts, makeKey, dedupeParts]);

  // Fetch report data from database or URL
  useEffect(() => {
    const fetchReport = async () => {
      try {
        const { data, error } = await supabase
          .from('documents')
          .select('report_pdf_url, status, id')
          .eq('id', documentId)
          .single();

        console.log('ReportViewer fetch result:', { data, error, documentId });
        
        if (error) {
          console.error('Error fetching document:', error);
          setLoading(false);
          return;
        }
        
        // Check if report is ready and has URLs
        if (data?.status === 'ready' && data?.report_pdf_url) {
          // Extract report JSON URL from PDF URL pattern
          const reportJsonUrl = data.report_pdf_url.replace('.pdf', '.json');
          
          console.log('Fetching report JSON from URL:', reportJsonUrl);
          
          const response = await fetch(reportJsonUrl);
          console.log('Response status:', response.status, 'Content-Type:', response.headers.get('content-type'));
          
          if (response.ok) {
            const contentType = response.headers.get('content-type');
            
            // Check if we got JSON or accidentally got PDF
            if (contentType?.includes('application/pdf')) {
              console.error('❌ Got PDF instead of JSON - URL pattern is wrong');
              console.error('PDF URL:', data.report_pdf_url);
              console.error('Constructed JSON URL:', reportJsonUrl);
              setReport(null);
              return;
            }
            
            const jsonText = await response.text();
            console.log('Raw JSON text (first 200 chars):', jsonText?.substring(0, 200));
            console.log('JSON text type:', typeof jsonText);
            console.log('JSON text length:', jsonText?.length);
            
            // Validate it looks like JSON before parsing
            if (!jsonText?.trim().startsWith('{') && !jsonText?.trim().startsWith('[')) {
              console.error('❌ Response does not look like JSON:', jsonText?.substring(0, 100));
              setReport(null);
              return;
            }
            
            try {
              const parsedReport = JSON.parse(jsonText);
              console.log('✅ Parsed JSON successfully:', parsedReport);
              console.log('🔥 SETTING REPORT FROM URL TO:', parsedReport);
              setReport(parsedReport);
            } catch (parseError) {
              console.error('❌ JSON parse error:', parseError);
              console.error('Failed to parse JSON data:', jsonText?.substring(0, 200));
              setReport(null);
            }
          } else {
            console.error('Failed to fetch JSON from URL:', response.status);
          }
        } else {
          console.log('No report_json or report_json_url found');
        }
      } catch (err) {
        console.error('Error in report fetching:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [documentId]);

  // Debug the report structure when it changes
  useEffect(() => {
    console.log('=== DEBUG: Report state updated ===');
    console.log('Full report:', report);
    console.log('Report keys:', report ? Object.keys(report).join(', ') : 'report is null');
    console.log('damaged_parts exists?', report?.damaged_parts ? true : false);
    console.log('damaged_parts value:', report?.damaged_parts);
  }, [report]);

  // Fetch images referenced by definitive and potential parts (unique)
  useEffect(() => {
    const fetchDamagedImages = async () => {
      try {
        if (!report?.damaged_parts && !report?.potential_parts) {
          setImages([]);
          return;
        }
        const allParts = [
          ...(report?.damaged_parts || []),
          ...(report?.potential_parts || []),
        ];
        const damagedNames = new Set(
          allParts
            .map((p) => (p?.image || '').toString().trim().toLowerCase())
            .filter((s) => !!s)
        );
        console.log('Damaged image names from report:', Array.from(damagedNames));

        const { data: imageData, error } = await supabase
          .from('document_images')
          .select('image_url, image_name')
          .eq('document_id', documentId);
        if (error) {
          console.error('Error fetching document images:', error);
          setImages([]);
          return;
        }

        const pickName = (url: string) => {
          try {
            const u = new URL(url);
            const base = u.pathname.split('/').pop() || '';
            return base.toLowerCase();
          } catch {
            const base = url.split('?')[0].split('/').pop() || '';
            return base.toLowerCase();
          }
        };

        const damagedUrls = (imageData || [])
          .filter((row: { image_url: string; image_name?: string | null }) => {
            const name = (row.image_name || '').toLowerCase();
            const urlName = pickName(row.image_url);
            return damagedNames.has(name) || damagedNames.has(urlName);
          })
          .map((row: { image_url: string }) => row.image_url);

        if (damagedUrls.length > 0) {
          setImages(Array.from(new Set(damagedUrls)));
        } else {
          // Safe fallback if names failed to match (should be rare)
          console.warn('No damaged image matches found; falling back to all document images');
          const allUrls = (imageData || []).map((row: { image_url: string }) => row.image_url);
          setImages(Array.from(new Set(allUrls)));
        }
      } catch (e) {
        console.error('Unexpected error fetching images:', e);
        setImages([]);
      }
    };
    fetchDamagedImages();
  }, [documentId, report?.damaged_parts, report?.potential_parts]);

  const generatePDF = useCallback(async () => {
    if (!report) return;
    
    setGeneratingPDF(true);
    
    try {
      const reportElement = document.getElementById(`report-content-${documentId}`);
      if (!reportElement) {
        throw new Error('Report element not found');
      }
      
      // Add PDF-specific styling temporarily
      const originalStyle = reportElement.style.cssText;
      reportElement.style.cssText = `
        max-width: none !important;
        width: 8.5in !important;
        margin: 0 !important;
        padding: 0.5in !important;
        background: white !important;
        font-family: Arial, sans-serif !important;
        font-size: 12px !important;
        line-height: 1.4 !important;
        color: #333 !important;
      `;
      
      const opt = {
        margin: 0.5,
        filename: `damage-report-${documentId}.pdf`,
        image: { 
          type: 'jpeg', 
          quality: 0.95 
        },
        html2canvas: { 
          scale: 1.5,
          useCORS: true,
          allowTaint: true,
          backgroundColor: '#ffffff',
          width: 816, // 8.5 inches at 96 DPI
          windowWidth: 816
        },
        jsPDF: { 
          unit: 'in', 
          format: 'letter', 
          orientation: 'portrait',
          compress: true
        },
        pagebreak: { 
          mode: ['avoid-all', 'css', 'legacy'],
          before: '.page-break-before',
          after: '.page-break-after',
          avoid: '.no-page-break'
        }
      };
      
      await html2pdf().set(opt).from(reportElement).save();
      
      // Restore original styling
      reportElement.style.cssText = originalStyle;
      
      toast({
        title: "PDF Generated",
        description: "Your damage report PDF has been downloaded.",
      });
    } catch (error) {
      console.error('Error generating PDF:', error);
      toast({
        title: "PDF Generation Failed",
        description: "There was an error generating the PDF. Please try again.",
        variant: "destructive",
      });
    } finally {
      setGeneratingPDF(false);
    }
  }, [documentId, report]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-lg">Loading report...</div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-lg text-red-600">No report data available</div>
      </div>
    );
  }

  return (
    <div className="w-full h-full overflow-auto">
      {/* PDF Download Button - Outside PDF content */}
      <div className="max-w-4xl mx-auto p-4 bg-gray-50 border-b">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-700">Report Actions</h2>
          <Button 
            onClick={generatePDF}
            disabled={generatingPDF}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {generatingPDF ? 'Generating PDF...' : 'Download PDF'}
          </Button>
        </div>
      </div>
      
      {/* PDF Content Area - Only this gets captured */}
      <div id={`report-content-${documentId}`} className="max-w-4xl mx-auto p-6 bg-white">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Vehicle Damage Report</h1>
          <p className="text-gray-600 mt-2">Generated on {new Date().toLocaleDateString()}</p>
        </div>
        
        {/* Vehicle Information */}
        <div className="mb-8 p-4 border rounded-lg">
          <h2 className="text-xl font-semibold mb-4">Vehicle Information</h2>
          <div className="grid grid-cols-3 gap-4">
            <div><strong>Make:</strong> {report.vehicle.make}</div>
            <div><strong>Model:</strong> {report.vehicle.model}</div>
            <div><strong>Year:</strong> {report.vehicle.year}</div>
          </div>
        </div>
        
        {/* Damage Images */}
        {images.length > 0 && (
          <div className="mb-8">
            <h2 className="text-xl font-semibold mb-4">Damage Images ({images.length})</h2>
            <div className="grid grid-cols-2 gap-4">
              {images.map((imageUrl, index) => (
                <div key={index} className="border rounded-lg overflow-hidden">
                  <img 
                    src={imageUrl} 
                    alt={`Damage ${index + 1}`}
                    className="w-full h-64 object-cover"
                  />
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Definitive Damaged Parts */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xl font-semibold">Definitive Damaged Parts</h2>
            <span className="text-sm px-2 py-1 rounded bg-green-100 text-green-800">{definitiveParts.length} items</span>
          </div>
          <div className="space-y-4">
            {definitiveParts.map((part, index) => (
              <div key={index} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-semibold text-gray-900">{part.name}</div>
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                    (part.severity || '').toLowerCase() === 'severe' ? 'bg-red-100 text-red-800' :
                    (part.severity || '').toLowerCase() === 'moderate' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-blue-100 text-blue-800'
                  }`}>
                    {part.severity || 'minor'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4 mb-2 text-sm">
                  <div><strong>Category:</strong> {part.category}</div>
                  <div><strong>Location:</strong> {part.location}</div>
                </div>
                {part.description && (
                  <div className="mb-2 text-sm text-gray-800">
                    <strong>Description:</strong> {part.description}
                  </div>
                )}
                {part.notes && (
                  <div className="text-xs text-gray-600">
                    <strong>Notes:</strong> {part.notes}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Potential Damaged Parts (Assessor to review) */}
        {potentialParts.length > 0 && (
          <div className="mb-8 page-break-before">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xl font-semibold">Potential Damaged Parts</h2>
              <span className="text-sm px-2 py-1 rounded bg-amber-100 text-amber-800">{potentialParts.length} items</span>
            </div>
            <p className="text-sm text-gray-600 mb-3">These items did not meet automated thresholds (votes/verification) but are plausible and included for independent assessor review.</p>
            <div className="space-y-4">
              {potentialParts.map((part, index) => (
                <div key={index} className="border rounded-lg p-4 bg-amber-50">
                  <div className="flex items-center justify-between mb-2">
                    <div className="font-semibold text-gray-900">{part.name}</div>
                    <span className="text-xs px-2 py-0.5 rounded font-medium bg-amber-200 text-amber-900">potential</span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 mb-2 text-sm">
                    <div><strong>Category:</strong> {part.category || '-'}</div>
                    <div><strong>Location:</strong> {part.location || '-'}</div>
                  </div>
                  {part.description && (
                    <div className="mb-2 text-sm text-gray-800">
                      <strong>Description:</strong> {part.description}
                    </div>
                  )}
                  {part.reason && (
                    <div className="text-xs text-gray-600">
                      <strong>Reason:</strong> {part.reason}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Summary */}
        <div className="mb-8 p-4 border rounded-lg bg-gray-50">
          <h2 className="text-xl font-semibold mb-4">Summary</h2>
          <div className="space-y-2">
            <div><strong>Overall Severity:</strong> {report.summary.overall_severity}</div>
            <div><strong>Repair Complexity:</strong> {report.summary.repair_complexity}</div>
            <div><strong>Safety Impacted:</strong> {report.summary.safety_impacted ? 'Yes' : 'No'}</div>
            <div><strong>Estimated Hours:</strong> {report.summary.total_estimated_hours}</div>
            <div><strong>Comments:</strong> {report.summary.comments}</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportViewer;
