import React from 'react';
import { AngleToken, CANON_ANGLES } from '../lib/angles';

export interface AngleCounts {
  [angle: string]: number | undefined;
}

interface AngleDiagramProps {
  selected?: AngleToken;
  counts?: AngleCounts;
  onSelect?: (angle: AngleToken) => void;
  disabled?: boolean;
}

// Minimal inline SVG placeholder with 9 hotspots
export default function AngleDiagram({ selected, counts, onSelect, disabled }: AngleDiagramProps) {
  const handleClick = (angle: AngleToken) => {
    if (disabled) return;
    onSelect?.(angle);
  };

  const badge = (angle: AngleToken) => (
    <span
      style={{
        position: 'absolute', top: -6, right: -6, background: '#111827', color: 'white',
        borderRadius: 12, padding: '0 6px', fontSize: 12, lineHeight: '20px'
      }}
      aria-hidden
    >{counts?.[angle] ?? 0}</span>
  );

  const Hotspot: React.FC<{ angle: AngleToken; cx: number; cy: number; label: string }>=({ angle, cx, cy, label }) => (
    <button
      type="button"
      role="radio"
      aria-checked={selected === angle}
      onClick={() => handleClick(angle)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleClick(angle); }
      }}
      aria-label={`${label} (${counts?.[angle] ?? 0} images)`}
      tabIndex={disabled ? -1 : 0}
      style={{
        position: 'absolute', left: cx, top: cy, transform: 'translate(-50%, -50%)',
        width: 56, height: 56, borderRadius: 12,
        border: selected === angle ? '2px solid #2563eb' : '1px solid #d1d5db',
        background: disabled ? '#f3f4f6' : (selected === angle ? '#eff6ff' : '#ffffff'),
        cursor: disabled ? 'not-allowed' : 'pointer',
        outline: 'none',
        boxShadow: selected === angle ? '0 0 0 2px rgba(37,99,235,0.2)' : 'none',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        color: '#111827', fontSize: 11
      }}
    >
      {badge(angle)}
      <span style={{ pointerEvents: 'none' }}>{label}</span>
    </button>
  );

  return (
    <div role="radiogroup" aria-label="Vehicle angles" style={{ position: 'relative', width: '100%', maxWidth: 360, height: 260, margin: '0 auto' }}>
      {/* Simple car body rectangle as placeholder */}
      <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%, -50%)', width: 220, height: 100, borderRadius: 16, background: '#e5e7eb' }} />

      <Hotspot angle="front"       cx={180} cy={20}  label="Front" />
      <Hotspot angle="front_left"  cx={80}  cy={40}  label="Front left" />
      <Hotspot angle="front_right" cx={280} cy={40}  label="Front right" />

      <Hotspot angle="side_left"   cx={40}  cy={130} label="Side left" />
      <Hotspot angle="side_right"  cx={320} cy={130} label="Side right" />

      <Hotspot angle="back"        cx={180} cy={240} label="Back" />
      <Hotspot angle="back_left"   cx={80}  cy={220} label="Back left" />
      <Hotspot angle="back_right"  cx={280} cy={220} label="Back right" />

      <Hotspot angle="unknown"     cx={180} cy={130} label="Unknown" />
    </div>
  );
}
