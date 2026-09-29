try:
    from opendrift.models.openoil import OpenOil
    OPENDRIFT_AVAILABLE = True
except ImportError:
    OPENDRIFT_AVAILABLE = False

from datetime import datetime, timedelta
import numpy as np
import os

class DriftSimulator:
    def __init__(self, use_dummy_forcing=True):
        self.use_dummy_forcing = use_dummy_forcing

    def run_hindcast(self, slick_lon, slick_lat, detection_time, days_back=3, current_u=0.15, current_v=0.10, wind_u=4.5, wind_v=2.5):
        """
        Runs backward trajectory simulation.
        If OpenDrift is installed, uses OpenOil.
        Otherwise uses Lagrangian particle advection with leeway factor (3% wind + current).
        """
        if OPENDRIFT_AVAILABLE:
            try:
                o = OpenOil(loglevel=50)
                from opendrift.readers import reader_basemap_landmask
                reader_basemap = reader_basemap_landmask.Reader(
                    llcrnrlon=slick_lon-5, llcrnrlat=slick_lat-5,
                    urcrnrlon=slick_lon+5, urcrnrlat=slick_lat+5,
                    resolution='i', projection='merc')
                o.add_reader([reader_basemap])
                o.set_config('environment:fallback:x_wind', -wind_u)
                o.set_config('environment:fallback:y_wind', -wind_v)
                o.set_config('environment:fallback:x_sea_water_velocity', -current_u)
                o.set_config('environment:fallback:y_sea_water_velocity', -current_v)
                o.seed_elements(lon=slick_lon, lat=slick_lat, radius=1000, 
                                number=2000, time=detection_time,
                                oil_type='GENERIC MEDIUM CRUDE')
                o.run(duration=timedelta(days=days_back), time_step=timedelta(hours=-1))
                lons = o.elements_lon
                lats = o.elements_lat
                return {
                    "status": "success",
                    "engine": "OpenDrift-OpenOil",
                    "origin_bbox": [float(lons.min()), float(lats.min()), float(lons.max()), float(lats.max())],
                    "spill_time_estimate": (detection_time - timedelta(days=days_back)).isoformat()
                }
            except Exception as e:
                print(f"OpenDrift execution failed ({e}), falling back to Lagrangian advection engine")

        # ── High-Precision Lagrangian Particle Back-Advection ──
        # Total drift velocity = current + (0.03 * wind) + turbulent diffusion
        leeway = 0.03
        total_u_ms = current_u + leeway * wind_u  # m/s eastward
        total_v_ms = current_v + leeway * wind_v  # m/s northward
        
        # Convert to degrees per hour
        # 1 deg lat ≈ 111,000 m; 1 deg lon ≈ 111,000 * cos(lat) m
        meters_per_deg_lat = 111000.0
        meters_per_deg_lon = 111000.0 * np.cos(np.radians(slick_lat))
        
        hours = days_back * 24
        # In reverse time (hindcast): particles moved FROM origin TO current slick position
        # So origin_pos = current_pos - (velocity * time)
        np.random.seed(42)
        n_particles = 1000
        # Turbulent diffusion spread over time
        diffusion_sigma_m = np.sqrt(2 * 1.0 * (hours * 3600))  # Kh ≈ 1 m^2/s
        
        dx_m = (total_u_ms * hours * 3600) + np.random.normal(0, diffusion_sigma_m, n_particles)
        dy_m = (total_v_ms * hours * 3600) + np.random.normal(0, diffusion_sigma_m, n_particles)
        
        origin_lons = slick_lon - (dx_m / meters_per_deg_lon)
        origin_lats = slick_lat - (dy_m / meters_per_deg_lat)
        
        return {
            "status": "success",
            "engine": "Lagrangian-BackAdvection",
            "particles_simulated": n_particles,
            "origin_center": [round(float(origin_lons.mean()), 4), round(float(origin_lats.mean()), 4)],
            "origin_bbox": [
                round(float(np.percentile(origin_lons, 5)), 4),
                round(float(np.percentile(origin_lats, 5)), 4),
                round(float(np.percentile(origin_lons, 95)), 4),
                round(float(np.percentile(origin_lats, 95)), 4)
            ],
            "spill_time_estimate": (detection_time - timedelta(days=days_back)).isoformat()
        }

if __name__ == "__main__":
    sim = DriftSimulator()
    det_time = datetime(2026, 9, 24, 12, 0, 0)
    print("Running OpenDrift Backward Hindcast...")
    result = sim.run_hindcast(slick_lon=70.5, slick_lat=18.2, detection_time=det_time)
    print(f"Hindcast completed. Probable origin bounding box: {result.get('origin_bbox')}")
