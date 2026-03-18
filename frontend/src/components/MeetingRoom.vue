<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { getSocket } from '../services/websocket.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  participantId: { type: String, required: true },
  participantsList: { type: Array, default: () => [] }
})

const localStream = ref(null)
const localVideoRef = ref(null)
const remoteStreams = ref({}) // participantId -> MediaStream
const isJoined = ref(false)
const isConnecting = ref(false)
const peers = ref({}) // participantId -> RTCPeerConnection
const meetingParticipants = ref([]) // participants currently in meeting

// Controls state
const isMuted = ref(false)
const isCameraOff = ref(false)
const audioDevices = ref([])
const videoDevices = ref([])
const selectedAudioId = ref('')
const selectedVideoId = ref('')
const showAudioSetting = ref(false)
const showCameraSetting = ref(false)
const audioTriggerRef = ref(null)
const videoTriggerRef = ref(null)
const audioDropdownStyle = ref({})
const videoDropdownStyle = ref({})

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
watch(showCameraSetting, (show) => {
  if (show) updateDropdownPosition(videoTriggerRef, videoDropdownStyle)
})

const otherParticipants = computed(() => {
  return (props.participantsList || []).filter(p => {
    const id = p?.id || p?.participant_id
    return id && id !== props.participantId
  })
})

const getLocalMedia = async (audioId = null, videoId = null) => {
  const constraints = {
    audio: audioId ? { deviceId: { exact: audioId } } : true,
    video: videoId ? { deviceId: { exact: videoId } } : true
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
  audioDevices.value = devices.filter(d => d.kind === 'audioinput')
  videoDevices.value = devices.filter(d => d.kind === 'videoinput')
  if (audioDevices.value.length > 0 && !selectedAudioId.value) {
    selectedAudioId.value = audioDevices.value[0].deviceId
  }
  if (videoDevices.value.length > 0 && !selectedVideoId.value) {
    selectedVideoId.value = videoDevices.value[0].deviceId
  }
}

const toggleMute = () => {
  if (!localStream.value) return
  const audioTrack = localStream.value.getAudioTracks()[0]
  if (audioTrack) {
    audioTrack.enabled = !audioTrack.enabled
    isMuted.value = !audioTrack.enabled
  }
}

const toggleCamera = () => {
  if (!localStream.value) return
  const videoTrack = localStream.value.getVideoTracks()[0]
  if (videoTrack) {
    videoTrack.enabled = !videoTrack.enabled
    isCameraOff.value = !videoTrack.enabled
  }
}

const replaceTrackInPeers = async (kind, newTrack) => {
  for (const [pid, pc] of Object.entries(peers.value)) {
    const sender = pc.getSenders().find(s => s.track?.kind === kind)
    if (sender && newTrack) {
      await sender.replaceTrack(newTrack)
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
    showAudioSetting.value = false
  } catch (err) {
    console.error('[MeetingRoom] Switch audio error:', err)
    alert('Failed to switch microphone: ' + (err.message || ''))
  }
}

const switchVideoDevice = async (deviceId) => {
  if (!localStream.value || !deviceId) return
  try {
    const newStream = await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: deviceId } } })
    const newTrack = newStream.getVideoTracks()[0]
    const oldTrack = localStream.value.getVideoTracks()[0]
    if (oldTrack) {
      localStream.value.removeTrack(oldTrack)
      oldTrack.stop()
    }
    newTrack.enabled = !isCameraOff.value
    localStream.value.addTrack(newTrack)
    selectedVideoId.value = deviceId
    await replaceTrackInPeers('video', newTrack)
    showCameraSetting.value = false
  } catch (err) {
    console.error('[MeetingRoom] Switch video error:', err)
    alert('Failed to switch camera: ' + (err.message || ''))
  }
}

// Assign local stream to video element when both are available (element mounts after isJoined=true)
watch([localStream, localVideoRef], ([stream, el]) => {
  if (stream && el) {
    el.srcObject = stream
  }
}, { immediate: true })

const createPeerConnection = (participantId) => {
  const pc = new RTCPeerConnection({
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
  })
  if (localStream.value) {
    localStream.value.getTracks().forEach(track => pc.addTrack(track, localStream.value))
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
  }
  pc.onconnectionstatechange = () => {
    if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
      delete peers.value[participantId]
      remoteStreams.value = { ...remoteStreams.value }
      delete remoteStreams.value[participantId]
    }
  }
  return pc
}

const joinMeeting = async () => {
  if (isJoined.value || isConnecting.value) return
  isConnecting.value = true
  try {
    await getLocalMedia()
    await enumerateDevices()
    isMuted.value = false
    isCameraOff.value = false
    getSocket().emit('meeting_join', {
      session_id: props.sessionId,
      participant_id: props.participantId
    })
    isJoined.value = true
  } catch (err) {
    alert('Could not access camera/microphone. ' + (err.message || ''))
  } finally {
    isConnecting.value = false
  }
}

const leaveMeeting = () => {
  localStream.value?.getTracks().forEach(t => t.stop())
  localStream.value = null
  Object.values(peers.value).forEach(pc => pc.close())
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

onMounted(() => {
  const ws = getSocket()
  offPeerJoined = (data) => handleMeetingPeerJoined(data)
  offSignal = (data) => handleMeetingSignal(data)
  ws.on('meeting_peer_joined', offPeerJoined)
  ws.on('meeting_signal', offSignal)
})

onUnmounted(() => {
  leaveMeeting()
  const ws = getSocket()
  if (offPeerJoined) ws.off('meeting_peer_joined', offPeerJoined)
  if (offSignal) ws.off('meeting_signal', offSignal)
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
    <div v-if="isJoined" class="meeting-videos">
      <div class="video-tile local">
        <video ref="localVideoRef" autoplay muted playsinline></video>
        <span class="label">You</span>
      </div>
      <div v-for="(stream, pid) in remoteStreams" :key="pid" class="video-tile remote">
        <video :ref="el => { if (el) el.srcObject = stream }" autoplay playsinline></video>
        <span class="label">{{ otherParticipants.find(p => (p?.id || p?.participant_id) === pid)?.name || pid }}</span>
      </div>
    </div>
    <div v-if="isJoined" class="meeting-controls">
      <!-- Audio: button toggles mute/unmute, dropdown switches device -->
      <div class="control-group">
        <button type="button" :class="['control-btn', { active: isMuted }]" @click="toggleMute" :title="isMuted ? 'Unmute' : 'Mute'">
          <i :class="isMuted ? 'fa-solid fa-microphone-slash' : 'fa-solid fa-microphone'"></i> {{ isMuted ? 'Unmute' : 'Mute' }}
        </button>
        <div class="control-dropdown">
          <button ref="audioTriggerRef" type="button" class="dropdown-trigger" @click="showAudioSetting = !showAudioSetting; showCameraSetting = false" title="Switch audio device">
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
      <!-- Video: button toggles camera on/off, dropdown switches device -->
      <div class="control-group">
        <button type="button" :class="['control-btn', { active: isCameraOff }]" @click="toggleCamera" :title="isCameraOff ? 'Turn on camera' : 'Turn off camera'">
          <i :class="isCameraOff ? 'fa-solid fa-video-slash' : 'fa-solid fa-video'"></i> {{ isCameraOff ? 'Start Video' : 'Stop Video' }}
        </button>
        <div class="control-dropdown">
          <button ref="videoTriggerRef" type="button" class="dropdown-trigger" @click="showCameraSetting = !showCameraSetting; showAudioSetting = false" title="Switch video device">
            <i class="fa-solid fa-chevron-down"></i>
          </button>
          <Teleport to="body">
            <div v-if="showCameraSetting" class="dropdown-menu dropdown-menu-portal" :style="videoDropdownStyle">
              <div v-for="d in videoDevices" :key="d.deviceId" class="dropdown-item" :class="{ selected: selectedVideoId === d.deviceId }" @click="switchVideoDevice(d.deviceId)">
                {{ d.label || `Camera ${videoDevices.indexOf(d) + 1}` }}
              </div>
            </div>
          </Teleport>
        </div>
      </div>
    </div>
    <div v-else-if="!isConnecting" class="meeting-placeholder">
      <p>Click "Join Meeting" to start video/audio chat with other participants</p>
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
.meeting-videos {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.video-tile {
  position: relative;
  width: 160px;
  height: 120px;
  background: #1f2937;
  border-radius: 6px;
  overflow: hidden;
}
.video-tile video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.video-tile .label {
  position: absolute;
  bottom: 4px;
  left: 4px;
  font-size: 10px;
  color: white;
  background: rgba(0,0,0,0.5);
  padding: 2px 6px;
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
