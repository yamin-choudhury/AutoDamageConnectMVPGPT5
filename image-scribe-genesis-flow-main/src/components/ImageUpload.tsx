
import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { toast } from "@/hooks/use-toast";
import ImagePreview from "@/components/ImagePreview";
import DropZone from "@/components/DropZone";
import { Upload, FileImage, Trash2 } from "lucide-react";

import { supabase } from "@/integrations/supabase/client";

interface UploadedImage {
  id: string;
  file: File;
  preview: string;
  uploaded: boolean;
  progress: number;
}

interface ImageUploadProps {
  documentId: string | null;
}

const ImageUpload = ({ documentId }: ImageUploadProps) => {
  const [images, setImages] = useState<UploadedImage[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files) return;

    const newImages: UploadedImage[] = [];
    Array.from(files).forEach((file) => {
      if (file.type.startsWith('image/')) {
        const id = Math.random().toString(36).substr(2, 9);
        const preview = URL.createObjectURL(file);
        newImages.push({
          id,
          file,
          preview,
          uploaded: false,
          progress: 0,
        });
      }
    });

    if (newImages.length > 0) {
      setImages(prev => [...prev, ...newImages]);
      toast({
        title: "Images added",
        description: `${newImages.length} image(s) ready for upload`,
      });
    }
  }, []);

  const removeImage = (id: string) => {
    setImages(prev => {
      const image = prev.find(img => img.id === id);
      if (image) {
        URL.revokeObjectURL(image.preview);
      }
      return prev.filter(img => img.id !== id);
    });
  };

  const uploadSingle = async (img: UploadedImage) => {
    if (!documentId) {
      toast({ title: "Save document first", description: "Upload is disabled until the document is saved", variant: "destructive" });
      return;
    }
    const filePath = `${documentId}/${Date.now()}_${img.file.name}`;
    // Upload to storage
    const { error: upErr } = await supabase.storage.from('images').upload(filePath, img.file, { upsert: true });
    if (upErr) {
      toast({ title: "Upload failed", description: upErr.message, variant: "destructive" });
      return;
    }
    const { data: urlData } = supabase.storage.from('images').getPublicUrl(filePath);
    // Insert DB row
    const { error: dbErr } = await supabase.from('images').insert({ document_id: documentId, url: urlData.publicUrl });
    if (dbErr) {
      toast({ title: "DB insert failed", description: dbErr.message, variant: "destructive" });
      return;
    }
    // Mark uploaded
    setImages(prev => prev.map(im => im.id === img.id ? { ...im, progress: 100, uploaded: true } : im));
  }
    return new Promise<void>((resolve) => {
      let progress = 0;
      const interval = setInterval(() => {
        progress += Math.random() * 30;
        if (progress >= 100) {
          progress = 100;
          clearInterval(interval);
          setImages(prev => prev.map(img => 
            img.id === imageId 
              ? { ...img, progress: 100, uploaded: true }
              : img
          ));
          resolve();
        } else {
          setImages(prev => prev.map(img => 
            img.id === imageId 
              ? { ...img, progress }
              : img
          ));
        }
      }, 200);
    });
  };

  const handleUpload = async () => {
    if (images.length === 0) {
      toast({
        title: "No images selected",
        description: "Please select some images first",
        variant: "destructive",
      });
      return;
    }

    setIsUploading(true);
    
    for (const image of images.filter(img => !img.uploaded)) {
      // show fake progress quickly since supabase-js does not yet expose progress for fetch uploads
      setImages(prev => prev.map(im => im.id === image.id ? { ...im, progress: 50 } : im));
      await uploadSingle(image);
    }

    setIsUploading(false);
    toast({
      title: "Upload complete!",
      description: "All images have been uploaded successfully",
    });
  };

  const clearAll = () => {
    images.forEach(image => URL.revokeObjectURL(image.preview));
    setImages([]);
  };

  const totalImages = images.length;
  const uploadedImages = images.filter(img => img.uploaded).length;
  const overallProgress = totalImages > 0 ? (uploadedImages / totalImages) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Drop Zone */}
      <DropZone onFileSelect={handleFileSelect} />

      {/* Upload Controls */}
      {images.length > 0 && (
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center space-x-4">
            <FileImage className="h-5 w-5 text-gray-500" />
            <span className="text-sm text-gray-600">
              {totalImages} image(s) selected, {uploadedImages} uploaded
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={clearAll}
              disabled={isUploading}
            >
              <Trash2 className="h-4 w-4 mr-1" />
              Clear All
            </Button>
            <Button
              onClick={handleUpload}
              disabled={isUploading || images.every(img => img.uploaded)}
              size="sm"
            >
              <Upload className="h-4 w-4 mr-1" />
              {isUploading ? "Uploading..." : "Upload Images"}
            </Button>
          </div>
        </div>
      )}

      {/* Overall Progress */}
      {isUploading && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-gray-600">
            <span>Upload Progress</span>
            <span>{Math.round(overallProgress)}%</span>
          </div>
          <Progress value={overallProgress} className="w-full" />
        </div>
      )}

      {/* Image Previews */}
      {images.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {images.map((image) => (
            <ImagePreview
              key={image.id}
              image={image}
              onRemove={() => removeImage(image.id)}
            />
          ))}
        </div>
      )}

      {/* Generate Document Button */}
      {images.length > 0 && images.every(img => img.uploaded) && (
        <div className="text-center pt-4">
          <Button 
            size="lg" 
            className="bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700"
          >
            Generate Document
          </Button>
          <p className="text-sm text-gray-500 mt-2">
            All images uploaded successfully. Ready to generate your document!
          </p>
        </div>
      )}
    </div>
  );
};

export default ImageUpload;
