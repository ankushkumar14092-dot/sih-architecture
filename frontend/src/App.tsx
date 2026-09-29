import React, { useState } from 'react';
import './index.css';
import MapView from './MapView';
import CasePanel from './CasePanel';
import ResultsPanel from './ResultsPanel';

const API = 'http://localhost:8000';

// Default slick polygon (Arabian Sea) for map display before pipeline
const DEFAULT_POLYGON = [[70.3,18.1],[70.6,18.1],[70.6,18.4],[70.3,18.4],[70.3,18.1]];

export default function App() {
  const [stage,  setStage]  = useState(0); // 0=idle 1=detect 2=hindcast 3=correlate 4=done
  const [result, setResult] = useState<any>(null);
  const [error,  setError]  = useState<string | null>(null);

  // SAR image state — lifted here so both CasePanel and MapView can share it
  const [sarImageSrc,   setSarImageSrc]   = useState<string>('/sar_raw.jpg');
  const [showDetected,  setShowDetected]  = useState(false);

  const slickPoly  = result?.detection?.slick_polygon?.geometry?.coordinates?.[0] ?? (stage > 0 ? DEFAULT_POLYGON : undefined);
  const originBbox = result?.hindcast?.origin_probability?.origin_bbox;
  const candidates = result?.correlation?.candidates;

  const runPipeline = async () => {
    setStage(1); setError(null); setResult(null);
    try {
      await delay(1200); setStage(2);
      await delay(1200); setStage(3);

      // Try real AI pipeline with Sentinel-1 SAR & real AIS tracks
      let resp = await fetch(`${API}/api/run-pipeline-real`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_uri:           'data/sample/sar/sample_sentinel1_slick.tif',
          sensor_type:         'SAR',
          acquisition_time:    '2026-09-24T06:00:00Z',
          earliest_spill_time: '2026-09-21T06:00:00Z',
        }),
      });
      if (!resp.ok) {
        resp = await fetch(`${API}/api/run-pipeline-mock`, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image_uri:           's3://imagery/S1A_2026.tif',
            sensor_type:         'SAR',
            acquisition_time:    '2026-09-24T05:42:00Z',
            earliest_spill_time: '2026-09-21T00:00:00Z',
          }),
        });
      }
      if (!resp.ok) throw new Error(`Backend error: ${resp.status}`);
      const data = await resp.json();
      await delay(600);
      setResult(data);
      setStage(4);
    } catch (e: any) {
      setError(e.message ?? 'Unknown error — is backend running on port 8000?');
      setStage(0);
    }
  };

  const reset = () => { setStage(0); setResult(null); setError(null); };


  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>

      {/* ── HEADER ── */}
      <header className="header">
        <div className="logo">
          <div className="logo-icon">🛢️</div>
          <div className="logo-text">
            <h1>Maritime Oil-Spill Attribution System</h1>
            <p>SIH 2026 · Problem #26143 · NTRO</p>
          </div>
        </div>
        <div className="header-right">
          <span className="badge badge-blue">Sentinel-1 SAR</span>
          <span className="badge badge-blue">OpenDrift</span>
          <span className="badge badge-blue">U-Net CNN</span>
          <span className={`badge ${stage === 4 ? 'badge-green' : stage > 0 ? 'badge-yellow' : 'badge-blue'}`}>
            {stage === 4 ? '✓ Attribution Complete' : stage > 0 ? '⟳ Running Pipeline...' : 'Standby'}
          </span>
        </div>
      </header>

      {/* ── LAYOUT ── */}
      <div className="layout">
        <CasePanel
          stage={stage}
          caseId={result?.case_id ?? null}
          onRun={runPipeline}
          onReset={reset}
          error={error}
          sarImageSrc={sarImageSrc}
          setSarImageSrc={setSarImageSrc}
          showDetected={showDetected}
          setShowDetected={setShowDetected}
        />

        {/* ── MAP ── */}
        <div className="map-panel" style={{ position: 'relative' }}>
          <MapView
            stage={stage}
            slickPolygon={slickPoly}
            originBbox={originBbox}
            candidates={candidates}
            sarImageSrc={showDetected ? '/sar_detected.jpg' : sarImageSrc}
            showSarOverlay={true}
          />

          {/* Legend */}
          <div style={{
            position: 'absolute', bottom: 16, left: 16,
            background: 'rgba(7,13,26,0.88)', border: '1px solid var(--border)',
            borderRadius: 8, padding: '8px 14px', backdropFilter: 'blur(10px)',
            display: 'flex', gap: 16, zIndex: 1000, fontSize: '0.7rem', color: 'var(--muted)',
          }}>
            {<LegendItem color="#a5b4fc" label="SAR Imagery" />}
            {stage >= 1 && <LegendItem color="#ef4444" label="Oil Slick" />}
            {stage >= 2 && <LegendItem color="#3b82f6" label="Origin Probability" dashed />}
            {stage >= 3 && <LegendItem color="#ef4444" label="Suspect #1" dot />}
            {stage >= 3 && <LegendItem color="#f59e0b" label="Suspect #2" dot />}
            {stage >= 3 && <LegendItem color="#3b82f6" label="Other Vessel" dot />}
            {stage === 0 && <span>Run pipeline to see map layers</span>}
          </div>

          {/* Status bar */}
          <div style={{
            position: 'absolute', bottom: 16, right: 16,
            background: 'rgba(7,13,26,0.88)', border: '1px solid var(--border)',
            borderRadius: 8, padding: '6px 12px', backdropFilter: 'blur(10px)',
            fontSize: '0.65rem', color: 'var(--muted)', zIndex: 1000,
          }}>
            70.5°E 18.2°N · Arabian Sea · EPSG:4326
          </div>
        </div>

        <ResultsPanel stage={stage} result={result} />
      </div>
    </div>
  );
}

function LegendItem({ color, label, dashed, dot }: { color: string; label: string; dashed?: boolean; dot?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      {dot ? (
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, boxShadow: `0 0 6px ${color}` }} />
      ) : (
        <div style={{
          width: 14, height: dashed ? 0 : 10,
          borderRadius: dashed ? 0 : 3,
          background: dashed ? undefined : color + '88',
          border: dashed ? `1.5px dashed ${color}` : `1.5px solid ${color}`,
        }} />
      )}
      <span>{label}</span>
    </div>
  );
}

const delay = (ms: number) => new Promise(r => setTimeout(r, ms));
