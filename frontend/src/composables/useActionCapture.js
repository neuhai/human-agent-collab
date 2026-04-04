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
 * html2canvas default (canvas) renderer often loses Vue/Vite styles in the cloned iframe.
 * foreignObjectRendering uses SVG foreignObject + copyStyles so layout/CSS matches the live page.
 */
async function html2canvasWithStyleOptions(el, foreignObjectRendering) {
  return html2canvas(el, {
    useCORS: true,
    allowTaint: true,
    scale: Math.min(2, Math.max(1, window.devicePixelRatio || 1)),
    logging: false,
    foreignObjectRendering,
    imageTimeout: 20000,
  })
}

/**
 * foreignObject + SVG snapshot often drops same-origin <img src="/api/maps/..."> pixels.
 * Fetch map bytes and swap to data URLs before capture, then restore (keeps live DOM unchanged).
 */
async function inlineMapImagesForHtml2Canvas(rootEl) {
  if (!rootEl?.querySelectorAll) return []
  const seen = new Set()
  const candidates = []
  for (const img of rootEl.querySelectorAll('img.map-image, img[src*="/api/maps"], img[src*="api/maps"]')) {
    if (seen.has(img)) continue
    seen.add(img)
    candidates.push(img)
  }
  const originals = []
  await Promise.all(
    candidates.map(async (img) => {
      const src = img.getAttribute('src')
      if (!src || src.startsWith('data:')) return
      const isMap =
        src.includes('api/maps') || (img.classList && img.classList.contains('map-image'))
      if (!isMap) return
      try {
        const href = new URL(src, window.location.origin).href
        const res = await fetch(href, { credentials: 'same-origin' })
        if (!res.ok) return
        const blob = await res.blob()
        const dataUrl = await new Promise((resolve, reject) => {
          const fr = new FileReader()
          fr.onload = () => resolve(fr.result)
          fr.onerror = reject
          fr.readAsDataURL(blob)
        })
        originals.push({ img, old: src })
        img.setAttribute('src', dataUrl)
        if (typeof img.decode === 'function') await img.decode().catch(() => {})
      } catch (e) {
        console.warn('[ActionCapture] inline map img failed:', e?.message || e)
      }
    }),
  )
  return originals
}

function restoreInlinedMapImages(originals) {
  for (const { img, old } of originals) {
    try {
      if (img?.isConnected) img.setAttribute('src', old)
    } catch {
      /* ignore */
    }
  }
}

/**
 * Capture screenshot of the viewport as base64.
 * scale capped at 2 for retina/high-DPI displays.
 */
export async function captureScreenshot() {
  try {
    const el = document.getElementById('app') || document.body
    if (!el) return null

    if (document.fonts?.ready) {
      try {
        await Promise.race([
          document.fonts.ready,
          new Promise((resolve) => setTimeout(resolve, 2500)),
        ])
      } catch {
        /* ignore */
      }
    }

    const inlined = await inlineMapImagesForHtml2Canvas(el)
    try {
      await waitForVisualUpdate()
    } catch {
      /* ignore */
    }
    let canvas
    try {
      canvas = await html2canvasWithStyleOptions(el, true)
    } catch (e) {
      console.warn('[ActionCapture] Screenshot with foreignObject failed, retrying:', e?.message || e)
      canvas = await html2canvasWithStyleOptions(el, false)
    } finally {
      restoreInlinedMapImages(inlined)
    }

    return canvas.toDataURL('image/jpeg', 0.92)
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

/**
 * Two animation frames so Vue DOM updates and computed styles (incl. scoped CSS) match the visible UI before html2canvas runs.
 */
export function waitForVisualUpdate() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve())
    })
  })
}

/**
 * html2canvas is not safe to run concurrently; overlapping captures (e.g. rapid map strokes + chat send)
 * caused blank/failed screenshots and dropped log_action / send payloads. Serialize all safe captures.
 */
let captureSafeTail = Promise.resolve()

/**
 * Resolves when all in-flight captureActionContextSafe jobs have finished (screenshots/html snapshots).
 * Use before navigating away so the last action is not dropped mid-capture.
 */
export function waitForActionCaptureIdle() {
  return captureSafeTail
}

/**
 * Same as captureActionContext but waits for layout/paint first, never throws, and caps wait time so callers (e.g. send_message) are not blocked forever.
 *
 * @param {Object} [options]
 * @param {number} [options.timeoutMs] - max time for capture (0 = no timeout). Default 12000.
 */
export async function captureActionContextSafe(options = {}) {
  const timeoutMs = options.timeoutMs ?? 12000
  const job = captureSafeTail.then(async () => {
    await waitForVisualUpdate()
    try {
      const p = captureActionContext()
      if (timeoutMs > 0) {
        const timeout = new Promise((_, reject) => {
          setTimeout(() => reject(new Error('capture timeout')), timeoutMs)
        })
        return await Promise.race([p, timeout])
      }
      return await p
    } catch (e) {
      console.warn('[ActionCapture] captureActionContextSafe:', e?.message || e)
      return {}
    }
  })
  captureSafeTail = job.catch(() => {})
  return job
}
