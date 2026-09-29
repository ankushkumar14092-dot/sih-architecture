from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import sys, os
from datetime import datetime

sys.path.append(os.path.dirname(__file__))
from simulation import DriftSimulator

app = FastAPI(title="Drift Hindcast Service", version="1.0.0")
simulator = DriftSimulator(use_dummy_forcing=True)

class HindcastRequest(BaseModel):
    slick_polygon: Dict[str, Any]
    detection_time: str
    earliest_spill_time: str
    latest_spill_time: str
    forecast_duration_hours: int = 72
    leeway_factor: float = 0.03
    particle_count: int = 2000

@app.get("/health")
def health():
    return {"status": "healthy", "service": "drift-hindcast"}

@app.post("/hindcast")
async def hindcast(req: HindcastRequest):
    """
    Run OpenDrift backward simulation from the detected slick polygon.
    """
    try:
        # Extract centroid from the polygon for seeding
        coords = req.slick_polygon.get("geometry", {}).get("coordinates", [[[70.5, 18.2]]])[0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        slick_lon = sum(lons) / len(lons)
        slick_lat = sum(lats) / len(lats)
        
        det_time = datetime.fromisoformat(req.detection_time.replace("Z", ""))
        days_back = (det_time - datetime.fromisoformat(req.earliest_spill_time.replace("Z", ""))).days or 3
        
        result = simulator.run_hindcast(slick_lon=slick_lon, slick_lat=slick_lat, 
                                        detection_time=det_time, days_back=days_back)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        
        return {
            "hindcast_id": "hind-proto-001",
            "origin_probability": {
                "grid_uri": result.get("output_file", "proto-grid.nc"),
                "origin_bbox": result.get("origin_bbox", [70.0, 17.8, 71.2, 18.9]),
                "crs": "EPSG:4326"
            },
            "spill_time_window": {
                "start": result.get("spill_time_estimate", req.earliest_spill_time),
                "end": req.detection_time
            },
            "metadata": {
                "particle_count": req.particle_count,
                "engine_version": "opendrift-1.x"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("service:app", host="0.0.0.0", port=8002, reload=True)
