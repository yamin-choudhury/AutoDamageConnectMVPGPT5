
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface VehicleInfo {
  vin: string;
  registrationPlate: string;
  make: string;
  model: string;
  year: string;
  trimBodyStyle: string;
}

interface VehicleInfoFormProps {
  vehicleInfo: VehicleInfo;
  onVehicleInfoChange: (info: VehicleInfo) => void;
}

const VehicleInfoForm = ({ vehicleInfo, onVehicleInfoChange }: VehicleInfoFormProps) => {
  const handleInputChange = (field: keyof VehicleInfo, value: string) => {
    onVehicleInfoChange({
      ...vehicleInfo,
      [field]: value,
    });
  };

  return (
    <Card className="shadow-lg border-0 bg-white/80 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-xl">Vehicle Information</CardTitle>
        <p className="text-gray-600">
          Provide vehicle details to enhance document accuracy (optional).
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="vin">VIN (17 characters)</Label>
            <Input
              id="vin"
              type="text"
              placeholder="e.g., 1HGBH41JXMN109186"
              value={vehicleInfo.vin}
              onChange={(e) => handleInputChange('vin', e.target.value)}
              maxLength={17}
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="registration">Registration / Plate Number</Label>
            <Input
              id="registration"
              type="text"
              placeholder="e.g., ABC123"
              value={vehicleInfo.registrationPlate}
              onChange={(e) => handleInputChange('registrationPlate', e.target.value)}
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="make">Make</Label>
            <Input
              id="make"
              type="text"
              placeholder="e.g., Toyota"
              value={vehicleInfo.make}
              onChange={(e) => handleInputChange('make', e.target.value)}
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="model">Model</Label>
            <Input
              id="model"
              type="text"
              placeholder="e.g., Camry"
              value={vehicleInfo.model}
              onChange={(e) => handleInputChange('model', e.target.value)}
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="year">Year / Build Date</Label>
            <Input
              id="year"
              type="text"
              placeholder="e.g., 2023"
              value={vehicleInfo.year}
              onChange={(e) => handleInputChange('year', e.target.value)}
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="trim">Trim / Body Style</Label>
            <Input
              id="trim"
              type="text"
              placeholder="e.g., Saloon, Hatch, SUV"
              value={vehicleInfo.trimBodyStyle}
              onChange={(e) => handleInputChange('trimBodyStyle', e.target.value)}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default VehicleInfoForm;
