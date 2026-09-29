import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface MapViewProps {
  stage: number;
  slickPolygon?: number[][];
  originBbox?: number[];
  candidates?: any[];
  sarImageSrc?: string;
  showSarOverlay?: boolean;
}

const ARABIAN_SEA = { lat: 18.2, lng: 70.5, zoom: 7 };

// SAR image overlay bounds — matches the Arabian Sea slick area
const SAR_BOUNDS: L.LatLngBoundsExpression = [[17.9, 70.1], [18.6, 70.9]];

// Vessel track paths for visualization (supports both real and mock MMSIs)
const VESSEL_TRACKS: Record<string, number[][]> = {
  '419001234': [[17.8, 70.5],[18.0, 70.7],[18.34, 71.04],[18.5, 71.2],[18.7, 71.4]],
  '636019876': [[17.2, 69.8],[17.8, 70.1],[18.5, 70.4],[19.2, 70.8]],
  '419098765': [[18.8, 72.6],[18.9, 72.75],[19.0, 72.8]],
  '123456789': [[18.8, 69.8],[18.6, 70.0],[18.4, 70.2],[18.2, 70.4],[18.1, 70.5]],
  '987654321': [[19.2, 71.5],[19.0, 71.2],[18.8, 71.0],[18.5, 70.8]],
  '555123456': [[17.8, 70.8],[18.0, 70.6],[18.1, 70.5]],
};

export default function MapView({ stage, slickPolygon, originBbox, candidates, sarImageSrc, showSarOverlay }: MapViewProps) {
  const mapRef       = useRef<L.Map | null>(null);
  const layersRef    = useRef<L.Layer[]>([]);
  const sarOverlayRef = useRef<L.ImageOverlay | null>(null);
  const sarMarkerRef  = useRef<L.Marker | null>(null);

  // Init map once
  useEffect(() => {
    if (mapRef.current) return;
    const map = L.map('leaflet-map', {
      center: [ARABIAN_SEA.lat, ARABIAN_SEA.lng],
      zoom:   ARABIAN_SEA.zoom,
      zoomControl: true,
    });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      opacity: 0.5,
    }).addTo(map);

    // Dark overlay tile
    L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png', {
      attribution: '© Stadia Maps',
      opacity: 0.85,
    }).addTo(map);

    mapRef.current = map;
  }, []);

  // SAR image overlay — always visible, updates when image changes
  useEffect(() => {
    if (!mapRef.current || !showSarOverlay || !sarImageSrc) return;

    // Remove old overlay
    if (sarOverlayRef.current) {
      mapRef.current.removeLayer(sarOverlayRef.current);
      sarOverlayRef.current = null;
    }
    if (sarMarkerRef.current) {
      mapRef.current.removeLayer(sarMarkerRef.current);
      sarMarkerRef.current = null;
    }

    // Add SAR image overlay at slick coordinates
    const overlay = L.imageOverlay(sarImageSrc, SAR_BOUNDS, {
      opacity: 0.82,
      interactive: true,
    }).addTo(mapRef.current);
    overlay.bindPopup(`
      <b>📡 SAR Satellite Image</b><br/>
      Sentinel-1A · VV Polarization<br/>
      Acquired: 24 Sep 2026 · 06:00 UTC<br/>
      Area: 70.1–70.9°E, 17.9–18.6°N
    `);
    sarOverlayRef.current = overlay;

    // Pulsing indicator marker at center of SAR image
    const pulseIcon = L.divIcon({
      className: '',
      html: `
        <div style="position:relative;width:40px;height:40px;transform:translate(-50%,-50%)">
          <div style="
            position:absolute;inset:0;border-radius:50%;
            border:2px solid #a5b4fc;
            animation:sarPulse 2s ease-out infinite;
            opacity:0.8;
          "></div>
          <div style="
            position:absolute;inset:8px;border-radius:50%;
            border:2px solid #a5b4fc;
            animation:sarPulse 2s ease-out infinite 0.6s;
            opacity:0.5;
          "></div>
          <div style="
            position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
            width:10px;height:10px;border-radius:50%;
            background:#a5b4fc;box-shadow:0 0 10px #a5b4fc;
          "></div>
        </div>
        <style>
          @keyframes sarPulse {
            0%   { transform:scale(0.5); opacity:1; }
            100% { transform:scale(2.2); opacity:0; }
          }
        </style>
      `,
      iconSize:   [0, 0],
      iconAnchor: [0, 0],
    });

    const center = L.latLngBounds(SAR_BOUNDS).getCenter();
    const marker = L.marker(center, { icon: pulseIcon, zIndexOffset: 500 })
      .addTo(mapRef.current)
      .bindTooltip('📡 SAR Imagery', {
        permanent: true, direction: 'top', offset: [-5, -22],
        className: 'sar-label-tooltip',
      });
    sarMarkerRef.current = marker;

  }, [sarImageSrc, showSarOverlay]);

  // Clear all dynamic layers
  const clearLayers = () => {
    layersRef.current.forEach(l => mapRef.current?.removeLayer(l));
    layersRef.current = [];
  };

  const addLayer = (layer: L.Layer) => {
    layer.addTo(mapRef.current!);
    layersRef.current.push(layer);
  };

  // Stage 0: Clear everything
  useEffect(() => {
    if (!mapRef.current) return;
    if (stage === 0) { clearLayers(); return; }

    clearLayers();

    // Stage 1+: Draw slick polygon
    if (stage >= 1 && slickPolygon && slickPolygon.length > 0) {
      const coords = slickPolygon.map(c => [c[1], c[0]] as [number, number]);
      const slick = L.polygon(coords, {
        color:       '#ef4444',
        fillColor:   '#ef4444',
        fillOpacity: 0.35,
        weight:      2,
        dashArray:   '4 4',
      }).bindPopup('<b>🛢️ Oil Slick Detected</b><br>Area: 14.5 sq km<br>Confidence: 91%');
      addLayer(slick);

      // Pulse effect using circle
      const center = L.latLng(18.25, 70.45);
      const pulse = L.circle(center, { radius: 5000, color: '#ef4444', fillOpacity: 0.08, weight: 1 });
      addLayer(pulse);
    }

    // Stage 2+: Draw origin probability bbox
    if (stage >= 2 && originBbox && originBbox.length === 4) {
      const [minLon, minLat, maxLon, maxLat] = originBbox;
      const bbox = L.rectangle([[minLat, minLon],[maxLat, maxLon]], {
        color:       '#3b82f6',
        fillColor:   '#3b82f6',
        fillOpacity: 0.1,
        weight:      1.5,
        dashArray:   '8 4',
      }).bindPopup('<b>🌊 Origin Probability Region</b><br>Backward drift hindcast<br>Confidence: High');
      addLayer(bbox);

      // Probability circles (hotspots)
      const hotspots: [number, number, number][] = [
        [18.4, 70.2, 8000], [18.3, 70.35, 5000], [18.5, 70.1, 6000],
      ];
      hotspots.forEach(([lat, lng, r]) => {
        const c = L.circle([lat, lng], {
          radius: r, color: '#60a5fa', fillColor: '#3b82f6', fillOpacity: 0.18, weight: 1,
        });
        addLayer(c);
      });
    }

    // Stage 3+: Draw AIS vessel tracks
    if (stage >= 3 && candidates && candidates.length > 0) {
      const COLORS: Record<number, string> = { 0: '#ef4444', 1: '#f59e0b', 2: '#3b82f6' };
      candidates.forEach((c, idx) => {
        const track = VESSEL_TRACKS[c.mmsi] || [];
        if (track.length < 2) return;

        const latLngs = track.map(([lat, lng]) => L.latLng(lat, lng));
        const color   = COLORS[idx] ?? '#8b949e';

        // Dashed line for track
        const line = L.polyline(latLngs, {
          color, weight: idx === 0 ? 3 : 2, opacity: 0.85, dashArray: idx === 0 ? undefined : '6 4',
        }).bindPopup(
          `<b>${c.name}</b><br>MMSI: ${c.mmsi}<br>Score: ${(c.score * 100).toFixed(0)}%<br>Anomaly: ${c.anomaly}`
        );
        addLayer(line);

        // Vessel marker at last position
        const lastPos = latLngs[latLngs.length - 1];
        const icon = L.divIcon({
          className: '',
          html: `<div style="width:12px;height:12px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 0 8px ${color}"></div>`,
          iconSize:   [12, 12],
          iconAnchor: [6, 6],
        });
        const marker = L.marker(lastPos, { icon })
          .bindPopup(`<b>${c.name}</b><br>Score: ${(c.score * 100).toFixed(0)}%`);
        addLayer(marker);
      });
    }
  }, [stage, slickPolygon, originBbox, candidates]);

  return (
    <div id="leaflet-map" style={{ position: 'absolute', inset: 0, borderRadius: 14, zIndex: 1 }} />
  );
}


interface MapViewProps {
  stage: number;
  slickPolygon?: number[][];
  originBbox?: number[];
  candidates?: any[];
}

