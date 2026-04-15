<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const sessionId = ref(route.query.session_id || sessionStorage.getItem('session_id') || '')
const participantId = ref(route.query.participant_id || sessionStorage.getItem('participant_id') || '')
const sessionName = ref('')

const mergedLogs = ref([])
const annotationMoments = ref([])
const participantNames = ref({})
const filesBase = ref('')
const loading = ref(true)
const error = ref('')

const sessionStartTime = ref(null)
const sessionDurationSeconds = ref(null)
const inSessionAnnotations = ref([])
/** From API; used to apply map-task-only interaction log filter */
const experimentType = ref('')

const currentMomentIndex = ref(0)
const currentMoment = computed(() => annotationMoments.value[currentMomentIndex.value] || null)
const annotationFinished = ref(false)

const SECTIONS = [
  {
    id: 'q1',
    category: 'Task Model',
    question: 'At this moment, my partner and I were:',
    labels: [
      { id: 't1', text: 'Still figuring out what we needed to do' },
      { id: 't2', text: 'Working toward a shared understanding' },
      { id: 't3', text: 'Clear on what to do and working on it' },
      { id: 't4', text: 'Something was unclear and we were working it out' },
      { id: 'other', text: 'Other' },
    ],
  },

  {
    id: 'q2',
    category: 'Partner Model',
    question: 'At this moment, I thought my partner:',
    labels: [
      { id: 'p1', text: 'Understood the situation and we were on the same page' },
      { id: 'p2', text: 'Probably understood our situation but I was not fully sure' },
      { id: 'p3', text: 'Is waiting for more information to understand the situation' },
      { id: 'p4', text: 'Misunderstood and we were not aligned' },
      { id: 'p5', text: 'Gave no clear signal either way' },
      { id: 'other', text: 'Other' },
    ],
  },

  {
    id: 'q3',
    category: 'Self Model',
    question: 'At this moment, my action was driven by:',
    labels: [
      { id: 'r1', text: 'Executing a plan we already agreed on' },
      { id: 'r2', text: 'Exploring on my own to gather information' },
      { id: 'r3', text: 'Confirming the situation with my partner' },
      { id: 'r4', text: 'Grounding by sharing or requesting information to align' },
      { id: 'r5', text: 'Repairing a mistake or misunderstanding' },
      { id: 'r6', text: 'Waiting for more information' },
      { id: 'other', text: 'Other' },
    ],
  },

  {
    id: 'q4',
    category: 'Alignment',
    question: 'At this moment, my partner and I were on the same page:',
    kind: 'yes_no_reasons',
    reasons: {
      no: [
        { id: 'n1', text: 'Different understanding of the task goal' },
        { id: 'n2', text: 'Different understanding of the current state' },
        { id: 'n3', text: 'One of us was missing key information' },
        { id: 'n4', text: 'Communication was unclear or ambiguous' },
        { id: 'n5', text: 'Technical or interface issue got in the way' },
      ],
    },
  },
]

const Q4_REASON_OTHER = 'Other'

const Q4_REASONS = [
  ...(SECTIONS.find((s) => s.id === 'q4')?.reasons?.no || []).map((r) => r.text),
  Q4_REASON_OTHER,
]

const RECORD_PHASE_INSTRUCTION =
  'Please briefly answer all four questions in one recording.\nClick the button to start recording.'

/** One combined explanation (transcribed) for all four questions per moment */
const MOMENT_EXPLAIN_KEY = 'momentExplanationTranscript'

const stepIndex = ref(0)
const currentSection = computed(() => SECTIONS[stepIndex.value] || null)

/** Bold the clause after this prefix in each section question (q1–q4). */
const SECTION_QUESTION_PREFIX = 'At this moment, '
const currentSectionQuestionParts = computed(() => {
  const q = currentSection.value?.question
  if (!q) return null
  const s = String(q)
  if (s.startsWith(SECTION_QUESTION_PREFIX)) {
    return { lead: SECTION_QUESTION_PREFIX, rest: s.slice(SECTION_QUESTION_PREFIX.length) }
  }
  return { plain: s }
})

/** 'record' = show all 4 questions + single recording; 'answer' = one question at a time */
const annotationPhase = ref('record')

const annotations = ref({})
const selectedLabelId = ref('')
/** Free text for the "Other" choice only */
const otherLabelText = ref('')
/** Combined explanation for the four questions (record phase) */
const explanationTranscript = ref('')
/** Matches AnnotationPopup: after a successful recording, show re-record affordance */
const hasRecordedExplanation = ref(false)
/** After Confirm on an answer step: big checkmark before flip to next */
const showStepSuccess = ref(false)
const q4Value = ref(null)
const q4Reasons = ref([])
/** Free text when Q4 "Other" reason is selected */
const q4OtherText = ref('')

const isQ4Step = computed(() => currentSection.value?.kind === 'yes_no_reasons')
const isLabelQuestionStep = computed(
  () => !!currentSection.value && currentSection.value.kind !== 'yes_no_reasons',
)

/** Per moment: 1 combined explanation step + 4 choice steps */
const STEPS_PER_MOMENT = 1 + SECTIONS.length

const currentProgressPct = computed(() => {
  const moments = annotationMoments.value.length
  const total = moments * STEPS_PER_MOMENT
  if (!total) return 0
  const phaseOffset = annotationPhase.value === 'record' ? 0 : 1 + stepIndex.value
  const done = currentMomentIndex.value * STEPS_PER_MOMENT + phaseOffset + 1
  return (done / total) * 100
})

/** 1 = record step; 2–5 = question steps */
const progressSubstepIndex = computed(() =>
  annotationPhase.value === 'record' ? 1 : 2 + stepIndex.value,
)

/** Full merged log for the interaction table — do not clip by configured session duration; that hid late send_message / map actions when the session ran past duration or clocks skewed. Researcher Conversations uses full session.messages; this should match. */
const visibleMergedLogs = computed(() => {
  if (!Array.isArray(mergedLogs.value)) return []
  return mergedLogs.value
})

/** Post-session UI: for maptask, show only message + key map actions (full data still in DB / merged_logs). */
function isMaptaskPostAnnotationLogEntry(entry) {
  const t = entry?.action_type
  const c = String(entry?.action_content || '').trim()
  // Humans: WebSocket logs send_message. AI agents: agent_context_protocol logs type "message".
  if (t === 'send_message' || t === 'message') return true
  if (t === 'map_tool_click' && ['brush', 'eraser', 'undo', 'reset'].includes(c)) return true
  if (t === 'map_draw_stop' && (c === 'brush_release' || c === 'eraser_release')) return true
  return false
}

/** Full interaction log (all participants). Screenshot carousel / click-to-preview: own rows only — see screenshotNavEntries. */
const displayMergedLogs = computed(() => {
  const rows = visibleMergedLogs.value
  const exp = (experimentType.value || '').toLowerCase()
  if (exp === 'maptask') {
    return rows.filter(isMaptaskPostAnnotationLogEntry)
  }
  return rows
})

/** action_id → index in annotationMoments (only rows that are annotatable moments) */
const momentIndexByActionId = computed(() => {
  const map = new Map()
  annotationMoments.value.forEach((mom, i) => {
    if (mom?.action_id) map.set(mom.action_id, i)
  })
  return map
})

function getMomentIndexForLogEntry(entry) {
  if (!entry?.action_id) return -1
  return momentIndexByActionId.value.get(entry.action_id) ?? -1
}

/** Merge legacy per-question transcripts into momentExplanationTranscript when loading old saves */
function migrateMomentAnnotation(saved) {
  if (!saved || typeof saved !== 'object') return {}
  const out = { ...saved }
  const existing = String(out[MOMENT_EXPLAIN_KEY] || '').trim()
  if (existing) return out
  const parts = []
  for (const s of SECTIONS) {
    if (s.kind === 'yes_no_reasons') continue
    const t = String(out[`${s.id}Transcript`] || '').trim()
    if (t) parts.push(t)
  }
  if (parts.length) out[MOMENT_EXPLAIN_KEY] = parts.join('\n\n')
  return out
}

function logEntryParticipantIsYou(entry) {
  if (!entry?.participant_id || !participantId.value) return false
  return String(entry.participant_id) === String(participantId.value)
}

/** True if merged log row has a screenshot we can show (path or URL). */
function logEntryHasScreenshot(entry) {
  if (!entry?.screenshot) return false
  const s = String(entry.screenshot).trim()
  if (!s) return false
  if (s.startsWith('http://') || s.startsWith('https://')) return true
  if (s.startsWith('s3://')) return true
  return !!filesBase.value
}

/** Only your rows with screenshots for carousel / click-to-preview (partner log lines stay visible but are not navigable here). */
const screenshotNavEntries = computed(() =>
  displayMergedLogs.value.filter((e) => logEntryParticipantIsYou(e) && logEntryHasScreenshot(e)),
)

const screenshotCarouselIndex = ref(0)

const screenshotDisplayEntry = computed(() => {
  const list = screenshotNavEntries.value
  if (!list.length) return currentMoment.value
  const i = Math.min(Math.max(0, screenshotCarouselIndex.value), list.length - 1)
  return list[i]
})

/** Right-side annotation UI only when the screenshot panel shows your current annotation moment. */
const showAnnotationPanel = computed(() => {
  const e = screenshotDisplayEntry.value
  const cm = currentMoment.value
  return !!(e && cm && e.action_id === cm.action_id && getMomentIndexForLogEntry(e) >= 0)
})

function syncCarouselToCurrentMoment() {
  const cm = currentMoment.value
  if (!cm?.action_id) return
  const list = screenshotNavEntries.value
  const i = list.findIndex((e) => e.action_id === cm.action_id)
  if (i >= 0) screenshotCarouselIndex.value = i
}

/** Stable key for tag styling + i18n-style labels in the interaction log */
const ACTION_TAG_LABELS = {
  message: 'Send message',
  brush_release: 'Draw route',
  brush: 'Brush tool',
  eraser_release: 'Erase route',
  eraser: 'Erase route',
  undo: 'Undo last action',
  reset: 'Reset map',
}

function getPostAnnotationActionKind(entry) {
  if (entry?.action_type === 'send_message' || entry?.action_type === 'message') return 'message'
  if (entry?.action_type === 'map_draw_stop') return String(entry.action_content || '').trim() || 'map_draw_stop'
  if (entry?.action_type === 'map_tool_click') return String(entry.action_content || '').trim() || 'map_tool_click'
  return entry?.action_type || 'action'
}

function getActionTagKey(entry) {
  const t = entry?.action_type
  const c = String(entry?.action_content || '').trim()
  if (t === 'send_message' || t === 'message') return 'message'
  if (t === 'map_draw_stop' && c === 'brush_release') return 'brush_release'
  if (t === 'map_draw_stop' && c === 'eraser_release') return 'eraser'
  if (t === 'map_tool_click') {
    if (c === 'brush') return 'brush'
    if (c === 'eraser') return 'eraser'
    if (c === 'undo') return 'undo'
    if (c === 'reset') return 'reset'
  }
  return 'default'
}

function getActionTagLabel(entry) {
  const key = getActionTagKey(entry)
  if (key !== 'default' && ACTION_TAG_LABELS[key]) return ACTION_TAG_LABELS[key]
  const raw = getPostAnnotationActionKind(entry)
  if (!raw) return 'Action'
  return raw
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ')
}

/** MM:SS from session-timer elapsed seconds (preferred for in-session annotation submit time). */
function formatElapsedSeconds(sec) {
  if (sec === null || sec === undefined || sec === '') return null
  const n = Number(sec)
  if (!Number.isFinite(n) || n < 0) return null
  const totalSeconds = Math.floor(n)
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/** Earliest valid timestamp (ms) in a log row list. */
function minLogTimeMs(rows) {
  if (!Array.isArray(rows) || !rows.length) return null
  let min = Infinity
  for (const e of rows) {
    const t = new Date(e?.timestamp).getTime()
    if (!Number.isNaN(t)) min = Math.min(min, t)
  }
  return Number.isFinite(min) ? min : null
}

/**
 * Elapsed MM:SS from wall clock: `ts` minus `session_started_at` (or earliest merged log).
 * Prefer `formatLogEntryTime(entry)` for interaction rows — it uses `session_elapsed_seconds`
 * when present (timer-consistent; excludes in-session annotation pauses).
 */
function formatTime(ts) {
  if (!ts) return '00:00'
  try {
    const d = new Date(ts)
    if (Number.isNaN(d.getTime())) return '—'
    let startMs = null
    if (sessionStartTime.value) {
      const s = sessionStartTime.value.getTime()
      if (!Number.isNaN(s)) startMs = s
    }
    if (startMs == null) startMs = minLogTimeMs(mergedLogs.value)
    if (startMs == null) return '—'
    const totalSeconds = Math.max(0, Math.floor((d.getTime() - startMs) / 1000))
    const m = Math.floor(totalSeconds / 60)
    const s = totalSeconds % 60
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  } catch {
    return '00:00'
  }
}

/** MM:SS for a merged log row: backend `session_elapsed_seconds` when set; else `formatTime(timestamp)`. */
function formatLogEntryTime(entry) {
  if (!entry) return '00:00'
  const sec = entry.session_elapsed_seconds
  if (sec !== null && sec !== undefined && sec !== '') {
    const n = Number(sec)
    if (Number.isFinite(n) && n >= 0) {
      const formatted = formatElapsedSeconds(n)
      if (formatted) return formatted
    }
  }
  return formatTime(entry.timestamp)
}

function getDisplayName(entry, isYou = false) {
  const pid = entry.participant_id
  const name = entry.participant_name || participantNames.value[pid] || pid?.slice(0, 8) || 'Unknown'
  return isYou ? `${name} (you)` : name
}

/** Resolve files/… ref or absolute URL for session log assets (screenshot, map_image, …). */
function getSessionLogAssetUrl(stored) {
  if (!stored || !String(stored).trim()) return null
  const s = String(stored).trim()
  if (s.startsWith('http://') || s.startsWith('https://')) return s
  if (!filesBase.value) return null
  const filename = s.startsWith('files/') ? s.slice(6) : s
  return `${filesBase.value}/${filename}`
}

/** Session-time screenshot only (from merged_logs); not post_annotation uploads. */
function getScreenshotUrlForLogEntry(entry) {
  if (!entry?.action_id) return null
  return getSessionLogAssetUrl(entry.screenshot)
}

function annotationsPayloadForSave(raw) {
  const out = {}
  for (const [k, v] of Object.entries(raw || {})) {
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      const { screenshot_s3, ...rest } = v
      out[k] = rest
    } else {
      out[k] = v
    }
  }
  return out
}

const screenshotUrl = computed(() => getScreenshotUrlForLogEntry(screenshotDisplayEntry.value))

/**
 * Map [0,100] session progress to one of three in-session checkpoints (≈25%, 50%, 75%)
 * by nearest anchor — matches how checkpoints are spaced in the experiment.
 */
function checkpointIndexFromNearestAnchorPct(pct) {
  const anchors = [25, 50, 75]
  let best = 0
  let bestD = Infinity
  for (let i = 0; i < anchors.length; i++) {
    const d = Math.abs(pct - anchors[i])
    if (d < bestD - 1e-9) {
      bestD = d
      best = i
    }
  }
  return best
}

const selectedInSessionThought = computed(() => {
  const _trackMoment = currentMomentIndex.value
  const m = currentMoment.value
  const ann = inSessionAnnotations.value || []
  const timerElapsed =
    m &&
    m.session_elapsed_seconds !== null &&
    m.session_elapsed_seconds !== undefined &&
    m.session_elapsed_seconds !== '' &&
    Number.isFinite(Number(m.session_elapsed_seconds))
      ? Math.max(0, Number(m.session_elapsed_seconds))
      : null
  if (!m || (timerElapsed === null && (!m.timestamp || !sessionStartTime.value))) {
    return { transcription: '', timeLabel: '—' }
  }
  let dur = sessionDurationSeconds.value
  if ((!dur || dur <= 0) && mergedLogs.value.length >= 2) {
    const first = new Date(mergedLogs.value[0].timestamp).getTime()
    const last = new Date(mergedLogs.value[mergedLogs.value.length - 1].timestamp).getTime()
    if (last > first) dur = Math.floor((last - first) / 1000)
  }
  if (!dur || dur <= 0) {
    return { transcription: '(Session duration unavailable; cannot map in-game thoughts.)', timeLabel: '—' }
  }
  let elapsedSec
  if (timerElapsed !== null) {
    elapsedSec = timerElapsed
  } else {
    const actionTime = new Date(m.timestamp).getTime()
    const start = sessionStartTime.value.getTime()
    elapsedSec = (actionTime - start) / 1000
  }
  const pct = elapsedSec < 0 ? 0 : (elapsedSec / dur) * 100
  const bucket = checkpointIndexFromNearestAnchorPct(pct)
  const list = [...ann].sort((a, b) => (Number(a.checkpoint_index) || 0) - (Number(b.checkpoint_index) || 0))
  const match = list.find((x) => Number(x.checkpoint_index) === bucket)
  if (!match?.transcription?.trim()) {
    return { transcription: '(No in-session annotation recorded for this period.)', timeLabel: '—' }
  }
  const fromElapsed = formatElapsedSeconds(match.elapsed_seconds)
  const timeLabel =
    fromElapsed != null
      ? fromElapsed
      : match.created_at
        ? formatTime(match.created_at)
        : '—'
  return { transcription: match.transcription.trim(), timeLabel }
})

const inGameThoughtsDisplayLabel = computed(() => {
  const t = selectedInSessionThought.value?.timeLabel
  if (t && t !== '—') return `Your in-game thoughts at ${t}`
  return 'Your In-Game Thoughts:'
})

const prevMomentSaved = computed(() => {
  if (currentMomentIndex.value <= 0) return null
  const prevMoment = annotationMoments.value[currentMomentIndex.value - 1]
  if (!prevMoment) return null
  return annotations.value[prevMoment.action_id] || null
})

const prevAnswerForStep = computed(() => {
  const prev = prevMomentSaved.value
  const sec = currentSection.value
  if (!prev || !sec) return null
  if (sec.kind === 'yes_no_reasons') {
    const v = prev.q4
    if (v !== 'yes' && v !== 'no') return null
    const reasons = (prev.q4Reasons || []).filter(Boolean)
    return {
      text: v === 'yes' ? 'Yes' : 'No',
      labelId: '',
      transcript: '',
      q4Reasons: reasons,
      q4OtherText: (prev.q4OtherText || '').trim(),
      isQ4: true,
    }
  }
  const text = (prev[sec.id] || '').trim()
  if (!text) return null
  return {
    text,
    labelId: prev[`${sec.id}LabelId`] || '',
    otherText: (prev[`${sec.id}OtherText`] || '').trim(),
    isQ4: false,
  }
})

const canConfirmCurrentStep = computed(() => {
  const sec = currentSection.value
  if (!sec) return false
  if (sec.kind === 'yes_no_reasons') {
    if (q4Value.value !== 'yes' && q4Value.value !== 'no') return false
    if (q4Value.value === 'no' && q4Reasons.value.length === 0) return false
    if (
      q4Value.value === 'no' &&
      q4Reasons.value.includes(Q4_REASON_OTHER) &&
      !q4OtherText.value.trim()
    ) {
      return false
    }
    return true
  }
  if (!selectedLabelId.value) return false
  if (selectedLabelId.value === 'other' && !otherLabelText.value.trim()) return false
  return true
})

const canConfirmExplanationPhase = computed(
  () =>
    explanationTranscript.value.trim().length > 0 &&
    !isTranscribing.value &&
    !isRecording.value,
)

const canRecordOtherLabel = computed(
  () => isLabelQuestionStep.value && selectedLabelId.value === 'other',
)

const isRecording = ref(false)
const mediaRecorder = ref(null)
const isTranscribing = ref(false)
const recordingTarget = ref(null)

function getLabelText(sectionId, labelId) {
  const sec = SECTIONS.find((s) => s.id === sectionId)
  if (!sec || !sec.labels) return ''
  const found = sec.labels.find((l) => l.id === labelId)
  return found?.text || ''
}

function selectLabel(labelId) {
  if (selectedLabelId.value !== labelId) {
    if (selectedLabelId.value === 'other' && labelId !== 'other') {
      otherLabelText.value = ''
    }
    selectedLabelId.value = labelId
  } else {
    selectedLabelId.value = labelId
  }
}

function loadStepStateFromSaved() {
  if (annotationPhase.value === 'record') return
  const m = currentMoment.value
  const sec = currentSection.value
  if (!m || !sec) return
  const saved = migrateMomentAnnotation(annotations.value[m.action_id] || {})
  if (sec.kind === 'yes_no_reasons') {
    q4Value.value = saved.q4 === 'yes' || saved.q4 === 'no' ? saved.q4 : null
    q4Reasons.value = Array.isArray(saved.q4Reasons) ? [...saved.q4Reasons] : []
    q4OtherText.value = typeof saved.q4OtherText === 'string' ? saved.q4OtherText : ''
    return
  }
  const savedLabelId = saved[`${sec.id}LabelId`] || ''
  const savedText = (saved[sec.id] || '').trim()
  const otKey = `${sec.id}OtherText`
  selectedLabelId.value = savedLabelId
  otherLabelText.value = typeof saved[otKey] === 'string' ? saved[otKey] : ''
  if (!selectedLabelId.value && savedText && sec.labels) {
    const byText = sec.labels.find((x) => x.text === savedText)
    if (byText) selectedLabelId.value = byText.id
  }
}

function syncPhaseFromSavedMoment() {
  const m = currentMoment.value
  if (!m) return
  const raw = annotations.value[m.action_id] || {}
  const saved = migrateMomentAnnotation({ ...raw })
  annotations.value[m.action_id] = saved
  const ex = String(saved[MOMENT_EXPLAIN_KEY] || '').trim()
  explanationTranscript.value = ex
  hasRecordedExplanation.value = !!ex
  if (!ex) {
    annotationPhase.value = 'record'
    stepIndex.value = 0
  } else {
    annotationPhase.value = 'answer'
    stepIndex.value = firstIncompleteStepIndexForSaved(saved)
  }
}

function loadCurrentMomentState() {
  const m = currentMoment.value
  if (!m) return
  if (!annotations.value[m.action_id]) {
    annotations.value[m.action_id] = {}
  }
  selectedLabelId.value = ''
  otherLabelText.value = ''
  q4Value.value = null
  q4Reasons.value = []
  q4OtherText.value = ''
  syncPhaseFromSavedMoment()
  loadStepStateFromSaved()
}

watch(currentMoment, () => loadCurrentMomentState(), { immediate: true })
watch(stepIndex, () => loadStepStateFromSaved())

watch(q4Value, (v) => {
  if (v === 'yes') {
    q4Reasons.value = []
    q4OtherText.value = ''
  }
})

function saveCurrentStepAnnotation() {
  if (annotationPhase.value === 'record') return
  const m = currentMoment.value
  const sec = currentSection.value
  if (!m || !sec) return
  const prev = annotations.value[m.action_id] || {}
  if (sec.kind === 'yes_no_reasons') {
    annotations.value[m.action_id] = {
      ...prev,
      q4: q4Value.value,
      q4Reasons: [...q4Reasons.value],
      q4OtherText: q4OtherText.value.trim(),
    }
    return
  }
  const labelText = getLabelText(sec.id, selectedLabelId.value)
  const otKey = `${sec.id}OtherText`
  annotations.value[m.action_id] = {
    ...prev,
    [sec.id]: labelText,
    [`${sec.id}LabelId`]: selectedLabelId.value,
    [otKey]: selectedLabelId.value === 'other' ? otherLabelText.value.trim() : '',
  }
}

function moveToNextStepOrMoment() {
  if (stepIndex.value < SECTIONS.length - 1) {
    stepIndex.value += 1
    return
  }
  if (currentMomentIndex.value < annotationMoments.value.length - 1) {
    currentMomentIndex.value += 1
    stepIndex.value = 0
    return
  }
  if (!allAnnotationMomentsComplete()) {
    const n = annotationMoments.value.filter(
      (mom) => !isMomentAnnotationComplete(annotations.value[mom.action_id] || {}),
    ).length
    alert(
      `Please annotate all of your actions before finishing. ${n} moment(s) still have incomplete answers. You will be taken to the first incomplete moment.`,
    )
    focusFirstIncompleteMoment()
    return
  }
  annotationFinished.value = true
}

function saveMomentExplanationOnly() {
  const m = currentMoment.value
  if (!m) return
  const prev = annotations.value[m.action_id] || {}
  annotations.value[m.action_id] = {
    ...prev,
    [MOMENT_EXPLAIN_KEY]: explanationTranscript.value.trim(),
  }
}

/** Persist in-progress UI when jumping moments / screenshots (avoid saving label step while still on record phase). */
function persistAnnotationUiBeforeLeave() {
  if (annotationPhase.value === 'record') {
    if (explanationTranscript.value.trim()) saveMomentExplanationOnly()
    return
  }
  saveCurrentStepAnnotation()
}

async function confirmExplanationPhase() {
  if (!canConfirmExplanationPhase.value) return
  saveMomentExplanationOnly()
  const ok = await saveAnnotationsToFile()
  if (!ok) return
  annotationPhase.value = 'answer'
  stepIndex.value = 0
  loadStepStateFromSaved()
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

async function confirmCurrentStep() {
  if (!canConfirmCurrentStep.value) return
  saveCurrentStepAnnotation()
  const ok = await saveAnnotationsToFile()
  if (!ok) return
  showStepSuccess.value = true
  await delay(750)
  showStepSuccess.value = false
  await delay(80)
  moveToNextStepOrMoment()
}

/** Fill current step UI from previous moment's saved answer for this question (user can edit, then Confirm). */
function applySameAsLastMomentToForm() {
  const prev = prevAnswerForStep.value
  const sec = currentSection.value
  if (!prev || !sec) return
  if (sec.kind === 'yes_no_reasons') {
    const yes = prev.text === 'Yes'
    q4Value.value = yes ? 'yes' : 'no'
    if (yes) {
      q4Reasons.value = []
      q4OtherText.value = ''
    } else {
      q4Reasons.value = [...(prev.q4Reasons || [])]
      q4OtherText.value = prev.q4OtherText || ''
    }
    return
  }
  selectedLabelId.value = prev.labelId || ''
  otherLabelText.value = prev.otherText || ''
}

function loadData() {
  if (!sessionId.value || !participantId.value) {
    error.value = 'Missing session_id or participant_id'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  fetch(`/api/sessions/${encodeURIComponent(sessionId.value)}/post_annotation_data?participant_id=${encodeURIComponent(participantId.value)}`)
    .then((r) => r.json())
    .then((data) => {
      if (data.error) {
        error.value = data.error
        return
      }
      mergedLogs.value = data.merged_logs || []
      annotationMoments.value = data.annotation_moments || []
      participantNames.value = data.participant_names || {}
      filesBase.value = data.files_base || ''
      sessionName.value = data.session_name || data.session_id || ''
      experimentType.value =
        data.experiment_type || (Array.isArray(data.merged_logs) && data.merged_logs[0]?.experiment_type) || ''
      inSessionAnnotations.value = data.in_session_annotations || []
      sessionDurationSeconds.value =
        data.session_duration_seconds != null && data.session_duration_seconds !== ''
          ? Number(data.session_duration_seconds)
          : null
      if (data.saved_annotations && typeof data.saved_annotations === 'object') {
        const raw = annotationsPayloadForSave(data.saved_annotations)
        const migrated = {}
        for (const [k, v] of Object.entries(raw)) {
          migrated[k] = migrateMomentAnnotation(v)
        }
        annotations.value = migrated
      }
      if (data.session_started_at) {
        const d = new Date(data.session_started_at)
        sessionStartTime.value = Number.isNaN(d.getTime()) ? null : d
      } else {
        sessionStartTime.value = null
      }
      if (!sessionStartTime.value) {
        const anchor = minLogTimeMs(mergedLogs.value)
        sessionStartTime.value = anchor != null ? new Date(anchor) : null
      }
      currentMomentIndex.value = 0
      stepIndex.value = 0
      annotationFinished.value = false
      loadCurrentMomentState()
      syncCarouselToCurrentMoment()
    })
    .catch((err) => {
      error.value = err.message || 'Failed to load annotation data'
    })
    .finally(() => {
      loading.value = false
    })
}

/** Returns true if saved (or nothing to save); false if the server rejected the save. */
async function saveAnnotationsToFile() {
  if (!sessionId.value || !participantId.value) return true
  try {
    const res = await fetch(
      `/api/sessions/${encodeURIComponent(sessionId.value)}/participants/${encodeURIComponent(participantId.value)}/post_annotations`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ annotations: annotationsPayloadForSave(annotations.value) }),
      }
    )
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const msg = data.error || `Save failed (${res.status})`
      console.error('[PostAnnotation]', msg)
      alert(msg)
      return false
    }
    return true
  } catch (err) {
    console.error('[PostAnnotation] Failed to save annotations:', err)
    alert(err.message || 'Could not save your answers. Check your connection and try again.')
    return false
  }
}

function isSectionCompleteForSaved(saved, sec) {
  if (sec.kind === 'yes_no_reasons') {
    if (!saved.q4 || (saved.q4 !== 'yes' && saved.q4 !== 'no')) return false
    if (saved.q4 === 'no' && !(saved.q4Reasons || []).length) return false
    const reasons = saved.q4Reasons || []
    if (saved.q4 === 'no' && reasons.includes(Q4_REASON_OTHER) && !(saved.q4OtherText || '').trim()) {
      return false
    }
    return true
  }
  const label = (saved[`${sec.id}LabelId`] || '').trim()
  if (!label) return false
  if (label === 'other' && !(saved[`${sec.id}OtherText`] || '').trim()) return false
  return true
}

function isMomentAnnotationComplete(rawSaved) {
  const saved = migrateMomentAnnotation(rawSaved || {})
  if (!(saved[MOMENT_EXPLAIN_KEY] || '').trim()) return false
  for (const s of SECTIONS) {
    if (!isSectionCompleteForSaved(saved, s)) return false
  }
  return true
}

function firstIncompleteStepIndexForSaved(rawSaved) {
  const saved = migrateMomentAnnotation(rawSaved || {})
  if (!(saved[MOMENT_EXPLAIN_KEY] || '').trim()) return 0
  for (let i = 0; i < SECTIONS.length; i++) {
    if (!isSectionCompleteForSaved(saved, SECTIONS[i])) return i
  }
  return SECTIONS.length - 1
}

function isLogEntryFullyAnnotated(entry) {
  const idx = getMomentIndexForLogEntry(entry)
  if (idx < 0) return false
  const aid = annotationMoments.value[idx]?.action_id
  if (!aid) return false
  return isMomentAnnotationComplete(annotations.value[aid] || {})
}

function allAnnotationMomentsComplete() {
  return annotationMoments.value.every((mom) =>
    isMomentAnnotationComplete(annotations.value[mom.action_id] || {}),
  )
}

function focusFirstIncompleteMoment() {
  for (let mi = 0; mi < annotationMoments.value.length; mi++) {
    const aid = annotationMoments.value[mi]?.action_id
    if (!aid) continue
    const saved = annotations.value[aid] || {}
    if (!isMomentAnnotationComplete(saved)) {
      currentMomentIndex.value = mi
      stepIndex.value = firstIncompleteStepIndexForSaved(saved)
      syncCarouselToCurrentMoment()
      return true
    }
  }
  return false
}

function logEntryIsInteractive(entry) {
  if (!logEntryParticipantIsYou(entry)) return false
  if (getMomentIndexForLogEntry(entry) >= 0) return true
  return logEntryHasScreenshot(entry)
}

async function onInteractionLogEntryClick(entry) {
  if (!logEntryParticipantIsYou(entry)) return
  const navIdx = screenshotNavEntries.value.findIndex((e) => e.action_id === entry.action_id)
  const ownMi = getMomentIndexForLogEntry(entry)
  if (ownMi < 0 && navIdx < 0) return

  persistAnnotationUiBeforeLeave()
  const ok = await saveAnnotationsToFile()
  if (!ok) return

  if (ownMi >= 0) {
    currentMomentIndex.value = ownMi
    const aid = annotationMoments.value[ownMi]?.action_id
    stepIndex.value = firstIncompleteStepIndexForSaved(annotations.value[aid] || {})
  }

  if (navIdx >= 0) {
    screenshotCarouselIndex.value = navIdx
  } else if (ownMi >= 0) {
    syncCarouselToCurrentMoment()
  }
}

async function screenshotNavDelta(delta) {
  const list = screenshotNavEntries.value
  if (!list.length) return
  const next = Math.min(list.length - 1, Math.max(0, screenshotCarouselIndex.value + delta))
  if (next === screenshotCarouselIndex.value) return
  const entry = list[next]
  persistAnnotationUiBeforeLeave()
  const ok = await saveAnnotationsToFile()
  if (!ok) return
  screenshotCarouselIndex.value = next
  const mi = getMomentIndexForLogEntry(entry)
  if (mi >= 0) {
    currentMomentIndex.value = mi
    stepIndex.value = firstIncompleteStepIndexForSaved(annotations.value[entry.action_id] || {})
  }
}

async function toggleRecording(target) {
  if (isTranscribing.value) return
  if (target === 'moment_explain' && hasRecordedExplanation.value && !isRecording.value) {
    explanationTranscript.value = ''
    hasRecordedExplanation.value = false
  }
  if (isRecording.value) {
    if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
      mediaRecorder.value.stop()
    }
    return
  }
  recordingTarget.value = target
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    const chunks = []
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data)
    }
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      isRecording.value = false
      if (chunks.length === 0) return
      isTranscribing.value = true
      try {
        const blob = new Blob(chunks, { type: 'audio/webm' })
        const form = new FormData()
        form.append('audio', blob, 'recording.webm')
        const res = await fetch('/api/transcribe', { method: 'POST', body: form })
        const data = await res.json().catch(() => ({}))
        const text = (data.text || '').trim()
        if (target === 'q4_other') {
          q4OtherText.value = text
        } else if (target === 'other_label') {
          otherLabelText.value = text
        } else if (target === 'moment_explain') {
          explanationTranscript.value = text
          hasRecordedExplanation.value = true
        }
      } catch (err) {
        console.error('[PostAnnotation] Transcribe error:', err)
        if (target === 'moment_explain') {
          explanationTranscript.value = '[Transcription failed. Please try again.]'
          hasRecordedExplanation.value = true
        }
      } finally {
        isTranscribing.value = false
      }
    }
    recorder.start()
    mediaRecorder.value = recorder
    isRecording.value = true
  } catch (err) {
    console.error('[PostAnnotation] Microphone error:', err)
    alert('Microphone access denied.')
  }
}

function handleUpdate(target) {
  if (isRecording.value && recordingTarget.value === target) {
    if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
      mediaRecorder.value.stop()
    }
  } else {
    toggleRecording(target)
  }
}

const canRecordQ4Other = computed(
  () =>
    isQ4Step.value &&
    q4Value.value === 'no' &&
    q4Reasons.value.includes(Q4_REASON_OTHER),
)

function toggleQ4Reason(reason) {
  const idx = q4Reasons.value.indexOf(reason)
  if (idx >= 0) {
    q4Reasons.value.splice(idx, 1)
    if (reason === Q4_REASON_OTHER) q4OtherText.value = ''
  } else {
    q4Reasons.value.push(reason)
  }
}

watch(currentMomentIndex, () => {
  syncCarouselToCurrentMoment()
})

onMounted(() => {
  if (route.query.session_id) sessionId.value = route.query.session_id
  if (route.query.participant_id) participantId.value = route.query.participant_id
  loadData()
})
</script>

<template>
  <div class="post-annotation-page">
    <div class="page-header">
      <h1>Post-Session Annotation <span class="session-name">- Session: {{ sessionName || sessionId }}</span></h1>
    </div>

    <div v-if="loading" class="loading-state">
      <p>Loading annotation data...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <p class="hint">For testing with sample data, use: ?session_id=016c8aca-bac7-4f60-ae36-0ccc5504a1fb&participant_id=a59bed79-e55a-417e-92cc-e0ff70fc8cf9</p>
    </div>

    <div v-else-if="annotationFinished" class="completion-state">
      <p class="completion-title">Congrats! You've finished the annotation.</p>
      <p class="completion-body">Thank you for your participation. You can close the window now.</p>
    </div>

    <div v-else-if="annotationMoments.length === 0" class="empty-state">
      <p>No annotation moments found for this session.</p>
    </div>

    <div v-else class="annotation-layout">
      <div class="left-panel">
        <h2 class="panel-title">
          <template v-if="screenshotDisplayEntry">
            You are revisiting your action at
            <span class="time-highlight">{{ formatLogEntryTime(screenshotDisplayEntry) }}</span>
          </template>
          <template v-else>Session replay</template>
        </h2>

        <div class="session-replay-preview">
          <button
            type="button"
            class="screenshot-nav-btn screenshot-nav-btn--prev"
            :disabled="screenshotNavEntries.length <= 1 || screenshotCarouselIndex <= 0"
            aria-label="Previous screenshot"
            @click="screenshotNavDelta(-1)"
          >
            <i class="fa-solid fa-chevron-left"></i>
          </button>
          <div class="session-replay-preview__frame">
            <img
              v-if="screenshotUrl"
              :src="screenshotUrl"
              alt="Session replay at action time"
              class="replay-screenshot"
            />
            <div v-else class="replay-placeholder">No screenshot</div>
          </div>
          <button
            type="button"
            class="screenshot-nav-btn screenshot-nav-btn--next"
            :disabled="screenshotNavEntries.length <= 1 || screenshotCarouselIndex >= screenshotNavEntries.length - 1"
            aria-label="Next screenshot"
            @click="screenshotNavDelta(1)"
          >
            <i class="fa-solid fa-chevron-right"></i>
          </button>
        </div>

        <div class="log-list-header">Interaction Log</div>
        <div class="log-list">
          <div
            v-for="(entry, logIdx) in displayMergedLogs"
            :key="entry.action_id || `log-${logIdx}-${entry.timestamp}-${entry.participant_id}-${entry.action_type}`"
            class="log-item"
            :class="{
              'log-item--screenshot-active':
                screenshotDisplayEntry && entry.action_id === screenshotDisplayEntry.action_id,
              'log-item--annotation-target':
                currentMoment && entry.action_id === currentMoment.action_id,
              'log-item--clickable': logEntryIsInteractive(entry),
              'log-item--annotated': isLogEntryFullyAnnotated(entry),
              'log-item--partner': !logEntryParticipantIsYou(entry),
            }"
            :tabindex="logEntryIsInteractive(entry) ? 0 : undefined"
            :title="
              !logEntryParticipantIsYou(entry)
                ? 'Partner (screenshot preview is only for your actions)'
                : logEntryIsInteractive(entry)
                  ? getMomentIndexForLogEntry(entry) >= 0
                    ? 'Jump to your annotation for this action'
                    : 'View screenshot for this action'
                  : undefined
            "
            :role="logEntryIsInteractive(entry) ? 'button' : undefined"
            :aria-label="
              !logEntryParticipantIsYou(entry)
                ? 'Partner at ' + formatLogEntryTime(entry)
                : logEntryIsInteractive(entry)
                  ? 'Your action at ' + formatLogEntryTime(entry)
                  : undefined
            "
            @click="onInteractionLogEntryClick(entry)"
            @keydown.enter.prevent="onInteractionLogEntryClick(entry)"
            @keydown.space.prevent="onInteractionLogEntryClick(entry)"
          >
            <span class="log-time">
              <span
                v-if="isLogEntryFullyAnnotated(entry)"
                class="log-annotated-indicator"
                title="All questions answered for this action"
              >✓</span>
              {{ formatLogEntryTime(entry) }}
            </span>
            <span class="log-participant">{{ getDisplayName(entry, entry.participant_id === participantId) }}</span>
            <span
              class="log-type-tag"
              :class="'tag-' + getActionTagKey(entry)"
            >{{ getActionTagLabel(entry) }}</span>
            <span class="log-content">{{ entry.action_content || '—' }}</span>
          </div>
        </div>
      </div>

      <div class="right-panel">
        <template v-if="showAnnotationPanel">
        <h2 class="panel-title">
          You are annotating your action at
          <span class="time-highlight">{{ currentMoment ? formatLogEntryTime(currentMoment) : '00:00' }}</span>
        </h2>

        <div class="progress-wrap">
          <div class="progress-label-row">
            <span>Moment {{ currentMomentIndex + 1 }} / {{ annotationMoments.length }}</span>
            <span
              >Step {{ progressSubstepIndex }} / {{ STEPS_PER_MOMENT
              }}<template v-if="annotationPhase === 'record'"> · Record</template
              ><template v-else> · Question {{ stepIndex + 1 }} / {{ SECTIONS.length }}</template></span
            >
          </div>
          <div class="progress-track">
            <div class="progress-fill" :style="{ width: `${currentProgressPct}%` }"></div>
          </div>
        </div>

        <div class="thoughts-box">
          <label>{{ inGameThoughtsDisplayLabel }}</label>
          <p>{{ selectedInSessionThought.transcription || '(No thoughts recorded)' }}</p>
        </div>

        <div class="annotation-workspace">
          <transition name="phase-flip" mode="out-in">
            <div v-if="annotationPhase === 'record'" key="phase-record" class="phase-block record-phase">
              <div class="all-questions-overview">
                <p class="overview-instruction">Please briefly answer the following questions.</p>
                <div class="overview-questions-text">At this moment:<br />
1. What are you and your partner trying to do?<br />
2. What do you think your partner was doing?<br />
3. Why did you take this action?</div>
              </div>
              <p class="record-phase-instruction">{{ RECORD_PHASE_INSTRUCTION }}</p>

              <div class="moment-explain-recording">
                <button
                  type="button"
                  class="record-btn-circle"
                  :class="{ recording: isRecording && recordingTarget === 'moment_explain', 'has-recorded': hasRecordedExplanation }"
                  :disabled="isTranscribing"
                  :title="hasRecordedExplanation ? 'Re-record' : (isRecording && recordingTarget === 'moment_explain' ? 'Stop' : 'Record')"
                  @click="handleUpdate('moment_explain')"
                >
                  <i
                    v-if="isRecording && recordingTarget === 'moment_explain'"
                    class="fa-solid fa-microphone record-circle-icon"
                  ></i>
                  <i
                    v-else-if="hasRecordedExplanation"
                    class="fa-solid fa-arrow-rotate-left record-circle-icon"
                  ></i>
                  <i v-else class="fa-solid fa-microphone record-circle-icon"></i>
                </button>

                <div v-if="isRecording && recordingTarget === 'moment_explain'" class="sound-wave">
                  <span v-for="wi in 12" :key="wi" class="wave-bar"></span>
                </div>

                <div
                  v-if="isTranscribing && recordingTarget === 'moment_explain'"
                  class="transcribing-hint"
                >
                  Transcribing…
                </div>

                <div
                  v-if="hasRecordedExplanation && !(isTranscribing && recordingTarget === 'moment_explain')"
                  class="moment-explain-transcription"
                >
                  <label class="moment-explain-label">Your response (editable)</label>
                  <textarea
                    v-model="explanationTranscript"
                    class="transcription-input"
                    rows="4"
                    placeholder="Edit your response…"
                  ></textarea>
                  <div class="action-row action-row--record-confirm">
                    <button
                      type="button"
                      class="btn-confirm-main"
                      :disabled="!canConfirmExplanationPhase"
                      @click="confirmExplanationPhase"
                    >
                      Confirm
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div v-else key="phase-answer" class="phase-block answer-phase">
              <div v-if="showStepSuccess" class="step-success-overlay" aria-hidden="true">
                <div class="step-success-check">
                  <i class="fa-solid fa-check"></i>
                </div>
              </div>

              <transition name="answer-card-flip" mode="out-in">
                <div v-if="currentSection" :key="`ans-${stepIndex}`" class="question-block question-block--step">
                  <div class="question-category">{{ currentSection.category }}</div>
                  <label class="question-prompt-label">
                    <template v-if="currentSectionQuestionParts && 'rest' in currentSectionQuestionParts">
                      {{ currentSectionQuestionParts.lead
                      }}<strong>{{ currentSectionQuestionParts.rest }}</strong>
                    </template>
                    <template v-else-if="currentSectionQuestionParts?.plain">{{
                      currentSectionQuestionParts.plain
                    }}</template>
                  </label>
                  <p v-if="currentSection.hint" class="question-note">{{ currentSection.hint }}</p>

                  <template v-if="isLabelQuestionStep && currentSection.labels">
                    <div
                      v-for="label in currentSection.labels"
                      :key="label.id"
                      class="label-option"
                      :class="{ selected: selectedLabelId === label.id }"
                      @click="selectLabel(label.id)"
                    >
                      <div class="radio-dot" :class="{ selected: selectedLabelId === label.id }"></div>
                      <div class="label-text">{{ label.text }}</div>
                      <div
                        v-if="label.id === 'other'"
                        class="other-inline-row"
                        @click.stop
                      >
                        <input
                          v-model="otherLabelText"
                          type="text"
                          class="other-inline-input"
                          placeholder="Please specify"
                          :disabled="selectedLabelId !== 'other'"
                        />
                        <button
                          type="button"
                          class="btn-voice-inline"
                          @click.stop="handleUpdate('other_label')"
                          :disabled="isTranscribing || !canRecordOtherLabel"
                        >
                          <span v-if="isRecording && recordingTarget === 'other_label'" class="recording-indicator">●</span>
                          <i v-else class="fa-solid fa-microphone"></i>
                        </button>
                      </div>
                    </div>

                    <div
                      v-if="isTranscribing && recordingTarget === 'other_label'"
                      class="transcribing-hint"
                    >
                      Transcribing…
                    </div>
                  </template>

                  <template v-else-if="isQ4Step">
                    <div class="q4-options">
                      <label class="radio-option">
                        <input v-model="q4Value" type="radio" value="yes" />
                        Yes
                      </label>
                      <label class="radio-option">
                        <input v-model="q4Value" type="radio" value="no" />
                        No
                      </label>
                    </div>
                    <div v-if="q4Value === 'no'" class="q4-reasons">
                      <div class="q4-reasons-hint">Select one or more reasons:</div>
                      <label v-for="r in Q4_REASONS" :key="r" class="checkbox-option">
                        <input type="checkbox" :checked="q4Reasons.includes(r)" @change="toggleQ4Reason(r)" />
                        {{ r }}
                      </label>
                    </div>
                    <div v-if="q4Value === 'no' && q4Reasons.includes(Q4_REASON_OTHER)" class="q4-other-block">
                      <label class="q4-other-label">Please specify your &quot;Other&quot; reason (type or record):</label>
                      <div class="recording-row">
                        <button
                          type="button"
                          class="btn-record"
                          @click="handleUpdate('q4_other')"
                          :disabled="isTranscribing || !canRecordQ4Other"
                          :class="{ active: canRecordQ4Other, disabled: !canRecordQ4Other }"
                        >
                          <span v-if="isRecording && recordingTarget === 'q4_other'" class="recording-indicator">●</span>
                          <i v-else class="fa-solid fa-microphone"></i>
                          {{
                            isRecording && recordingTarget === 'q4_other'
                              ? ' Recording - tap to stop'
                              : q4OtherText
                                ? ' Re-record'
                                : canRecordQ4Other
                                  ? ' Tap to record'
                                  : ' Select Other above first'
                          }}
                        </button>
                      </div>
                      <div v-if="isTranscribing && canRecordQ4Other" class="transcribing-hint">Transcribing…</div>
                      <textarea
                        v-model="q4OtherText"
                        class="transcription-input q4-other-textarea"
                        rows="2"
                        placeholder="Type your other reason here."
                      ></textarea>
                    </div>
                  </template>

                  <div class="action-row">
                    <button
                      v-if="prevAnswerForStep"
                      type="button"
                      class="btn-same"
                      @click="applySameAsLastMomentToForm"
                    >
                      Same as last moment
                    </button>
                    <button
                      type="button"
                      class="btn-confirm-main"
                      :disabled="!canConfirmCurrentStep"
                      @click="confirmCurrentStep"
                    >
                      Confirm
                    </button>
                  </div>
                </div>
              </transition>
            </div>
          </transition>
        </div>
        </template>

        <div v-else class="right-panel-preview-placeholder">
          <p class="preview-placeholder-body">
            This screenshot is not the moment you are currently annotating.
          </p>
          <button type="button" class="btn-back-annotation btn-back-annotation--block" @click="syncCarouselToCurrentMoment">
            Back to my current annotation
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
:global(html),
:global(body),
:global(#app) {
  height: 100%;
}

/* This page is full-screen; remove global app shell padding here. */
:global(#app) {
  padding: 0 !important;
}

.page-header {
  text-align: center;
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #111;
  margin: 0;
}

.page-header .session-name {
  font-size: 20px;
  font-weight: 500;
  color: #6b7280;
}

.post-annotation-page {
  color-scheme: light;
  height: 100%;
  background: #f5f5f5;
  padding: 12px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.loading-state,
.error-state,
.empty-state,
.completion-state {
  text-align: center;
  padding: 48px 24px;
  color: #666;
  max-width: 560px;
  margin: 0 auto;
}

.completion-title {
  font-size: 22px;
  font-weight: 700;
  color: #111;
  margin: 0 0 16px 0;
  line-height: 1.4;
}

.completion-body {
  font-size: 16px;
  color: #4b5563;
  margin: 0;
  line-height: 1.6;
}

.error-state .hint {
  font-size: 12px;
  color: #999;
  margin-top: 12px;
}

.annotation-layout {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;
  margin: 0 auto;
  width: 100%;
  flex: 1;
  min-height: 0;
}

@media (max-width: 900px) {
  .annotation-layout {
    grid-template-columns: 1fr;
    height: auto;
  }
}

.left-panel,
.right-panel {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.left-panel {
  overflow-y: auto;
}

.right-panel {
  overflow-y: auto;
}

.panel-title {
  font-size: 18px;
  font-weight: 600;
  color: #111;
  margin: 0 0 16px 0;
  flex-shrink: 0;
}

.time-highlight {
  color: #dc2626;
  font-weight: 700;
}

.session-replay-preview {
  width: 100%;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 8px;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.session-replay-preview__frame {
  flex: 1;
  min-width: 0;
  min-height: 340px;
  max-height: 560px;
  aspect-ratio: 16/10;
  background: #eee;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.screenshot-nav-btn {
  flex-shrink: 0;
  align-self: center;
  width: 40px;
  min-height: 44px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  color: #374151;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.screenshot-nav-btn:hover:not(:disabled) {
  background: #f3f4f6;
  border-color: #9ca3af;
}

.screenshot-nav-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.btn-back-annotation {
  font-size: 13px;
  font-weight: 600;
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid #6366f1;
  background: #eef2ff;
  color: #3730a3;
  cursor: pointer;
}

.btn-back-annotation:hover {
  background: #e0e7ff;
}

.btn-back-annotation--block {
  display: block;
  width: 100%;
  margin-top: 8px;
}

.right-panel-preview-placeholder {
  padding: 8px 0;
}

.preview-placeholder-body {
  font-size: 15px;
  color: #4b5563;
  line-height: 1.6;
  margin: 0 0 16px 0;
}

.replay-screenshot {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.replay-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
}

.log-list-header {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.log-list {
  flex: 0 0 210px;
  /* min-height: 160px;
  max-height: 260px; */
  overflow-y: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.log-item {
  display: grid;
  grid-template-columns: 48px minmax(88px, 1fr) minmax(118px, 150px) minmax(0, 2fr);
  gap: 8px;
  padding: 10px 12px;
  font-size: 13px;
  border-bottom: 1px solid #f3f4f6;
  align-items: center;
}

.log-item:last-child {
  border-bottom: none;
}

.log-item--screenshot-active {
  background: linear-gradient(90deg, #eef2ff 0%, #dbeafe 100%);
  border-left: 3px solid #4f46e5;
  box-shadow:
    0 0 0 1px rgba(99, 102, 241, 0.25),
    0 0 14px rgba(99, 102, 241, 0.35),
    0 0 28px rgba(59, 130, 246, 0.2);
  position: relative;
  z-index: 1;
}

.log-item--screenshot-active .log-type-tag {
  transform: translateY(-0.5px);
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.9) inset,
    0 6px 16px rgba(79, 70, 229, 0.18);
}

.log-item--screenshot-active .log-content {
  color: #0f172a;
  font-weight: 600;
}

.log-item--screenshot-active .log-content::before {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 99px;
  background: rgba(79, 70, 229, 0.9);
  margin-right: 8px;
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.35);
  vertical-align: middle;
}

.log-item--annotation-target:not(.log-item--screenshot-active) {
  box-shadow: inset 3px 0 0 0 #d97706;
  background: #fffbeb;
}

.log-item--partner {
  opacity: 0.92;
}

.log-item--clickable {
  cursor: pointer;
}

.log-item--clickable:hover:not(.log-item--screenshot-active) {
  background: #f9fafb;
}

.log-item--annotated:not(.log-item--screenshot-active) {
  background: #f0fdf4;
  border-left: 3px solid #22c55e;
  padding-left: 9px;
}

.log-item--annotated.log-item--clickable:hover:not(.log-item--screenshot-active) {
  background: #ecfdf5;
}

.log-annotated-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  margin-right: 6px;
  border-radius: 999px;
  background: #16a34a;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  vertical-align: middle;
}

.log-time {
  font-weight: 500;
  color: #374151;
}

.log-participant {
  color: #6b7280;
}

.log-type-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  max-width: 100%;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.tag-message {
  background: #e0e7ff;
  color: #3730a3;
  border: 1px solid #c7d2fe;
}

.tag-brush_release {
  background: #d1fae5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}

.tag-brush {
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #6ee7b7;
}

.tag-eraser {
  background: #ffedd5;
  color: #9a3412;
  border: 1px solid #fed7aa;
}

.tag-undo {
  background: #e2e8f0;
  color: #334155;
  border: 1px solid #cbd5e1;
}

.tag-reset {
  background: #ffe4e6;
  color: #9f1239;
  border: 1px solid #fecdd3;
}

.tag-default {
  background: #f3f4f6;
  color: #4b5563;
  border: 1px solid #e5e7eb;
}

.log-content {
  color: #4b5563;
  word-break: break-word;
  white-space: pre-wrap;
}

.progress-wrap {
  margin-bottom: 16px;
}

.progress-label-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
  color: #6b7280;
}

.progress-track {
  height: 6px;
  border-radius: 999px;
  background: #e5e7eb;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #6366f1;
  transition: width 0.2s ease;
}

.thoughts-box {
  background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
  border: 1px solid #dbe4ff;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.08);
  padding: 14px 16px;
  border-radius: 12px;
  margin-bottom: 20px;
  text-align: left;
}

.thoughts-box label {
  font-size: 13px;
  font-weight: 700;
  color: #4f46e5;
  display: block;
  margin-bottom: 6px;
  letter-spacing: 0.01em;
  text-align: left;
}

.thoughts-box p {
  margin: 0;
  font-size: 16px;
  line-height: 1.55;
  font-weight: 500;
  color: #1f2937;
  text-align: left;
  white-space: pre-wrap;
}

.question-block {
  margin-bottom: 20px;
}

.question-block > label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #111;
  margin-bottom: 8px;
  text-align: left;
}

.question-category {
  font-size: 11px;
  font-weight: 700;
  color: #6366f1;
  letter-spacing: 0.7px;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.question-note {
  font-size: 12px;
  color: #6b7280;
  margin: -4px 0 8px 0;
  text-align: left;
}

.label-option {
  display: flex;
  gap: 10px;
  align-items: center;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
}

.label-option.selected {
  border-color: #6366f1;
  background: #eef2ff;
}

.radio-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid #cbd5e1;
  flex-shrink: 0;
}

.radio-dot.selected {
  border-width: 5px;
  border-color: #6366f1;
}

.label-text {
  font-size: 13px;
  color: #111827;
  font-weight: 500;
}

.other-inline-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 auto;
}

.other-inline-input {
  flex: 1 1 auto;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 13px;
  line-height: 1.2;
  color: #1f2937;
  background: #fff;
}

.other-inline-input:disabled {
  background: #f3f4f6;
  color: #9ca3af;
}

.btn-voice-inline {
  width: 34px;
  height: 34px;
  border-radius: 999px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #374151;
}

.btn-voice-inline:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.recording-row {
  margin-top: 10px;
}

.btn-record {
  width: 100%;
  padding: 10px 12px;
  font-size: 13px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
}

.btn-record:hover:not(:disabled) {
  background: #f8fafc;
}

.btn-record.active {
  border-color: #6366f1;
  background: #eef2ff;
  color: #4338ca;
}

.btn-record.disabled {
  border-style: dashed;
}

.btn-record:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.transcription-box {
  margin-top: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
  background: #f8fafc;
}

.transcription-box span {
  font-size: 11px;
  color: #64748b;
  display: block;
  margin-bottom: 2px;
}

.transcription-box p {
  margin: 0;
  font-size: 13px;
  color: #334155;
}

.transcription-input {
  width: 100%;
  margin-top: 6px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  line-height: 1.45;
  resize: vertical;
  box-sizing: border-box;
  color: #1f2937;
  background: #fff;
}

.transcription-input:focus {
  outline: none;
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
}

.transcribing-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #6366f1;
  font-weight: 500;
}

.q4-options {
  display: flex;
  gap: 20px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.q4-options .radio-option {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
}

.q4-reasons {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.q4-other-block {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e5e7eb;
}

.q4-other-label {
  display: block;
  font-size: 12px;
  color: #4b5563;
  margin-bottom: 6px;
  font-weight: 500;
}

.q4-other-textarea {
  margin-top: 8px;
  min-height: 72px;
}

.q4-reasons-hint {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.q4-reasons .checkbox-option {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: #4b5563;
  cursor: pointer;
  line-height: 1.4;
}

.action-row {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}

.btn-same,
.btn-confirm-main {
  flex: 1;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  cursor: pointer;
}

.btn-same {
  background: #fff;
  color: #6b7280;
}

.btn-confirm-main {
  background: #6366f1;
  color: #fff;
  border-color: #6366f1;
}

.btn-confirm-main:disabled {
  background: #e5e7eb;
  border-color: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
}

.recording-indicator {
  color: #dc2626;
  font-weight: bold;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.annotation-workspace {
  position: relative;
  min-height: 200px;
  perspective: 1200px;
}

.phase-block {
  transform-style: preserve-3d;
}

.record-phase-instruction {
  margin: 0 0 20px 0;
  font-size: 14px;
  color: #6b7280;
  font-style: italic;
  text-align: center;
  white-space: pre-line;
  line-height: 1.5;
}

.all-questions-overview {
  text-align: left;
  margin-bottom: 16px;
}

.overview-instruction {
  margin: 0 0 10px 0;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  line-height: 1.45;
}

.overview-questions-text {
  margin: 0;
  font-size: 16px;
  color: #374151;
  line-height: 1.55;
}

.moment-explain-recording {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.record-btn-circle {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  border: none;
  background: #3b82f6;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.record-btn-circle:hover:not(:disabled) {
  background: #2563eb;
}

.record-btn-circle.recording {
  background: #ef4444;
  animation: record-pulse 1s infinite;
}

.record-btn-circle.has-recorded:hover:not(:disabled) {
  background: #2563eb;
}

.record-btn-circle:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.record-circle-icon {
  font-size: 28px;
  color: white;
}

@keyframes record-pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.85;
    transform: scale(1.05);
  }
}

.sound-wave {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 40px;
}

.wave-bar {
  width: 4px;
  height: 20px;
  background: #3b82f6;
  border-radius: 2px;
  animation: sound-wave 0.8s ease-in-out infinite;
}

.wave-bar:nth-child(1) {
  animation-delay: 0s;
}
.wave-bar:nth-child(2) {
  animation-delay: 0.1s;
}
.wave-bar:nth-child(3) {
  animation-delay: 0.2s;
}
.wave-bar:nth-child(4) {
  animation-delay: 0.3s;
}
.wave-bar:nth-child(5) {
  animation-delay: 0.4s;
}
.wave-bar:nth-child(6) {
  animation-delay: 0.5s;
}
.wave-bar:nth-child(7) {
  animation-delay: 0.4s;
}
.wave-bar:nth-child(8) {
  animation-delay: 0.3s;
}
.wave-bar:nth-child(9) {
  animation-delay: 0.2s;
}
.wave-bar:nth-child(10) {
  animation-delay: 0.1s;
}
.wave-bar:nth-child(11) {
  animation-delay: 0s;
}
.wave-bar:nth-child(12) {
  animation-delay: 0.1s;
}

@keyframes sound-wave {
  0%,
  100% {
    height: 8px;
  }
  50% {
    height: 24px;
  }
}

.moment-explain-transcription {
  width: 100%;
  margin-top: 4px;
}

.moment-explain-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 8px;
  text-align: left;
}

.action-row--record-confirm {
  margin-top: 14px;
  justify-content: flex-end;
}

.action-row--record-confirm .btn-confirm-main {
  flex: 0 0 auto;
  min-width: 120px;
}

.answer-phase {
  position: relative;
  min-height: 120px;
}

.step-success-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.94);
  border-radius: 10px;
  animation: success-fade-in 0.2s ease;
}

.step-success-check {
  font-size: 96px;
  line-height: 1;
  color: #16a34a;
  animation: success-pop 0.45s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes success-fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes success-pop {
  from {
    transform: scale(0.2);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

.phase-flip-enter-active,
.phase-flip-leave-active {
  transition:
    transform 0.5s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.35s ease;
}

.phase-flip-enter-from {
  transform: rotateY(-88deg);
  opacity: 0;
}

.phase-flip-leave-to {
  transform: rotateY(88deg);
  opacity: 0;
}

.answer-card-flip-enter-active,
.answer-card-flip-leave-active {
  transition:
    transform 0.45s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.3s ease;
}

.answer-card-flip-enter-from {
  transform: rotateY(-75deg);
  opacity: 0;
}

.answer-card-flip-leave-to {
  transform: rotateY(75deg);
  opacity: 0;
}

.question-block--step {
  padding-bottom: 4px;
}

</style>
