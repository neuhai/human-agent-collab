<script setup>
import { ref, computed, provide, watch, onMounted, onUnmounted } from 'vue'
import Setup from '../components/setup.vue'
import Monitor from '../components/monitor.vue'
import Analysis from '../components/analysis.vue'
import { joinSession, leaveSession, onMessageReceived, offMessageReceived, onParticipantsUpdate, offParticipantsUpdate, onTypingIndicator, getSocket } from '../services/websocket.js'

// Experiments configuration - loaded from backend API (single source of truth)
// Fallback used only if API fails; backend experiments.py is the source of truth
const FALLBACK_EXPERIMENTS = [
    { 
        id: 'shapefactory', 
        name: 'Shape Factory', 
        tags: ['Coordination', 'Trade'], 
        description: '**Procedures**: Each participant can produce shapes, buy&sell shapes, and chat with others. Each one is assigned a specialty shape that can be cheaply produced.\n\n**Constraints**: shape production limit; time limit.\n\n**Goal**: Maximize individual profit.',
        params: [
            {
                "General Settings": [{label: "Session Duration (min)", type: "number", default: 30, path: 'Session.Params.duration'}],
                "Money": [
                    {label: "Participant Initial Money ($)", type: "number", default: 200, path: 'Session.Params.startingMoney'},
                    {label: "Regular Shape Production Cost ($)", type: "number", default: 40, path: 'Session.Params.regularCost'},
                    {label: "Specialty Production Cost ($)", type: "number", default: 15, path: 'Session.Params.specialtyCost'},
                    {label: "Min. Trade Price ($)", type: "number", default: 15, path: 'Session.Params.minTradePrice'},
                    {label: "Max. Trade Price ($)", type: "number", default: 100, path: 'Session.Params.maxTradePrice'},
                    {label: "Order Incentive ($/shape fulfilled)", type: "number", default: 60, path: 'Session.Params.incentiveMoney'}
                ],
                "Shape Production & Order": [
                    {label: "Production Time (sec)", type: "number", default: 30, path: 'Session.Params.productionTime', description: "Time required to produce one shape."},
                    {label: "# Max. Production", type: "number", default: 3, path: 'Session.Params.maxProductionNum', description: "Maximum total number of shapes a participant can produce (specialty and non-specialty combined)."},
                    {label: "# Shapes Order", type: "number", default: 4, path: 'Session.Params.shapesOrder', description: "Number of shapes required to complete one order."},
                    {label: "# Shapes Types", type: "number", default: 3, path: 'Session.Params.shapesTypes', description: "Number of distinct shape categories in the game."}
                ]
            }
        ],
        interaction: {
            "Information Flow": [
                {label: "Communication Level", type: "list", default: "Private Messaging", options: [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], path: 'Session.Interaction.communicationLevel', description: "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {label: "Communication Media", type: "multi_checkbox", default: ["text"], options: [{label: "Text Message", value: "text", description: "Participants type messages"}, {label: "Audio", value: "audio", description: "Voice input with Whisper transcription"}, {label: "Meeting Room", value: "meeting_room", description: "Real-time video/audio like Zoom"}], path: 'Session.Interaction.communicationMedia', description: "Select which communication media to enable."},
                {
                  label: "Awareness Dashboard",
                  type: "tiered_checkbox", // 分层的选择
                  default: {
                    enabled: true, // 一级开关，是否启用 Dashboard
                    items: [0, 1]       // 二级数组，哪些信息项被勾选显示 (默认选中 Name 和 Specialty Shape)
                  },
                  description: "Enable the Awareness Dashboard for participants. When enabled, select the information items to display to participants (e.g., others' money, order progress).",
                  options: [
                    { 
                    label: 'Name', // 显示的标签
                    path: 'Participant.name', // 数据路径，用于从后端获取数据
                    control: 'text' // 控件类型：文本显示
                    },
                    // Specialty shape (图形显示)
                    { 
                    label: 'Specialty Shape', 
                    path: 'Participant.specialty', // 数据路径，期望值为 'circle', 'triangle', 或 'square'
                    control: 'shape', // 控件类型：图形显示
                    value: 'circle' // 临时示例值，实际应从 path 动态获取
                    },
                    // Money (字符串显示)
                    { 
                    label: 'Money', 
                    path: 'Participant.money', // 数据路径
                    control: 'text' // 控件类型：文本显示
                    },
                    // Production number (字符串显示)
                    { 
                    label: 'Production', 
                    path: 'Participant.production_number', // 数据路径
                    control: 'text' // 控件类型：文本显示
                    },
                    // Order progress (进度条)
                    { 
                    label: 'Orders', 
                    path: 'Participant.order_progress', // 数据路径，期望值为 0-100 的数字
                    control: 'progress', // 控件类型：进度条
                    value: 75 // 临时示例值，实际应从 path 动态获取（范围：0-100）
                    }
                ],
                path: 'Session.Interaction.awarenessDashboard',
            }],
            "Action Structures": [
                {label: "Negotiations", type: "boolean", default: "allow", options: ["Counter", "No Counter"], path: 'Session.Interaction.negotiations', description: "Counter: Participants can make counter offers. No Counter: Offers can only be accepted or rejected."},
                {label: "Simultaneous Actions", type: "boolean", default: "allow", options: ["Allowed", "Not Allowed"], path: 'Session.Interaction.simultaneousActions', description: "Allow: Multiple offers can be made at once. Not Allow: Each offer must be resolved before a new one begins."},
            ],
            "Agent Behaviors": [
                {label: "Agent Perception Time Window (sec)", type: "number", default: 15, path: 'Session.Interaction.agentPerceptionTimeWindow', description: "Frequency (in seconds) at which agents update their view of the game state."},
                {label: "Rationales", type: "boolean", default: "step_wise", options: ["Step-wise", "None"], path: 'Session.Interaction.rationales', description: "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        }
    },
    {
        id: 'daytrader',
        name: 'DayTrader',
        description: '**Setup:** Market-style investment game where participants can invest individually with safe returns or collectively with higher risk shared across the group.\n\n**Communication:** Occurs through assigned media channels.\n\n**Goal:** Optimize gains by balancing individual safety with group risk.',
        tags: ['Social Dilemma', 'Trade'],
        params: [
            {
                "General Settings": [{label: "Session Duration (min)", type: "number", default: 30, path: 'Session.Params.duration'}],
                "Money": [
                    {label: "Participant Initial Money ($)", type: "number", default: 200, path: 'Session.Params.startingMoney'},
                    {label: "Min. Trade Price ($)", type: "number", default: 15, path: 'Session.Params.minTradePrice'},
                    {label: "Max. Trade Price ($)", type: "number", default: 100, path: 'Session.Params.maxTradePrice'},
                    {label: "Order Incentive ($/trade fulfilled)", type: "number", default: 60, path: 'Session.Params.incentiveMoney'}
                ]
            }
        ],
        interaction: {
            "Information Flow": [
                {label: "Communication Level", type: "list", default: "Private Messaging", options: [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], path: 'Session.Interaction.communicationLevel', description: "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {label: "Communication Media", type: "multi_checkbox", default: ["text"], options: [{label: "Text Message", value: "text", description: "Participants type messages"}, {label: "Audio", value: "audio", description: "Voice input with Whisper transcription"}, {label: "Meeting Room", value: "meeting_room", description: "Real-time video/audio like Zoom"}], path: 'Session.Interaction.communicationMedia', description: "Select which communication media to enable."},
                {
                    label: "Awareness Dashboard",
                    type: "tiered_checkbox",
                    default: {
                        enabled: true,
                        items: [0, 1]
                    },
                    description: "Enable the Awareness Dashboard for participants. When enabled, select the information items to display to participants (e.g., others' money, investment).",
                    options: [
                        {label: 'Name', path: 'Participant.name', control: 'text'},
                        {label: 'Money', path: 'Participant.money', control: 'text'},
                        {label: 'Investment', path: 'Participant.investment_history', control: 'investment_history'}
                    ],
                    path: 'Session.Interaction.awarenessDashboard',
                }
            ],
            "Agent Behaviors": [
                {label: "Agent Perception Time Window (sec)", type: "number", default: 15, path: 'Session.Interaction.agentPerceptionTimeWindow', description: "Frequency (in seconds) at which agents update their view of the game state."},
                {label: "Rationales", type: "boolean", default: "step_wise", options: ["Step-wise", "None"], path: 'Session.Interaction.rationales', description: "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        }
    },
    {
        id: 'essayranking',
        name: 'Essay Ranking',
        description: '**Setup:** Participants read and discuss essays, then vote to produce a collective ranking.\n\n**AI Integration:** In some settings, AI agents contribute votes or reasoning alongside humans.\n\n**Goal:** Reach consensus on rankings.',
        tags: ['Collaborative Decision Making'],
        params: [
            {
                "General Settings": [{label: "Session Duration (min)", type: "number", default: 30, path: 'Session.Params.duration'}],
                "Essay Parameters": [
                    {label: "# Essays", type: "number", default: 5, path: 'Session.Params.essayNumber'},
                    {label: "Upload Essays", type: "file", default: null, path: 'Session.Params.essays'},
                ]
            }
        ],
        interaction: {
            "Information Flow": [
                {label: "Communication Level", type: "list", default: "Private Messaging", options: [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], path: 'Session.Interaction.communicationLevel', description: "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {label: "Communication Media", type: "multi_checkbox", default: ["text"], options: [{label: "Text Message", value: "text", description: "Participants type messages"}, {label: "Audio", value: "audio", description: "Voice input with Whisper transcription"}, {label: "Meeting Room", value: "meeting_room", description: "Real-time video/audio like Zoom"}], path: 'Session.Interaction.communicationMedia', description: "Select which communication media to enable."},
                {
                    'label': "Awareness Dashboard",
                    'type': "tiered_checkbox",
                    'default': {
                        'enabled': true,
                        'items': [0, 1],
                    },
                    'description': "Enable the Awareness Dashboard for participants. When enabled, select the information items to display to participants (e.g., others' rankings).",
                    'options': [
                        {'label': 'Name', 'path': 'Participant.name', 'control': 'text'},
                        {'label': 'Rankings', 'path': 'Participant.rankings', 'control': 'rankings'},
                    ],
                    'path': 'Session.Interaction.awarenessDashboard',
                }
            ],
            "Agent Behaviors": [
                {label: "Agent Perception Time Window (sec)", type: "number", default: 15, path: 'Session.Interaction.agentPerceptionTimeWindow', description: "Frequency (in seconds) at which agents update their view of the game state."},
                {label: "Rationales", type: "boolean", default: "step_wise", options: ["Step-wise", "None"], path: 'Session.Interaction.rationales', description: "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        }
    },
    {
        id: 'wordguessing',
        name: 'Word-Guessing Game',
        description: '**Setup:** one participant tries to guess a word the other participant is thinking of, and the other participant only provides one word hint each round.\n\n**Goal:** investigate people\'s mental models of AI',
        tags: ['Turn-Taking'],
        params: [
            {
                "General Settings": [{label: "Session Duration (min)", type: "number", default: 30, path: 'Session.Params.duration'}],
                "Word Settings": [
                    {label: "Word List", type: "input", default: "apple, banana, cherry, date, elderberry", path: 'Session.Params.wordList'}
                ]
            }
        ],
        interaction: {
            "Information Flow": [
                {label: "Communication Level", type: "list", default: "Private Messaging", options: [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], path: 'Session.Interaction.communicationLevel', description: "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {label: "Communication Media", type: "multi_checkbox", default: ["text"], options: [{label: "Text Message", value: "text", description: "Participants type messages"}, {label: "Audio", value: "audio", description: "Voice input with Whisper transcription"}, {label: "Meeting Room", value: "meeting_room", description: "Real-time video/audio like Zoom"}], path: 'Session.Interaction.communicationMedia', description: "Select which communication media to enable."}
            ],
            "Agent Behaviors": [
                {label: "Agent Perception Time Window (sec)", type: "number", default: 15, path: 'Session.Interaction.agentPerceptionTimeWindow', description: "Frequency (in seconds) at which agents update their view of the game state."},
                {label: "Rationales", type: "boolean", default: "step_wise", options: ["Step-wise", "None"], path: 'Session.Interaction.rationales', description: "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        }
    },
    {
        id: 'hiddenprofile',
        name: 'Hidden Profile',
        description: '**Setup:** participants are given assymetric information about job candidates.\n\n**Goal:** vote on the best candidate through discussion',
        tags: ['Collaborative Decision Making'],
        params: [
            {
                "General Settings": [{label: "Session Duration (min)", type: "number", default: 30, path: 'Session.Params.duration'}],
                "Hidden Profile Settings": [
                    {label: "Reading Time (minutes)", type: "number", default: 1, path: 'Session.Params.readingTime', description: "Time limit for reading the candidate document."},
                    {label: "Candidate Names", type: "input_list", default: "", path: 'Session.Params.candidateNames', description: "Enter the names of the candidates and click 'Add' to add them to the list."},
                    {label: "Participant Viewable Documents", type: "file", default: null, path: 'Session.Params.candidateDocuments', description: "Upload the documents that will be visible to the participants."},
                ]
            }
        ],
        interaction: {
            "Information Flow": [
                {label: "Communication Level", type: "list", default: "Private Messaging", options: [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], path: 'Session.Interaction.communicationLevel', description: "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {label: "Communication Media", type: "multi_checkbox", default: ["text"], options: [{label: "Text Message", value: "text", description: "Participants type messages"}, {label: "Audio", value: "audio", description: "Voice input with Whisper transcription"}, {label: "Meeting Room", value: "meeting_room", description: "Real-time video/audio like Zoom"}], path: 'Session.Interaction.communicationMedia', description: "Select which communication media to enable."}
            ],
            "Awareness Dashboard": [
                {
                    label: "Awareness Dashboard",
                    type: "tiered_checkbox",
                    default: {
                        enabled: true,
                        items: [0, 1],
                    },
                    description: "Enable the Awareness Dashboard for participants. When enabled, select the information items to display to participants (e.g., others' initial votes).",
                    options: [
                        {label: 'Name', path: 'Participant.name', control: 'text'},
                        {label: 'Initial Vote', path: 'Participant.initial_vote', control: 'text'},
                    ],
                    path: 'Session.Interaction.awarenessDashboard',
                }
            ],
            "Agent Behaviors": [
                {label: "Agent Perception Time Window (sec)", type: "number", default: 15, path: 'Session.Interaction.agentPerceptionTimeWindow', description: "Frequency (in seconds) at which agents update their view of the game state."},
                {label: "Rationales", type: "boolean", default: "step_wise", options: ["Step-wise", "None"], path: 'Session.Interaction.rationales', description: "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        }
    },
    {
        "id": "maptask",
        "name": "The Map Task",
        "description": "**Setup: ** A guide is given a map including the landmarks and a route. A follower is given a map with landmarks only. **Communication: ** The two participants can send messages to each other. **Goal: ** The two participants need to collaborate to let the follower reproduce the route.",
        "tags": ["Turn-Taking"],
        "params": [
            {
                "General Settings": [
                    {'label': "Session Duration (min)", 'type': "number", 'default': 30, 'path': 'Session.Params.duration'}
                ],
                "Map Settings": [
                    {'label': "Maps", 'type': "file", 'default': null, 'path': 'Session.Params.maps', 'description': "Upload the maps that will be used in the session.", 'control': 'map_upload'},
                ]
            }
        ],
        "interaction": {
            "Information Flow": [
                {'label': "Communication Level", 'type': "list", 'default': "Private Messaging", 'options': [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], 'path': 'Session.Interaction.communicationLevel', 'description': "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {'label': "Communication Media", type: "multi_checkbox", default: ["text"], options: [{label: "Text Message", value: "text", description: "Participants type messages"}, {label: "Audio", value: "audio", description: "Voice input with Whisper transcription"}, {label: "Meeting Room", value: "meeting_room", description: "Real-time video/audio like Zoom"}], path: 'Session.Interaction.communicationMedia', description: "Select which communication media to enable."},
                {
                    'label': "Awareness Dashboard",
                    'type': "tiered_checkbox",
                    'default': {
                        'enabled': true,
                        'items': [0, 1],
                    },
                    'description': "Enable the Awareness Dashboard for participants. When enabled, select the information items to display to participants (e.g., others' map progress).",
                    'options': [
                        {'label': 'Name', 'path': 'Participant.name', 'control': 'text'},
                        {'label': 'Map Progress', 'path': 'Participant.map_progress', 'control': 'map_progress'},
                    ],
                    'path': 'Session.Interaction.awarenessDashboard',
                }
            ],
            "Action Structures": [
                {'label': 'message_length', 'type': 'boolean_number', 'default': { enabled: false, value: 100 }, 'path': 'Session.Interaction.messageLength', 'description': 'Maximum length of the message sent by participants.'},
            ],
            "Agent Behaviors": [
                {'label': "Agent Perception Time Window (sec)", 'type': "number", 'default': 15, 'path': 'Session.Interaction.agentPerceptionTimeWindow', 'description': "Frequency (in seconds) at which agents update their view of the game state."},
                {'label': "Rationales", 'type': "boolean", 'default': "step_wise", 'options': ["Step-wise", "None"], 'path': 'Session.Interaction.rationales', 'description': "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        },
        "participant_settings": {
            'auto_start': false,
        },
        "interface": {
            "My Tasks": [
                {
                    "id": "my_tasks",
                    "label": "My Tasks",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "Your Map",
                            "path": "Participant.map",
                            "control": "map",
                            "default": null
                        },
                        {
                            "label": "Your toolbox",
                            "visible_if": "Participant.role == 'follower'",
                            "default": null,
                            "control": "map_toolbox"
                        }
                    ]
                }
            ],
            "Social Panel": [
                {
                    "id": "social_panel",
                    "label": "Social Panel",
                    "visible_if": "true",
                    "bindings": [],
                    "tabs": ["messages"],
                }
            ]
        }
    }
]

const experiments = ref([...FALLBACK_EXPERIMENTS])
const participantTemplates = ref({})

// Load experiments from backend (single source of truth - includes Communication Media for all experiments)
const loadExperiments = async () => {
  try {
    const [experimentsRes, templatesRes] = await Promise.all([
      fetch('/api/experiments'),
      fetch('/api/participants/templates'),
    ])

    if (experimentsRes.ok) {
      const data = await experimentsRes.json()
      if (Array.isArray(data) && data.length > 0) {
        experiments.value = data
      }
    }

    if (templatesRes.ok) {
      const templates = await templatesRes.json()
      if (templates && typeof templates === 'object') {
        participantTemplates.value = templates
      }
    }
  } catch (e) {
    console.warn('[Researcher] Could not load experiments from API, using fallback:', e)
  }
}

// Selected experiment type and config
const selectedExperimentType = ref(null)

// Computed: Get current experiment config based on selected type
const selectedExperimentConfig = computed(() => {
  if (!selectedExperimentType.value) return null
  return experiments.value.find(e => e.id === selectedExperimentType.value) || null
})

// Function to update selected experiment type (provided to child components)
const updateSelectedExperimentType = (experimentId) => {
  selectedExperimentType.value = experimentId
}

const upsertExperimentConfig = (uploadedExperiment) => {
  if (!uploadedExperiment || !uploadedExperiment.id) return
  const index = experiments.value.findIndex(e => e.id === uploadedExperiment.id)
  if (index >= 0) {
    experiments.value[index] = uploadedExperiment
  } else {
    experiments.value.push(uploadedExperiment)
  }
}

const upsertParticipantTemplate = (experimentId, uploadedTemplateArray) => {
  if (!experimentId || !Array.isArray(uploadedTemplateArray)) return
  participantTemplates.value = {
    ...participantTemplates.value,
    [experimentId]: uploadedTemplateArray,
  }
}

// Tab management
const activeTab = ref('setup')

// Timer and session state (placeholder - to be connected to backend)
const timerDisplay = ref('00:00')
const isSessionCreated = ref(false)
const currentSessionId = ref('')
const currentSessionName = ref('')
const experimentStatus = ref('waiting') // 'waiting', 'running', 'paused'

// Real-time data for monitor tab
const conversations = ref({}) // Format: { "from_to": [messages] }
const messages = ref([]) // Flat array of all messages
const activeConversations = computed(() => {
  return Object.keys(conversations.value).length
})
const interactionConfig = ref({}) // Will be updated from session config
/** Live typing for monitor: senderId -> { receiver: string|null } (entry removed after idle timeout). */
const liveTypingBySender = ref({})
const typingExpiryTimers = {}
const allParticipants = ref([]) // Array of participant objects
const pendingOffers = ref([]) // Pending trade offers
const completedTrades = ref([]) // Completed trades
const totalTrades = computed(() => completedTrades.value.length)
const pendingTrades = computed(() => pendingOffers.value.filter(o => o.status === 'pending').length)
const participantsMap = computed(() => {
  // Convert array to map: id -> participant
  const map = {}
  allParticipants.value.forEach(p => {
    const id = p.id || p.participant_id
    if (id) {
      map[id] = p
    }
  })
  return map
})

// Provide experiments and selected experiment info to child components
provide('experiments', experiments)
provide('participantTemplates', participantTemplates)
provide('selectedExperimentType', selectedExperimentType)
provide('selectedExperimentConfig', selectedExperimentConfig)
provide('updateSelectedExperimentType', updateSelectedExperimentType)
provide('upsertExperimentConfig', upsertExperimentConfig)
provide('upsertParticipantTemplate', upsertParticipantTemplate)
provide('isSessionCreated', isSessionCreated)
provide('currentSessionId', currentSessionId)
provide('currentSessionName', currentSessionName)
provide('conversations', conversations)
provide('messages', messages)
provide('activeConversations', activeConversations)
// Function to update interactionConfig (can be called from child components)
const updateInteractionConfig = (newConfig) => {
  interactionConfig.value = newConfig
  console.log('[Researcher] Updated interactionConfig:', newConfig)
  if (newConfig && newConfig.communicationLevel) {
    console.log('[Researcher] Communication Level updated to:', newConfig.communicationLevel)
  }
}

provide('interactionConfig', interactionConfig)
provide('updateInteractionConfig', updateInteractionConfig)
provide('allParticipants', allParticipants)
provide('participantsMap', participantsMap)
provide('pendingOffers', pendingOffers)
provide('completedTrades', completedTrades)
provide('totalTrades', totalTrades)
provide('pendingTrades', pendingTrades)
provide('liveTypingBySender', liveTypingBySender)

// Computed properties for button states
const canStartExperiment = computed(() => {
  return experimentStatus.value === 'waiting' || experimentStatus.value === 'paused'
})

const canPauseExperiment = computed(() => {
  return experimentStatus.value === 'running'
})

const canResetExperiment = computed(() => {
  return experimentStatus.value === 'running' || experimentStatus.value === 'paused'
})

const startButtonIcon = computed(() => {
  if (experimentStatus.value === 'paused') return '▶'
  if (experimentStatus.value === 'running') return '⏸'
  return '▶'
})

const startButtonText = computed(() => {
  if (experimentStatus.value === 'paused') return 'Resume'
  if (experimentStatus.value === 'running') return 'Pause'
  return 'Start'
})

// Control methods - connected to backend
const toggleExperiment = async () => {
  if (!isSessionCreated.value || !currentSessionId.value && !currentSessionName.value) {
    console.error('[Researcher] Cannot toggle experiment: no active session')
    return
  }
  
  try {
    const sessionIdentifier = currentSessionId.value || currentSessionName.value
    const encodedSessionId = encodeURIComponent(sessionIdentifier)
    
    if (experimentStatus.value === 'waiting' || experimentStatus.value === 'paused') {
      // Start or resume
      const response = await fetch(`/api/sessions/${encodedSessionId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (response.ok) {
        const session = await response.json()
        experimentStatus.value = session.status || 'running'
        console.log('[Researcher] Experiment started/resumed')
      } else {
        const error = await response.json()
        console.error('[Researcher] Failed to start experiment:', error)
        alert(`Failed to start experiment: ${error.error || 'Unknown error'}`)
      }
    } else if (experimentStatus.value === 'running') {
      // Pause
      const response = await fetch(`/api/sessions/${encodedSessionId}/pause`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (response.ok) {
        const session = await response.json()
        experimentStatus.value = session.status || 'paused'
        console.log('[Researcher] Experiment paused')
      } else {
        const error = await response.json()
        console.error('[Researcher] Failed to pause experiment:', error)
        alert(`Failed to pause experiment: ${error.error || 'Unknown error'}`)
      }
    }
  } catch (error) {
    console.error('[Researcher] Error toggling experiment:', error)
    alert(`Error: ${error.message}`)
  }
}

const resetTimer = async () => {
  if (!isSessionCreated.value || !currentSessionId.value && !currentSessionName.value) {
    console.error('[Researcher] Cannot reset timer: no active session')
    return
  }
  
  if (!confirm('Are you sure you want to reset the timer? This will reset the experiment to waiting state.')) {
    return
  }
  
  try {
    const sessionIdentifier = currentSessionId.value || currentSessionName.value
    const encodedSessionId = encodeURIComponent(sessionIdentifier)
    
    const response = await fetch(`/api/sessions/${encodedSessionId}/reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (response.ok) {
      const session = await response.json()
      experimentStatus.value = session.status || 'waiting'
      timerDisplay.value = '00:00'
      console.log('[Researcher] Experiment reset')
    } else {
      const error = await response.json()
      console.error('[Researcher] Failed to reset experiment:', error)
      alert(`Failed to reset experiment: ${error.error || 'Unknown error'}`)
    }
  } catch (error) {
    console.error('[Researcher] Error resetting experiment:', error)
    alert(`Error: ${error.message}`)
  }
}

const resetExperiment = async () => {
  if (!isSessionCreated.value || !currentSessionId.value && !currentSessionName.value) {
    console.error('[Researcher] Cannot end experiment: no active session')
    return
  }
  
  if (!confirm('Are you sure you want to end the experiment? This will delete the session and all its data.')) {
    return
  }
  
  try {
    const sessionIdentifier = currentSessionId.value || currentSessionName.value
    const encodedSessionId = encodeURIComponent(sessionIdentifier)
    
    const response = await fetch(`/api/sessions/${encodedSessionId}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (response.ok) {
      timerDisplay.value = '00:00'
      experimentStatus.value = 'waiting'
      isSessionCreated.value = false
      currentSessionId.value = ''
      currentSessionName.value = ''
      console.log('[Researcher] Experiment ended and session deleted')
    } else {
      const error = await response.json()
      console.error('[Researcher] Failed to end experiment:', error)
      alert(`Failed to end experiment: ${error.error || 'Unknown error'}`)
    }
  } catch (error) {
    console.error('[Researcher] Error ending experiment:', error)
    alert(`Error: ${error.message}`)
  }
}

// WebSocket session management - centralized at researcher level
const currentJoinedSession = ref(null)

// Helper function to get session ID for WebSocket (always return session_id UUID)
const getSessionIdForWebSocket = async () => {
  // Prefer session_id (UUID) as it's the actual room identifier
  if (currentSessionId.value) {
    // Verify it's a UUID format (basic check)
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    if (uuidRegex.test(currentSessionId.value)) {
      return currentSessionId.value
    }
    // If it's not a UUID, treat it as session_name and fetch the actual session_id
  }
  
  // If only session_name is available, fetch session to get session_id (UUID)
  const sessionNameToUse = currentSessionName.value || currentSessionId.value
  if (sessionNameToUse) {
    try {
      const encodedSessionName = encodeURIComponent(sessionNameToUse)
      const response = await fetch(`/api/sessions/${encodedSessionName}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })
      if (response.ok) {
        const session = await response.json()
        // Always return session_id (UUID), never session_name
        const sessionId = session.session_id || session.id
        if (sessionId) {
          return sessionId
        }
      }
    } catch (error) {
      console.error('Error fetching session ID:', error)
    }
  }
  
  return null
}

// Watch for session changes and manage WebSocket connection
watch([currentSessionId, currentSessionName, isSessionCreated], async () => {
  const sessionIdForWebSocket = await getSessionIdForWebSocket()
  
  // Only leave and rejoin if session actually changed
  if (currentJoinedSession.value && currentJoinedSession.value !== sessionIdForWebSocket) {
    // Leave previous session
    leaveSession(currentJoinedSession.value)
    currentJoinedSession.value = null
    // Clear old messages and participants when leaving a session
    conversations.value = {}
    messages.value = []
    allParticipants.value = []
    Object.keys(typingExpiryTimers).forEach((k) => {
      const t = typingExpiryTimers[k]
      if (t) clearTimeout(t)
      delete typingExpiryTimers[k]
    })
    liveTypingBySender.value = {}
  }
  
  // Join new session if it exists and is created
  if (sessionIdForWebSocket && isSessionCreated.value) {
    // Only join if not already joined
    if (currentJoinedSession.value !== sessionIdForWebSocket) {
      joinSession(sessionIdForWebSocket, 'researcher')
      currentJoinedSession.value = sessionIdForWebSocket
      console.log(`[Researcher] Joined session: ${sessionIdForWebSocket}`)
      
      // Fetch session config to get interaction config and load existing messages
      try {
        const encodedSessionName = encodeURIComponent(currentSessionName.value || '')
        const response = await fetch(`/api/sessions/${encodedSessionName}`, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' }
        })
        if (response.ok) {
          const session = await response.json()
          // Update interactionConfig from session
          if (session.interaction) {
            interactionConfig.value = session.interaction
            console.log('[Researcher] Loaded interactionConfig from session.interaction:', interactionConfig.value)
            if (session.interaction.communicationLevel) {
              console.log('[Researcher] Communication Level from session.interaction:', session.interaction.communicationLevel)
            }
          } else if (session.experiment_config?.interaction) {
            interactionConfig.value = session.experiment_config.interaction
            console.log('[Researcher] Loaded interactionConfig from session.experiment_config.interaction:', interactionConfig.value)
            if (session.experiment_config.interaction.communicationLevel) {
              console.log('[Researcher] Communication Level from experiment_config:', session.experiment_config.interaction.communicationLevel)
            }
          } else {
            console.log('[Researcher] No interaction config found in session')
          }
          
          // Log communication level for debugging
          if (interactionConfig.value && interactionConfig.value.communicationLevel) {
            console.log('[Researcher] Final Communication Level:', interactionConfig.value.communicationLevel)
          } else {
            console.log('[Researcher] Communication Level not found in interactionConfig')
          }
          
          // Load existing messages from session
          if (session.messages && Array.isArray(session.messages)) {
            console.log(`[Researcher] Loading ${session.messages.length} existing messages from session`)
            // Process each message
            session.messages.forEach(message => {
              handleMessageReceived(message)
            })
          }
          
          // Load participants from session
          if (session.participants && Array.isArray(session.participants)) {
            allParticipants.value = session.participants
            console.log(`[Researcher] Loaded ${session.participants.length} participants from session`)
          }
          
          // Update session status
          if (session.status) {
            experimentStatus.value = session.status
            console.log(`[Researcher] Loaded session status: ${session.status}`)
          }
          
          // Update timer if remaining_seconds is provided
          if (session.remaining_seconds !== undefined && session.remaining_seconds !== null) {
            const totalSeconds = session.remaining_seconds
            const minutes = Math.floor(totalSeconds / 60)
            const seconds = totalSeconds % 60
            timerDisplay.value = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
          }
        }
      } catch (error) {
        console.error('[Researcher] Error fetching session config:', error)
      }
    }
  } else if (!sessionIdForWebSocket || !isSessionCreated.value) {
    // Clean up if session is no longer valid
    if (currentJoinedSession.value) {
      leaveSession(currentJoinedSession.value)
      console.log(`[Researcher] Left session: ${currentJoinedSession.value}`)
      currentJoinedSession.value = null
    }
    // Clear messages and participants when session is cleared
    conversations.value = {}
    messages.value = []
    allParticipants.value = []
    Object.keys(typingExpiryTimers).forEach((k) => {
      const t = typingExpiryTimers[k]
      if (t) clearTimeout(t)
      delete typingExpiryTimers[k]
    })
    liveTypingBySender.value = {}
  }
}, { immediate: true })

// Handle incoming messages from WebSocket
const handleMessageReceived = (message) => {
  console.log('[Researcher] Received message:', message)
  
  // Validate message has required fields
  if (!message || !message.sender) {
    console.warn('[Researcher] Invalid message received, missing sender:', message)
    return
  }
  
  const sender = String(message.sender) // Ensure it's a string
  const receiver = message.receiver ? String(message.receiver) : null // null for group chat
  
  // Convert backend message format to frontend format
  // Normalize timestamp to number (milliseconds) for consistent comparison
  let msgTimestamp = Date.now()
  if (message.timestamp) {
    if (typeof message.timestamp === 'string') {
      msgTimestamp = new Date(message.timestamp).getTime()
    } else if (typeof message.timestamp === 'number') {
      // If already a number, check if it's in seconds (less than year 2000 in ms) or milliseconds
      msgTimestamp = message.timestamp < 946684800000 ? message.timestamp * 1000 : message.timestamp
    }
  }
  
  const msg = {
    id: message.id || `msg_${Date.now()}_${Math.random()}`,
    from: sender,
    to: receiver,
    sender: sender,
    receiver: receiver,
    content: message.content,
    timestamp: msgTimestamp
  }
  
  // Helper function to normalize timestamp for comparison
  const normalizeTimestamp = (ts) => {
    if (!ts) return 0
    if (typeof ts === 'number') {
      return ts < 946684800000 ? ts * 1000 : ts
    }
    if (typeof ts === 'string') {
      return new Date(ts).getTime()
    }
    return 0
  }
  
  // Add to flat messages array
  const existsInFlat = messages.value.some(m => {
    // Check by id first (most reliable)
    if (m.id === msg.id) return true
    // Check by content + sender + timestamp (within 5 seconds for network delays)
    const mTs = normalizeTimestamp(m.timestamp)
    const msgTs = normalizeTimestamp(msg.timestamp)
    const timeDiff = Math.abs(mTs - msgTs)
    return m.content === msg.content && 
           (m.sender || m.from) === (msg.sender || msg.from) &&
           timeDiff < 2000
  })
  if (!existsInFlat) {
    messages.value.push(msg)
    // Keep sorted by timestamp
    messages.value.sort((a, b) => (normalizeTimestamp(a.timestamp) || 0) - (normalizeTimestamp(b.timestamp) || 0))
    console.log('[Researcher] Added message to flat array, total:', messages.value.length, 'sender:', sender)
  } else {
    console.log('[Researcher] Message already exists in flat array, skipping:', msg)
  }
  
  // Add to conversations object - use Vue's reactive update
  if (receiver === null || receiver === undefined) {
    // Group chat: use special key
    const key = 'group'
    const existing = conversations.value[key] || []
    // Check for duplicates more carefully - compare by id, or by content + sender + timestamp (within 5 seconds)
    const exists = existing.some(m => {
      // If same id, definitely duplicate
      if (m.id === msg.id) return true
      // If same content, sender, and timestamp within 5 seconds, it's likely a duplicate
      const mTs = normalizeTimestamp(m.timestamp)
      const msgTs = normalizeTimestamp(msg.timestamp)
      const timeDiff = Math.abs(mTs - msgTs)
      return m.content === msg.content && 
             (m.sender || m.from) === (msg.sender || msg.from) &&
             timeDiff < 2000
    })
    if (!exists) {
      // Use Vue's reactive array update
      if (!conversations.value[key]) {
        conversations.value[key] = []
      }
      conversations.value[key].push(msg)
      // Force reactivity by reassigning - create a new object to trigger reactivity
      conversations.value = { ...conversations.value }
      console.log('[Researcher] Added group chat message, total:', conversations.value[key].length, 'message:', msg, 'sender:', sender)
    } else {
      console.log('[Researcher] Group chat message already exists, skipping:', msg)
    }
  } else {
    // Private chat: determine conversation key (sender_receiver or receiver_sender)
    // At this point, receiver should be a valid string (not null/undefined)
    const key1 = `${sender}_${receiver}`
    const key2 = `${receiver}_${sender}`
    const key = conversations.value[key1] ? key1 : (conversations.value[key2] ? key2 : key1)
    
    const existing = conversations.value[key] || []
    const exists = existing.some(m => {
      // Check by id first
      if (m.id === msg.id) return true
      // Check by content + sender + timestamp (within 5 seconds)
      const mTs = normalizeTimestamp(m.timestamp)
      const msgTs = normalizeTimestamp(msg.timestamp)
      const timeDiff = Math.abs(mTs - msgTs)
      return m.content === msg.content && 
             (m.sender || m.from) === (msg.sender || msg.from) &&
             timeDiff < 2000
    })
    if (!exists) {
      // Use Vue's reactive array update
      if (!conversations.value[key]) {
        conversations.value[key] = []
      }
      conversations.value[key].push(msg)
      // Force reactivity by reassigning
      conversations.value = { ...conversations.value }
      console.log('[Researcher] Added private message to', key, 'total:', conversations.value[key].length, 'sender:', sender, 'receiver:', receiver)
    } else {
      console.log('[Researcher] Private message already exists, skipping:', msg)
    }
  }
}

// Handle participants update from WebSocket
const handleParticipantsUpdate = (data) => {
  // Check if this update is for the current session
  if (data.session_id) {
    const updateSessionId = data.session_id
    const sessionIdForWebSocket = currentSessionId.value
    
    // If we have session_id, compare directly
    if (sessionIdForWebSocket && updateSessionId !== sessionIdForWebSocket) {
      return
    }
  }
  
  // Update participants
  if (data.participants && Array.isArray(data.participants)) {
    allParticipants.value = data.participants
  }
  
  // Update trades data if provided
  if (data.pending_offers && Array.isArray(data.pending_offers)) {
    pendingOffers.value = data.pending_offers
    console.log('[Researcher] Updated pending offers:', pendingOffers.value.length)
  }
  
  if (data.completed_trades && Array.isArray(data.completed_trades)) {
    completedTrades.value = data.completed_trades
    console.log('[Researcher] Updated completed trades:', completedTrades.value.length)
  }
  
  // Update session status if provided
  if (data.session_info) {
    const sessionInfo = data.session_info
    if (sessionInfo.status) {
      experimentStatus.value = sessionInfo.status
      console.log('[Researcher] Session status updated via WebSocket:', sessionInfo.status)
    }
    
    // Update timer if remaining_seconds is provided
    if (sessionInfo.remaining_seconds !== undefined && sessionInfo.remaining_seconds !== null) {
      const totalSeconds = sessionInfo.remaining_seconds
      const minutes = Math.floor(totalSeconds / 60)
      const seconds = totalSeconds % 60
      timerDisplay.value = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    }
    
    // Also update trades from session_info if available
    if (sessionInfo.pending_offers && Array.isArray(sessionInfo.pending_offers)) {
      pendingOffers.value = sessionInfo.pending_offers
    }
    if (sessionInfo.completed_trades && Array.isArray(sessionInfo.completed_trades)) {
      completedTrades.value = sessionInfo.completed_trades
    }
    
    // Update interactionConfig from session_info if available
    if (sessionInfo.interaction) {
      interactionConfig.value = sessionInfo.interaction
      console.log('[Researcher] Updated interactionConfig from session_info:', sessionInfo.interaction)
      if (sessionInfo.interaction.communicationLevel) {
        console.log('[Researcher] Communication Level from session_info:', sessionInfo.interaction.communicationLevel)
      }
    }
  }
  
  // Also handle status_changed update type
  if (data.update_type === 'status_changed' && data.session_info) {
    const sessionInfo = data.session_info
    if (sessionInfo.status) {
      experimentStatus.value = sessionInfo.status
      console.log('[Researcher] Session status changed via WebSocket:', sessionInfo.status)
    }
  }
}

// Handle timer update from WebSocket
const handleTimerUpdate = (data) => {
  // Check if this update is for the current session
  if (data.session_id) {
    const updateSessionId = data.session_id
    const sessionIdForWebSocket = currentSessionId.value
    
    // If we have session_id, compare directly
    if (sessionIdForWebSocket && updateSessionId !== sessionIdForWebSocket) {
      return
    }
  }
  
  // Update timer display
  if (data.remaining_seconds !== undefined && data.remaining_seconds !== null) {
    const totalSeconds = data.remaining_seconds
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    timerDisplay.value = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    
    // Update experiment status if timer is paused
    if (data.is_paused && experimentStatus.value === 'running') {
      experimentStatus.value = 'paused'
    } else if (data.is_running && !data.is_paused && experimentStatus.value === 'paused') {
      experimentStatus.value = 'running'
    }
  }
}

const handleTypingIndicatorPayload = (payload) => {
  if (interactionConfig.value?.typeIndicator !== 'enabled') return
  if (!payload?.sender) return
  const sid = String(payload.sender)
  if (typingExpiryTimers[sid]) {
    clearTimeout(typingExpiryTimers[sid])
    delete typingExpiryTimers[sid]
  }
  if (!payload.is_typing) {
    const next = { ...liveTypingBySender.value }
    delete next[sid]
    liveTypingBySender.value = next
    return
  }
  const receiver = payload.receiver == null || payload.receiver === '' ? null : String(payload.receiver)
  liveTypingBySender.value = { ...liveTypingBySender.value, [sid]: { receiver } }
  typingExpiryTimers[sid] = setTimeout(() => {
    const next = { ...liveTypingBySender.value }
    delete next[sid]
    liveTypingBySender.value = next
    delete typingExpiryTimers[sid]
  }, 4000)
}

// Register WebSocket listeners
let cleanupMessageListener = null
let cleanupParticipantsListener = null
let cleanupTimerListener = null
let cleanupTypingListener = null
watch([currentJoinedSession, isSessionCreated], () => {
  // Clean up old listeners
  if (cleanupMessageListener) {
    cleanupMessageListener()
    cleanupMessageListener = null
  }
  if (cleanupParticipantsListener) {
    cleanupParticipantsListener()
    cleanupParticipantsListener = null
  }
  if (cleanupTimerListener) {
    cleanupTimerListener()
    cleanupTimerListener = null
  }
  if (cleanupTypingListener) {
    cleanupTypingListener()
    cleanupTypingListener = null
  }
  
  // Register new listeners when session is joined
  if (currentJoinedSession.value && isSessionCreated.value) {
    const ws = getSocket()
    
    cleanupMessageListener = onMessageReceived(handleMessageReceived)
    cleanupParticipantsListener = onParticipantsUpdate(handleParticipantsUpdate)
    cleanupTypingListener = onTypingIndicator(handleTypingIndicatorPayload)
    
    // Register timer update listener
    const timerUpdateHandler = (data) => {
      handleTimerUpdate(data)
    }
    ws.on('timer_update', timerUpdateHandler)
    cleanupTimerListener = () => {
      ws.off('timer_update', timerUpdateHandler)
    }
    
    console.log('[Researcher] Registered WebSocket listeners (message_received, participants_updated, timer_update, typing_indicator)')
  }
}, { immediate: true })

// Load experiments from backend on mount
onMounted(() => {
  loadExperiments()
})

// Clean up on unmount
onUnmounted(() => {
  if (cleanupMessageListener) {
    cleanupMessageListener()
    cleanupMessageListener = null
  }
  if (cleanupParticipantsListener) {
    cleanupParticipantsListener()
    cleanupParticipantsListener = null
  }
  if (cleanupTimerListener) {
    cleanupTimerListener()
    cleanupTimerListener = null
  }
  if (cleanupTypingListener) {
    cleanupTypingListener()
    cleanupTypingListener = null
  }
  if (currentJoinedSession.value) {
    leaveSession(currentJoinedSession.value)
    currentJoinedSession.value = null
  }
})
</script>

<template>
  <div class="researcher-container">
  <!-- Header -->
  <header class="header-row">
    <div class="timer-display">
      <div class="timer-value">{{ timerDisplay }}</div>
      <div v-if="isSessionCreated" class="current-session-display">
        <div class="session-label">Session: {{ currentSessionName || currentSessionId }}</div>
      </div>
    </div>
      
    <div class="control-buttons">
      <button 
        class="control-rect start" 
        :class="{ 'paused': experimentStatus === 'paused' }"
        @click="toggleExperiment"
        :disabled="!isSessionCreated || (!canStartExperiment && !canPauseExperiment)"
        :title="experimentStatus === 'paused' ? 'Resume experiment' : experimentStatus === 'running' ? 'Pause experiment' : 'Start experiment'"
      >
        <span class="button-icon">{{ startButtonIcon }}</span>
        <span class="button-text">{{ startButtonText }}</span>
      </button>
      <button 
        class="control-rect reset" 
        @click="resetTimer"
        :disabled="!isSessionCreated || !canResetExperiment"
        title="Reset timer and clear game data (requires active session)"
      >
        <span class="button-text">Reset</span>
      </button>
      <button class="control-rect end" @click="resetExperiment"
        :disabled="!isSessionCreated"
        title="End experiment and delete session (requires active session)">END</button>
    </div>
  </header>

  <!-- MAIN SECTION HEADERS (CLICKABLE TABS) -->
  <main>
    <div class="tab-header-row">
      <div
        class="tab-header-item"
        :class="{ active: activeTab === 'setup' }"
        @click="activeTab = 'setup'"
      >
        Setup
      </div>
      <div
        class="tab-header-item"
        :class="{ active: activeTab === 'monitor' }"
        @click="activeTab = 'monitor'"
      >
        Real-Time Monitor
      </div>
      <div
        class="tab-header-item"
        :class="{ active: activeTab === 'analysis' }"
        @click="activeTab = 'analysis'"
      >
        Result Analysis
      </div>
    </div>

    <div class="tab-group-card">
      <div class="tab-content-grid" :class="{ 
          'setup-mode': activeTab === 'setup',
          'monitor-mode': activeTab === 'monitor',
          'analysis-mode': activeTab === 'analysis'
        }">
          <Setup v-if="activeTab === 'setup'" />
          <Monitor v-if="activeTab === 'monitor'" />
          <Analysis v-if="activeTab === 'analysis'" />
      </div>
    </div>
  </main>
  </div>
</template>

<style scoped>
.researcher-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 2vh); /* 减去 #app 的上下 padding (1vh * 2) */
  overflow: hidden;
}

.header-row {
  flex-shrink: 0;
}

.control-buttons {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
}

/* MAIN SECTION */
main {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* HEADER TABS */
.tab-header-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 0; /* connect with content card */
  position: relative; /* for z-index layering */
  flex-shrink: 0;
}

.tab-header-item {
  background: #f5f7fa;
  border: 1px solid #e5e7eb;
  border-radius: 8px 8px 0 0;
  padding: 12px;
  text-align: center;
  font-weight: 600;
  color: #374151;
  user-select: none;
  z-index: 1;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

.tab-header-item:hover {
  cursor: pointer;
  background: #eef2f7;
}

.tab-header-item.active {
  background: #ffffff; /* same as content card */
  color: #111827;
  border-color: #e5e7eb;
  border-bottom-color: transparent; /* blend with card border */
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  z-index: 2;
}

.tab-header-item.disabled {
  opacity: 0.6;
  pointer-events: none;
}

/* CONTENT GRID */
.tab-group-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
  border-bottom-left-radius: 12px;
  border-bottom-right-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
  margin-top: -1px; /* pull up to hide double border under active tab */
  display: flex; /* fill remaining height */
  flex-direction: column;
  flex: 1;
  min-height: 0; /* allow children to shrink and scroll */
  overflow: hidden; /* Prevent card from scrolling */
}

.group-header {
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 16px;
  padding: 4px 8px;
  border-left: 4px solid #2563eb;
  background: #f1f5fe;
  border-radius: 6px;
}

.tab-content-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  flex: 1; /* fill the card */
  min-height: 0; /* allow inner columns to shrink */
  overflow: hidden; /* Prevent grid from scrolling */
}

.tab-content-grid.monitor-mode {
  grid-template-columns: 1fr;
  gap: 0;
}


.tab-content-grid.analysis-mode {
  grid-template-columns: 1fr;
  gap: 0;
}

.tab-content-grid.setup-mode {
  grid-template-columns: 1fr;
  gap: 0;
}

.grouping-btn {
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.grouping-btn:hover {
  background: #2563eb;
}
</style>
