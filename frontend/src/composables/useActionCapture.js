/**
 * Composable for capturing screenshot and HTML snapshot when human performs actions.
 * Used for action logging.
 */

import html2canvas from 'html2canvas'

/**
 * Capture HTML snapshot of the main app content.
 * Limits to #app or body to avoid huge payloads.
 */
export function captureHtmlSnapshot() {
  try {
    const el = document.getElementById('app') || document.body
    if (!el) return null
    const html = el.innerHTML
    // Limit size to ~100KB to avoid huge logs
    if (html.length > 100000) {
      return html.substring(0, 100000) + '...[truncated]'
    }
    return html
  } catch (e) {
    console.warn('[ActionCapture] HTML snapshot failed:', e)
    return null
  }
}

/**
 * Capture screenshot of the viewport as base64.
 * scale: 2 for retina/high-DPI displays (higher resolution)
 */
export async function captureScreenshot() {
  try {
    const el = document.getElementById('app') || document.body
    if (!el) return null
    const canvas = await html2canvas(el, {
      useCORS: true,
      allowTaint: true,
      scale: 2, // Higher resolution (was 0.5)
      logging: false,
    })
    return canvas.toDataURL('image/jpeg', 0.9)
  } catch (e) {
    console.warn('[ActionCapture] Screenshot failed:', e)
    return null
  }
}

/**
 * Capture both screenshot and HTML snapshot.
 * Returns { screenshot, html_snapshot }.
 */
export async function captureActionContext() {
  const [screenshot, html_snapshot] = await Promise.all([
    captureScreenshot(),
    Promise.resolve(captureHtmlSnapshot()),
  ])
  return { screenshot: screenshot || undefined, html_snapshot: html_snapshot || undefined }
}
