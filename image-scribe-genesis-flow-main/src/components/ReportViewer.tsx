import React, { useState, useEffect, useCallback } from 'react';
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
}

interface ReportViewerProps {
  documentId: string;
}

const ReportViewer: React.FC<ReportViewerProps> = ({ documentId }) => {
  const [report, setReport] = useState<DamageReport | null>(null);
  const [images, setImages] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [generatingPDF, setGeneratingPDF] = useState(false);

  // Fetch report data from database or URL
  useEffect(() => {
    const fetchReport = async () => {
      try {
        const { data, error } = await supabase
          .from('documents')
          .select('report_json, report_json_url')
          .eq('id', documentId)
          .single();

        console.log('ReportViewer fetch result:', { data, error, documentId });
        
        if (data?.report_json) {
          console.log('Found report_json in database, parsing...');
          const dbReport = JSON.parse(data.report_json) as DamageReport;
          console.log('🔥 SETTING REPORT FROM DB TO:', dbReport);
          setReport(dbReport);
        } else if (data?.report_json_url) {
          console.log('No report_json in database, fetching from URL:', data.report_json_url);
          
          const response = await fetch(data.report_json_url);
          if (response.ok) {
            const jsonText = await response.text();
            console.log('Raw JSON text:', jsonText);
            console.log('JSON text type:', typeof jsonText);
            console.log('JSON text length:', jsonText?.length);
            
            try {
              const parsedReport = JSON.parse(jsonText);
              console.log('Parsed JSON successfully:', parsedReport);
              console.log('🔥 SETTING REPORT FROM URL TO:', parsedReport);
              setReport(parsedReport);
            } catch (parseError) {
              console.error('JSON parse error:', parseError);
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

  // Fetch damage images when report changes
  useEffect(() => {
    const fetchDamageImages = async () => {
      console.log('=== FETCHING DAMAGE IMAGES ===');
      if (!report?.damaged_parts) {
        console.log('No damaged_parts in report, setting empty images');
        setImages([]);
        return;
      }

      try {
        // Get unique image filenames that contain damage  
        const damageImageFiles = [...new Set(
          report.damaged_parts.map((part: any) => part.image).filter(Boolean)
        )];
        
        console.log('Damage image filenames:', damageImageFiles);
        
        if (damageImageFiles.length === 0) {
          console.log('No damage image files found');
          setImages([]);
          return;
        }
        
        // Fetch URLs for all images of this document
        const { data: imageData, error: imageError } = await supabase
          .from('images')
          .select('url')
          .eq('document_id', documentId);
        
        if (imageError) {
          console.error('Error fetching images:', imageError);
          setImages([]);
          return;
        }
        
        console.log('All image URLs from database:', imageData);
        
        if (imageData && imageData.length > 0) {
          // Smart matching: map simplified JSON names to actual URLs
          const filteredImageUrls: string[] = [];
          
          damageImageFiles.forEach(jsonImageName => {
            console.log('Looking for match for:', jsonImageName);
            
            // First try exact match
            let matchedUrl = imageData.find((img: any) => 
              img.url.includes(jsonImageName)
            )?.url;
            
            // If no exact match, use position-based matching
            if (!matchedUrl) {
              const imageIndex = parseInt(jsonImageName.replace(/\D/g, '')) - 1;
              if (imageIndex >= 0 && imageIndex < imageData.length) {
                matchedUrl = imageData[imageIndex]?.url;
                console.log(`Position-based match: ${jsonImageName} -> index ${imageIndex} -> ${matchedUrl}`);
              }
            }
            
            if (matchedUrl) {
              filteredImageUrls.push(matchedUrl);
              console.log('✅ Matched:', jsonImageName, '->', matchedUrl);
            } else {
              console.log('❌ No match found for:', jsonImageName);
            }
          });
          
          console.log('Final filtered damage image URLs:', filteredImageUrls);
          setImages(filteredImageUrls);
        } else {
          console.log('No image data found in database');
          setImages([]);
        }
      } catch (error) {
        console.error('Error fetching damage images:', error);
        setImages([]);
      }
    };

    fetchDamageImages();
  }, [report, documentId]);

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
        
        {/* Damaged Parts */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Damaged Parts ({report.damaged_parts.length})</h2>
          <div className="space-y-4">
            {report.damaged_parts.map((part, index) => (
              <div key={index} className="border rounded-lg p-4">
                <div className="grid grid-cols-2 gap-4 mb-2">
                  <div><strong>Part:</strong> {part.name}</div>
                  <div><strong>Category:</strong> {part.category}</div>
                  <div><strong>Location:</strong> {part.location}</div>
                  <div><strong>Severity:</strong> {part.severity}</div>
                </div>
                <div className="mb-2">
                  <strong>Description:</strong> {part.description}
                </div>
                {part.notes && (
                  <div className="text-sm text-gray-600">
                    <strong>Notes:</strong> {part.notes}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
        
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
