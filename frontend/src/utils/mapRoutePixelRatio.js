/** Canonical size and denominator for map-task route coverage (matches offline GT). */
export const MAP_ROUTE_CANON_W = 810
export const MAP_ROUTE_CANON_H = 1180

/** Half-width of route stroke on the 810×1180 grid (diameter = 8 px). */
const STROKE_RADIUS_EUCLIDEAN = 4
const STROKE_RADIUS_SQ = STROKE_RADIUS_EUCLIDEAN * STROKE_RADIUS_EUCLIDEAN

/** Alpha threshold after scaling ink onto canonical canvas (binary foreground). */
const BINARY_ALPHA_THRESHOLD = 12

/**
 * Neighbors P2..P9 clockwise from top, P1 = center (Zhang–Suen layout).
 *   P9 P2 P3
 *   P8 P1 P4
 *   P7 P6 P5
 */
function neighborBits(bin, w, x, y) {
  const row = y * w
  const p = (dx, dy) => (bin[row + dy * w + x + dx] ? 1 : 0)
  return {
    p2: p(0, -1),
    p3: p(1, -1),
    p4: p(1, 0),
    p5: p(1, 1),
    p6: p(0, 1),
    p7: p(-1, 1),
    p8: p(-1, 0),
    p9: p(-1, -1),
  }
}

/** Count 0→1 transitions in cyclic order P2..P9,P2. */
function transitions01(n) {
  const seq = [n.p2, n.p3, n.p4, n.p5, n.p6, n.p7, n.p8, n.p9, n.p2]
  let b = 0
  for (let i = 0; i < 8; i++) {
    if (seq[i] === 0 && seq[i + 1] === 1) b++
  }
  return b
}

function neighborSum(n) {
  return n.p2 + n.p3 + n.p4 + n.p5 + n.p6 + n.p7 + n.p8 + n.p9
}

/**
 * Zhang–Suen thinning to a 1-pixel-wide medial skeleton (8-connected).
 * Mutates `bin` in place (Uint8Array 0/1, row-major width w).
 */
function zhangSuenThin(bin, w, h) {
  const toClear = []
  let changed = true
  while (changed) {
    changed = false
    // Subiteration 1
    toClear.length = 0
    for (let y = 1; y < h - 1; y++) {
      const row = y * w
      for (let x = 1; x < w - 1; x++) {
        const i = row + x
        if (!bin[i]) continue
        const n = neighborBits(bin, w, x, y)
        const a = neighborSum(n)
        if (a < 2 || a > 6) continue
        if (transitions01(n) !== 1) continue
        if (n.p2 * n.p4 * n.p6 !== 0) continue
        if (n.p4 * n.p6 * n.p8 !== 0) continue
        toClear.push(i)
      }
    }
    for (const i of toClear) {
      bin[i] = 0
      changed = true
    }
    // Subiteration 2
    toClear.length = 0
    for (let y = 1; y < h - 1; y++) {
      const row = y * w
      for (let x = 1; x < w - 1; x++) {
        const i = row + x
        if (!bin[i]) continue
        const n = neighborBits(bin, w, x, y)
        const a = neighborSum(n)
        if (a < 2 || a > 6) continue
        if (transitions01(n) !== 1) continue
        if (n.p2 * n.p4 * n.p8 !== 0) continue
        if (n.p2 * n.p6 * n.p8 !== 0) continue
        toClear.push(i)
      }
    }
    for (const i of toClear) {
      bin[i] = 0
      changed = true
    }
  }
}

/** Euclidean disk dilation (radius STROKE_RADIUS_EUCLIDEAN → 8px diameter stroke). */
function dilateEuclideanDisk(skeleton, w, h) {
  const out = new Uint8Array(w * h)
  const R = STROKE_RADIUS_EUCLIDEAN
  for (let y = 0; y < h; y++) {
    const row = y * w
    for (let x = 0; x < w; x++) {
      if (!skeleton[row + x]) continue
      for (let dy = -R; dy <= R; dy++) {
        const ny = y + dy
        if (ny < 0 || ny >= h) continue
        const dy2 = dy * dy
        const nrow = ny * w
        for (let dx = -R; dx <= R; dx++) {
          if (dx * dx + dy2 > STROKE_RADIUS_SQ) continue
          const nx = x + dx
          if (nx < 0 || nx >= w) continue
          out[nrow + nx] = 1
        }
      }
    }
  }
  return out
}

/**
 * 1) Scale stroke-only canvas into 810×1180 with uniform contain (letterbox).
 * 2) Binarize ink (alpha).
 * 3) Zhang–Suen thinning → medial axis.
 * 4) Dilate with Euclidean r=4 → fixed 8px stroke width on the canonical grid.
 * 5) Ratio = filled pixels / (810×1180).
 *
 * @param {HTMLCanvasElement | null} canvas
 * @returns {number | null}
 */
export function computeRoutePixelRatioFromCanvas(canvas) {
  if (!canvas || !canvas.width || !canvas.height) return null
  const w = canvas.width
  const h = canvas.height
  const cw = MAP_ROUTE_CANON_W
  const ch = MAP_ROUTE_CANON_H
  const scale = Math.min(cw / w, ch / h)
  const dw = Math.round(w * scale)
  const dh = Math.round(h * scale)
  const ox = Math.floor((cw - dw) / 2)
  const oy = Math.floor((ch - dh) / 2)

  const off = document.createElement('canvas')
  off.width = cw
  off.height = ch
  const ctx = off.getContext('2d')
  if (!ctx) return null
  ctx.clearRect(0, 0, cw, ch)
  ctx.imageSmoothingEnabled = true
  ctx.drawImage(canvas, 0, 0, w, h, ox, oy, dw, dh)

  let data
  try {
    data = ctx.getImageData(0, 0, cw, ch).data
  } catch {
    return null
  }

  const bin = new Uint8Array(cw * ch)
  for (let i = 0, p = 3; p < data.length; i++, p += 4) {
    if (data[p] > BINARY_ALPHA_THRESHOLD) bin[i] = 1
  }

  let inkCount = 0
  for (let i = 0; i < bin.length; i++) {
    if (bin[i]) inkCount++
  }
  if (inkCount === 0) return 0

  zhangSuenThin(bin, cw, ch)

  let skelCount = 0
  for (let i = 0; i < bin.length; i++) {
    if (bin[i]) skelCount++
  }
  if (skelCount === 0) return 0

  const dilated = dilateEuclideanDisk(bin, cw, ch)
  let filled = 0
  for (let i = 0; i < dilated.length; i++) {
    if (dilated[i]) filled++
  }

  const total = cw * ch
  return total > 0 ? filled / total : null
}
