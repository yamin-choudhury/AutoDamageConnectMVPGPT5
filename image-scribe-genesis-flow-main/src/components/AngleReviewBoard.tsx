import React, { useEffect, useMemo, useRef, useState } from 'react';
import AngleDiagram, { AngleToken, CANON_ANGLES } from './AngleDiagram';
import AngleBucketPanel, { ReviewImage } from './AngleBucketPanel';

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
}

const EXTERIOR_ANGLES: AngleToken[] = [
  'front','front_left','front_right','side_left','side_right','back','back_left','back_right'
];

export default function AngleReviewBoard({ documentId, backendBaseUrl, initialImages, onConfirm }: AngleReviewBoardProps) {
  const [images, setImages] = useState<ReviewImage[]>(() => initialImages.map(i => ({
    url: i.url,
    id: i.id,
    category: i.category || 'exterior',
    angle: (i.angle as AngleToken | 'unknown') || 'unknown',
    is_closeup: i.is_closeup,
    source: (i.source as ReviewImage['source'] | undefined),
    confidence: i.confidence ?? null,
  })));
  const [selected, setSelected] = useState<AngleToken>('unknown');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  // Debounce autosave
  const saveTimer = useRef<number | null>(null);
  const scheduleSave = () => {
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => void autosave(), 600);
  };

  useEffect(() => {
    // classify on mount for only unknown exterior images
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

  const buckets = useMemo(() => {
    const map: Record<AngleToken | 'unknown', ReviewImage[]> = {
      front: [], front_left: [], front_right: [], side_left: [], side_right: [], back: [], back_left: [], back_right: [], unknown: []
    };
    images.forEach((img) => {
      const angle = (img.category === 'exterior' ? (img.angle || 'unknown') : 'unknown') as AngleToken | 'unknown';
      map[angle].push(img);
    });
    return map;
  }, [images]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    (CANON_ANGLES as (AngleToken | 'unknown')[]).forEach(a => { c[a] = buckets[a].length; });
    return c;
  }, [buckets]);

  const autosave = async () => {
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
    await autosave();
    onConfirm?.(images);
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: 12, alignItems: 'start' }}>
      <div>
        <h2 style={{ marginTop: 0 }}>Angle Review</h2>
        {loading && <div>Classifying angles…</div>}
        {error && <div style={{ color: '#b91c1c' }}>{error}</div>}
        <AngleDiagram selected={selected} counts={counts} onSelect={setSelected} disabled={loading} />
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <button type="button" onClick={confirm} disabled={!allExteriorLabeled}>Confirm</button>
          <span style={{ fontSize: 12, color: '#6b7280' }}>
            {allExteriorLabeled ? 'All exterior images labeled' : 'Label all exterior images to continue'}
          </span>
        </div>
      </div>
      <AngleBucketPanel
        angle={selected}
        images={buckets[selected]}
        onMove={move}
        onToggleCloseup={toggleClose}
        onSetCategory={setCat}
      />
    </div>
  );
}
