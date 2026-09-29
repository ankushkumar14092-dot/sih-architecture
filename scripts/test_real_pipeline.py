#!/usr/bin/env python3
"""
SIH26143 – End-to-End Real Data Pipeline Test
==============================================
Runs the full 3-stage attribution pipeline using real GeoTIFF and AIS data:
  1. SAR Slick Detection: PyTorch U-Net on GeoTIFF image
  2. Drift Hindcast: Lagrangian / OpenDrift backward trajectory to origin
  3. AIS Correlation: Trajectory, proximity & anomaly analysis on vessel tracks
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Setup paths
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR / "services" / "slick-detection"))
sys.path.append(str(ROOT_DIR / "services" / "drift-hindcast"))
sys.path.append(str(ROOT_DIR / "services" / "ais-correlation"))

from inference import SlickDetector
from simulation import DriftSimulator
from scorer import AisCorrelator

def run_real_test():
    print("=" * 70)
    print(" 🛰️  SIH26143: REAL DATA TEST RUNNER")
    print("    Satellite SAR + Drift Hindcast + AIS Vessel Attribution")
    print("=" * 70 + "\n")

    # -------------------------------------------------------------
    # STAGE 1: Real SAR GeoTIFF Slick Detection (PyTorch U-Net)
    # -------------------------------------------------------------
    sar_sample_path = ROOT_DIR / "data" / "sample" / "sar" / "sample_sentinel1_slick.tif"
    print(f"📡 [STAGE 1] Loading SAR GeoTIFF from:\n    {sar_sample_path}")
    
    if not sar_sample_path.exists():
        print(f"❌ Error: SAR GeoTIFF not found at {sar_sample_path}")
        return

    detector = SlickDetector()
    det_result = detector.detect(str(sar_sample_path))
    
    if det_result.get("status") != "success":
        print(f"❌ Slick Detection Error: {det_result.get('message')}")
        return

    poly = det_result.get("polygon")
    area_km2 = det_result.get("area_sq_km", 0.0)
    conf = det_result.get("confidence", 0.0)

    print(f"  ✓ Model Status : {det_result['status'].upper()}")
    print(f"  ✓ Slick Area   : {area_km2:.2f} km²")
    print(f"  ✓ Confidence   : {conf:.1%}")
    
    # Calculate slick center coordinates from polygon coordinates
    if poly and "coordinates" in poly:
        coords = poly["coordinates"][0]
        slick_lons = [pt[0] for pt in coords]
        slick_lats = [pt[1] for pt in coords]
        slick_lon = float(sum(slick_lons) / len(slick_lons))
        slick_lat = float(sum(slick_lats) / len(slick_lats))
        print(f"  ✓ Slick Center : Lon {slick_lon:.4f}°, Lat {slick_lat:.4f}°")
    else:
        slick_lon, slick_lat = 71.75, 18.75
        print(f"  ✓ Default Slick Center: Lon {slick_lon}°, Lat {slick_lat}°")

    print("\n" + "-" * 70)

    # -------------------------------------------------------------
    # STAGE 2: Oceanographic Drift Hindcast (OpenDrift / Lagrangian)
    # -------------------------------------------------------------
    detection_time = datetime(2026, 9, 24, 6, 0)
    print(f"🌊 [STAGE 2] Running 72-Hour Backward Drift Hindcast...")
    print(f"    Detection Timestamp: {detection_time.isoformat()}")

    simulator = DriftSimulator()
    hindcast = simulator.run_hindcast(
        slick_lon=slick_lon,
        slick_lat=slick_lat,
        detection_time=detection_time,
        days_back=3
    )

    origin_bbox = hindcast.get("origin_bbox", [slick_lon - 0.5, slick_lat - 0.5, slick_lon + 0.1, slick_lat + 0.1])
    spill_time_est = hindcast.get("spill_time_estimate", "2026-09-21T06:00:00")
    engine_used = hindcast.get("engine", "Physics Engine")

    print(f"  ✓ Simulation Engine : {engine_used}")
    print(f"  ✓ Estimated Origin  : Bounding Box [Lon {origin_bbox[0]:.4f}..{origin_bbox[2]:.4f}, Lat {origin_bbox[1]:.4f}..{origin_bbox[3]:.4f}]")
    print(f"  ✓ Spill Time Window : {spill_time_est} to {detection_time.isoformat()}")

    print("\n" + "-" * 70)

    # -------------------------------------------------------------
    # STAGE 3: AIS Correlation & Suspect Vessel Scoring
    # -------------------------------------------------------------
    ais_path = ROOT_DIR / "data" / "sample" / "ais" / "real_ais_tracks.csv"
    print(f"🚢 [STAGE 3] Correlating with AIS Vessel Dataset from:\n    {ais_path}")

    correlator = AisCorrelator()
    time_window = {"start": spill_time_est, "end": detection_time.isoformat()}
    candidates = correlator.correlate(str(ais_path), origin_bbox, time_window)

    print(f"  ✓ Evaluated Vessels : {len(candidates)} vessels tracked\n")
    print("  🏆 Attribution Results (Ranked by Probability):")
    print("  " + "-" * 66)
    print(f"  {'Rank':<5} {'Score':<8} {'MMSI':<12} {'Vessel Name':<20} {'Anomalies Detected'}")
    print("  " + "-" * 66)

    for i, c in enumerate(candidates, 1):
        flag = "🚨 PRIMARY SUSPECT" if i == 1 and c['score'] > 0.75 else "   "
        print(f"  #{i:<4} {c['score']:<8.2f} {c['mmsi']:<12} {c['name']:<20} {c['anomaly']} {flag}")

    print("  " + "-" * 66)
    
    if candidates:
        culprit = candidates[0]
        print(f"\n🎯 [FORENSIC VERDICT]")
        print(f"   Vessel Identified  : {culprit['name']} (MMSI: {culprit['mmsi']})")
        print(f"   Attribution Score  : {culprit['score']:.0%}")
        print(f"   Behavioral Anomaly : {culprit['anomaly']}")
        print(f"   Proximity Evidence : Score {culprit['evidence']['proximity_score']:.2f}")
        print(f"   Anomaly Evidence   : Score {culprit['evidence']['anomaly_score']:.2f}")

    print("\n" + "=" * 70)
    print(" ✅ TEST COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_real_test()
