import React from 'react';

export type AngleToken =
  | 'front' | 'front_left' | 'front_right'
  | 'side_left' | 'side_right'
  | 'back' | 'back_left' | 'back_right'
  | 'unknown';

export const CANON_ANGLES: AngleToken[] = [
  'front', 'front_left', 'front_right',
  'side_left', 'side_right',
  'back', 'back_left', 'back_right',
  'unknown',
];

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
      onClick={() => handleClick(angle)}
      aria-label={`${label} (${counts?.[angle] ?? 0} images)`}
      style={{
        position: 'absolute', left: cx, top: cy, transform: 'translate(-50%, -50%)',
        width: 44, height: 44, borderRadius: 22,
        border: selected === angle ? '2px solid #2563eb' : '1px solid #d1d5db',
        background: disabled ? '#f3f4f6' : '#ffffff', cursor: disabled ? 'not-allowed' : 'pointer'
      }}
    >
      {badge(angle)}
    </button>
  );

  return (
    <div style={{ position: 'relative', width: 360, height: 260, margin: '0 auto' }}>
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
