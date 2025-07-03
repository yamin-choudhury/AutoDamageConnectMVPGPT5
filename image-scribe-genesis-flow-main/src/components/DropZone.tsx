
import { useCallback } from "react";
import { Upload, Image } from "lucide-react";

interface DropZoneProps {
  onFileSelect: (files: FileList | null) => void;
}

const DropZone = ({ onFileSelect }: DropZoneProps) => {
  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      const files = e.dataTransfer.files;
      onFileSelect(files);
    },
    [onFileSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onFileSelect(e.target.files);
    },
    [onFileSelect]
  );

  return (
    <div
      className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors cursor-pointer bg-gray-50/50"
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onClick={() => document.getElementById('file-input')?.click()}
    >
      <input
        id="file-input"
        type="file"
        multiple
        accept="image/*"
        onChange={handleFileInput}
        className="hidden"
      />
      
      <div className="space-y-4">
        <div className="flex justify-center">
          <div className="p-3 bg-blue-100 rounded-full">
            <Upload className="h-8 w-8 text-blue-600" />
          </div>
        </div>
        
        <div>
          <h3 className="text-lg font-medium text-gray-900">Upload your images</h3>
          <p className="text-gray-500 mt-1">
            Drag and drop images here, or click to browse
          </p>
        </div>
        
        <div className="flex items-center justify-center space-x-2 text-sm text-gray-400">
          <Image className="h-4 w-4" />
          <span>Supports JPG, PNG, GIF, WebP</span>
        </div>
      </div>
    </div>
  );
};

export default DropZone;
