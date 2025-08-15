import React from 'react';
import type { AngleToken } from '../lib/angles';
import { swapLR, arrowFor, badgeFor, colorFor } from '../lib/angles';

export interface ReviewImage {
  url: string;
  id?: string;
  angle?: AngleToken | 'unknown';
  category?: 'exterior' | 'interior' | 'document';
  is_closeup?: boolean;
  source?: 'heuristic' | 'llm' | 'user' | 'cache';
  confidence?: number | null;
  subcategory?: string; // ephemeral, frontend-only
}

interface AngleBucketPanelProps {
  angle: AngleToken | 'unknown';
  images: ReviewImage[];
  onMove?: (image: ReviewImage, to: AngleToken) => void;
  onToggleCloseup?: (image: ReviewImage) => void;
  onSetCategory?: (image: ReviewImage, cat: 'exterior' | 'interior' | 'document') => void;
  selectedAngle?: AngleToken; // for one-click move
  onDelete?: (image: ReviewImage) => void;
}

const buttonStyle: React.CSSProperties = {
  padding: '6px 10px',
  borderRadius: 6,
  border: '1px solid #d1d5db',
  background: '#ffffff',
  color: '#111827',
  fontSize: 13,
  cursor: 'pointer',
};

function AngleBucketPanel({ angle, images, onMove, onToggleCloseup, onSetCategory, selectedAngle, onDelete }: AngleBucketPanelProps) {
  return (
    <div style={{ borderLeft: '1px solid #e5e7eb', padding: 12, width: '100%', boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', minWidth: 0 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{(angle as string).replace(/_/g, ' ')}</h3>
        <span style={{ fontSize: 12, color: '#6b7280' }}>{images.length} images</span>
      </div>
      <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr', gap: 8, maxHeight: '70vh', overflowY: 'auto', paddingRight: 4 }}>
        {images.length === 0 && (
          <div style={{ border: '1px dashed #d1d5db', borderRadius: 8, padding: 16, color: '#6b7280', fontSize: 13 }}>
            No images in this angle yet.
          </div>
        )}
        {images.map((img) => {
          const a = (img.category === 'exterior' ? (img.angle || 'unknown') : 'unknown') as AngleToken | 'unknown';
          const color = colorFor(a);
          const swapped = swapLR((img.angle || 'unknown'));
          return (
          <div key={img.url} style={{ display: 'flex', gap: 12, alignItems: 'center', border: '1px solid #e5e7eb', padding: 10, borderRadius: 10, background: '#ffffff', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}>
            <div style={{ position: 'relative' }}>
              <img src={img.url} alt="thumb" loading="lazy" style={{ width: 96, height: 72, objectFit: 'cover', borderRadius: 8, border: `2px solid ${color}` }} />
              <span
                style={{ position: 'absolute', top: 4, left: 4, fontSize: 11, background: '#ffffff', color, border: `1px solid ${color}`, padding: '1px 4px', borderRadius: 6 }}
                aria-label={`Angle badge ${a}`}
              >{badgeFor(a)} {arrowFor(a)}</span>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {img.source && <span style={{ fontSize: 11, background: '#eef2ff', color: '#3730a3', padding: '2px 6px', borderRadius: 6 }}>{img.source}</span>}
                {typeof img.confidence === 'number' && (
                  <span title={String(img.confidence)} style={{ fontSize: 11, background: '#ecfeff', color: '#155e75', padding: '2px 6px', borderRadius: 6 }}>
                    {img.confidence >= 0.75 ? 'High' : img.confidence >= 0.5 ? 'Med' : 'Low'}
                  </span>
                )}
                {img.is_closeup && <span style={{ fontSize: 11, background: '#fef3c7', color: '#92400e', padding: '2px 6px', borderRadius: 6 }}>close-up</span>}
                {img.category && <span style={{ fontSize: 11, background: '#f3f4f6', color: '#374151', padding: '2px 6px', borderRadius: 6 }}>{img.category}</span>}
                {img.subcategory && <span style={{ fontSize: 11, background: '#e0f2fe', color: '#075985', padding: '2px 6px', borderRadius: 6 }}>{img.subcategory}</span>}
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                <select aria-label="Move to angle" defaultValue="" style={{ ...buttonStyle }} onChange={(e) => {
                  const v = e.target.value as AngleToken | '';
                  if (v) onMove?.(img, v);
                  e.currentTarget.value = '';
                }}>
                  <option value="">Move to angle…</option>
                  <option value="front">Front</option>
                  <option value="front_left">Front left</option>
                  <option value="front_right">Front right</option>
                  <option value="side_left">Side left</option>
                  <option value="side_right">Side right</option>
                  <option value="back">Back</option>
                  <option value="back_left">Back left</option>
                  <option value="back_right">Back right</option>
                </select>
                <button
                  type="button"
                  onClick={() => { if (selectedAngle) onMove?.(img, selectedAngle); }}
                  disabled={!selectedAngle}
                  title={selectedAngle ? `Move to ${String(selectedAngle).replace(/_/g,' ')}` : 'Select an angle on the diagram'}
                  style={{ ...buttonStyle, opacity: (!selectedAngle) ? 0.5 : 1 }}
                >Move to selected</button>
                <button
                  type="button"
                  onClick={() => { if (swapped !== 'unknown') onMove?.(img, swapped as AngleToken); }}
                  title="Swap Left/Right"
                  style={buttonStyle}
                >Swap L/R</button>
                <button type="button" onClick={() => onToggleCloseup?.(img)} style={buttonStyle}>Toggle close-up</button>
                <select aria-label="Set category" value={img.category || 'exterior'} style={{ ...buttonStyle }} onChange={(e) => onSetCategory?.(img, e.target.value as 'exterior'|'interior'|'document')}>
                  <option value="exterior">Exterior</option>
                  <option value="interior">Interior</option>
                  <option value="document">Document</option>
                </select>
                <button
                  type="button"
                  onClick={() => onDelete?.(img)}
                  title="Delete image"
                  style={{ ...buttonStyle, borderColor: '#ef4444', color: '#b91c1c' }}
                >Delete</button>
              </div>
            </div>
          </div>
        );})}
      </div>
    </div>
  );
}

export default React.memo(AngleBucketPanel);
