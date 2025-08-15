import React, { useEffect, useMemo, useRef, useState } from 'react';
import AngleDiagram from './AngleDiagram';
import { AngleToken, CANON_ANGLES } from '../lib/angles';
import AngleBucketPanel, { ReviewImage } from './AngleBucketPanel';
import { pairOf } from '../lib/angles';
import { supabase } from '@/integrations/supabase/client';

interface AngleReviewBoardProps {
  documentId: string;
  backendBaseUrl: string; // e.g., https://your-backend.example.com
  initialImages: Array<{
    url: string;
    id?: string;
    category?: 'exterior' | 'interior' | 'document';
    angle?: AngleToken | 'unknown';
    is_closeup?: boolean;
    source?: ReviewImage['source'];
    confidence?: number | null;
  }>;
  onConfirm?: (images: ReviewImage[]) => void;
  autoClassifyOnMount?: boolean; // default: true
}

const EXTERIOR_ANGLES: AngleToken[] = [
  'front','front_left','front_right','side_left','side_right','back','back_left','back_right'
];

export default function AngleReviewBoard({ documentId, backendBaseUrl, initialImages, onConfirm, autoClassifyOnMount = true }: AngleReviewBoardProps) {
  const [images, setImages] = useState<ReviewImage[]>(() => initialImages.map(i => ({
    url: i.url,
    id: i.id,
    category: i.category || 'exterior',
    angle: (i.angle as AngleToken | 'unknown') || 'unknown',
    is_closeup: i.is_closeup,
    source: (i.source as ReviewImage['source'] | undefined),
    confidence: i.confidence ?? null,
  })));
  const [tab, setTab] = useState<'exterior'|'interior'|'closeups'|'documents'>('exterior');
  const [selected, setSelected] = useState<AngleToken>('unknown');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [lowOnly, setLowOnly] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isNarrow, setIsNarrow] = useState(false);

  // Build storage path from a Supabase public URL for the 'images' bucket
  const storagePathFromPublicUrl = (url: string): string | null => {
    try {
      const withoutQuery = url.split('?')[0];
      const marker = '/storage/v1/object/public/images/';
      const idx = withoutQuery.indexOf(marker);
      if (idx === -1) return null;
      return withoutQuery.slice(idx + marker.length);
    } catch {
      return null;
    }
  };

  const handleDelete = async (img: ReviewImage) => {
    const confirmed = window.confirm('Delete this image? This cannot be undone.');
    if (!confirmed) return;
    try {
      const path = storagePathFromPublicUrl(img.url);
      if (path) {
        await supabase.storage.from('images').remove([path]);
      }
      // Delete from legacy table; DB trigger will mirror removal to public.images
      await supabase
        .from('document_images')
        .delete()
        .eq('document_id', documentId)
        .eq('image_url', img.url);
      // Optimistic update
      setImages(prev => prev.filter(i => i.url !== img.url));
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to delete image', e);
      alert('Failed to delete image. Please try again.');
    }
  };

  // Debounce autosave
  const saveTimer = useRef<number | null>(null);
  const scheduleSave = () => {
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => void autosave(), 600);
  };

  useEffect(() => {
    // Optionally classify on mount for only unknown exterior images
    if (!autoClassifyOnMount) return;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const toClassify = images.filter(i => (i.category ?? 'exterior') === 'exterior' && (!i.angle || i.angle === 'unknown'));
        if (toClassify.length === 0) return; // nothing to do
        const body = {
          images: toClassify.map(i => ({ url: i.url, id: i.id })),
          reclassify_unknown_only: true,
          llm_enabled: true,
        };
        const res = await fetch(`${backendBaseUrl}/classify-angles`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
        });
        if (!res.ok) throw new Error(`classify-angles failed: ${res.status}`);
        const data = await res.json();
        interface ClassifyResult {
          url: string;
          id?: string;
          angle?: AngleToken | 'unknown';
          source?: ReviewImage['source'];
          confidence?: number | null;
          status?: string;
          error?: string | null;
        }
        const results: ClassifyResult[] = (data?.results || []) as ClassifyResult[];
        const byUrl: Record<string, Pick<ReviewImage, 'angle' | 'source' | 'confidence'>> = {};
        results.forEach((r) => { byUrl[r.url] = { angle: r.angle, source: r.source, confidence: r.confidence ?? null }; });
        setImages((prev) => prev.map(i => ({ ...i, ...byUrl[i.url] })));
        // persist results via autosave
        scheduleSave();
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'Failed to classify';
        setError(msg);
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Responsive: stack columns under ~900px and recalc on resize
  useEffect(() => {
    const handle = () => {
      const w = containerRef.current?.offsetWidth || window.innerWidth;
      setIsNarrow(w < 900);
    };
    handle();
    window.addEventListener('resize', handle);
    return () => window.removeEventListener('resize', handle);
  }, []);

  const buckets = useMemo(() => {
    const map: Record<AngleToken | 'unknown', ReviewImage[]> = {
      front: [], front_left: [], front_right: [], side_left: [], side_right: [], back: [], back_left: [], back_right: [], unknown: []
    };
    images.forEach((img) => {
      // Only bucket exterior images; non-exterior are shown in their own tabs
      if ((img.category ?? 'exterior') !== 'exterior') return;
      // If marked as close-up, do not show in Exterior tab; handled in Close-ups tab
      if (img.is_closeup) return;
      const angle = ((img.angle || 'unknown') as AngleToken | 'unknown');
      map[angle].push(img);
    });
    return map;
  }, [images]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    (CANON_ANGLES as (AngleToken | 'unknown')[]).forEach(a => { c[a] = buckets[a].length; });
    return c;
  }, [buckets]);

  const autosave = async (includeSubcategory = false) => {
    try {
      const payload = {
        document_id: documentId,
        images: images.map(i => ({
          url: i.url,
          angle: i.category === 'exterior' ? i.angle : undefined,
          category: i.category,
          is_closeup: i.is_closeup,
          source: i.source,
          confidence: i.confidence ?? undefined,
          // ephemeral: only included when confirming, backend may ignore
          subcategory: includeSubcategory ? i['subcategory' as keyof ReviewImage] : undefined,
        }))
      };
      await fetch(`${backendBaseUrl}/save-angle-metadata`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
    } catch (e) {
      // quietly ignore autosave errors
    }
  };

  const move = (img: ReviewImage, to: AngleToken) => {
    setImages(prev => prev.map(i => i.url === img.url ? { ...i, angle: to, source: 'user' } : i));
    scheduleSave();
  };

  const toggleClose = (img: ReviewImage) => {
    setImages(prev => prev.map(i => i.url === img.url ? { ...i, is_closeup: !i.is_closeup, source: 'user' } : i));
    scheduleSave();
  };

  const setCat = (img: ReviewImage, cat: 'exterior' | 'interior' | 'document') => {
    setImages(prev => prev.map(i => i.url === img.url ? { ...i, category: cat, source: 'user', angle: cat === 'exterior' ? i.angle : 'unknown' } : i));
    scheduleSave();
  };

  const allExteriorLabeled = useMemo(() => {
    return images.filter(i => (i.category ?? 'exterior') === 'exterior')
      .every(i => i.angle && i.angle !== 'unknown');
  }, [images]);

  const confirm = async () => {
    setConfirmed(true);
    // include ephemeral subcategory once at confirm-time
    await autosave(true);
    onConfirm?.(images);
  };

  const swapPair = () => {
    const other = pairOf(selected);
    if (!other || other === 'unknown') return;
    setImages(prev => prev.map((i) => {
      if ((i.category ?? 'exterior') !== 'exterior') return i;
      if (i.angle === selected) return { ...i, angle: other as AngleToken, source: 'user' };
      if (i.angle === other) return { ...i, angle: selected as AngleToken, source: 'user' };
      return i;
    }));
    scheduleSave();
  };

  const filtered = (list: ReviewImage[]) => {
    if (!lowOnly) return list;
    return list.filter((i) => {
      const exterior = (i.category ?? 'exterior') === 'exterior';
      if (!exterior) return false;
      if (!i.angle || i.angle === 'unknown') return true;
      if (typeof i.confidence === 'number' && i.confidence < 0.75) return true;
      return false;
    });
  };

  const primaryBtn: React.CSSProperties = { padding: '8px 12px', borderRadius: 8, border: '1px solid #2563eb', background: '#2563eb', color: '#ffffff', fontWeight: 600, cursor: 'pointer' };
  const subtleBtn: React.CSSProperties = { padding: '6px 10px', borderRadius: 8, border: '1px solid #d1d5db', background: '#ffffff', color: '#111827', cursor: 'pointer' };
  const tabBtn: React.CSSProperties = { padding: '6px 10px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#f9fafb', color: '#111827', cursor: 'pointer' };

  // Precompute lists for non-exterior tabs
  const interiorList = useMemo(() => images.filter(i => (i.category ?? 'exterior') === 'interior'), [images]);
  const documentList = useMemo(() => images.filter(i => (i.category ?? 'exterior') === 'document'), [images]);
  const closeupList = useMemo(() => images.filter(i => (i.category ?? 'exterior') === 'exterior' && i.is_closeup), [images]);

  // Ephemeral subcategory options
  const INTERIOR_SUBTYPES = ['dashboard','seats','steering_wheel','console','infotainment','odometer','trunk','other'] as const;
  const DOCUMENT_SUBTYPES = ['registration','insurance','licence','other'] as const;
  const CLOSEUP_SUBTYPES = ['front_bumper','rear_bumper','headlight','taillight','wheel','windscreen','dent','scratch','other'] as const;
  // When a close-up is exterior, allow users to tag the angle directly
  const CLOSEUP_SUBTYPES_EXTERIOR_ANGLES = ['front','front_left','front_right','side_left','side_right','back_left','back_right','back'] as const;

  const setSubcategory = (img: ReviewImage, sub: string) => {
    setImages(prev => prev.map(i => i.url === img.url ? { ...i, subcategory: sub } : i));
    // Do not autosave; ephemeral only
  };

  const renderSimpleList = (list: ReviewImage[], subtypeKind: 'interior'|'document'|'closeup') => {
    const baseOptions = subtypeKind === 'interior' ? INTERIOR_SUBTYPES : subtypeKind === 'document' ? DOCUMENT_SUBTYPES : CLOSEUP_SUBTYPES;
    return (
      <div style={{ borderLeft: '1px solid #e5e7eb', padding: 12, width: '100%', boxSizing: 'border-box' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', minWidth: 0 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0, textTransform: 'capitalize' }}>{subtypeKind === 'closeup' ? 'Close-ups' : `${subtypeKind.charAt(0).toUpperCase()}${subtypeKind.slice(1)} Images`}</h3>
          <span style={{ fontSize: 12, color: '#6b7280' }}>{list.length} images</span>
        </div>
        <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr', gap: 8, maxHeight: '70vh', overflowY: 'auto', paddingRight: 4 }}>
          {list.length === 0 && (
            <div style={{ border: '1px dashed #d1d5db', borderRadius: 8, padding: 16, color: '#6b7280', fontSize: 13 }}>
              No images in this list.
            </div>
          )}
          {list.map((img) => {
            const useAngleOptions = subtypeKind === 'closeup' && ((img.category ?? 'exterior') === 'exterior');
            const options = useAngleOptions ? CLOSEUP_SUBTYPES_EXTERIOR_ANGLES : baseOptions;
            return (
            <div key={img.url} style={{ display: 'flex', gap: 12, alignItems: 'center', border: '1px solid #e5e7eb', padding: 10, borderRadius: 10, background: '#ffffff', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}>
              <div>
                <img src={img.url} alt="thumb" loading="lazy" style={{ width: 96, height: 72, objectFit: 'cover', borderRadius: 8, border: '2px solid #e5e7eb' }} />
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
                  {/* Toggle close-up still useful for interior/close-up corrections */}
                  <button type="button" onClick={() => toggleClose({ ...img })} style={subtleBtn}>Toggle close-up</button>
                  <select aria-label="Set category" value={img.category || 'exterior'} style={{ ...subtleBtn }} onChange={(e) => setCat(img, e.target.value as 'exterior'|'interior'|'document')}>
                    <option value="exterior">Exterior</option>
                    <option value="interior">Interior</option>
                    <option value="document">Document</option>
                  </select>
                  <select aria-label={useAngleOptions ? 'Set angle tag' : 'Set subcategory'} value={img.subcategory || ''} style={{ ...subtleBtn }} onChange={(e) => setSubcategory(img, e.target.value)}>
                    <option value="">{useAngleOptions ? 'Angle…' : 'Subcategory…'}</option>
                    {options.map((o) => (<option key={o} value={o}>{o.replace(/_/g,' ')}</option>))}
                  </select>
                  <button type="button" onClick={() => handleDelete(img)} style={{ ...subtleBtn, borderColor: '#ef4444', color: '#b91c1c' }}>Delete</button>
                </div>
              </div>
            </div>
          );})}
        </div>
      </div>
    );
  };

  return (
    <div ref={containerRef} style={{ display: 'grid', gridTemplateColumns: isNarrow ? '1fr' : '380px minmax(0, 1fr)', gap: 12, alignItems: 'start', width: '100%', boxSizing: 'border-box' }}>
      <div>
        <h2 style={{ marginTop: 0 }}>Angle Review</h2>
        <div style={{ fontSize: 12, color: '#374151', background: '#f9fafb', border: '1px solid #e5e7eb', padding: '8px 10px', borderRadius: 8, marginBottom: 8 }}>
          Left/Right are from the vehicle’s perspective (as if seated facing forward).
        </div>
        {loading && (
          <div aria-live="polite" style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#eff6ff', border: '1px solid #bfdbfe', color: '#1e40af', padding: '8px 10px', borderRadius: 8, marginBottom: 8 }}>
            <span role="status" aria-label="Loading" style={{ width: 12, height: 12, borderRadius: 6, background: '#3b82f6', animation: 'pulse 1s ease-in-out infinite' }} />
            Classifying angles…
          </div>
        )}
        {error && <div style={{ color: '#b91c1c' }}>{error}</div>}
        <AngleDiagram selected={selected} counts={counts} onSelect={setSelected} disabled={loading} />
        <div style={{ marginTop: 8 }}>
          <label style={{ fontSize: 12, color: '#374151' }}>
            <input type="checkbox" checked={lowOnly} onChange={(e) => setLowOnly(e.target.checked)} style={{ marginRight: 6 }} />
            Show only low-confidence / unknown exterior images
          </label>
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button type="button" onClick={confirm} disabled={!allExteriorLabeled} style={{ ...primaryBtn, opacity: allExteriorLabeled ? 1 : 0.6, cursor: allExteriorLabeled ? 'pointer' : 'not-allowed' }}>Confirm</button>
          <span style={{ fontSize: 12, color: '#6b7280' }}>
            {allExteriorLabeled ? 'All exterior images labeled' : 'Label all exterior images to continue'}
          </span>
        </div>
      </div>
      <div style={{ minWidth: 0, overflowX: 'hidden' }}>
        {/* Tabs header */}
        <div style={{ position: 'sticky', top: 0, background: '#ffffff', zIndex: 2, paddingTop: 4, paddingBottom: 8 }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap', borderBottom: '1px solid #e5e7eb', paddingBottom: 6 }}>
            <button type="button" onClick={() => setTab('exterior')} style={{ ...tabBtn, background: tab==='exterior' ? '#dbeafe' : '#f9fafb', borderColor: tab==='exterior' ? '#60a5fa' : '#e5e7eb' }}>Exterior ({counts['front']+counts['front_left']+counts['front_right']+counts['side_left']+counts['side_right']+counts['back']+counts['back_left']+counts['back_right']+counts['unknown']})</button>
            <button type="button" onClick={() => setTab('interior')} style={{ ...tabBtn, background: tab==='interior' ? '#dbeafe' : '#f9fafb', borderColor: tab==='interior' ? '#60a5fa' : '#e5e7eb' }}>Interior ({interiorList.length})</button>
            <button type="button" onClick={() => setTab('closeups')} style={{ ...tabBtn, background: tab==='closeups' ? '#dbeafe' : '#f9fafb', borderColor: tab==='closeups' ? '#60a5fa' : '#e5e7eb' }}>Close-ups ({closeupList.length})</button>
            <button type="button" onClick={() => setTab('documents')} style={{ ...tabBtn, background: tab==='documents' ? '#dbeafe' : '#f9fafb', borderColor: tab==='documents' ? '#60a5fa' : '#e5e7eb' }}>Documents ({documentList.length})</button>
          </div>
        </div>

        {tab === 'exterior' && (() => {
          const other = pairOf(selected);
          if (!other || other === 'unknown') {
            return (
              <AngleBucketPanel
                angle={selected}
                images={filtered(buckets[selected])}
                onMove={move}
                onToggleCloseup={toggleClose}
                onSetCategory={setCat}
                selectedAngle={selected === 'unknown' ? undefined : selected}
                onDelete={handleDelete}
              />
            );
          }
          // Render pair view with Swap Pair button: header + two columns grid
          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0, fontSize: 14, color: '#374151' }}>Left/Right Pair</h3>
                <button type="button" onClick={swapPair} title="Swap all images across this pair" style={subtleBtn}>Swap Pair</button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 12 }}>
                <AngleBucketPanel
                  angle={selected}
                  images={filtered(buckets[selected])}
                  onMove={move}
                  onToggleCloseup={toggleClose}
                  onSetCategory={setCat}
                  selectedAngle={selected === 'unknown' ? undefined : selected}
                  onDelete={handleDelete}
                />
                <AngleBucketPanel
                  angle={other}
                  images={filtered(buckets[other])}
                  onMove={move}
                  onToggleCloseup={toggleClose}
                  onSetCategory={setCat}
                  selectedAngle={selected === 'unknown' ? undefined : selected}
                  onDelete={handleDelete}
                />
              </div>
            </div>
          );
        })()}

        {tab === 'interior' && renderSimpleList(interiorList, 'interior')}
        {tab === 'closeups' && renderSimpleList(closeupList, 'closeup')}
        {tab === 'documents' && renderSimpleList(documentList, 'document')}
      </div>
    </div>
  );
}
