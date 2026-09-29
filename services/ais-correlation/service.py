from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import sys, os

sys.path.append(os.path.dirname(__file__))
from scorer import AisCorrelator

app = FastAPI(title="AIS Correlation Service", version="1.0.0")
correlator = AisCorrelator()

class ScoringWeights(BaseModel):
    proximity: float = 0.35
    trajectory: float = 0.25
    timing: float = 0.20
    anomaly: float = 0.20

class CorrelationRequest(BaseModel):
    origin_probability: Dict[str, Any]
    spill_time_window: Dict[str, str]
    ais_track_uri: Optional[str] = None
    scoring_weights: Optional[ScoringWeights] = None

@app.get("/health")
def health():
    return {"status": "healthy", "service": "ais-correlation"}

@app.post("/correlate")
async def correlate(req: CorrelationRequest):
    """
    Run real AIS correlation scoring against the hindcast origin bounding box.
    """
    try:
        weights = None
        if req.scoring_weights:
            weights = {
                "proximity": req.scoring_weights.proximity,
                "trajectory": req.scoring_weights.trajectory,
                "timing": req.scoring_weights.timing,
                "anomaly": req.scoring_weights.anomaly,
            }
        
        c = AisCorrelator(weights=weights)
        origin_bbox = req.origin_probability.get("origin_bbox", [70.0, 17.8, 71.2, 18.9])
        ais_uri = req.ais_track_uri or "dummy_path.parquet"  # fallback to dummy
        
        candidates = c.correlate(ais_uri, origin_bbox, req.spill_time_window)
        
        return {
            "correlation_id": "corr-proto-001",
            "candidates": candidates,
            "scoring_metadata": {
                "model_version": "weighted-v1",
                "weights_used": c.weights,
                "generated_at": req.spill_time_window.get("end")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("service:app", host="0.0.0.0", port=8003, reload=True)
