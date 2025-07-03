
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { X, CheckCircle } from "lucide-react";

interface UploadedImage {
  id: string;
  file: File;
  preview: string;
  uploaded: boolean;
  progress: number;
}

interface ImagePreviewProps {
  image: UploadedImage;
  onRemove: () => void;
}

const ImagePreview = ({ image, onRemove }: ImagePreviewProps) => {
  return (
    <div className="relative group bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      {/* Image */}
      <div className="aspect-square relative overflow-hidden bg-gray-100">
        <img
          src={image.preview}
          alt={image.file.name}
          className="w-full h-full object-cover"
        />
        
        {/* Overlay for uploading state */}
        {!image.uploaded && image.progress > 0 && (
          <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
            <div className="text-white text-sm font-medium">
              {Math.round(image.progress)}%
            </div>
          </div>
        )}
        
        {/* Success indicator */}
        {image.uploaded && (
          <div className="absolute top-2 right-2">
            <CheckCircle className="h-5 w-5 text-green-500 bg-white rounded-full" />
          </div>
        )}
        
        {/* Remove button */}
        <Button
          variant="destructive"
          size="sm"
          className="absolute top-2 left-2 opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 p-0"
          onClick={onRemove}
        >
          <X className="h-3 w-3" />
        </Button>
      </div>
      
      {/* File info */}
      <div className="p-3">
        <p className="text-xs text-gray-600 truncate" title={image.file.name}>
          {image.file.name}
        </p>
        <p className="text-xs text-gray-400">
          {(image.file.size / 1024 / 1024).toFixed(1)} MB
        </p>
        
        {/* Progress bar */}
        {!image.uploaded && image.progress > 0 && (
          <div className="mt-2">
            <Progress value={image.progress} className="h-1" />
          </div>
        )}
      </div>
    </div>
  );
};

export default ImagePreview;
