/**
 * Log actions to backend. Used for map task tool clicks and other client-side actions.
 */

import { captureActionContextSafe } from './useActionCapture.js'

/** Large screenshot + map_image JSON can be slow; without a timeout a stalled fetch blocks the whole chain forever. */
const LOG_ACTION_FETCH_TIMEOUT_MS = 120000

/** Serialize map log_action POSTs (each includes capture + fetch) so none are lost before navigation. */
let logActionChain = Promise.resolve()

function rafTick() {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()))
}

/**
 * Resolves when all queued map log_action requests have finished (including network).
 */
export function waitForPendingActionLogs() {
  return logActionChain
}

/**
 * Internal: screenshot + HTML snapshot + POST. Kept async for heavy html2canvas work.
 */
async function logActionToBackendAsync({ actionType, actionContent, mapImage, metadata = {}, clientTimestamp }) {
  const sessionId = sessionStorage.getItem('session_id') || sessionStorage.getItem('session_code') || sessionStorage.getItem('session_name')
  const participantId = sessionStorage.getItem('participant_id')
  if (!sessionId || !participantId) {
    console.warn('[ActionLog] Cannot log: missing sessionId or participantId')
    return
  }

  const ctx = await captureActionContextSafe({ timeoutMs: 15000 })

  try {
    const body = {
      action_type: actionType,
      action_content: actionContent,
      metadata,
      page: 'map_task',
      ...(clientTimestamp ? { client_timestamp: clientTimestamp } : {}),
      ...ctx,
    }
    if (mapImage) body.map_image = mapImage

    const enc = encodeURIComponent(sessionId)
    const url = `/api/sessions/${enc}/participants/${participantId}/log_action`
    const ac = new AbortController()
    const timeoutId = setTimeout(() => ac.abort(), LOG_ACTION_FETCH_TIMEOUT_MS)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: ac.signal,
      })
      if (!res.ok) {
        const t = await res.text()
        console.warn('[ActionLog] log_action API error:', res.status, t?.slice?.(0, 500) || t)
      }
    } catch (e) {
      if (e?.name === 'AbortError') {
        console.warn(
          '[ActionLog] log_action timed out after',
          LOG_ACTION_FETCH_TIMEOUT_MS,
          'ms — later map actions were queued behind this request. Check backend/nginx (body size, service up).',
        )
      } else {
        console.warn('[ActionLog] Failed to log action:', e)
      }
    } finally {
      clearTimeout(timeoutId)
    }
  } catch (e) {
    console.warn('[ActionLog] Failed to log action:', e)
  }
}

/**
 * Log an action to the backend (non-blocking for UI).
 * Defers one animation frame so the caller's UI update (e.g. map tool highlight) can paint; capture uses waitForVisualUpdate inside captureActionContextSafe for styled screenshots.
 *
 * @param {Object} params
 * @param {string} params.actionType - e.g. 'map_tool_click', 'map_draw_stop'
 * @param {string} params.actionContent - e.g. 'brush', 'eraser', 'reset'
 * @param {string} [params.mapImage] - base64 image (for follower map task, image map)
 * @param {Object} [params.metadata] - extra data (e.g. filledCells for txt map)
 */
export function logActionToBackend(params) {
  const clientTimestamp = new Date().toISOString()
  logActionChain = logActionChain
    .then(() => rafTick())
    .then(() => logActionToBackendAsync({ ...params, clientTimestamp }))
    .catch(() => {})
}
