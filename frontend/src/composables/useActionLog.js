/**
 * Log actions to backend. Used for map task tool clicks and other client-side actions.
 */

import { captureActionContext } from './useActionCapture.js'

/**
 * Internal: screenshot + HTML snapshot + POST. Kept async for heavy html2canvas work.
 */
async function logActionToBackendAsync({ actionType, actionContent, mapImage, metadata = {} }) {
  const sessionId = sessionStorage.getItem('session_id') || sessionStorage.getItem('session_code') || sessionStorage.getItem('session_name')
  const participantId = sessionStorage.getItem('participant_id')
  if (!sessionId || !participantId) {
    console.warn('[ActionLog] Cannot log: missing sessionId or participantId')
    return
  }

  let ctx = {}
  try {
    ctx = await captureActionContext()
  } catch (captureErr) {
    // If capture fails (e.g. html2canvas error), still log the action without screenshot
    console.warn('[ActionLog] Capture failed, logging without screenshot:', captureErr)
  }

  try {
    const body = {
      action_type: actionType,
      action_content: actionContent,
      metadata,
      page: 'map_task',
      ...ctx
    }
    if (mapImage) body.map_image = mapImage

    const enc = encodeURIComponent(sessionId)
    const res = await fetch(`/api/sessions/${enc}/participants/${participantId}/log_action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    if (!res.ok) {
      console.warn('[ActionLog] log_action API error:', res.status, await res.text())
    }
  } catch (e) {
    console.warn('[ActionLog] Failed to log action:', e)
  }
}

/**
 * Log an action to the backend (non-blocking for UI).
 * Defers work to the next animation frame so clicks (e.g. tool switch) paint before html2canvas.
 *
 * @param {Object} params
 * @param {string} params.actionType - e.g. 'map_tool_click', 'map_draw_stop'
 * @param {string} params.actionContent - e.g. 'brush', 'eraser', 'reset'
 * @param {string} [params.mapImage] - base64 image (for follower map task, image map)
 * @param {Object} [params.metadata] - extra data (e.g. filledCells for txt map)
 */
export function logActionToBackend(params) {
  requestAnimationFrame(() => {
    void logActionToBackendAsync(params)
  })
}
