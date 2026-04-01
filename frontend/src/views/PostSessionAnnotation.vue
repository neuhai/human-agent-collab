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
const savedAnnotationAssetUrls = ref({})
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
    category: 'Grounding State',
    question: 'At this moment, what do you think you and your partner are trying to do together?',
    labels: [
      { id: 'g1', text: 'We are building a shared understanding' },
      { id: 'g2', text: 'We are deciding on the next step together' },
      { id: 'g3', text: 'We are checking that we understood each other' },
      { id: 'g4', text: 'We are resolving a misunderstanding' },
      { id: 'g5', text: 'I am not sure what we are trying to do right now' },
      { id: 'other', text: 'Other' },
    ],
  },
  {
    id: 'q2',
    category: 'Perceived Partner State',
    question: "At this moment, what was your impression of your partner's understanding?",
    hint: 'This is about your impression, not what they were actually thinking.',
    labels: [
      { id: 'p1', text: "I'm confident they understood as their action shows" },
      { id: 'p2', text: "I'm concerned they misunderstood as their action shows" },
      { id: 'p3', text: "I'm sensing they are unsure as they are hesitating" },
      { id: 'p4', text: "I'm unable to tell what they are thinking right now" },
      { id: 'other', text: 'Other' },
    ],
  },
  {
    id: 'q3',
    category: 'Self-Reasoning',
    question: 'What was the main reason behind your action at this moment?',
    labels: [
      { id: 'r1', text: "I'm moving forward as we have shared understanding" },
      { id: 'r2', text: "I'm clarifying as there is a gap in our shared understanding" },
      { id: 'r3', text: "I'm repairing as I noticed a mistake" },
      { id: 'r4', text: "I'm verifying as I want to make sure we are aligned" },
      { id: 'other', text: 'Other' },
    ],
  },
  {
    id: 'q4',
    category: 'Alignment',
    question: 'Do you think you and your partner are on the same page?',
    kind: 'yes_no_reasons',
  },
]

const Q4_REASON_OTHER = 'Other'

const Q4_REASONS = [
  'Goal misunderstanding',
  'Unclear communication',
  'Poor coordination',
  'Unexpected actions / errors',
  'Low trust in partner',
  'Interface / context issues',
  Q4_REASON_OTHER,
]

const stepIndex = ref(0)
const currentSection = computed(() => SECTIONS[stepIndex.value] || null)

const annotations = ref({})
const selectedLabelId = ref('')
const transcriptText = ref('')
/** After at least one successful record+transcribe on this step; also true when reloading saved transcript */
const transcriptUiShown = ref(false)
const q4Value = ref(null)
const q4Reasons = ref([])
/** Free text when Q4 "Other" reason is selected */
const q4OtherText = ref('')
const showSameAsLastConfirm = ref(false)

const isQ4Step = computed(() => currentSection.value?.kind === 'yes_no_reasons')
const isLabelQuestionStep = computed(
  () => !!currentSection.value && currentSection.value.kind !== 'yes_no_reasons',
)

const currentProgressPct = computed(() => {
  const total = annotationMoments.value.length * SECTIONS.length
  if (!total) return 0
  return ((currentMomentIndex.value * SECTIONS.length + stepIndex.value + 1) / total) * 100
})

const visibleMergedLogs = computed(() => {
  if (!Array.isArray(mergedLogs.value)) return []
  if (!sessionStartTime.value || !sessionDurationSeconds.value || sessionDurationSeconds.value <= 0) {
    return mergedLogs.value
  }
  const startMs = sessionStartTime.value.getTime()
  const maxMs = startMs + sessionDurationSeconds.value * 1000
  return mergedLogs.value.filter((entry) => {
    const ts = new Date(entry.timestamp).getTime()
    return Number.isFinite(ts) && ts >= startMs && ts <= maxMs
  })
})

/** Post-session UI: for maptask, show only message + key map actions (full data still in DB / merged_logs). */
function isMaptaskPostAnnotationLogEntry(entry) {
  const t = entry?.action_type
  const c = String(entry?.action_content || '').trim()
  if (t === 'send_message') return true
  if (t === 'map_tool_click' && ['eraser', 'undo', 'reset'].includes(c)) return true
  if (t === 'map_draw_stop' && c === 'brush_release') return true
  return false
}

const displayMergedLogs = computed(() => {
  const rows = visibleMergedLogs.value
  const exp = (experimentType.value || '').toLowerCase()
  if (exp === 'maptask') {
    return rows.filter(isMaptaskPostAnnotationLogEntry)
  }
  return rows
})

/** Stable key for tag styling + i18n-style labels in the interaction log */
const ACTION_TAG_LABELS = {
  message: 'Send message',
  brush_release: 'Draw route',
  eraser: 'Erase route',
  undo: 'Undo last action',
  reset: 'Reset map',
}

function getPostAnnotationActionKind(entry) {
  if (entry?.action_type === 'send_message') return 'message'
  if (entry?.action_type === 'map_draw_stop') return String(entry.action_content || '').trim() || 'map_draw_stop'
  if (entry?.action_type === 'map_tool_click') return String(entry.action_content || '').trim() || 'map_tool_click'
  return entry?.action_type || 'action'
}

function getActionTagKey(entry) {
  const t = entry?.action_type
  const c = String(entry?.action_content || '').trim()
  if (t === 'send_message') return 'message'
  if (t === 'map_draw_stop' && c === 'brush_release') return 'brush_release'
  if (t === 'map_tool_click') {
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

function formatTime(ts) {
  if (!ts) return '00:00'
  try {
    const d = new Date(ts)
    if (sessionStartTime.value) {
      const diff = d.getTime() - sessionStartTime.value.getTime()
      if (diff < 0) return '00:00'
      const totalSeconds = Math.floor(diff / 1000)
      const m = Math.floor(totalSeconds / 60)
      const s = totalSeconds % 60
      return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    }
    const m = d.getMinutes()
    const s = d.getSeconds()
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  } catch {
    return '00:00'
  }
}

function getDisplayName(entry, isYou = false) {
  const pid = entry.participant_id
  const name = entry.participant_name || participantNames.value[pid] || pid?.slice(0, 8) || 'Unknown'
  return isYou ? `${name} (you)` : name
}

const screenshotUrl = computed(() => {
  const m = currentMoment.value
  if (!m) return null
  const aid = m.action_id
  const apiUrls = savedAnnotationAssetUrls.value[aid]
  if (apiUrls?.screenshot_s3) return apiUrls.screenshot_s3
  const saved = annotations.value[aid]
  if (saved?.screenshot_s3?.startsWith('http')) return saved.screenshot_s3
  const s = m.screenshot
  if (!s) return null
  if (s.startsWith('http://') || s.startsWith('https://')) return s
  if (!filesBase.value) return null
  const filename = s.startsWith('files/') ? s.slice(6) : s
  return `${filesBase.value}/${filename}`
})

function bucketIndexFromProgressPct(pct) {
  if (pct < 33) return 0
  if (pct <= 66) return 1
  return 2
}

const selectedInSessionThought = computed(() => {
  const m = currentMoment.value
  const ann = inSessionAnnotations.value || []
  if (!m?.timestamp || !sessionStartTime.value) {
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
  const actionTime = new Date(m.timestamp).getTime()
  const start = sessionStartTime.value.getTime()
  const elapsedSec = (actionTime - start) / 1000
  const pct = elapsedSec < 0 ? 0 : (elapsedSec / dur) * 100
  const bucket = bucketIndexFromProgressPct(pct)
  const list = [...ann].sort((a, b) => (Number(a.checkpoint_index) || 0) - (Number(b.checkpoint_index) || 0))
  const match = list.find((x) => Number(x.checkpoint_index) === bucket)
  if (!match?.transcription?.trim()) {
    return { transcription: '(No in-session annotation recorded for this period.)', timeLabel: '—' }
  }
  const timeLabel = match.created_at ? formatTime(match.created_at) : '—'
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
    transcript: prev[`${sec.id}Transcript`] || '',
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
  return !!selectedLabelId.value && !!transcriptText.value.trim()
})

const canRecordExplanation = computed(() => !!selectedLabelId.value && selectedLabelId.value !== 'other')
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
    selectedLabelId.value = labelId
    if (labelId !== 'other') {
      transcriptText.value = ''
      transcriptUiShown.value = false
    } else {
      transcriptUiShown.value = false
    }
  } else {
    selectedLabelId.value = labelId
  }
}

function loadStepStateFromSaved() {
  const m = currentMoment.value
  const sec = currentSection.value
  if (!m || !sec) return
  const saved = annotations.value[m.action_id] || {}
  if (sec.kind === 'yes_no_reasons') {
    q4Value.value = saved.q4 === 'yes' || saved.q4 === 'no' ? saved.q4 : null
    q4Reasons.value = Array.isArray(saved.q4Reasons) ? [...saved.q4Reasons] : []
    q4OtherText.value = typeof saved.q4OtherText === 'string' ? saved.q4OtherText : ''
    return
  }
  const savedLabelId = saved[`${sec.id}LabelId`] || ''
  const savedText = (saved[sec.id] || '').trim()
  selectedLabelId.value = savedLabelId
  transcriptText.value = saved[`${sec.id}Transcript`] || ''
  transcriptUiShown.value = !!transcriptText.value.trim() && savedLabelId !== 'other'
  if (!selectedLabelId.value && savedText && sec.labels) {
    const byText = sec.labels.find((x) => x.text === savedText)
    if (byText) selectedLabelId.value = byText.id
  }
}

function loadCurrentMomentState() {
  const m = currentMoment.value
  if (!m) return
  if (!annotations.value[m.action_id]) {
    annotations.value[m.action_id] = {}
  }
  stepIndex.value = 0
  selectedLabelId.value = ''
  transcriptText.value = ''
  transcriptUiShown.value = false
  q4Value.value = null
  q4Reasons.value = []
  q4OtherText.value = ''
  showSameAsLastConfirm.value = false
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
  annotations.value[m.action_id] = {
    ...prev,
    [sec.id]: labelText,
    [`${sec.id}LabelId`]: selectedLabelId.value,
    [`${sec.id}Transcript`]: transcriptText.value.trim(),
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
  annotationFinished.value = true
}

async function confirmCurrentStep() {
  if (!canConfirmCurrentStep.value) return
  saveCurrentStepAnnotation()
  const ok = await saveAnnotationsToFile()
  if (!ok) return
  moveToNextStepOrMoment()
}

function requestSameAsLastMoment() {
  showSameAsLastConfirm.value = true
}

async function applySameAsLastMoment() {
  const prev = prevAnswerForStep.value
  const sec = currentSection.value
  const m = currentMoment.value
  if (!prev || !sec || !m) {
    showSameAsLastConfirm.value = false
    return
  }
  const prevSaved = annotations.value[m.action_id] || {}
  if (sec.kind === 'yes_no_reasons' && prev.isQ4) {
    annotations.value[m.action_id] = {
      ...prevSaved,
      q4: prev.text === 'Yes' ? 'yes' : 'no',
      q4Reasons: [...(prev.q4Reasons || [])],
      q4OtherText: prev.q4OtherText || '',
    }
    q4Value.value = annotations.value[m.action_id].q4
    q4Reasons.value = [...(annotations.value[m.action_id].q4Reasons || [])]
    q4OtherText.value = annotations.value[m.action_id].q4OtherText || ''
  } else {
    annotations.value[m.action_id] = {
      ...prevSaved,
      [sec.id]: prev.text,
      [`${sec.id}LabelId`]: prev.labelId,
      [`${sec.id}Transcript`]: prev.transcript,
    }
    selectedLabelId.value = prev.labelId || ''
    transcriptText.value = prev.transcript || ''
    transcriptUiShown.value = !!transcriptText.value.trim()
  }
  showSameAsLastConfirm.value = false
  const ok = await saveAnnotationsToFile()
  if (!ok) return
  moveToNextStepOrMoment()
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
      savedAnnotationAssetUrls.value = data.saved_annotation_asset_urls || {}
      inSessionAnnotations.value = data.in_session_annotations || []
      sessionDurationSeconds.value =
        data.session_duration_seconds != null && data.session_duration_seconds !== ''
          ? Number(data.session_duration_seconds)
          : null
      if (data.saved_annotations && typeof data.saved_annotations === 'object') {
        annotations.value = { ...data.saved_annotations }
      }
      if (data.session_started_at) {
        sessionStartTime.value = new Date(data.session_started_at)
      } else if (mergedLogs.value.length > 0 && mergedLogs.value[0].timestamp) {
        sessionStartTime.value = new Date(mergedLogs.value[0].timestamp)
      } else {
        sessionStartTime.value = null
      }
      currentMomentIndex.value = 0
      stepIndex.value = 0
      annotationFinished.value = false
      loadCurrentMomentState()
    })
    .catch((err) => {
      error.value = err.message || 'Failed to load annotation data'
    })
    .finally(() => {
      loading.value = false
    })
}

async function fetchPostAnnotationPresign(actionId, asset, contentType) {
  const encSid = encodeURIComponent(sessionId.value)
  const encPid = encodeURIComponent(participantId.value)
  const res = await fetch(`/api/sessions/${encSid}/participants/${encPid}/post_annotation_presign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action_id: actionId, asset, content_type: contentType }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'presign failed')
  return data
}

async function uploadCurrentMomentScreenshotToS3IfNeeded() {
  const m = currentMoment.value
  if (!m?.action_id) return
  const aid = m.action_id
  const row = annotations.value[aid]
  if (row?.screenshot_s3) return

  let pres
  try {
    pres = await fetchPostAnnotationPresign(aid, 'screenshot', 'image/jpeg')
  } catch (e) {
    console.warn('[PostAnnotation] presign screenshot skipped:', e)
    return
  }
  if (!pres?.upload_url) return

  const img = document.querySelector('.replay-screenshot')
  if (img && img.complete && img.naturalWidth) {
    try {
      const canvas = document.createElement('canvas')
      canvas.width = img.naturalWidth
      canvas.height = img.naturalHeight
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0)
      const blob = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', 0.88))
      if (blob) {
        const put = await fetch(pres.upload_url, {
          method: 'PUT',
          body: blob,
          headers: { 'Content-Type': 'image/jpeg' },
        })
        if (!put.ok) throw new Error('S3 PUT failed')
        const prev = annotations.value[aid] || {}
        annotations.value[aid] = { ...prev, screenshot_s3: pres.s3_uri }
        if (pres.view_url) {
          savedAnnotationAssetUrls.value = {
            ...savedAnnotationAssetUrls.value,
            [aid]: { ...(savedAnnotationAssetUrls.value[aid] || {}), screenshot_s3: pres.view_url },
          }
        }
        return
      }
    } catch (e) {
      console.warn('[PostAnnotation] canvas from replay img failed:', e)
    }
  }

  try {
    const html2canvas = (await import('html2canvas')).default
    const el = document.getElementById('app') || document.body
    const canvas = await html2canvas(el, { useCORS: true, allowTaint: true, scale: 1, logging: false })
    const blob = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', 0.88))
    if (!blob) return
    const put = await fetch(pres.upload_url, {
      method: 'PUT',
      body: blob,
      headers: { 'Content-Type': 'image/jpeg' },
    })
    if (!put.ok) throw new Error('S3 PUT failed')
    const prev = annotations.value[aid] || {}
    annotations.value[aid] = { ...prev, screenshot_s3: pres.s3_uri }
    if (pres.view_url) {
      savedAnnotationAssetUrls.value = {
        ...savedAnnotationAssetUrls.value,
        [aid]: { ...(savedAnnotationAssetUrls.value[aid] || {}), screenshot_s3: pres.view_url },
      }
    }
  } catch (e) {
    console.warn('[PostAnnotation] html2canvas fallback failed:', e)
  }
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
        body: JSON.stringify({ annotations: annotations.value }),
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

async function prevMoment() {
  saveCurrentStepAnnotation()
  const ok = await saveAnnotationsToFile()
  if (!ok) return
  if (currentMomentIndex.value > 0) {
    currentMomentIndex.value--
    stepIndex.value = 0
  }
}

function isMomentAnnotationComplete(saved) {
  for (const s of SECTIONS) {
    if (s.kind === 'yes_no_reasons') {
      if (!saved.q4 || (saved.q4 !== 'yes' && saved.q4 !== 'no')) return false
      if (saved.q4 === 'no' && !(saved.q4Reasons || []).length) return false
      const reasons = saved.q4Reasons || []
      if (saved.q4 === 'no' && reasons.includes(Q4_REASON_OTHER) && !(saved.q4OtherText || '').trim()) {
        return false
      }
    } else {
      const label = (saved[`${s.id}LabelId`] || '').trim()
      const transcript = (saved[`${s.id}Transcript`] || '').trim()
      if (!label || !transcript) return false
    }
  }
  return true
}

async function nextMoment() {
  const m = currentMoment.value
  if (!m) return
  const saved = annotations.value[m.action_id] || {}
  if (!isMomentAnnotationComplete(saved)) {
    alert('Please complete all questions for this moment before moving to next.')
    return
  }
  const ok = await saveAnnotationsToFile()
  if (!ok) return
  if (currentMomentIndex.value < annotationMoments.value.length - 1) {
    currentMomentIndex.value++
    stepIndex.value = 0
  } else {
    annotationFinished.value = true
  }
}

async function toggleRecording(target) {
  if (isTranscribing.value) return
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
          transcriptText.value = text
        } else if (target === currentSection.value?.id) {
          transcriptText.value = text
          transcriptUiShown.value = true
        }
      } catch (err) {
        console.error('[PostAnnotation] Transcribe error:', err)
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

onMounted(() => {
  if (route.query.session_id) sessionId.value = route.query.session_id
  if (route.query.participant_id) participantId.value = route.query.participant_id
  loadData()
  uploadCurrentMomentScreenshotToS3IfNeeded().catch(() => {})
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
          You are revisiting your action at
          <span class="time-highlight">{{ currentMoment ? formatTime(currentMoment.timestamp) : '00:00' }}</span>
        </h2>

        <div class="session-replay-preview">
          <img
            v-if="screenshotUrl"
            :src="screenshotUrl"
            alt="Session replay at action time"
            class="replay-screenshot"
          />
          <div v-else class="replay-placeholder">No screenshot</div>
        </div>

        <div class="log-list-header">Interaction Log</div>
        <div class="log-list">
          <div
            v-for="entry in displayMergedLogs"
            :key="entry.action_id"
            class="log-item"
            :class="{ highlighted: currentMoment && entry.action_id === currentMoment.action_id }"
          >
            <span class="log-time">{{ formatTime(entry.timestamp) }}</span>
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
        <h2 class="panel-title">
          You are annotating your action at
          <span class="time-highlight">{{ currentMoment ? formatTime(currentMoment.timestamp) : '00:00' }}</span>
        </h2>

        <div class="progress-wrap">
          <div class="progress-label-row">
            <span>Moment {{ currentMomentIndex + 1 }} / {{ annotationMoments.length }}</span>
            <span>Question {{ stepIndex + 1 }} / {{ SECTIONS.length }}</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" :style="{ width: `${currentProgressPct}%` }"></div>
          </div>
        </div>

        <div class="thoughts-box">
          <label>{{ inGameThoughtsDisplayLabel }}</label>
          <p>{{ selectedInSessionThought.transcription || '(No thoughts recorded)' }}</p>
        </div>

        <div v-if="currentSection" class="question-block">
          <div class="question-category">{{ currentSection.category }}</div>
          <label>{{ currentSection.question }}</label>
          <p v-if="currentSection.hint" class="question-note">{{ currentSection.hint }}</p>

          <div v-if="prevAnswerForStep" class="previous-answer-panel">
            <div class="previous-title">Last moment annotation</div>
            <div class="previous-label">{{ prevAnswerForStep.text }}</div>
            <div
              v-if="prevAnswerForStep.isQ4 && prevAnswerForStep.q4Reasons?.length"
              class="previous-transcript"
            >
              <span>Reasons</span>
              <p>{{ prevAnswerForStep.q4Reasons.join('; ') }}</p>
            </div>
            <div
              v-if="prevAnswerForStep.isQ4 && prevAnswerForStep.q4OtherText"
              class="previous-transcript"
            >
              <span>Other (specified)</span>
              <p>{{ prevAnswerForStep.q4OtherText }}</p>
            </div>
            <div
              v-if="!prevAnswerForStep.isQ4 && prevAnswerForStep.transcript"
              class="previous-transcript"
            >
              <span>Transcription</span>
              <p>{{ prevAnswerForStep.transcript }}</p>
            </div>
          </div>

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
                  v-model="transcriptText"
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

            <div v-if="selectedLabelId !== 'other'" class="recording-row">
              <button
                type="button"
                class="btn-record"
                @click="handleUpdate(currentSection.id)"
                :disabled="isTranscribing || !canRecordExplanation"
                :class="{ active: canRecordExplanation, disabled: !canRecordExplanation }"
              >
                <span v-if="isRecording && recordingTarget === currentSection.id" class="recording-indicator">●</span>
                <i v-else class="fa-solid fa-microphone"></i>
                {{
                  isRecording && recordingTarget === currentSection.id
                    ? ' Recording - tap to stop'
                    : transcriptText
                      ? ' Re-record explanation'
                      : (canRecordExplanation ? ' Tap to record explanation' : ' Select a label first')
                }}
              </button>
            </div>

            <div v-if="isTranscribing && canRecordExplanation" class="transcribing-hint">
              Transcribing…
            </div>

            <div v-if="isTranscribing && canRecordOtherLabel" class="transcribing-hint">
              Transcribing…
            </div>

            <div v-if="transcriptUiShown" class="transcription-box">
              <span>Transcription (editable)</span>
              <textarea
                v-model="transcriptText"
                class="transcription-input"
                rows="4"
                placeholder="Edit your transcription if needed."
              ></textarea>
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
                rows="3"
                placeholder="Type your other reason here."
              ></textarea>
            </div>
          </template>

          <div class="action-row">
            <button
              v-if="prevAnswerForStep"
              type="button"
              class="btn-same"
              @click="requestSameAsLastMoment"
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

        <div class="nav-footer">
          <button
            type="button"
            class="btn-prev"
            :disabled="currentMomentIndex <= 0"
            @click="prevMoment"
          >
            Prev
          </button>
          <button
            type="button"
            class="btn-next"
            @click="nextMoment"
          >
            Skip to next moment
          </button>
        </div>
      </div>
    </div>

    <div v-if="showSameAsLastConfirm" class="confirm-overlay" @click.self="showSameAsLastConfirm = false">
      <div class="confirm-modal">
        <h3>Confirm "Same as last moment"</h3>
        <p>This will copy your answers from the previous moment for this question (including labels, transcription, or Yes/No and reasons).</p>
        <div class="confirm-actions">
          <button type="button" class="btn-cancel" @click="showSameAsLastConfirm = false">Cancel</button>
          <button type="button" class="btn-apply" @click="applySameAsLastMoment">Confirm</button>
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
  grid-template-columns: 1.5fr 1fr;
  gap: 24px;
  max-width: 1400px;
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
  padding: 24px;
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
  max-height: 400px;
  aspect-ratio: 16/10;
  background: #eee;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 16px;
  flex-shrink: 0;
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
  flex: 1;
  min-height: 200px;
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

.log-item.highlighted {
  background: linear-gradient(90deg, #eef2ff 0%, #dbeafe 100%);
  border-left: 3px solid #4f46e5;
  box-shadow:
    0 0 0 1px rgba(99, 102, 241, 0.25),
    0 0 14px rgba(99, 102, 241, 0.35),
    0 0 28px rgba(59, 130, 246, 0.2);
  position: relative;
  z-index: 1;
}

/* Make the key information pop on the highlighted row */
.log-item.highlighted .log-type-tag {
  transform: translateY(-0.5px);
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.9) inset,
    0 6px 16px rgba(79, 70, 229, 0.18);
}

.log-item.highlighted .log-content {
  color: #0f172a;
  font-weight: 600;
}

.log-item.highlighted .log-content::before {
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

.previous-answer-panel {
  border: 1px dashed #c7d2fe;
  border-radius: 10px;
  background: #eef2ff;
  padding: 10px 12px;
  margin-bottom: 10px;
}

.previous-title {
  font-size: 11px;
  color: #4f46e5;
  font-weight: 700;
  margin-bottom: 6px;
}

.previous-label {
  font-size: 13px;
  color: #1f2937;
  font-weight: 600;
}

.previous-transcript {
  margin-top: 8px;
}

.previous-transcript span {
  font-size: 11px;
  color: #64748b;
  display: block;
  margin-bottom: 2px;
}

.previous-transcript p {
  margin: 0;
  font-size: 12px;
  color: #334155;
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
  min-height: 84px;
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

.nav-footer {
  margin-top: 24px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.btn-prev,
.btn-next {
  padding: 12px 24px;
  font-size: 14px;
  font-weight: 500;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.btn-prev {
  background: #e5e7eb;
  color: #374151;
}

.btn-prev:hover:not(:disabled) {
  background: #d1d5db;
}

.btn-prev:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-next {
  background: #6b7280;
  color: white;
}

.btn-next:hover {
  background: #4b5563;
}

.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 30;
}

.confirm-modal {
  width: min(92vw, 430px);
  background: #fff;
  border-radius: 12px;
  padding: 18px;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18);
}

.confirm-modal h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  color: #111827;
}

.confirm-modal p {
  margin: 0;
  font-size: 14px;
  color: #4b5563;
  line-height: 1.5;
}

.confirm-actions {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn-cancel,
.btn-apply {
  padding: 9px 12px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  cursor: pointer;
}

.btn-cancel {
  background: #fff;
  color: #374151;
}

.btn-apply {
  background: #6366f1;
  border-color: #6366f1;
  color: #fff;
}
</style>
