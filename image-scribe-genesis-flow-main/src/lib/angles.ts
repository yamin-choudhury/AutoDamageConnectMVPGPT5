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

export function isLeft(a: AngleToken | 'unknown'): boolean {
  return a === 'front_left' || a === 'side_left' || a === 'back_left';
}
export function isRight(a: AngleToken | 'unknown'): boolean {
  return a === 'front_right' || a === 'side_right' || a === 'back_right';
}
export function isFront(a: AngleToken | 'unknown'): boolean {
  return a === 'front' || a === 'front_left' || a === 'front_right';
}
export function isBack(a: AngleToken | 'unknown'): boolean {
  return a === 'back' || a === 'back_left' || a === 'back_right';
}

export function swapLR(a: AngleToken | 'unknown'): AngleToken | 'unknown' {
  switch (a) {
    case 'front_left': return 'front_right';
    case 'front_right': return 'front_left';
    case 'side_left': return 'side_right';
    case 'side_right': return 'side_left';
    case 'back_left': return 'back_right';
    case 'back_right': return 'back_left';
    default: return a;
  }
}

export function pairOf(a: AngleToken | 'unknown'): AngleToken | 'unknown' | null {
  switch (a) {
    case 'front_left': return 'front_right';
    case 'front_right': return 'front_left';
    case 'side_left': return 'side_right';
    case 'side_right': return 'side_left';
    case 'back_left': return 'back_right';
    case 'back_right': return 'back_left';
    default: return null;
  }
}

export function colorFor(a: AngleToken | 'unknown'): string {
  // Tailwind-like hex palette
  if (a === 'unknown') return '#6b7280'; // gray-500
  if (isFront(a)) return '#7c3aed';      // purple-600
  if (isBack(a)) return '#f59e0b';       // amber-500
  if (isLeft(a)) return '#2563eb';       // blue-600
  if (isRight(a)) return '#10b981';      // emerald-500
  return '#6b7280';
}

export function arrowFor(a: AngleToken | 'unknown'): string {
  switch (a) {
    case 'front_left': return '↖';
    case 'front_right': return '↗';
    case 'back_left': return '↙';
    case 'back_right': return '↘';
    case 'side_left': return '←';
    case 'side_right': return '→';
    case 'front': return '↑';
    case 'back': return '↓';
    default: return '·';
  }
}

export function badgeFor(a: AngleToken | 'unknown'): string {
  if (a === 'unknown') return 'UNK';
  const parts = [] as string[];
  if (isFront(a)) parts.push('F'); else if (isBack(a)) parts.push('B');
  if (isLeft(a)) parts.push('L'); else if (isRight(a)) parts.push('R');
  return parts.join('') || '·';
}
