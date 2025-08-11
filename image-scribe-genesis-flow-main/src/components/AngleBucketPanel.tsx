import React from 'react';
import type { AngleToken } from './AngleDiagram';

export interface ReviewImage {
  url: string;
  id?: string;
  angle?: AngleToken | 'unknown';
  category?: 'exterior' | 'interior' | 'document';
  is_closeup?: boolean;
  source?: 'heuristic' | 'llm' | 'user' | 'cache';
  confidence?: number | null;
}

interface AngleBucketPanelProps {
  angle: AngleToken | 'unknown';
  images: ReviewImage[];
  onMove?: (image: ReviewImage, to: AngleToken) => void;
  onToggleCloseup?: (image: ReviewImage) => void;
  onSetCategory?: (image: ReviewImage, cat: 'exterior' | 'interior' | 'document') => void;
}

export default function AngleBucketPanel({ angle, images, onMove, onToggleCloseup, onSetCategory }: AngleBucketPanelProps) {
  return (
    <div style={{ borderLeft: '1px solid #e5e7eb', padding: 12, minWidth: 320 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>{angle.replace('_', ' ')}</h3>
        <span style={{ fontSize: 12, color: '#6b7280' }}>{images.length} images</span>
      </div>
      <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr', gap: 8 }}>
        {images.map((img) => (
          <div key={img.url} style={{ display: 'flex', gap: 8, alignItems: 'center', border: '1px solid #e5e7eb', padding: 8, borderRadius: 8 }}>
            <img src={img.url} alt="thumb" style={{ width: 80, height: 60, objectFit: 'cover', borderRadius: 6 }} />
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
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <select aria-label="Move to angle" defaultValue="" onChange={(e) => {
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
                <button type="button" onClick={() => onToggleCloseup?.(img)}>Toggle close-up</button>
                <select aria-label="Set category" value={img.category || 'exterior'} onChange={(e) => onSetCategory?.(img, e.target.value as any)}>
                  <option value="exterior">Exterior</option>
                  <option value="interior">Interior</option>
                  <option value="document">Document</option>
                </select>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
