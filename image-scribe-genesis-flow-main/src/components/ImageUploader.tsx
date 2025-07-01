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

interface Props {
  documentId: string | null;
}

const ImageUploader = ({ documentId }: Props) => {
  const [images, setImages] = useState<UploadedImage[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  // handle file selection from drop zone
  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files) return;
    const newImgs: UploadedImage[] = Array.from(files)
      .filter((f) => f.type.startsWith("image/"))
      .map((file) => ({
        id: Math.random().toString(36).slice(2),
        file,
        preview: URL.createObjectURL(file),
        uploaded: false,
        progress: 0,
      }));
    if (newImgs.length) {
      setImages((prev) => [...prev, ...newImgs]);
      toast({ title: "Images added", description: `${newImgs.length} image(s) ready for upload` });
    }
  }, []);

  const removeImage = (id: string) => {
    setImages((prev) => {
      const img = prev.find((i) => i.id === id);
      if (img) URL.revokeObjectURL(img.preview);
      return prev.filter((i) => i.id !== id);
    });
  };

  // uploads a single file to storage & inserts DB row
  const uploadOne = async (img: UploadedImage) => {
    if (!documentId) {
      toast({ title: "Save document first", variant: "destructive" });
      return false;
    }
    const path = `${documentId}/${Date.now()}_${img.file.name}`;
    const { error: upErr } = await supabase.storage.from("images").upload(path, img.file, { upsert: true });
    if (upErr) {
      toast({ title: "Upload failed", description: upErr.message, variant: "destructive" });
      return false;
    }
    const { data: urlData } = supabase.storage.from("images").getPublicUrl(path);
    const publicUrl = (urlData as any).publicUrl || (urlData as any).publicURL || urlData?.publicUrl;
    const { error: dbErr } = await (supabase as any).from('images').insert({
      document_id: documentId,
      url: publicUrl,
    });
    if (dbErr) {
      toast({ title: "DB insert failed", description: dbErr.message, variant: "destructive" });
      return false;
    }
    return true;
  };

  const handleUpload = async () => {
    if (!images.length) {
      toast({ title: "No images selected", variant: "destructive" });
      return;
    }
    setIsUploading(true);
    for (const img of images.filter((i) => !i.uploaded)) {
      // optimistic 50% to show some movement
      setImages((prev) => prev.map((p) => (p.id === img.id ? { ...p, progress: 50 } : p)));
      const ok = await uploadOne(img);
      setImages((prev) => prev.map((p) => (p.id === img.id ? { ...p, progress: ok ? 100 : 0, uploaded: ok } : p)));
    }
    setIsUploading(false);
    toast({ title: "Upload complete" });
  };

  const clearAll = () => {
    images.forEach((i) => URL.revokeObjectURL(i.preview));
    setImages([]);
  };

  const total = images.length;
  const done = images.filter((i) => i.uploaded).length;
  const overall = total ? (done / total) * 100 : 0;

  return (
    <div className="space-y-6">
      <DropZone onFileSelect={handleFileSelect} />

      {images.length > 0 && (
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center space-x-4">
            <FileImage className="h-5 w-5 text-gray-500" />
            <span className="text-sm text-gray-600">
              {total} image(s) selected, {done} uploaded
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <Button variant="outline" size="sm" onClick={clearAll} disabled={isUploading}>
              <Trash2 className="h-4 w-4 mr-1" /> Clear All
            </Button>
            <Button size="sm" onClick={handleUpload} disabled={isUploading || images.every((i) => i.uploaded)}>
              <Upload className="h-4 w-4 mr-1" /> {isUploading ? "Uploading..." : "Upload Images"}
            </Button>
          </div>
        </div>
      )}

      {isUploading && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-gray-600">
            <span>Upload Progress</span>
            <span>{Math.round(overall)}%</span>
          </div>
          <Progress value={overall} className="w-full" />
        </div>
      )}

      {images.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {images.map((img) => (
            <ImagePreview key={img.id} image={img} onRemove={() => removeImage(img.id)} />
          ))}
        </div>
      )}
    </div>
  );
};

export default ImageUploader;
