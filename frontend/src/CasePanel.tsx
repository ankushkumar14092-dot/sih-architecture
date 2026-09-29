interface CasePanelProps {
  stage: number;
  caseId: string | null;
  onRun: () => void;
  onReset: () => void;
  error: string | null;
  sarImageSrc: string;
  setSarImageSrc: (src: string) => void;
  showDetected: boolean;
  setShowDetected: (v: boolean) => void;
}

const STAGES = [
  { icon: '🛰️', label: 'Stage 1 · Slick Detection',  sub: 'U-Net CNN · SAR preprocessing',     color: 'blue' },
  { icon: '🌊', label: 'Stage 2 · Drift Hindcast',    sub: 'OpenDrift · ERA5 + HYCOM forcing',  color: 'teal' },
  { icon: '🚢', label: 'Stage 3 · AIS Correlation',   sub: 'Spatial-temporal scoring engine',   color: 'green' },
];

import { useState, useRef } from 'react';


export default function CasePanel({ stage, caseId, onRun, onReset, error, sarImageSrc, setSarImageSrc, showDetected, setShowDetected }: CasePanelProps) {
  const si = stage - 1;
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (file: File) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      setSarImageSrc(e.target?.result as string);
      setShowDetected(false);
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  return (
    <aside className="panel">
      <div className="panel-title">Case Workspace</div>

      {/* Case Info */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Case #SIH26143-A</div>
            <div className="card-meta">Arabian Sea Oil Spill · Sep 2026</div>
          </div>
          <span className={`badge ${stage === 4 ? 'badge-green' : stage > 0 ? 'badge-yellow' : 'badge-blue'}`}>
            {stage === 4 ? 'Complete' : stage > 0 ? 'Active' : 'Pending'}
          </span>
        </div>
        <div className="meta-grid" style={{ marginTop: 10 }}>
          <div className="meta-item"><div className="val">SAR</div><div className="lbl">Sensor</div></div>
          <div className="meta-item"><div className="val">VV/VH</div><div className="lbl">Polarization</div></div>
          <div className="meta-item"><div className="val">S-1A</div><div className="lbl">Platform</div></div>
          <div className="meta-item"><div className="val">24 Sep</div><div className="lbl">Acquired</div></div>
        </div>
        {caseId && (
          <div className="card-meta" style={{ marginTop: 8, fontFamily: 'monospace', fontSize: '0.7rem', color: 'var(--accent)' }}>
            ID: {caseId}
          </div>
        )}
      </div>

      {/* SAR Image Preview */}
      <div className="panel-title">SAR Image Preview</div>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>

        {/* Toggle Buttons */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
          <button
            onClick={() => setShowDetected(false)}
            style={{
              flex: 1, padding: '7px 0', fontSize: '0.68rem', fontWeight: 600,
              background: !showDetected ? 'rgba(59,130,246,0.15)' : 'transparent',
              color: !showDetected ? 'var(--accent)' : 'var(--muted)',
              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
              borderRight: '1px solid var(--border)', letterSpacing: '0.04em',
              transition: 'all 0.2s',
            }}
          >
            RAW SAR
          </button>
          <button
            onClick={() => setShowDetected(true)}
            style={{
              flex: 1, padding: '7px 0', fontSize: '0.68rem', fontWeight: 600,
              background: showDetected ? 'rgba(239,68,68,0.15)' : 'transparent',
              color: showDetected ? 'var(--danger)' : 'var(--muted)',
              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
              letterSpacing: '0.04em', transition: 'all 0.2s',
            }}
          >
            AI DETECTED
          </button>
        </div>

        {/* Image Display */}
        <div style={{ position: 'relative', width: '100%', aspectRatio: '1/1' }}>
          <img
            src={showDetected ? '/sar_detected.jpg' : sarImageSrc}
            alt={showDetected ? 'AI Detected Oil Slick' : 'Raw SAR Image'}
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', transition: 'opacity 0.3s ease' }}
          />
          {/* Overlay badge */}
          <div style={{
            position: 'absolute', top: 8, right: 8,
            background: 'rgba(7,13,26,0.82)', backdropFilter: 'blur(8px)',
            border: `1px solid ${showDetected ? 'rgba(239,68,68,0.4)' : 'rgba(59,130,246,0.3)'}`,
            borderRadius: 6, padding: '3px 8px',
            fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.06em',
            color: showDetected ? 'var(--danger)' : 'var(--accent)',
          }}>
            {showDetected ? '🛰️ U-Net CNN Output' : sarImageSrc !== '/sar_raw.jpg' ? '📂 Uploaded Image' : '📡 Sentinel-1 SAR'}
          </div>
          {showDetected && (
            <div style={{
              position: 'absolute', bottom: 8, left: 8,
              background: 'rgba(239,68,68,0.12)', backdropFilter: 'blur(8px)',
              border: '1px solid rgba(239,68,68,0.35)', borderRadius: 6,
              padding: '3px 8px', fontSize: '0.6rem', fontWeight: 600,
              color: 'var(--danger)',
            }}>
              14.5 km² · 91% confidence
            </div>
          )}
          {/* Change image button on hover */}
          {!showDetected && (
            <button
              onClick={() => fileInputRef.current?.click()}
              title="Upload your own SAR image"
              style={{
                position: 'absolute', bottom: 8, right: 8,
                background: 'rgba(7,13,26,0.82)', backdropFilter: 'blur(8px)',
                border: '1px solid rgba(88,166,255,0.3)', borderRadius: 6,
                padding: '4px 9px', fontSize: '0.6rem', fontWeight: 600,
                color: 'var(--accent)', cursor: 'pointer', fontFamily: 'inherit',
                letterSpacing: '0.04em', transition: 'all 0.2s',
              }}
            >
              ↑ Change
            </button>
          )}
        </div>

        {/* Upload Zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{
            padding: '10px 14px',
            borderTop: '1px solid var(--border)',
            background: isDragging ? 'rgba(59,130,246,0.08)' : 'transparent',
            display: 'flex', alignItems: 'center', gap: 8,
            cursor: 'pointer', transition: 'background 0.2s',
          }}
        >
          <span style={{ fontSize: '1rem' }}>📁</span>
          <div>
            <div style={{ fontSize: '0.68rem', fontWeight: 600, color: isDragging ? 'var(--accent)' : 'var(--text)' }}>
              {isDragging ? 'Drop to upload' : 'Upload SAR Image'}
            </div>
            <div style={{ fontSize: '0.6rem', color: 'var(--muted)', marginTop: 1 }}>
              Click or drag & drop · .tif, .jpg, .png
            </div>
          </div>
          {sarImageSrc !== '/sar_raw.jpg' && (
            <button
              onClick={(e) => { e.stopPropagation(); setSarImageSrc('/sar_raw.jpg'); }}
              title="Remove uploaded image"
              style={{
                marginLeft: 'auto', background: 'rgba(239,68,68,0.12)',
                border: '1px solid rgba(239,68,68,0.3)', borderRadius: 5,
                color: 'var(--danger)', cursor: 'pointer', fontSize: '0.6rem',
                fontWeight: 700, padding: '2px 7px', fontFamily: 'inherit',
              }}
            >
              ✕ Reset
            </button>
          )}
        </div>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,.tif,.tiff"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFileSelect(file);
            e.target.value = ''; // allow re-uploading same file
          }}
        />
      </div>



      {/* Data Sources */}
      <div className="panel-title">Data Sources</div>
      {[
        { name: 'Sentinel-1 SAR', detail: 'S1A_2026_09_24.tif', status: 'Ready', color: 'var(--success)' },
        { name: 'ERA5 Wind Data', detail: '72-hr coverage',       status: stage >= 2 ? 'Used' : 'Available', color: stage >= 2 ? 'var(--accent)' : 'var(--muted)' },
        { name: 'HYCOM Currents', detail: 'Ocean forcing',        status: stage >= 2 ? 'Used' : 'Available', color: stage >= 2 ? 'var(--accent)' : 'var(--muted)' },
        { name: 'AIS Track Data', detail: 'MarineCadastre',       status: stage >= 3 ? 'Used' : 'Available', color: stage >= 3 ? 'var(--accent)' : 'var(--muted)' },
      ].map(src => (
        <div className="card" key={src.name} style={{ padding: '10px 14px' }}>
          <div className="card-header" style={{ marginBottom: 0 }}>
            <div className="card-title" style={{ fontSize: '0.8rem' }}>{src.name}</div>
            <span style={{ fontSize: '0.7rem', color: src.color, fontWeight: 600 }}>{src.status}</span>
          </div>
          <div className="card-meta">{src.detail}</div>
        </div>
      ))}

      {/* Pipeline stages */}
      <div className="panel-title" style={{ marginTop: 4 }}>AI Pipeline</div>
      {STAGES.map((s, i) => (
        <div key={i} className={`stage-row ${si === i ? 'active' : si > i ? 'done' : 'idle'}`}>
          <div className={`stage-icon ${s.color} ${si === i ? 'spin' : ''}`}>{s.icon}</div>
          <div className="stage-info">
            <div className="label">{s.label}</div>
            <div className="sub">{s.sub}</div>
          </div>
          <div className="stage-check">
            {si > i  && <span style={{ color: 'var(--success)' }}>✓</span>}
            {si === i && <span style={{ color: 'var(--accent)', animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>}
          </div>
        </div>
      ))}

      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {error && (
          <div style={{ color: 'var(--danger)', fontSize: '0.75rem', padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.3)' }}>
            ⚠ {error}
          </div>
        )}
        <button
          className={`run-btn ${stage === 4 ? 'done' : ''}`}
          onClick={stage === 4 ? onReset : onRun}
          disabled={stage > 0 && stage < 4}
        >
          {stage === 0 && <><span>▶</span> Run Full Attribution Pipeline</>}
          {stage > 0 && stage < 4 && <><span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span> Processing Stage {stage} of 3...</>}
          {stage === 4 && <><span>↺</span> Reset &amp; Run Again</>}
        </button>
      </div>
    </aside>
  );
}


