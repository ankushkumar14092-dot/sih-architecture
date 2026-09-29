interface ResultsPanelProps {
  stage: number;
  result: any;
}

const RANK_CLASSES = ['rank-1', 'rank-2', 'rank-3'];
const RANK_BADGE   = ['badge-red', 'badge-yellow', 'badge-blue'];

export default function ResultsPanel({ stage, result }: ResultsPanelProps) {
  const detection   = result?.detection;
  const hindcast    = result?.hindcast;
  const candidates  = result?.correlation?.candidates ?? [];

  return (
    <aside className="panel">
      <div className="panel-title">Analysis Results</div>

      {/* Empty state */}
      {stage === 0 && (
        <div style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:12, color:'var(--muted)' }}>
          <div style={{ fontSize:'2.5rem' }}>📊</div>
          <div style={{ fontSize:'0.8rem', textAlign:'center' }}>
            Run the pipeline to see<br/>analysis results here
          </div>
        </div>
      )}

      {/* Stage 1 – Detection */}
      <div className="card" style={{ opacity: stage >= 1 ? 1 : 0.3, transition: 'opacity 0.4s' }}>
        <div className="card-header">
          <div>
            <div className="card-title">🛰️ Slick Detection</div>
            <div className="card-meta">U-Net CNN · model v1</div>
          </div>
          {stage > 1 && <span className="badge badge-green">Done ✓</span>}
          {stage === 1 && <span className="badge badge-yellow">Running</span>}
          {stage < 1 && <span className="badge badge-blue">Pending</span>}
        </div>
        {detection ? (
          <>
            <div className="meta-grid" style={{ marginTop: 10 }}>
              <div className="meta-item">
                <div className="val">{detection.geometry_stats?.area_sq_km ?? '14.5'}</div>
                <div className="lbl">Area (km²)</div>
              </div>
              <div className="meta-item">
                <div className="val">{Math.round((detection.model_confidence ?? 0.91) * 100)}%</div>
                <div className="lbl">Confidence</div>
              </div>
              <div className="meta-item">
                <div className="val">{detection.geometry_stats?.perimeter_km ?? '21.3'}</div>
                <div className="lbl">Perimeter (km)</div>
              </div>
              <div className="meta-item">
                <div className="val">Null</div>
                <div className="lbl">Age Est.</div>
              </div>
            </div>
            {detection.quality_warnings?.length > 0 && (
              <div style={{ marginTop: 8, fontSize: '0.7rem', color: 'var(--warning)', lineHeight: 1.4 }}>
                ⚠ {detection.quality_warnings[0]}
              </div>
            )}
          </>
        ) : (
          <div className="card-meta" style={{ marginTop: 8 }}>
            {stage === 1 ? 'Running U-Net inference...' : 'Awaiting pipeline run'}
          </div>
        )}
      </div>

      {/* Stage 2 – Hindcast */}
      <div className="card" style={{ opacity: stage >= 2 ? 1 : 0.3, transition: 'opacity 0.4s' }}>
        <div className="card-header">
          <div>
            <div className="card-title">🌊 Drift Hindcast</div>
            <div className="card-meta">OpenDrift · 3-day backward</div>
          </div>
          {stage > 2 && <span className="badge badge-green">Done ✓</span>}
          {stage === 2 && <span className="badge badge-yellow">Running</span>}
          {stage < 2 && <span className="badge badge-blue">Pending</span>}
        </div>
        {hindcast ? (
          <div style={{ marginTop: 8 }}>
            <div className="evidence-row">
              <span>Spill Window Start</span>
              <span>{hindcast.spill_time_window?.start?.replace('T',' ').replace('Z','')}</span>
            </div>
            <div className="evidence-row">
              <span>Origin Bbox</span>
              <span>[{hindcast.origin_probability?.origin_bbox?.map((n: number) => n.toFixed(1)).join(', ')}]</span>
            </div>
            <div className="evidence-row">
              <span>Particles</span>
              <span>2,000</span>
            </div>
          </div>
        ) : (
          <div className="card-meta" style={{ marginTop: 8 }}>
            {stage === 2 ? 'Running backward simulation...' : 'Awaiting detection result'}
          </div>
        )}
      </div>

      {/* Stage 3 – Candidates */}
      <div className="panel-title" style={{ opacity: stage >= 3 ? 1 : 0.3, transition: 'opacity 0.4s' }}>
        🚢 Suspect Vessels
        {candidates.length > 0 && (
          <span style={{ marginLeft: 'auto', fontSize: '0.7rem', color: 'var(--muted)', fontWeight: 400 }}>
            {candidates.length} candidates
          </span>
        )}
      </div>

      {stage === 3 && candidates.length === 0 && (
        <div className="card-meta" style={{ color: 'var(--accent)' }}>Scoring AIS candidates...</div>
      )}
      {stage < 3 && (
        <div className="card" style={{ opacity: 0.3 }}>
          <div className="card-meta">Awaiting drift hindcast result</div>
        </div>
      )}

      {candidates.map((c: any, i: number) => (
        <div key={c.mmsi} className={`vessel-card ${RANK_CLASSES[i] ?? ''}`}>
          <div className="card-header">
            <div>
              <div className="card-title">{c.name}</div>
              <div className="card-meta" style={{ fontFamily: 'monospace' }}>MMSI {c.mmsi}</div>
            </div>
            <span className={`badge ${RANK_BADGE[i] ?? 'badge-blue'}`}>
              {Math.round(c.score * 100)}%
            </span>
          </div>
          <div className="score-bar">
            <div
              className={`score-fill ${i === 0 ? 'high' : i === 1 ? 'medium' : 'low'}`}
              style={{ width: `${c.score * 100}%` }}
            />
          </div>
          <div style={{ marginTop: 8 }}>
            <div className="evidence-row">
              <span>Proximity Score</span>
              <span>{Math.round((c.evidence?.proximity_score ?? 0.5) * 100)}%</span>
            </div>
            <div className="evidence-row">
              <span>Anomaly Score</span>
              <span>{Math.round((c.evidence?.anomaly_score ?? 0.5) * 100)}%</span>
            </div>
            <div className="evidence-row">
              <span>Detected Anomalies</span>
              <span style={{ color: c.anomaly !== 'None' ? 'var(--warning)' : 'var(--success)' }}>
                {c.anomaly || 'None'}
              </span>
            </div>
          </div>
        </div>
      ))}

      {/* Attribution disclaimer */}
      {stage === 4 && (
        <div style={{ marginTop: 8, padding: '10px 12px', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 8, fontSize: '0.7rem', color: 'var(--warning)', lineHeight: 1.5 }}>
          ⚖ High score = investigative lead only. Not proof of responsibility.
        </div>
      )}
    </aside>
  );
}
