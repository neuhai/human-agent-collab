/**
 * Stable identity for the same map asset across API/WebSocket payloads.
 * Bindings may expose only file_path first, then add filename (or vice versa); comparing raw
 * filename vs "/api/maps/foo.png" must not count as a map switch.
 */
export function normalizeMapIdentity(mapObj) {
  if (!mapObj || typeof mapObj !== 'object') return null
  const fn = mapObj.filename
  if (fn != null && String(fn).trim() !== '') {
    return String(fn).trim()
  }
  const fp = mapObj.file_path
  if (fp != null && String(fp).trim() !== '') {
    const raw = String(fp).trim()
    const base = raw.split('/').filter(Boolean).pop() || raw
    return base.split('?')[0].trim() || null
  }
  if (mapObj.id != null && String(mapObj.id).trim() !== '') {
    return String(mapObj.id).trim()
  }
  return null
}
