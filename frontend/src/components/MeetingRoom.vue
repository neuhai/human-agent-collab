<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick, reactive } from 'vue'
import { getSocket } from '../services/websocket.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  participantId: { type: String, required: true },
  participantsList: { type: Array, default: () => [] }
})

const localStream = ref(null)
const remoteStreams = ref({}) // participantId -> MediaStream
const isJoined = ref(false)
const isConnecting = ref(false)
const peers = ref({}) // participantId -> RTCPeerConnection

const isMuted = ref(false)
const audioDevices = ref([])
const selectedAudioId = ref('')
const showAudioSetting = ref(false)
const audioTriggerRef = ref(null)
const audioDropdownStyle = ref({})

/** All AI participants (each gets its own Realtime WebRTC connection) */
const aiParticipantsList = computed(() =>
  (props.participantsList || []).filter((p) =>
    ['ai', 'ai_agent'].includes(String(p.type || '').toLowerCase())
  )
)

/** First AI in roster = only session with input VAD when orchestrated (matches backend). */
const vadLeaderAgentId = computed(() => {
  const list = aiParticipantsList.value
  if (!list.length) return null
  const a = list[0]
  return a?.id ?? a?.participant_id ?? null
})

/**
 * Server confirms REALTIME_ORCHESTRATED_FLOOR + meeting_room via session_update.
 * Default true so speech_stopped runs dispatch before the first session_update returns (fixes early silent turns).
 */
const orchestratedFloor = ref(true)

/** Human participants except self (for tiles + P2P audio) */
const humanOthers = computed(() =>
  (props.participantsList || []).filter((p) => {
    const id = p?.id || p?.participant_id
    if (!id || id === props.participantId) return false
    return !['ai', 'ai_agent'].includes(String(p.type || '').toLowerCase())
  })
)

const updateDropdownPosition = async (triggerRef, styleRef) => {
  await nextTick()
  const el = triggerRef.value
  if (el) {
    const rect = el.getBoundingClientRect()
    styleRef.value = {
      position: 'fixed',
      bottom: `${window.innerHeight - rect.top + 4}px`,
      right: `${window.innerWidth - rect.right}px`
    }
  }
}

watch(showAudioSetting, (show) => {
  if (show) updateDropdownPosition(audioTriggerRef, audioDropdownStyle)
})

const resolveDisplayName = (pid) => {
  const list = props.participantsList || []
  const p = list.find((x) => (x?.id || x?.participant_id) === pid)
  return p?.name || p?.participant_name || pid
}

const localDisplayName = computed(() => resolveDisplayName(props.participantId))

const realtimeError = ref('')
/** agentParticipantId -> { pc, dc } */
const agentRealtime = ref({})
/** Hidden <audio> elements for model output per agent */
const oaiAudioEls = ref({})
/** participantId -> stop fn; never deep-watch MediaStream in Vue */
const remoteMonitorsByPid = ref({})
const aiLevelStopFns = ref([])

/** Who is currently highlighted as speaking (Zoom-style) */
const speaking = reactive({})
const liveTranscriptions = ref([])
const MAX_LIVE_TRANSCRIPT_ITEMS = 8
const responseTranscriptBufferByAgent = new Map()
/** Streaming user text from conversation.item.input_audio_transcription.delta */
const interimUserTranscript = ref('')

function participantKey(pid) {
  if (pid == null || pid === '') return ''
  return String(pid)
}

function setSpeaking(pid, on) {
  const k = participantKey(pid)
  if (!k) return
  speaking[k] = !!on
}

const isSpeaking = (pid) => !!speaking[participantKey(pid)]

/** kind: 'human' = participant speech (local or shared), 'ai' = model output */
function pushLiveTranscription(speaker, text, kind = 'human') {
  const cleanSpeaker = String(speaker || '').trim()
  const cleanText = String(text || '').trim()
  if (!cleanSpeaker || !cleanText) return
  const item = {
    id: `lt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    speaker: cleanSpeaker,
    text: cleanText,
    kind
  }
  const next = [...liveTranscriptions.value, item]
  if (next.length > MAX_LIVE_TRANSCRIPT_ITEMS) {
    liveTranscriptions.value = next.slice(next.length - MAX_LIVE_TRANSCRIPT_ITEMS)
  } else {
    liveTranscriptions.value = next
  }
}

function getSocketSessionId() {
  const sid = props.sessionId || (typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('session_id') : '')
  return sid ? String(sid).trim() : ''
}

/** Chrome/Edge: local human captions via Web Speech API (Realtime input_transcription is often missing on Azure / non-VAD DC). */
function speechRecognitionCtor() {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}

function humanCaptionUiPrefersBrowser() {
  return !!speechRecognitionCtor() && !browserSpeechCaptionsFailed.value
}

let browserSpeechRec = null
let browserSpeechWanted = false
/** True after start() error or not-allowed — fall back to Realtime for human lines */
const browserSpeechCaptionsFailed = ref(false)
/**
 * True once we've applied Realtime session.update for a *running* session after join,
 * or when connect-time session was already running (avoids duplicate refresh).
 * When the user joins before the researcher clicks Start, the first session.update is from
 * a waiting session — we must refresh when the session flips to running.
 */
const realtimeSessionRunningRefreshed = ref(false)

function shareHumanTranscriptLine(text) {
  const tr = String(text || '').trim()
  if (!tr) return
  lastUserTranscript.value = tr
  pushLiveTranscription(localDisplayName.value || 'You', tr, 'human')
  try {
    const ws = getSocket()
    const sid = getSocketSessionId()
    if (ws?.connected && sid) {
      ws.emit('meeting_transcript_share', {
        session_id: sid,
        participant_id: props.participantId,
        text: tr
      })
    }
  } catch {
    /* ignore */
  }
}

function stopBrowserSpeechCaptions() {
  browserSpeechWanted = false
  if (browserSpeechRec) {
    try {
      browserSpeechRec.onresult = null
      browserSpeechRec.onend = null
      browserSpeechRec.onerror = null
      browserSpeechRec.stop()
    } catch {
      /* ignore */
    }
    browserSpeechRec = null
  }
}

function startBrowserSpeechCaptions() {
  const Ctor = speechRecognitionCtor()
  if (!Ctor || !isJoined.value) return
  stopBrowserSpeechCaptions()
  browserSpeechWanted = true
  const rec = new Ctor()
  browserSpeechRec = rec
  rec.continuous = true
  rec.interimResults = true
  rec.lang =
    (typeof navigator !== 'undefined' && navigator.language && navigator.language.trim()) || 'en-US'

  rec.onresult = (event) => {
    if (!browserSpeechWanted) return
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const r = event.results[i]
      if (r.isFinal) {
        const piece = (r[0]?.transcript || '').trim()
        if (piece) shareHumanTranscriptLine(piece)
      }
    }
    let interim = ''
    for (let i = 0; i < event.results.length; i++) {
      const r = event.results[i]
      if (!r.isFinal) interim += r[0]?.transcript || ''
    }
    interimUserTranscript.value = interim.trim()
  }

  rec.onerror = (e) => {
    const err = e?.error || ''
    if (err === 'not-allowed' || err === 'service-not-allowed') {
      browserSpeechCaptionsFailed.value = true
      browserSpeechWanted = false
    }
  }

  rec.onend = () => {
    if (!browserSpeechWanted || !isJoined.value) return
    try {
      rec.start()
    } catch {
      setTimeout(() => {
        if (browserSpeechWanted && isJoined.value) {
          try {
            rec.start()
          } catch {
            /* ignore */
          }
        }
      }, 400)
    }
  }

  try {
    rec.start()
  } catch {
    browserSpeechCaptionsFailed.value = true
    browserSpeechWanted = false
    browserSpeechRec = null
  }
}

/** Local tile key — stable for template even if id types differ */
const localTileKey = computed(() => participantKey(props.participantId))

let localLevelCleanup = null

function startAudioLevelMonitor(stream, participantId, threshold = 0.12) {
  if (!stream?.getAudioTracks?.()?.length) return () => {}
  let ctx
  try {
    ctx = new AudioContext()
  } catch {
    return () => {}
  }
  void ctx.resume().catch(() => {})
  const src = ctx.createMediaStreamSource(stream)
  const an = ctx.createAnalyser()
  an.fftSize = 512
  src.connect(an)
  const buf = new Uint8Array(an.fftSize)
  let raf = 0
  const pk = participantKey(participantId)
  const tick = () => {
    if (ctx.state === 'suspended') {
      void ctx.resume().catch(() => {})
    }
    an.getByteTimeDomainData(buf)
    let s = 0
    for (let i = 0; i < buf.length; i++) {
      const v = (buf[i] - 128) / 128
      s += v * v
    }
    const rms = Math.sqrt(s / buf.length)
    if (pk) setSpeaking(pk, rms > threshold)
    raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)
  return () => {
    cancelAnimationFrame(raf)
    try {
      src.disconnect()
      ctx.close()
    } catch {
      /* ignore */
    }
  }
}

function setRemoteMonitor(participantId, stream) {
  const prev = remoteMonitorsByPid.value[participantId]
  if (typeof prev === 'function') {
    try {
      prev()
    } catch {
      /* ignore */
    }
  }
  if (!stream) return
  const stop = startAudioLevelMonitor(stream, participantId)
  remoteMonitorsByPid.value = { ...remoteMonitorsByPid.value, [participantId]: stop }
}

function clearRemoteMonitor(participantId) {
  const stop = remoteMonitorsByPid.value[participantId]
  if (typeof stop === 'function') {
    try {
      stop()
    } catch {
      /* ignore */
    }
  }
  if (!(participantId in remoteMonitorsByPid.value)) return
  const { [participantId]: _, ...rest } = remoteMonitorsByPid.value
  remoteMonitorsByPid.value = rest
}

function clearAllRemoteMonitors() {
  for (const stop of Object.values(remoteMonitorsByPid.value)) {
    if (typeof stop === 'function') {
      try {
        stop()
      } catch {
        /* ignore */
      }
    }
  }
  remoteMonitorsByPid.value = {}
}

const getLocalMedia = async (audioId = null) => {
  const constraints = {
    audio: audioId ? { deviceId: { exact: audioId } } : true
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia(constraints)
    localStream.value = stream
    return stream
  } catch (err) {
    console.error('[MeetingRoom] getUserMedia error:', err)
    throw err
  }
}

const enumerateDevices = async () => {
  const devices = await navigator.mediaDevices.enumerateDevices()
  audioDevices.value = devices.filter((d) => d.kind === 'audioinput')
  if (audioDevices.value.length > 0 && !selectedAudioId.value) {
    selectedAudioId.value = audioDevices.value[0].deviceId
  }
}

const toggleMute = () => {
  if (!localStream.value) return
  const audioTrack = localStream.value.getAudioTracks()[0]
  if (audioTrack) {
    audioTrack.enabled = !audioTrack.enabled
    isMuted.value = !audioTrack.enabled
    if (isMuted.value) {
      stopBrowserSpeechCaptions()
      interimUserTranscript.value = ''
    } else if (isJoined.value && speechRecognitionCtor() && !browserSpeechCaptionsFailed.value) {
      startBrowserSpeechCaptions()
    }
  }
}

const replaceTrackInPeers = async (kind, newTrack) => {
  for (const [, pc] of Object.entries(peers.value)) {
    const sender = pc.getSenders().find((s) => s.track?.kind === kind)
    if (sender && newTrack) {
      await sender.replaceTrack(newTrack)
    }
  }
  for (const ar of Object.values(agentRealtime.value)) {
    if (ar?.pc && newTrack) {
      const sender = ar.pc.getSenders().find((s) => s.track?.kind === kind)
      if (sender) await sender.replaceTrack(newTrack.clone())
    }
  }
}

const switchAudioDevice = async (deviceId) => {
  if (!localStream.value || !deviceId) return
  try {
    const newStream = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: { exact: deviceId } } })
    const newTrack = newStream.getAudioTracks()[0]
    const oldTrack = localStream.value.getAudioTracks()[0]
    if (oldTrack) {
      localStream.value.removeTrack(oldTrack)
      oldTrack.stop()
    }
    newTrack.enabled = !isMuted.value
    localStream.value.addTrack(newTrack)
    selectedAudioId.value = deviceId
    await replaceTrackInPeers('audio', newTrack)
    if (localLevelCleanup) {
      localLevelCleanup()
      localLevelCleanup = null
    }
    localLevelCleanup = startAudioLevelMonitor(localStream.value, props.participantId)
    showAudioSetting.value = false
  } catch (err) {
    console.error('[MeetingRoom] Switch audio error:', err)
    alert('Failed to switch microphone: ' + (err.message || ''))
  }
}

const createPeerConnection = (participantId) => {
  const pc = new RTCPeerConnection({
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
  })
  if (localStream.value) {
    localStream.value.getTracks().forEach((track) => pc.addTrack(track, localStream.value))
  }
  pc.onicecandidate = (e) => {
    if (e.candidate) {
      getSocket().emit('meeting_signal', {
        session_id: props.sessionId,
        from_participant: props.participantId,
        to_participant: participantId,
        type: 'ice',
        data: e.candidate
      })
    }
  }
  pc.ontrack = (e) => {
    const [stream] = e.streams
    remoteStreams.value = { ...remoteStreams.value, [participantId]: stream }
    setRemoteMonitor(participantId, stream)
  }
  pc.onconnectionstatechange = () => {
    if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
      clearRemoteMonitor(participantId)
      delete peers.value[participantId]
      remoteStreams.value = { ...remoteStreams.value }
      delete remoteStreams.value[participantId]
    }
  }
  return pc
}

/** Stop in-flight model audio on a Realtime data channel (OpenAI / Azure WebRTC). */
function cancelResponseOnDc(dc) {
  if (!dc || dc.readyState !== 'open') return
  try {
    dc.send(JSON.stringify({ type: 'response.cancel' }))
  } catch {
    /* ignore */
  }
  try {
    // WebRTC: cut off model audio (OpenAI / Azure Realtime)
    dc.send(JSON.stringify({ type: 'output_audio_buffer.clear' }))
  } catch {
    /* ignore — not all transports support this */
  }
}

/** User spoke: stop all agents from talking over them (barge-in). */
function cancelAllAgentResponses() {
  for (const ar of Object.values(agentRealtime.value)) {
    cancelResponseOnDc(ar?.dc)
  }
}

/** One agent's speaker started: cut off other agents so voices do not overlap. */
function cancelOtherAgentsResponses(exceptAgentId) {
  const ex = participantKey(exceptAgentId)
  for (const [aid, ar] of Object.entries(agentRealtime.value)) {
    if (participantKey(aid) === ex) continue
    cancelResponseOnDc(ar?.dc)
  }
}

/**
 * Only one agent may hold an active response at a time (first response.created wins).
 * Cleared when that agent finishes or when the user speaks.
 */
let responseFloorAgentId = null
let userVoiceActive = false

/**
 * Mute all agent <audio> unless they hold the floor.
 * When floor is unset, keep everyone muted so leaked TTS from a slow cancel is inaudible.
 */
function applyOaiAudioMuting() {
  const floor = responseFloorAgentId != null ? participantKey(responseFloorAgentId) : null
  for (const [aid, el] of Object.entries(oaiAudioEls.value)) {
    if (!el) continue
    const a = participantKey(aid)
    if (userVoiceActive) {
      el.muted = true
    } else if (floor === null) {
      el.muted = true
    } else {
      el.muted = a !== floor
    }
  }
}

/** First output chunk of a response — earlier than <audio> "play"; use to claim the floor. */
const outputAudioFloorKeys = new Set()
/** Some payloads omit response_id on deltas; pair with response.created id. */
const pendingResponseIdByAgent = new Map()

/** Last user utterance text (for urgency scoring); filled from transcription server events when available. */
const lastUserTranscript = ref('')
/** Skip one moderation round — our own response.create also emits response.created. */
const skipNextModerationForAgent = new Set()

/** One mic feeds N Realtime connections — count VAD depth so we don't spam human true/false. */
let vadSpeechDepth = 0

/** idle | bidding | speaking — system-managed voice turns */
let orchestrationPhase = 'idle'
const bidResults = new Map()
/** Snapshot of agent ids for this dispatch round. */
let lastTurnDispatchAgentIds = []

function agentIdsForOrchestration() {
  return aiParticipantsList.value.map((ap) => ap.id || ap.participant_id).filter(Boolean)
}

/** Weighted random: higher urgent_score is more likely, but not deterministic. */
function pickTurnSpeakerWeighted(ids) {
  const weights = ids.map((id) => {
    const r = bidResults.get(participantKey(id))
    const s = r?.score
    const x = Number.isFinite(s) ? Math.max(0, Math.min(1, s)) : 0
    return 0.08 + x * x * 1.5
  })
  const sum = weights.reduce((a, b) => a + b, 0)
  let roll = Math.random() * sum
  for (let i = 0; i < ids.length; i++) {
    roll -= weights[i]
    if (roll <= 0) return ids[i]
  }
  return ids[ids.length - 1]
}

function startBiddingPhase() {
  if (orchestratedFloor.value === false) return
  if (userVoiceActive) return
  if (orchestrationPhase !== 'idle') return
  const ids = agentIdsForOrchestration()
  if (ids.length === 0) return

  cancelAllAgentResponses()
  orchestrationPhase = 'bidding'
  bidResults.clear()
  lastTurnDispatchAgentIds = []

  for (const aid of ids) {
    const ar = agentRealtime.value[aid]
    if (!ar?.dc || ar.dc.readyState !== 'open') continue
    lastTurnDispatchAgentIds.push(aid)
    const k = participantKey(aid)
    bidResults.set(k, {
      score: computeAgentUrgencyScore(aid),
      reason: 'client'
    })
  }

  if (lastTurnDispatchAgentIds.length === 0) {
    orchestrationPhase = 'idle'
    return
  }

  finalizeBiddingRound()
}

function finalizeBiddingRound() {
  if (orchestrationPhase !== 'bidding') return

  const ids =
    lastTurnDispatchAgentIds.length > 0 ? [...lastTurnDispatchAgentIds] : agentIdsForOrchestration()
  if (ids.length === 0) {
    orchestrationPhase = 'idle'
    return
  }

  for (const aid of ids) {
    const k = participantKey(aid)
    if (!bidResults.has(k)) bidResults.set(k, { score: 0, reason: 'no_request' })
  }

  const winner = pickTurnSpeakerWeighted(ids)

  const transcript =
    (lastUserTranscript.value || '').trim() || 'The user spoke (audio only; no transcript).'
  const wname = resolveDisplayName(winner)

  for (const id of ids) {
    if (participantKey(id) === participantKey(winner)) continue
    const ar = agentRealtime.value[id]
    if (!ar?.dc || ar.dc.readyState !== 'open') continue
    const text = `${wname} is speaking. Content: ${transcript}\nStay silent for this turn until the app assigns you a voice turn.`
    ar.dc.send(
      JSON.stringify({
        type: 'conversation.item.create',
        item: {
          type: 'message',
          role: 'system',
          content: [{ type: 'input_text', text }]
        }
      })
    )
  }

  orchestrationPhase = 'speaking'
  grantLocalFloorAndSpeak(winner)
}

/** Collect simultaneous response.created (one per agent); only one winner requests floor + speaks. */
const moderationBatchIds = new Set()
let moderationBatchTimer = null
const MODERATION_BATCH_MS = 100

function postMeetingFloorHuman(active) {
  return fetch('/api/meeting/floor/human', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: props.sessionId, active })
  }).catch(() => {})
}

/**
 * Heuristic 0..1 urgency: name in transcript, group address, small jitter.
 * Replace with embedding / LLM later for topic relevance.
 */
function computeAgentUrgencyScore(agentId) {
  const name = resolveDisplayName(agentId)
  const text = (lastUserTranscript.value || '').toLowerCase()
  const sid = String(agentId || '')
  let tie = 0
  for (let i = 0; i < sid.length; i++) {
    tie = (tie + sid.charCodeAt(i) * (i + 1)) % 997
  }
  let score = 0.38 + (tie / 997) * 0.12
  const first = (name || '').trim().split(/\s+/)[0]?.toLowerCase() || ''
  if (first.length >= 2 && text.includes(first)) {
    score += 0.42
  }
  if (/(everyone|all|you guys|team|大家|各位|你们|老师们)/i.test(text)) {
    score += 0.28
  }
  if (!text.trim()) {
    score += 0.12
  }
  return Math.min(1, score)
}

function scheduleModerationRound(agentParticipantId) {
  moderationBatchIds.add(participantKey(agentParticipantId))
  if (moderationBatchTimer) clearTimeout(moderationBatchTimer)
  moderationBatchTimer = setTimeout(() => {
    moderationBatchTimer = null
    void flushModerationBatch()
  }, MODERATION_BATCH_MS)
}

/**
 * After batch window: pick highest urgency, single /floor/request, single response.create.
 * Avoids parallel requests racing and fixes “all agents talk at once”.
 */
async function flushModerationBatch() {
  if (orchestratedFloor.value !== false) return
  const raw = [...moderationBatchIds]
  moderationBatchIds.clear()
  if (raw.length === 0) return
  if (userVoiceActive) return

  let winner = raw[0]
  let best = computeAgentUrgencyScore(raw[0])
  for (let i = 1; i < raw.length; i++) {
    const id = raw[i]
    const sc = computeAgentUrgencyScore(id)
    if (sc > best) {
      best = sc
      winner = id
    } else if (Math.abs(sc - best) < 1e-9 && id < winner) {
      winner = id
    }
  }

  await runModerationForWinner(winner)
}

function grantLocalFloorAndSpeak(agentParticipantId) {
  const ar = agentRealtime.value[agentParticipantId]
  if (!ar?.dc || ar.dc.readyState !== 'open') return
  responseFloorAgentId = agentParticipantId
  skipNextModerationForAgent.add(participantKey(agentParticipantId))
  ar.dc.send(JSON.stringify({ type: 'response.create' }))
  setSpeaking(agentParticipantId, true)
  applyOaiAudioMuting()
}

async function runModerationForWinner(agentParticipantId) {
  const ar = agentRealtime.value[agentParticipantId]
  if (!ar?.dc || ar.dc.readyState !== 'open') return
  if (userVoiceActive) return
  const score = computeAgentUrgencyScore(agentParticipantId)
  try {
    const r = await fetch('/api/meeting/floor/request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: props.sessionId,
        agent_participant_id: agentParticipantId,
        score
      })
    })
    const data = await r.json().catch(() => ({}))
    if (!r.ok) {
      console.warn('[MeetingRoom] floor API failed HTTP', r.status, '— using client-only single speaker')
      grantLocalFloorAndSpeak(agentParticipantId)
      return
    }
    if (!data.granted) {
      applyOaiAudioMuting()
      return
    }
    grantLocalFloorAndSpeak(agentParticipantId)
  } catch (e) {
    console.error('[MeetingRoom] floor request', e)
    grantLocalFloorAndSpeak(agentParticipantId)
  }
}

function handleRealtimeDataChannelMessage(agentParticipantId, ev) {
  let evt
  try {
    evt = JSON.parse(ev.data)
  } catch {
    return
  }
  const t = evt.type || ''
  const agentKey = participantKey(agentParticipantId)

  // User speech → text (Realtime). Often missing on Azure / wrong DC — browser Web Speech handles UI when available.
  if (typeof t === 'string' && t.includes('input_audio_transcription') && t.includes('delta')) {
    if (!humanCaptionUiPrefersBrowser()) {
      const d = evt.delta ?? evt.transcript ?? ''
      if (typeof d === 'string' && d) {
        interimUserTranscript.value = `${interimUserTranscript.value}${d}`.trim()
      }
    }
  }
  if (typeof t === 'string' && t.includes('input_audio_transcription') && t.includes('completed')) {
    const tr =
      (typeof evt.transcript === 'string' && evt.transcript.trim()) ||
      (typeof evt.item?.transcript === 'string' && evt.item.transcript.trim()) ||
      (typeof evt.item?.content?.[0]?.transcript === 'string' && evt.item.content[0].transcript.trim()) ||
      (typeof evt.item?.formatted?.transcript === 'string' && evt.item.formatted.transcript.trim()) ||
      interimUserTranscript.value.trim() ||
      ''
    if (tr) {
      lastUserTranscript.value = tr
      if (!humanCaptionUiPrefersBrowser()) {
        pushLiveTranscription(localDisplayName.value || 'You', tr, 'human')
        try {
          const ws = getSocket()
          const sid = getSocketSessionId()
          if (ws?.connected && sid) {
            ws.emit('meeting_transcript_share', {
              session_id: sid,
              participant_id: props.participantId,
              text: tr
            })
          }
        } catch {
          /* ignore */
        }
      }
    }
    if (!humanCaptionUiPrefersBrowser()) {
      interimUserTranscript.value = ''
    }
  }

  // Model speech → text (OpenAI: response.audio_transcript.*; some builds use response.output_audio_transcript.*)
  const isRespAudioTranscriptDelta =
    typeof t === 'string' && /^response\./.test(t) && t.includes('audio_transcript') && t.includes('delta')
  const isRespAudioTranscriptDone =
    typeof t === 'string' && /^response\./.test(t) && t.includes('audio_transcript') && /\.done$/.test(t)

  if (isRespAudioTranscriptDelta) {
    const rid = evt.response_id || evt.response?.id || pendingResponseIdByAgent.get(agentParticipantId) || 'no_response'
    const key = `${participantKey(agentParticipantId)}:${rid}`
    const delta = String(evt.delta ?? evt.transcript ?? '').trim()
    if (delta) {
      const prev = responseTranscriptBufferByAgent.get(key) || ''
      responseTranscriptBufferByAgent.set(key, `${prev}${delta}`.trim())
    }
  }
  if (isRespAudioTranscriptDone) {
    const rid = evt.response_id || evt.response?.id || pendingResponseIdByAgent.get(agentParticipantId) || 'no_response'
    const key = `${participantKey(agentParticipantId)}:${rid}`
    const finalText =
      String(evt.transcript || '').trim() ||
      String(responseTranscriptBufferByAgent.get(key) || '').trim()
    if (finalText) {
      pushLiveTranscription(resolveDisplayName(agentParticipantId), finalText, 'ai')
    }
    responseTranscriptBufferByAgent.delete(key)
  }

  if (
    t === 'input_audio_buffer.speech_started' ||
    (typeof t === 'string' && t.includes('input_audio') && t.includes('speech_started'))
  ) {
    const ignoreVadEvent =
      orchestratedFloor.value !== false &&
      vadLeaderAgentId.value != null &&
      participantKey(agentParticipantId) !== participantKey(vadLeaderAgentId.value)
    if (!ignoreVadEvent) {
      vadSpeechDepth += 1
      if (vadSpeechDepth === 1) {
        if (orchestratedFloor.value !== false) {
          if (orchestrationPhase === 'bidding') {
            bidResults.clear()
            lastTurnDispatchAgentIds = []
            orchestrationPhase = 'idle'
          }
          if (orchestrationPhase === 'speaking') {
            orchestrationPhase = 'idle'
          }
        }
        void postMeetingFloorHuman(true)
        userVoiceActive = true
        responseFloorAgentId = null
        setSpeaking(props.participantId, true)
        cancelAllAgentResponses()
        applyOaiAudioMuting()
      }
    }
  }
  if (
    t === 'input_audio_buffer.speech_stopped' ||
    (typeof t === 'string' && t.includes('input_audio') && t.includes('speech_stopped'))
  ) {
    const ignoreVadEvent =
      orchestratedFloor.value !== false &&
      vadLeaderAgentId.value != null &&
      participantKey(agentParticipantId) !== participantKey(vadLeaderAgentId.value)
    if (!ignoreVadEvent) {
      vadSpeechDepth = Math.max(0, vadSpeechDepth - 1)
      if (vadSpeechDepth === 0) {
        void postMeetingFloorHuman(false)
        userVoiceActive = false
        setSpeaking(props.participantId, false)
        applyOaiAudioMuting()
        if (orchestratedFloor.value !== false && vadLeaderAgentId.value != null) {
          if (participantKey(agentParticipantId) === participantKey(vadLeaderAgentId.value)) {
            const ldc = agentRealtime.value[vadLeaderAgentId.value]?.dc
            if (ldc) cancelResponseOnDc(ldc)
            startBiddingPhase()
          }
        }
      }
    }
  }
  if (t === 'response.output_audio.delta') {
    const floorK = responseFloorAgentId != null ? participantKey(responseFloorAgentId) : null
    if (floorK !== null && agentKey !== floorK) {
      cancelResponseOnDc(agentRealtime.value[agentParticipantId]?.dc)
      const badEl = oaiAudioEls.value[agentParticipantId]
      if (badEl) badEl.muted = true
    } else {
      const rid =
        evt.response_id ||
        evt.response?.id ||
        pendingResponseIdByAgent.get(agentParticipantId)
      if (rid) {
        const key = `${agentKey}:${rid}`
        if (!outputAudioFloorKeys.has(key)) {
          outputAudioFloorKeys.add(key)
          cancelOtherAgentsResponses(agentParticipantId)
          applyOaiAudioMuting()
        }
      }
    }
  }
  if (t === 'response.created') {
    const rid = evt.response?.id
    if (rid) pendingResponseIdByAgent.set(agentParticipantId, rid)
    if (skipNextModerationForAgent.has(agentKey)) {
      skipNextModerationForAgent.delete(agentKey)
      responseFloorAgentId = agentParticipantId
      setSpeaking(agentParticipantId, true)
      applyOaiAudioMuting()
    } else if (orchestratedFloor.value !== false) {
      const ar = agentRealtime.value[agentParticipantId]
      if (ar?.dc) cancelResponseOnDc(ar.dc)
      setSpeaking(agentParticipantId, false)
      applyOaiAudioMuting()
    } else {
      const ar = agentRealtime.value[agentParticipantId]
      if (ar?.dc) cancelResponseOnDc(ar.dc)
      setSpeaking(agentParticipantId, false)
      applyOaiAudioMuting()
      scheduleModerationRound(agentParticipantId)
    }
  }
  if (t === 'response.done') {
    const wasOrchestratedSpeakingHolder =
      orchestratedFloor.value !== false &&
      orchestrationPhase === 'speaking' &&
      participantKey(responseFloorAgentId) === agentKey
    void fetch('/api/meeting/floor/release', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: props.sessionId,
        agent_participant_id: agentParticipantId
      })
    }).catch(() => {})
    const rid = evt.response?.id
    if (rid) {
      outputAudioFloorKeys.delete(`${agentKey}:${rid}`)
      responseTranscriptBufferByAgent.delete(`${agentKey}:${rid}`)
    }
    pendingResponseIdByAgent.delete(agentParticipantId)
    setSpeaking(agentParticipantId, false)
    if (participantKey(responseFloorAgentId) === agentKey) {
      responseFloorAgentId = null
    }
    applyOaiAudioMuting()
    if (wasOrchestratedSpeakingHolder) {
      orchestrationPhase = 'idle'
    }
    const out = evt.response?.output
    if (Array.isArray(out)) {
      for (const item of out) {
        if (item.type === 'function_call' && item.call_id && item.name) {
          handleRealtimeFunctionCall(agentParticipantId, item)
        }
      }
    }
  }
}

async function handleRealtimeFunctionCall(agentParticipantId, item) {
  const ar = agentRealtime.value[agentParticipantId]
  if (!ar?.dc || ar.dc.readyState !== 'open') return
  let args = item.arguments
  if (typeof args === 'string') {
    try {
      args = JSON.parse(args)
    } catch {
      args = {}
    }
  }
  const isLegacyTurnTool = item.name === 'request_turn' || item.name === 'bid_speak'
  try {
    const res = await fetch('/api/realtime/execute_function', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: props.sessionId,
        agent_participant_id: agentParticipantId,
        name: item.name,
        arguments: args || {}
      })
    })
    const data = await res.json().catch(() => ({}))
    const output = data.output != null ? String(data.output) : '{"success":false}'
    ar.dc.send(
      JSON.stringify({
        type: 'conversation.item.create',
        item: {
          type: 'function_call_output',
          call_id: item.call_id,
          output
        }
      })
    )
    if (isLegacyTurnTool && orchestratedFloor.value !== false) {
      return
    }
    skipNextModerationForAgent.add(participantKey(agentParticipantId))
    ar.dc.send(JSON.stringify({ type: 'response.create' }))
  } catch (e) {
    console.error('[MeetingRoom] execute_function', e)
  }
}

async function fetchAndSendRealtimeSessionUpdate(dc, agentParticipantId) {
  if (!dc || dc.readyState !== 'open') return
  try {
    const r = await fetch(
      `/api/realtime/session_update?session_id=${encodeURIComponent(props.sessionId)}&agent_participant_id=${encodeURIComponent(agentParticipantId)}`
    )
    if (r.status === 204) return
    if (!r.ok) {
      const t = await r.text()
      console.error('[MeetingRoom] session_update HTTP', r.status, t)
      return
    }
    const data = await r.json()
    const events = Array.isArray(data.events)
      ? data.events
      : data?.type === 'session.update'
        ? [data]
        : []
    for (const ev of events) {
      if (ev?.type === 'session.update') dc.send(JSON.stringify(ev))
    }
    if (typeof data.orchestrated_floor === 'boolean') {
      orchestratedFloor.value = data.orchestrated_floor
    }
  } catch (e) {
    console.error('[MeetingRoom] session_update', e)
  }
}

async function applyRealtimeSessionUpdateToAllAgents() {
  const ids = Object.keys(agentRealtime.value)
  for (const agentParticipantId of ids) {
    const ar = agentRealtime.value[agentParticipantId]
    if (!ar?.dc || ar.dc.readyState !== 'open') continue
    await fetchAndSendRealtimeSessionUpdate(ar.dc, agentParticipantId)
  }
}

function maybeRefreshRealtimeWhenSessionRunning(data) {
  if (!isJoined.value) return
  if (!sessionIdsMatch(data?.session_id, getSocketSessionId())) return
  const statusRunning = data?.session_info?.status === 'running'
  const timerRunning = data?.is_running === true && data?.is_paused !== true
  if (!statusRunning && !timerRunning) return
  if (realtimeSessionRunningRefreshed.value) return
  realtimeSessionRunningRefreshed.value = true
  void applyRealtimeSessionUpdateToAllAgents()
}

async function connectOneRealtimeAgent(agentParticipantId) {
  if (!localStream.value) return
  const track = localStream.value.getAudioTracks()[0]
  if (!track) return

  const iceServers = [{ urls: 'stun:stun.l.google.com:19302' }]
  const pc = new RTCPeerConnection({ iceServers })
  pc.ontrack = (e) => {
    const [stream] = e.streams
    const el = oaiAudioEls.value[agentParticipantId]
    if (el) el.srcObject = stream
    aiLevelStopFns.value.push(startAudioLevelMonitor(stream, agentParticipantId, 0.02))
  }
  pc.addTrack(track.clone())
  const dc = pc.createDataChannel('oai-events')
  dc.onmessage = (ev) => handleRealtimeDataChannelMessage(agentParticipantId, ev)
  dc.onopen = async () => {
    await fetchAndSendRealtimeSessionUpdate(dc, agentParticipantId)
  }
  const offer = await pc.createOffer()
  await pc.setLocalDescription(offer)
  const url = `/api/realtime/calls?session_id=${encodeURIComponent(props.sessionId)}&agent_participant_id=${encodeURIComponent(agentParticipantId)}`
  const sdpRes = await fetch(url, {
    method: 'POST',
    body: offer.sdp,
    headers: { 'Content-Type': 'application/sdp' }
  })
  if (!sdpRes.ok) {
    const errText = await sdpRes.text()
    throw new Error(errText || `Realtime ${sdpRes.status}`)
  }
  const answerSdp = await sdpRes.text()
  await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp })
  agentRealtime.value = {
    ...agentRealtime.value,
    [agentParticipantId]: { pc, dc }
  }
}

async function startOpenAIRealtime() {
  realtimeError.value = ''
  const agents = aiParticipantsList.value
  if (!agents.length) return

  try {
    for (const ap of agents) {
      const aid = ap.id || ap.participant_id
      await connectOneRealtimeAgent(aid)
    }
    if (localStream.value) {
      if (localLevelCleanup) localLevelCleanup()
      localLevelCleanup = startAudioLevelMonitor(localStream.value, props.participantId, 0.065)
    }
    applyOaiAudioMuting()
    try {
      const sid = getSocketSessionId()
      if (sid) {
        const r = await fetch(`/api/sessions/${encodeURIComponent(sid)}`)
        if (r.ok) {
          const s = await r.json()
          if (s.status === 'running') {
            realtimeSessionRunningRefreshed.value = true
          }
        }
      }
    } catch {
      /* ignore */
    }
  } catch (e) {
    console.error('[MeetingRoom] OpenAI Realtime:', e)
    realtimeError.value = e.message || 'Realtime connection failed'
    stopOpenAIRealtime()
  }
}

function stopOpenAIRealtime() {
  void fetch('/api/meeting/floor/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: props.sessionId })
  }).catch(() => {})
  clearAllRemoteMonitors()
  aiLevelStopFns.value.forEach((fn) => {
    try {
      fn()
    } catch {
      /* ignore */
    }
  })
  aiLevelStopFns.value = []
  if (localLevelCleanup) {
    localLevelCleanup()
    localLevelCleanup = null
  }
  for (const aid of Object.keys(agentRealtime.value)) {
    const ar = agentRealtime.value[aid]
    if (ar?.dc) {
      ar.dc.onmessage = null
      ar.dc.close()
    }
    if (ar?.pc) ar.pc.close()
  }
  agentRealtime.value = {}
  responseFloorAgentId = null
  userVoiceActive = false
  outputAudioFloorKeys.clear()
  pendingResponseIdByAgent.clear()
  responseTranscriptBufferByAgent.clear()
  interimUserTranscript.value = ''
  skipNextModerationForAgent.clear()
  moderationBatchIds.clear()
  if (moderationBatchTimer) {
    clearTimeout(moderationBatchTimer)
    moderationBatchTimer = null
  }
  orchestratedFloor.value = true
  orchestrationPhase = 'idle'
  bidResults.clear()
  lastTurnDispatchAgentIds = []
  vadSpeechDepth = 0
  for (const k of Object.keys(speaking)) {
    delete speaking[k]
  }
  liveTranscriptions.value = []
  for (const el of Object.values(oaiAudioEls.value)) {
    if (el) {
      el.muted = false
      el.srcObject = null
    }
  }
  oaiAudioEls.value = {}
}

function attachOaiPlayHandler(agentId, el) {
  if (!el || el.dataset.oaiPlayBound === '1') return
  el.dataset.oaiPlayBound = '1'
  el.addEventListener('play', () => {
    cancelOtherAgentsResponses(agentId)
    applyOaiAudioMuting()
  })
}

/** Function refs run on every render; must not assign new reactive state unless el actually changed or Vue will update-loop. */
function setOaiAudioRef(agentId, el) {
  const cur = oaiAudioEls.value[agentId]
  if (el) {
    if (cur === el) return
    oaiAudioEls.value = { ...oaiAudioEls.value, [agentId]: el }
    el.muted = true
    attachOaiPlayHandler(agentId, el)
    applyOaiAudioMuting()
  } else {
    if (cur == null) return
    const { [agentId]: _, ...rest } = oaiAudioEls.value
    oaiAudioEls.value = rest
  }
}

const joinMeeting = async () => {
  if (isJoined.value || isConnecting.value) return
  isConnecting.value = true
  browserSpeechCaptionsFailed.value = false
  realtimeSessionRunningRefreshed.value = false
  try {
    await getLocalMedia()
    await enumerateDevices()
    isMuted.value = false
    getSocket().emit('meeting_join', {
      session_id: props.sessionId,
      participant_id: props.participantId
    })
    isJoined.value = true
    await startOpenAIRealtime()
    startBrowserSpeechCaptions()
  } catch (err) {
    alert('Could not access microphone. ' + (err.message || ''))
  } finally {
    isConnecting.value = false
  }
}

const leaveMeeting = () => {
  stopBrowserSpeechCaptions()
  stopOpenAIRealtime()
  localStream.value?.getTracks().forEach((t) => t.stop())
  localStream.value = null
  Object.values(peers.value).forEach((pc) => pc.close())
  peers.value = {}
  remoteStreams.value = {}
  getSocket().emit('meeting_leave', {
    session_id: props.sessionId,
    participant_id: props.participantId
  })
  isJoined.value = false
}

const handleMeetingPeerJoined = async (data) => {
  const { participant_id } = data
  if (participant_id === props.participantId) return
  if (peers.value[participant_id]) return

  const pc = createPeerConnection(participant_id)
  peers.value[participant_id] = pc
  try {
    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    getSocket().emit('meeting_signal', {
      session_id: props.sessionId,
      from_participant: props.participantId,
      to_participant: participant_id,
      type: 'offer',
      data: offer
    })
  } catch (err) {
    console.error('[MeetingRoom] createOffer error:', err)
  }
}

const handleMeetingSignal = async (data) => {
  const { from_participant, to_participant, type, data: signalData } = data
  if (to_participant !== props.participantId) return

  let pc = peers.value[from_participant]
  if (!pc) {
    pc = createPeerConnection(from_participant)
    peers.value[from_participant] = pc
  }

  try {
    if (type === 'offer') {
      await pc.setRemoteDescription(new RTCSessionDescription(signalData))
      const answer = await pc.createAnswer()
      await pc.setLocalDescription(answer)
      getSocket().emit('meeting_signal', {
        session_id: props.sessionId,
        from_participant: props.participantId,
        to_participant: from_participant,
        type: 'answer',
        data: answer
      })
    } else if (type === 'answer') {
      await pc.setRemoteDescription(new RTCSessionDescription(signalData))
    } else if (type === 'ice') {
      await pc.addIceCandidate(new RTCIceCandidate(signalData))
    }
  } catch (err) {
    console.error('[MeetingRoom] handle signal error:', err)
  }
}

let offPeerJoined = null
let offSignal = null
let offMeetingTranscript = null
let offTimerUpdate = null
let offParticipantsUpdated = null

function sessionIdsMatch(a, b) {
  if (a == null || b == null) return false
  return String(a).trim() === String(b).trim()
}

onMounted(() => {
  const ws = getSocket()
  offPeerJoined = (data) => handleMeetingPeerJoined(data)
  offSignal = (data) => handleMeetingSignal(data)
  offMeetingTranscript = (data) => {
    const sid = getSocketSessionId()
    if (!data || !sessionIdsMatch(data.session_id, sid)) return
    const pid = data.participant_id
    if (pid == null || participantKey(pid) === participantKey(props.participantId)) return
    const text = String(data.text || '').trim()
    if (!text) return
    pushLiveTranscription(resolveDisplayName(pid), text, 'human')
  }
  offTimerUpdate = (data) => maybeRefreshRealtimeWhenSessionRunning(data)
  offParticipantsUpdated = (data) => maybeRefreshRealtimeWhenSessionRunning(data)
  ws.on('meeting_peer_joined', offPeerJoined)
  ws.on('meeting_signal', offSignal)
  ws.on('meeting_transcript', offMeetingTranscript)
  ws.on('timer_update', offTimerUpdate)
  ws.on('participants_updated', offParticipantsUpdated)
})

onUnmounted(() => {
  leaveMeeting()
  const ws = getSocket()
  if (offPeerJoined) ws.off('meeting_peer_joined', offPeerJoined)
  if (offSignal) ws.off('meeting_signal', offSignal)
  if (offMeetingTranscript) ws.off('meeting_transcript', offMeetingTranscript)
  if (offTimerUpdate) ws.off('timer_update', offTimerUpdate)
  if (offParticipantsUpdated) ws.off('participants_updated', offParticipantsUpdated)
})
</script>

<template>
  <div class="meeting-room">
    <div class="meeting-header">
      <h4>Meeting Room</h4>
      <button v-if="!isJoined" class="join-btn" :disabled="isConnecting" @click="joinMeeting">
        {{ isConnecting ? 'Connecting...' : 'Join Meeting' }}
      </button>
      <button v-else class="leave-btn" @click="leaveMeeting">Leave Meeting</button>
    </div>
    <template v-for="ap in aiParticipantsList" :key="ap.id || ap.participant_id">
      <audio
        :ref="(el) => setOaiAudioRef(ap.id || ap.participant_id, el)"
        class="oai-realtime-audio"
        autoplay
        playsinline
      />
    </template>
    <div v-if="realtimeError" class="ai-realtime-error">{{ realtimeError }}</div>
    <div v-if="isJoined" class="meeting-tiles">
      <div
        class="participant-tile local"
        :class="{ speaking: isSpeaking(localTileKey) }"
      >
        <div class="participant-name">{{ localDisplayName }}</div>
        <span class="corner-label">You</span>
      </div>
      <div
        v-for="p in humanOthers"
        :key="p.id || p.participant_id"
        class="participant-tile remote"
        :class="{ speaking: isSpeaking(p.id || p.participant_id) }"
      >
        <audio
          :ref="(el) => { if (el) el.srcObject = remoteStreams[p.id || p.participant_id] }"
          autoplay
          playsinline
          class="remote-audio"
        />
        <div class="participant-name">{{ resolveDisplayName(p.id || p.participant_id) }}</div>
      </div>
      <div
        v-for="ap in aiParticipantsList"
        :key="'ai-' + (ap.id || ap.participant_id)"
        class="participant-tile remote ai-tile"
        :class="{ speaking: isSpeaking(ap.id || ap.participant_id) }"
      >
        <div class="participant-name">{{ resolveDisplayName(ap.id || ap.participant_id) }}</div>
        <span class="corner-label ai-badge">AI</span>
      </div>
    </div>
    <div v-if="isJoined" class="meeting-controls">
      <div class="control-group">
        <button type="button" :class="['control-btn', { active: isMuted }]" @click="toggleMute" :title="isMuted ? 'Unmute' : 'Mute'">
          <i :class="isMuted ? 'fa-solid fa-microphone-slash' : 'fa-solid fa-microphone'"></i> {{ isMuted ? 'Unmute' : 'Mute' }}
        </button>
        <div class="control-dropdown">
          <button ref="audioTriggerRef" type="button" class="dropdown-trigger" @click="showAudioSetting = !showAudioSetting" title="Switch audio device">
            <i class="fa-solid fa-chevron-down"></i>
          </button>
          <Teleport to="body">
            <div v-if="showAudioSetting" class="dropdown-menu dropdown-menu-portal" :style="audioDropdownStyle">
              <div v-for="d in audioDevices" :key="d.deviceId" class="dropdown-item" :class="{ selected: selectedAudioId === d.deviceId }" @click="switchAudioDevice(d.deviceId)">
                {{ d.label || `Microphone ${audioDevices.indexOf(d) + 1}` }}
              </div>
            </div>
          </Teleport>
        </div>
      </div>
    </div>
    <div v-if="isJoined" class="live-transcription-panel" aria-live="polite">
      <div class="live-transcription-header">Live Transcription</div>
      <div v-if="liveTranscriptions.length" class="live-transcription-list">
        <div
          v-for="item in liveTranscriptions"
          :key="item.id"
          class="live-transcription-item"
          :class="{ 'is-human': item.kind === 'human', 'is-ai': item.kind === 'ai' }"
        >
          <span class="live-transcription-speaker">{{ item.speaker }}:</span>
          <span class="live-transcription-text">{{ item.text }}</span>
        </div>
      </div>
      <!-- Human interim: must show even when the list already has AI lines (do not use v-else with the list). -->
      <div v-if="interimUserTranscript.trim()" class="live-transcription-interim">
        <span class="live-transcription-speaker">{{ localDisplayName }}:</span>
        <span class="live-transcription-text interim">{{ interimUserTranscript.trim() }}</span>
      </div>
      <div v-if="!liveTranscriptions.length && !interimUserTranscript.trim()" class="live-transcription-empty">
        Captions appear here after you or others speak (human + AI).
      </div>
    </div>
    <div v-else-if="!isConnecting" class="meeting-placeholder">
      <p>Click &quot;Join Meeting&quot; for voice chat with other participants (camera off)</p>
    </div>
  </div>
</template>

<style scoped>
.meeting-room {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  background: #f9fafb;
  margin-top: 8px;
}
.meeting-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.meeting-header h4 {
  margin: 0;
  font-size: 14px;
}
.join-btn, .leave-btn {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  border: none;
}
.join-btn {
  background: #667eea;
  color: white;
}
.join-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.leave-btn {
  background: #ef4444;
  color: white;
}
.meeting-tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.participant-tile {
  position: relative;
  width: 160px;
  height: 120px;
  background: linear-gradient(145deg, #374151 0%, #1f2937 100%);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 3px solid #111827;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.participant-tile.speaking {
  border-color: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.45);
}
.participant-tile.ai-tile {
  background: linear-gradient(145deg, #1e3a5f 0%, #172554 100%);
}
.participant-tile .participant-name {
  padding: 8px 12px;
  font-size: 15px;
  font-weight: 600;
  color: #f9fafb;
  text-align: center;
  line-height: 1.25;
  word-break: break-word;
  max-width: 100%;
}
.participant-tile .corner-label {
  position: absolute;
  bottom: 6px;
  left: 6px;
  font-size: 10px;
  color: #e5e7eb;
  background: rgba(0,0,0,0.45);
  padding: 3px 8px;
  border-radius: 4px;
  max-width: calc(100% - 12px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.corner-label.ai-badge {
  left: auto;
  right: 6px;
  background: rgba(59, 130, 246, 0.5);
}
.remote-audio {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
.oai-realtime-audio {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
.ai-realtime-error {
  margin-bottom: 8px;
  padding: 6px 8px;
  font-size: 11px;
  color: #b91c1c;
  background: #fef2f2;
  border-radius: 4px;
}
.meeting-placeholder {
  padding: 24px;
  text-align: center;
  color: #6b7280;
  font-size: 13px;
}
.meeting-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e5e7eb;
  align-items: center;
}
.live-transcription-panel {
  margin-top: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
  overflow: hidden;
  text-align: left;
}
.live-transcription-header {
  font-size: 12px;
  font-weight: 700;
  color: #1f2937;
  padding: 8px 10px;
  border-bottom: 1px solid #e5e7eb;
  background: #f3f4f6;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  text-align: left;
}
.live-transcription-list {
  max-height: 180px;
  overflow-y: auto;
  padding: 8px 10px;
  text-align: left;
}
.live-transcription-empty {
  padding: 0 10px 10px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.45;
  text-align: left;
}
.live-transcription-text.interim {
  font-style: italic;
  color: #374151;
}
.live-transcription-interim {
  padding: 8px 10px 10px;
  border-top: 1px dashed #e5e7eb;
  text-align: left;
  font-size: 12px;
  line-height: 1.45;
}
.live-transcription-item {
  font-size: 12px;
  color: #111827;
  line-height: 1.45;
  margin-bottom: 6px;
  word-break: break-word;
  text-align: left;
}
.live-transcription-item:last-child {
  margin-bottom: 0;
}
.live-transcription-speaker {
  font-weight: 700;
  margin-right: 6px;
  color: #374151;
}
.live-transcription-item.is-human .live-transcription-speaker {
  color: #047857;
}
.live-transcription-item.is-ai .live-transcription-speaker {
  color: #1d4ed8;
}
.live-transcription-interim .live-transcription-speaker {
  color: #047857;
}
.live-transcription-text {
  color: #1f2937;
}
.control-group {
  display: flex;
  align-items: stretch;
  height: 32px;
}
.control-group .control-btn {
  border-radius: 6px 0 0 6px;
  padding: 0 12px;
  height: 100%;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.control-group .control-dropdown {
  display: flex;
  margin-left: -1px;
}
.control-group .control-dropdown .dropdown-trigger {
  width: 28px;
  min-width: 28px;
  height: 100%;
  padding: 0;
  border-radius: 0 6px 6px 0;
  border: 1px solid #d1d5db;
  border-left: none;
  background: #e5e7eb;
  cursor: pointer;
  color: #374151;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
}
.control-group .control-dropdown .dropdown-trigger:hover {
  background: #d1d5db;
}
.control-group .control-dropdown .dropdown-menu {
  left: auto;
  right: 0;
}
.control-btn {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  background: #e5e7eb;
  border: 1px solid #d1d5db;
  cursor: pointer;
  color: #374151;
}
.control-btn:hover {
  background: #d1d5db;
}
.control-btn.active {
  background: #ef4444;
  border-color: #ef4444;
  color: white;
}
.control-dropdown {
  position: relative;
}
.control-dropdown .dropdown-menu {
  position: absolute;
  bottom: 100%;
  left: 0;
  margin-bottom: 4px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  min-width: 180px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 9999;
}
.dropdown-menu-portal {
  position: fixed !important;
  z-index: 99999 !important;
  background: #ffffff !important;
  border: 1px solid #e5e7eb !important;
}
.dropdown-item {
  padding: 8px 12px;
  font-size: 12px;
  cursor: pointer;
  color: #374151;
}
.dropdown-item:hover {
  background: #f3f4f6;
}
.dropdown-item.selected {
  background: #eff6ff;
  color: #1d4ed8;
}
</style>
