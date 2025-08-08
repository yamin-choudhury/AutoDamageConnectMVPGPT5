/// <reference types="vite/client" />
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// Proactively clear expired Supabase auth token to avoid noisy refresh errors
(() => {
  try {
    const projectRef = 'urdbbrndqpbhxjfpeafd';
    const key = `sb-${projectRef}-auth-token`;
    const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(key) : null;
    if (raw) {
      const data = JSON.parse(raw);
      const exp = data?.currentSession?.expires_at ?? data?.expires_at;
      if (typeof exp === 'number') {
        const expMs = exp * 1000;
        if (expMs < Date.now() - 60_000) { // expired with 60s grace
          localStorage.removeItem(key);
          if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem(key);
        }
      }
    }
  } catch { /* ignore */ }
})();

// Global console silencer for development to reduce noise.
// Toggle by setting localStorage.DEBUG = 'true' or VITE_DEBUG = 'true'.
(() => {
  try {
    const viteEnv = (typeof import.meta !== 'undefined' ? (import.meta as ImportMeta).env : undefined);
    const debugFlag = (typeof localStorage !== 'undefined' && localStorage.getItem('DEBUG') === 'true')
      || (viteEnv?.VITE_DEBUG === 'true');
    if (!debugFlag && typeof console !== 'undefined') {
      const noop = () => {};
      // Keep errors and warnings visible; silence info-level noise
      console.log = noop;
      console.info = noop;
      console.debug = noop;
    }
  } catch { /* ignore */ }
})();

createRoot(document.getElementById("root")!).render(<App />);
