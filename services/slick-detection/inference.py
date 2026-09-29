import os
import torch
import numpy as np
import rasterio
from unet_model import UNet
from shapely.geometry import shape
import rasterio.features

class SlickDetector:
    def __init__(self, model_path=None):
        from pathlib import Path
        # Device selection: CUDA -> Apple Silicon MPS -> CPU
        if torch.cuda.is_available():
            self.device = torch.device('cuda')
        elif torch.backends.mps.is_available():
            self.device = torch.device('mps')
        else:
            self.device = torch.device('cpu')

        self.model = UNet(n_channels=1, n_classes=1).to(self.device)
        
        # Auto-detect trained weights if none specified
        if model_path is None:
            default_weights = Path(__file__).parent / "checkpoints" / "best_model.pt"
            if default_weights.exists():
                model_path = str(default_weights)

        if model_path and os.path.exists(str(model_path)):
            try:
                state = torch.load(model_path, map_location=self.device)
                if isinstance(state, dict) and "model_state" in state:
                    state = state["model_state"]
                self.model.load_state_dict(state)
                print(f"  ✓ Loaded trained weights from: {model_path} on {self.device}")
            except Exception as e:
                print(f"  ⚠ Failed to load weights from {model_path}: {e}")

        self.model.eval()

    def preprocess_image(self, image_path):
        """Read GeoTIFF and normalize for inference."""
        with rasterio.open(image_path) as src:
            # Read first band (e.g., VV polarization)
            img = src.read(1)
            transform = src.transform
            crs = src.crs
            
        # Basic SAR Preprocessing (Normalization, handling NaNs)
        img = np.nan_to_num(img, nan=0.0)
        img = (img - np.min(img)) / (np.max(img) - np.min(img) + 1e-8)
        
        # Convert to PyTorch Tensor (Batch, Channel, Height, Width)
        tensor = torch.from_numpy(img).float().unsqueeze(0).unsqueeze(0)
        return tensor.to(self.device), transform, crs, img.shape

    def detect(self, image_path):
        """Run inference and extract GeoJSON polygon of oil slick."""
        try:
            tensor, transform, crs, shape2d = self.preprocess_image(image_path)
            
            with torch.no_grad():
                # Forward pass through the real U-Net model
                output = self.model(tensor)
                
            # Convert prediction to binary mask (threshold > 0.5)
            pred_mask = (output.squeeze().cpu().numpy() > 0.5).astype(np.uint8)
            
            # Extract polygons using rasterio
            polygons = []
            for geom, val in rasterio.features.shapes(pred_mask, transform=transform):
                if val == 1:  # 1 represents the oil slick
                    polygons.append(geom)

            area_sq_km = 0.0
            if len(polygons) > 0:
                pixel_count = int(np.sum(pred_mask == 1))
                dx = abs(transform[0])
                dy = abs(transform[4])
                if dx < 1.0:
                    # Geographic CRS (degrees)
                    lat_center = (transform[3] + transform[3] + shape2d[0] * transform[4]) / 2.0
                    km_per_deg_lon = 111.32 * np.cos(np.radians(lat_center))
                    km_per_deg_lat = 110.57
                    pixel_area_km2 = (dx * km_per_deg_lon) * (dy * km_per_deg_lat)
                else:
                    # Projected CRS (meters)
                    pixel_area_km2 = (dx * dy) / 1e6
                area_sq_km = pixel_count * pixel_area_km2

            return {
                "status": "success",
                "polygon": polygons[0] if polygons else None,
                "confidence": float(output.max().item()),
                "area_sq_km": round(float(area_sq_km), 2)
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

# For quick local testing without FastAPI overhead
if __name__ == "__main__":
    detector = SlickDetector()
    print("Real PyTorch Model initialized and ready for inference!")
