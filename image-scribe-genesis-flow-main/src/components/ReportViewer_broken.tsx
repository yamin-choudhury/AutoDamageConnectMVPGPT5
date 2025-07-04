import React, { useState, useEffect, useCallback } from 'react';
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/use-toast";
import html2pdf from 'html2pdf.js';

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

  useEffect(() => {
    console.log('=== DEBUG: Report state updated ===');
    console.log('Full report:', report);
    console.log('Report keys:', report ? Object.keys(report).join(', ') : 'report is null');
    console.log('damaged_parts exists?', report?.damaged_parts ? true : false);
    console.log('damaged_parts value:', report?.damaged_parts);
  }, [report]);

  useEffect(() => {
    const fetchDamageImages = async () => {
      console.log('=== FETCHING DAMAGE IMAGES ===');
      if (!report?.damaged_parts) {
        console.log('No damaged_parts in report, setting empty images');
        setImages([]);
        return;
      }

      try {
        const damageImageFiles = [...new Set(
          report.damaged_parts.map((part: any) => part.image).filter(Boolean)
        )];
        
        console.log('Damage image filenames:', damageImageFiles);
        
        if (damageImageFiles.length === 0) {
          console.log('No damage image files found');
          setImages([]);
          return;
        }
        
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
          const filteredImageUrls: string[] = [];
          
          damageImageFiles.forEach(jsonImageName => {
            console.log('Looking for match for:', jsonImageName);
            
            let matchedUrl = imageData.find((img: any) => 
              img.url.includes(jsonImageName)
            )?.url;
            
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
      
      const opt = {
        margin: 1,
        filename: `damage-report-${documentId}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2 },
        jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
      };
      
      await html2pdf().set(opt).from(reportElement).save();
      
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
                  <div><strong>Location:</strong></div><div>${part.location || 'N/A'}</div>
                  <div><strong>Category:</strong></div><div>${part.category || 'N/A'}</div>
                  <div><strong>Damage Type:</strong></div><div>${part.damage_type || 'N/A'}</div>
                  <div><strong>Severity:</strong></div>
                  <div><span class="badge severity-${part.severity || 'mild'}">${(part.severity || 'N/A').toUpperCase()}</span></div>
                  <div><strong>Repair Method:</strong></div><div>${part.repair_method || 'N/A'}</div>
                </div>
                ${part.description ? `<p><strong>Description:</strong> ${part.description}</p>` : ''}
                ${part.notes ? `<p><strong>Notes:</strong> ${part.notes}</p>` : ''}
              </div>
            `).join('')}
          </div>

          ${repairParts.length > 0 ? `
            <div class="section">
              <h2>Required Parts & Labor</h2>
              <table>
                <thead>
                  <tr><th>Part Name</th><th>Category</th><th>Labor Hours</th><th>Paint Hours</th></tr>
                </thead>
                <tbody>
                  ${repairParts.map(part => `
                    <tr>
                      <td>${part.name}</td>
                      <td>${part.category || 'N/A'}</td>
                      <td>${part.labour_hours || 0}h</td>
                      <td>${part.paint_hours || 0}h</td>
                    </tr>
                  `).join('')}
                  <tr style="font-weight: bold; background: #f7fafc;">
                    <td>TOTAL</td><td></td>
                    <td>${repairParts.reduce((sum, p) => sum + (p.labour_hours || 0), 0)}h</td>
                    <td>${repairParts.reduce((sum, p) => sum + (p.paint_hours || 0), 0)}h</td>
                  </tr>
                </tbody>
              </table>
            </div>
          ` : ''}
        </body>
      </html>
    `;
  };

  const getSeverityColor = (severity?: string) => {
    switch (severity?.toLowerCase()) {
      case 'severe': return 'destructive';
      case 'moderate': return 'secondary';
      default: return 'default';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="text-center py-8">
        <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-600">No report data available</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header with Download Button */}
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-blue-900">🚗 Damage Assessment Report</h1>
        <Button 
          onClick={generateClientSidePDF} 
          disabled={generatingPDF}
          className="flex items-center gap-2"
        >
          <Download className="h-4 w-4" />
          {generatingPDF ? 'Generating PDF...' : 'Download PDF'}
        </Button>
      </div>

      {/* Vehicle Information */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Car className="h-5 w-5" />
            Vehicle Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div><strong>Make:</strong> {report.vehicle?.make || 'N/A'}</div>
            <div><strong>Model:</strong> {report.vehicle?.model || 'N/A'}</div>
            <div><strong>Year:</strong> {report.vehicle?.year || 'N/A'}</div>
          </div>
        </CardContent>
      </Card>

      {/* Vehicle Images */}
      {images.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Camera className="h-5 w-5" />
              Vehicle Images
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {images.map((imageUrl, index) => (
                <div key={index} className="relative group">
                  <img 
                    src={imageUrl} 
                    alt={`Vehicle image ${index + 1}`}
                    className="w-full h-48 object-cover rounded-lg border shadow-sm hover:shadow-md transition-shadow"
                    onError={(e) => {
                      console.log('Image load error:', imageUrl);
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Damage Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Damage Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <strong>Overall Severity:</strong>
              <Badge variant={getSeverityColor(report.summary?.overall_severity)} className="ml-2">
                {report.summary?.overall_severity?.toUpperCase() || 'N/A'}
              </Badge>
            </div>
            <div><strong>Repair Complexity:</strong> {report.summary?.repair_complexity || 'N/A'}</div>
            <div><strong>Safety Impact:</strong> {report.summary?.safety_impacted ? 'YES' : 'NO'}</div>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              <strong>Estimated Hours:</strong> {report.summary?.total_estimated_hours || 0} hours
            </div>
          </div>
          {report.summary?.comments && (
            <div className="mt-4 p-3 bg-gray-50 rounded">
              <strong>Comments:</strong> {report.summary.comments}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Damaged Parts */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className="h-5 w-5" />
            Damaged Parts Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {report.damaged_parts?.map((part, index) => (
              <div key={index} className="border-l-4 border-blue-500 pl-4 py-3 bg-blue-50 rounded-r">
                <h3 className="font-semibold text-lg text-blue-900">
                  {index + 1}. {part.name}
                </h3>
                <div className="grid grid-cols-2 gap-2 mt-2 text-sm">
                  <div><strong>Location:</strong> {part.location || 'N/A'}</div>
                  <div><strong>Category:</strong> {part.category || 'N/A'}</div>
                  <div><strong>Damage Type:</strong> {part.damage_type || 'N/A'}</div>
                  <div>
                    <strong>Severity:</strong>
                    <Badge variant={getSeverityColor(part.severity)} className="ml-1 text-xs">
                      {part.severity?.toUpperCase() || 'N/A'}
                    </Badge>
                  </div>
                  <div><strong>Repair Method:</strong> {part.repair_method || 'N/A'}</div>
                </div>
                {part.description && (
                  <p className="mt-2 text-sm"><strong>Description:</strong> {part.description}</p>
                )}
                {part.notes && (
                  <p className="mt-1 text-sm text-gray-600"><strong>Notes:</strong> {part.notes}</p>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Repair Parts Table */}
      {report.repair_parts && report.repair_parts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wrench className="h-5 w-5" />
              Required Parts & Labor
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse border border-gray-300">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="border border-gray-300 px-4 py-2 text-left">Part Name</th>
                    <th className="border border-gray-300 px-4 py-2 text-left">Category</th>
                    <th className="border border-gray-300 px-4 py-2 text-center">Labor Hours</th>
                    <th className="border border-gray-300 px-4 py-2 text-center">Paint Hours</th>
                  </tr>
                </thead>
                <tbody>
                  {report.repair_parts.map((part, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="border border-gray-300 px-4 py-2">{part.name}</td>
                      <td className="border border-gray-300 px-4 py-2">{part.category || 'N/A'}</td>
                      <td className="border border-gray-300 px-4 py-2 text-center">{part.labour_hours || 0}h</td>
                      <td className="border border-gray-300 px-4 py-2 text-center">{part.paint_hours || 0}h</td>
                    </tr>
                  ))}
                  <tr className="bg-gray-100 font-semibold">
                    <td className="border border-gray-300 px-4 py-2">TOTAL</td>
                    <td className="border border-gray-300 px-4 py-2"></td>
                    <td className="border border-gray-300 px-4 py-2 text-center">
                      {report.repair_parts.reduce((sum, part) => sum + (part.labour_hours || 0), 0)}h
                    </td>
                    <td className="border border-gray-300 px-4 py-2 text-center">
                      {report.repair_parts.reduce((sum, part) => sum + (part.paint_hours || 0), 0)}h
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default ReportViewer;
