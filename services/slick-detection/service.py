from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys
import os

# Add parent dir so we can import the inference module
sys.path.append(os.path.dirname(__file__))
from inference import SlickDetector

app = FastAPI(title="Slick Detection Service", version="1.0.0")
detector = SlickDetector()  # loads U-Net (no weights = random init, ready for real weights)

class SlickDetectionRequest(BaseModel):
    image_uri: str
    sensor_type: str = "SAR"
    acquisition_time: str
    product_id: Optional[str] = None
    polarization: Optional[str] = "VV"

@app.get("/health")
def health():
    return {"status": "healthy", "service": "slick-detection"}

@app.post("/detect-slick")
async def detect_slick(req: SlickDetectionRequest):
    """
    Accepts a SAR/EO image URI and runs the real PyTorch U-Net inference.
    For prototype: uses a dummy local path if the URI is not a real file.
    """
    # Check if local file exists, else run a dummy inference
    local_path = req.image_uri.replace("s3://", "/tmp/")  
    
    if not os.path.exists(local_path):
        # Prototype fallback: return a mock result since no real SAR file is available
        return {
            "detection_id": "det-proto-001",
            "sensor_type": req.sensor_type,
            "acquisition_time": req.acquisition_time,
            "slick_polygon": {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[70.3, 18.1],[70.6, 18.1],[70.6, 18.4],[70.3, 18.4],[70.3, 18.1]]]
                },
                "properties": {}
            },
            "geometry_stats": {"area_sq_km": 14.5, "perimeter_km": 21.3},
            "model_version": "unet-v1-untrained",
            "model_confidence": 0.91,
            "age_estimate": None,
            "quality_warnings": ["Using prototype mock result — real SAR image not found at URI"]
        }
    
    # Run real inference on a local GeoTIFF
    result = detector.detect(local_path)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    
    return {
        "detection_id": "det-real-001",
        "sensor_type": req.sensor_type,
        "acquisition_time": req.acquisition_time,
        "slick_polygon": {"type": "Feature", "geometry": result["polygon"], "properties": {}},
        "geometry_stats": {"area_sq_km": result["area_sq_km"]},
        "model_version": "unet-v1",
        "model_confidence": result["confidence"],
        "age_estimate": None,
        "quality_warnings": []
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("service:app", host="0.0.0.0", port=8001, reload=True)
