/**
 * Absolute URL for an API path. Use when calling fetch() so deployments without
 * same-origin /api proxy (or with split frontend/backend hosts) still work.
 *
 * - Default: relative path (Vite dev proxy, nginx in Docker, etc.)
 * - Set VITE_BACKEND_URL at build time (e.g. https://api.example.com) when needed
 */
export function apiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  const raw = import.meta.env.VITE_BACKEND_URL
  const base = typeof raw === 'string' ? raw.trim().replace(/\/$/, '') : ''
  if (base !== '') {
    return `${base}${p}`
  }
  return p
}
