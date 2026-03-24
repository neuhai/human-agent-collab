<script setup>
import { ref, computed, watch, inject, onMounted, onUnmounted, nextTick } from 'vue'
import BaseParticipantStatusComponent from './BaseParticipantStatusComponent.vue'
import MturkPanel from './MturkPanel.vue'
import { onParticipantsUpdate, offParticipantsUpdate } from '../services/websocket.js'
import mapPreviewImg from '../assets/map_preview.png'

// Inject experiments and update function from researcher.vue
const experiments = inject('experiments')
const participantTemplates = inject('participantTemplates', ref({}))
const updateSelectedExperimentType = inject('updateSelectedExperimentType')
const upsertExperimentConfig = inject('upsertExperimentConfig', () => {})
const upsertParticipantTemplate = inject('upsertParticipantTemplate', () => {})
const selectedExperimentType = inject('selectedExperimentType') // Inject from researcher.vue to maintain state
const isSessionCreated = inject('isSessionCreated')
const currentSessionId = inject('currentSessionId')
const currentSessionName = inject('currentSessionName')

const setupWorkflowSteps = ref([
  { id: 'initialSelection', label: 'Initial Selection' },
  { id: 'experimentSelection', label: 'Experiment Selection' },
  { id: 'parameters', label: 'Parameters' },
  { id: 'interactionVariables', label: 'Interaction Controls' },
  { id: 'participantRegistration', label: 'Participant Registration' },
  { id: 'mturkPanel', label: 'MTurk Panel (Optional)' }
])

const activeSetupTab = ref('initialSelection')
const setupTabs = ref({
  initialSelection: true,
  experimentSelection: true,
  parameters: true,
  interactionVariables: true,
  participantRegistration: true,
  mturkPanel: true
})

const MBTI_PROFILES = {
  "INTJ": {
    "name": "Strategic Architect",
    "description": "Analytical and strategic thinker who plans carefully and values efficiency",
    "behavior": "Plan long-term strategies, analyze market conditions, optimize for maximum efficiency",
    "communication": "Direct, analytical, and focused on facts and logic"
  },
  "INTP": {
    "name": "Innovative Thinker",
    "description": "Creative problem solver who enjoys exploring new trading strategies",
    "behavior": "Experiment with different approaches, think outside the box, adapt to changing conditions",
    "communication": "Thoughtful, curious, and enjoys discussing complex ideas"
  },
  "ENTJ": {
    "name": "Bold Commander",
    "description": "Natural leader who takes charge and makes decisive trading decisions",
    "behavior": "Take initiative, lead negotiations, make bold strategic moves",
    "communication": "Confident, assertive, and direct in expressing goals"
  },
  "ENTP": {
    "name": "Clever Strategist",
    "description": "Quick-witted and adaptable trader who thrives on dynamic market conditions",
    "behavior": "Adapt quickly to changes, find creative solutions, take calculated risks",
    "communication": "Enthusiastic, persuasive, and enjoys intellectual debates"
  },
  "INFJ": {
    "name": "Empathetic Negotiator",
    "description": "Insightful and caring trader who builds strong relationships",
    "behavior": "Build trust with others, consider long-term relationships, seek win-win solutions",
    "communication": "Warm, understanding, and focused on mutual benefit"
  },
  "INFP": {
    "name": "Idealistic Trader",
    "description": "Values-driven trader who prioritizes fairness and cooperation",
    "behavior": "Seek fair deals, avoid aggressive tactics, prioritize ethical trading",
    "communication": "Gentle, idealistic, and focused on creating positive relationships"
  },
  "ENFJ": {
    "name": "Charismatic Leader",
    "description": "Inspiring and supportive trader who motivates others to cooperate",
    "behavior": "Inspire cooperation, build alliances, create supportive trading networks",
    "communication": "Encouraging, diplomatic, and skilled at bringing people together"
  },
  "ENFP": {
    "name": "Enthusiastic Collaborator",
    "description": "Energetic and creative trader who brings excitement to negotiations",
    "behavior": "Generate enthusiasm for deals, think creatively, adapt to others' needs",
    "communication": "Energetic, optimistic, and skilled at building rapport"
  }
}

// Function to generate default persona from MBTI profile
function generateDefaultPersona(mbtiType, participantName) {
  const profile = MBTI_PROFILES[mbtiType]
  if (!profile) {
    return `Your nickname in this experiment is ${participantName}. You need to behave like a real human participant in this experiment.`
  }
  
  return `Your nickname in this experiment is ${participantName}. You need to behave like a real human participant in this experiment. Generally speaking, you are a "${profile.name}" in your daily life. Your MBTI personality is ${mbtiType}.

${profile.description}.

Your personality influences how you approach trading, communication, and decision-making. Stay true to your personality type in all interactions.`
}

// Experiment Selection
const previewedExperiment = ref(null)
const expandedExperiments = ref(new Set())
const selectedTags = ref([])
const allUniqueTags = ref(['Coordination', 'Trade', 'Social Dilemma', 'Collaborative Decision Making', 'Turn-Taking'])

const fileInputRef = ref(null)
const isUploadingConfig = ref(false)
const configValidationStatus = ref(null)
const validatedUploadedConfig = ref(null)

// Parameters
const experimentConfig = ref({})
const parameterClustersExpanded = ref({})

const wordAssignmentText = ref('')
const essayFileInput = ref(null)
const uploadedEssays = ref([])
const candidateDocumentsFileInput = ref(null)
const uploadedCandidateDocuments = ref([])
const mapsFileInput = ref(null)
const uploadedMaps = ref([])
const activeTooltip = ref(null)
const paramTooltipPosition = ref({ x: 0, y: 0 })
const candidateNamesList = ref([])
const candidateNameInput = ref('')
const editingCandidateIndex = ref(-1)
const editingCandidateValue = ref('')

// Interaction Variables
const interactionConfig = ref({})
const interactionSectionsExpanded = ref({})
const selectedInteractionEntry = ref(null)
const showCommDropdown = ref({}) // Changed to object to support multiple dropdowns
const awarenessDashboardItems = ref([]) // For tiered_checkbox items

// Auto start setting
const autoStartEnabled = ref(false)

// In-session annotation setting
const annotationEnabled = ref(false)

// Participant Registration
// Participant configuration based on experiment type (excluding mbti and experiment_params)
const DEFAULT_PARTICIPANT_CONFIG = {
  shapefactory: {
    id: { type: 'string', default: '' },
    name: { type: 'string', default: '' },
    type: { type: 'string', options: ['human', 'ai'], default: '' },
    specialty: { type: 'string', options: ['circle', 'square', 'triangle', 'rectangle'], default: '' }
  },
  daytrader: {
    id: { type: 'string', default: '' },
    name: { type: 'string', default: '' },
    type: { type: 'string', options: ['human', 'ai'], default: '' }
  },
  essayranking: {
    id: { type: 'string', default: '' },
    name: { type: 'string', default: '' },
    type: { type: 'string', options: ['human', 'ai'], default: '' }
  },
  wordguessing: {
    id: { type: 'string', default: '' },
    name: { type: 'string', default: '' },
    type: { type: 'string', options: ['human', 'ai'], default: '' },
    role: { type: 'string', options: ['guesser', 'hinter'], default: '' }
  },
  hiddenprofile: {
    id: { type: 'string', default: '' },
    name: { type: 'string', default: '' },
    type: { type: 'string', options: ['human', 'ai'], default: '' }
  },
  maptask: {
    id: { type: 'string', default: '' },
    name: { type: 'string', default: '' },
    type: { type: 'string', options: ['human', 'ai'], default: '' },
    role: { type: 'string', options: ['guider', 'follower'], default: '' }
  }
}

// Backend participant templates include schema for runtime (experiment_params) and agent MBTI.
// Those must not appear as Individual Participant Registration fields; MBTI is embedded in Agent Persona when type is AI.
const PARTICIPANT_REGISTRATION_OMIT_KEYS = ['experiment_params', 'mbti']

function omitParticipantRegistrationSchemaKeys(config) {
  const out = { ...config }
  for (const key of PARTICIPANT_REGISTRATION_OMIT_KEYS) {
    delete out[key]
  }
  return out
}

// Get participant config for current experiment type
const getParticipantConfig = computed(() => {
  if (!selectedExperimentType.value) return null
  
  const templateFromBackend = participantTemplates.value?.[selectedExperimentType.value]?.[0]
  const rawConfig = templateFromBackend || DEFAULT_PARTICIPANT_CONFIG[selectedExperimentType.value]
  if (!rawConfig) return null

  const baseConfig = omitParticipantRegistrationSchemaKeys(rawConfig)
  
  // For shapefactory, dynamically update specialty options based on # Shapes Types
  if (selectedExperimentType.value === 'shapefactory' && baseConfig.specialty) {
    const shapesTypes = experimentConfig.value.shapesTypes || 3
    const allShapes = Array.isArray(baseConfig.specialty.options) && baseConfig.specialty.options.length > 0
      ? baseConfig.specialty.options
      : ['circle', 'square', 'triangle', 'rectangle']
    const availableShapes = allShapes.slice(0, shapesTypes)
    
    // Add 'auto-assign' option to the beginning of the options array
    const specialtyOptions = ['auto-assign', ...availableShapes]
    
    // Return a new config object with updated specialty options
    return {
      ...baseConfig,
      specialty: {
        ...baseConfig.specialty,
        options: specialtyOptions
      }
    }
  }
  
  return baseConfig
})

// Initialize participant form ref first
const participantForm = ref({})

// Helper function to get random MBTI type
const getRandomMBTI = () => {
  const mbtiTypes = Object.keys(MBTI_PROFILES)
  const randomIndex = Math.floor(Math.random() * mbtiTypes.length)
  return mbtiTypes[randomIndex]
}

// Initialize participant form based on current experiment type
const initializeParticipantForm = () => {
  const config = getParticipantConfig.value
  if (!config) {
    participantForm.value = {}
    return
  }
  
  const form = {}
  Object.keys(config).forEach(key => {
    form[key] = config[key].default || ''
  })
  // Add persona field for AI agents
  form.persona = ''
  participantForm.value = form
}

// Watch for type changes to auto-generate persona for AI agents
watch(() => participantForm.value.type, (newType, oldType) => {
  if (newType === 'ai' || newType === 'ai_agent') {
    // Only generate if persona is empty or if switching from non-AI type
    if (!participantForm.value.persona || (oldType !== 'ai' && oldType !== 'ai_agent')) {
      // Generate random MBTI and default persona
      const randomMBTI = getRandomMBTI()
      const participantName = participantForm.value.name || 'Agent'
      participantForm.value.persona = generateDefaultPersona(randomMBTI, participantName)
    }
  } else {
    // Clear persona if type is not AI
    participantForm.value.persona = ''
  }
})

const participants = ref([])

// Agent auto registration
const agentAutoRegistrationCount = ref(1)
const isAutoRegistering = ref(false)

// Load participants from backend
const loadParticipants = async () => {
  if (!isSessionCreated.value || !currentSessionName.value) {
    participants.value = []
    return
  }
  
  try {
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    const response = await fetch(`/api/sessions/${encodedSessionName}/participants`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    
    if (response.ok) {
      const data = await response.json()
      participants.value = data.participants || []
      console.log('Loaded participants from backend:', participants.value.length)
    } else {
      console.error('Failed to load participants:', response.statusText)
      participants.value = []
    }
  } catch (error) {
    console.error('Error loading participants:', error)
    participants.value = []
  }
}

// Update auto_start setting
const updateAutoStartSetting = async (event) => {
  if (!isSessionCreated.value || !currentSessionName.value) {
    return
  }
  
  const newValue = event.target.checked
  
  try {
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    
    // First, get the current session to preserve experiment_config
    const getResponse = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    
    if (!getResponse.ok) {
      console.error('Failed to fetch session for auto_start update')
      autoStartEnabled.value = !newValue
      return
    }
    
    const session = await getResponse.json()
    
    // Update experiment_config.participant_settings.auto_start
    if (!session.experiment_config) {
      session.experiment_config = {}
    }
    if (!session.experiment_config.participant_settings) {
      session.experiment_config.participant_settings = {}
    }
    session.experiment_config.participant_settings.auto_start = newValue
    
    // Update the session via PUT request
    const updateResponse = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        experiment_config: session.experiment_config
      }),
    })
    
    if (updateResponse.ok) {
      autoStartEnabled.value = newValue
      console.log('Auto start setting updated:', newValue)
    } else {
      console.error('Failed to update auto_start setting:', updateResponse.statusText)
      // Revert the UI state
      autoStartEnabled.value = !newValue
      alert('Failed to update auto start setting. Please try again.')
    }
  } catch (error) {
    console.error('Error updating auto_start setting:', error)
    // Revert the UI state
    autoStartEnabled.value = !newValue
    alert('Error updating auto start setting. Please try again.')
  }
}

// Update annotation setting
const updateAnnotationSetting = async (event) => {
  if (!isSessionCreated.value || !currentSessionName.value) {
    return
  }
  const newValue = event.target.checked
  try {
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    const getResponse = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    if (!getResponse.ok) {
      annotationEnabled.value = !newValue
      return
    }
    const session = await getResponse.json()
    if (!session.experiment_config) {
      session.experiment_config = {}
    }
    if (!session.experiment_config.annotation) {
      session.experiment_config.annotation = { enabled: false, checkpoints: [20, 45, 70] }
    }
    session.experiment_config.annotation.enabled = newValue
    const updateResponse = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ experiment_config: session.experiment_config })
    })
    if (updateResponse.ok) {
      annotationEnabled.value = newValue
    } else {
      annotationEnabled.value = !newValue
      alert('Failed to update annotation setting. Please try again.')
    }
  } catch (error) {
    annotationEnabled.value = !newValue
    alert('Error updating annotation setting. Please try again.')
  }
}

// Handle WebSocket participant updates
const handleParticipantsUpdate = (data) => {
  if (data.participants) {
    participants.value = data.participants
    console.log('Updated participants from WebSocket:', participants.value.length)
  }
}

const participantsUpdateHandler = ref(null)

// Helper: Convert backend config structure to frontend flat structure
// Universal function that works for both params and interaction configs
const convertBackendConfigToFrontend = (
  backendConfig, 
  definitions, 
  options = {}
) => {
  const {
    handleNumericKeys = false,  // For params: handle {0: {...}} structure
    handleNestedObjects = false,  // For interaction: deep copy nested objects
    fallbackConfig = null  // Existing config to fall back to
  } = options

  if (!backendConfig || !definitions) return {}
  
  const frontendConfig = {}
  
  // Handle numeric keys (like {0: {...}}) - only for params
  if (handleNumericKeys) {
    const numericKeys = Object.keys(backendConfig).filter(key => !isNaN(parseInt(key)))
    if (numericKeys.length > 0) {
      const firstNumericKey = numericKeys[0]
      if (typeof backendConfig[firstNumericKey] === 'object' && backendConfig[firstNumericKey] !== null) {
        // Recursively convert the nested object
        return convertBackendConfigToFrontend(backendConfig[firstNumericKey], definitions, options)
      }
    }
  }
  
  // If backend config is already flat (object with string keys), use it directly
  if (typeof backendConfig === 'object' && !Array.isArray(backendConfig)) {
    const numericKeys = handleNumericKeys ? Object.keys(backendConfig).filter(key => !isNaN(parseInt(key))) : []
    const hasGroupKeys = Object.keys(backendConfig).some(key => {
      // Check if any key matches a group name (cluster/section)
      return Object.keys(definitions).some(groupName => 
        key === groupName || key.toLowerCase().replace(/\s+/g, '') === groupName.toLowerCase().replace(/\s+/g, '')
      )
    })
    
    if (!hasGroupKeys && numericKeys.length === 0) {
      // Already in flat format
      return { ...backendConfig }
    }
  }
  
  // Convert grouped structure to flat structure
  Object.keys(definitions).forEach((groupName) => {
    definitions[groupName].forEach((param) => {
      const configKey = getConfigKey(param)
      
      // Helper to set value with optional deep copy for nested objects
      const setValue = (value) => {
        if (handleNestedObjects && typeof value === 'object' && value !== null && !Array.isArray(value)) {
          frontendConfig[configKey] = { ...value }
        } else {
          frontendConfig[configKey] = value
        }
      }
      
      // Try to find value in backend config
      // First, try direct key match
      if (backendConfig[configKey] !== undefined) {
        setValue(backendConfig[configKey])
        return
      }
      
      // Try to find in grouped structure by group name
      const groupKey = Object.keys(backendConfig).find(key => 
        key === groupName || key.toLowerCase().replace(/\s+/g, '') === groupName.toLowerCase().replace(/\s+/g, '')
      )
      
      if (groupKey) {
        const groupConfig = backendConfig[groupKey]
        if (Array.isArray(groupConfig)) {
          // If it's an array, find the param by label or path
          const paramConfig = groupConfig.find(p => {
            if (typeof p === 'object' && p !== null) {
              return p.label === param.label || p.path === param.path || p.key === configKey
            }
            return false
          })
          if (paramConfig) {
            // Extract value from param config object
            const value = paramConfig.value !== undefined ? paramConfig.value : 
                         (paramConfig.default !== undefined ? paramConfig.default : paramConfig)
            if (value !== undefined) {
              setValue(value)
              return
            }
          }
        } else if (typeof groupConfig === 'object' && groupConfig !== null) {
          // If it's an object, try to find by configKey
          if (groupConfig[configKey] !== undefined) {
            setValue(groupConfig[configKey])
            return
          }
          // Also try to find by path or label
          const paramKey = Object.keys(groupConfig).find(key => {
            const item = groupConfig[key]
            return item && (item.path === param.path || item.label === param.label)
          })
          if (paramKey) {
            const item = groupConfig[paramKey]
            const value = item.value !== undefined ? item.value : item
            if (value !== undefined) {
              setValue(value)
              return
            }
          }
        }
      }
      
      // If not found, keep existing value from fallback config
      if (fallbackConfig && fallbackConfig[configKey] !== undefined) {
        frontendConfig[configKey] = fallbackConfig[configKey]
      }
    })
  })
  
  return frontendConfig
}

// Wrapper for params conversion
const ParamConverter = (backendConfig, paramDefinitions) => {
  return convertBackendConfigToFrontend(backendConfig, paramDefinitions, {
    handleNumericKeys: true,
    handleNestedObjects: false,
    fallbackConfig: experimentConfig.value
  })
}

// Wrapper for interaction conversion
const InteractionConverter = (backendInteraction, interactionDefinitions) => {
  return convertBackendConfigToFrontend(backendInteraction, interactionDefinitions, {
    handleNumericKeys: false,
    handleNestedObjects: true,
    fallbackConfig: interactionConfig.value
  })
}

// Load experiment config from backend
const loadExperimentConfig = async (forceReload = false) => {
  if (!isSessionCreated.value || !currentSessionName.value) {
    return
  }
  
  try {
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    const response = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    
    if (response.ok) {
      const session = await response.json()
      
      // Load params if they exist
      if (session.params && Object.keys(session.params).length > 0) {
        // Always load if forceReload is true, otherwise only if config is empty
        if (forceReload || !experimentConfig.value || Object.keys(experimentConfig.value).length === 0) {
          // Get current experiment params structure to convert backend config
          const params = getCurrentExperimentParams.value
          
          if (forceReload && params) {
            // Convert backend config structure to frontend flat structure
            const convertedConfig = ParamConverter(session.params, params)
            // Merge with existing config to preserve any initialized values
            experimentConfig.value = { ...experimentConfig.value, ...convertedConfig }
          } else {
            // If config is empty, try to use backend config directly, or convert if needed
            if (params) {
              const convertedConfig = ParamConverter(session.params, params)
              experimentConfig.value = convertedConfig
            } else {
              // Fallback: use backend config as-is (might be in wrong format)
              experimentConfig.value = { ...session.params }
            }
          }
          
          // Also update wordAssignmentText if wordList exists
          if (session.params.wordList) {
            wordAssignmentText.value = session.params.wordList
          }
          
          // Load candidate names if they exist
          if (session.params.candidateNames) {
            if (Array.isArray(session.params.candidateNames)) {
              candidateNamesList.value = session.params.candidateNames
            } else if (typeof session.params.candidateNames === 'string' && session.params.candidateNames.trim()) {
              candidateNamesList.value = session.params.candidateNames.split(',').map(name => name.trim()).filter(name => name)
            }
          }
          
          // Load candidate documents if they exist
          if (session.params.candidateDocuments) {
            if (Array.isArray(session.params.candidateDocuments)) {
              uploadedCandidateDocuments.value = session.params.candidateDocuments
            } else if (typeof session.params.candidateDocuments === 'object' && session.params.candidateDocuments !== null) {
              uploadedCandidateDocuments.value = Object.values(session.params.candidateDocuments)
            } else if (typeof session.params.candidateDocuments === 'string') {
              uploadedCandidateDocuments.value = [session.params.candidateDocuments]
            }
          } else if (experimentConfig.value.wordList) {
            wordAssignmentText.value = experimentConfig.value.wordList
          }

          // Load maps if they exist
          if (session.params.maps && Array.isArray(session.params.maps)) {
            uploadedMaps.value = session.params.maps
          }
          
          console.log('Loaded experiment config from backend (raw):', JSON.stringify(session.params, null, 2))
          console.log('Current experiment params structure:', getCurrentExperimentParams.value)
          console.log('Converted experiment config:', experimentConfig.value)
        }
      }
      
      // Load interaction config if it exists
      if (session.interaction && Object.keys(session.interaction).length > 0) {
        // Always load if forceReload is true, otherwise only if config is empty
        if (forceReload || !interactionConfig.value || Object.keys(interactionConfig.value).length === 0) {
          // Get current experiment interaction structure to convert backend config
          const interaction = getCurrentExperimentInteraction.value
          
          if (forceReload && interaction) {
            // Convert backend config structure to frontend flat structure
            const convertedInteraction = InteractionConverter(session.interaction, interaction)
            // Merge with existing config to preserve any initialized values
            interactionConfig.value = { ...interactionConfig.value, ...convertedInteraction }
          } else {
            // If config is empty, try to use backend config directly, or convert if needed
            if (interaction) {
              const convertedInteraction = InteractionConverter(session.interaction, interaction)
              interactionConfig.value = convertedInteraction
            } else {
              // Fallback: use backend config as-is (might be in wrong format)
              interactionConfig.value = { ...session.interaction }
            }
          }
          
          console.log('Loaded interaction config from backend (raw):', JSON.stringify(session.interaction, null, 2))
          console.log('Current experiment interaction structure:', getCurrentExperimentInteraction.value)
          console.log('Converted interaction config:', interactionConfig.value)
        }
      }
    }
  } catch (error) {
    console.error('Error loading experiment config:', error)
  }
}

// Watch for session changes and load participants and config
watch([isSessionCreated, currentSessionName, currentSessionId], () => {
  if (isSessionCreated.value && (currentSessionName.value || currentSessionId.value)) {
    loadParticipants()
    // Force reload config when session changes (e.g., when switching back to setup tab)
    loadExperimentConfig(true)
    
    // Set up WebSocket listener for real-time updates
    if (!participantsUpdateHandler.value) {
      participantsUpdateHandler.value = handleParticipantsUpdate
      onParticipantsUpdate(handleParticipantsUpdate)
    }
  } else {
    participants.value = []
    // Reset configs when session is cleared
    experimentConfig.value = {}
    interactionConfig.value = {}
    // Clean up WebSocket listener if session is no longer valid
    if (participantsUpdateHandler.value) {
      offParticipantsUpdate(participantsUpdateHandler.value)
      participantsUpdateHandler.value = null
    }
  }
}, { immediate: true })

// Load participants on mount and set up WebSocket listener
onMounted(() => {
  if (isSessionCreated.value && (currentSessionName.value || currentSessionId.value)) {
    loadParticipants()
    // Force reload config on mount to ensure consistency when switching tabs
    loadExperimentConfig(true)
    
    // Set up WebSocket listener for real-time updates
    if (!participantsUpdateHandler.value) {
      participantsUpdateHandler.value = handleParticipantsUpdate
      onParticipantsUpdate(handleParticipantsUpdate)
    }
  }
})

// Clean up WebSocket listener on unmount
onUnmounted(() => {
  if (participantsUpdateHandler.value) {
    offParticipantsUpdate(participantsUpdateHandler.value)
    participantsUpdateHandler.value = null
  }
})
const showGroupingModal = ref(false)
const sessionName = ref('')
const showEditModal = ref(false)

// Computed properties
const filteredExperiments = computed(() => {
  if (selectedTags.value.length === 0) return experiments.value
  return experiments.value.filter(exp => 
    exp.tags.some(tag => selectedTags.value.includes(tag))
  )
})

// Computed: Get current experiment's parameter structure
const getCurrentExperimentParams = computed(() => {
  if (!selectedExperimentType.value) return null
  const exp = experiments.value.find(e => e.id === selectedExperimentType.value)
  return exp?.params?.[0] || null
})

// Computed: Get current experiment's interaction structure
const getCurrentExperimentInteraction = computed(() => {
  if (!selectedExperimentType.value) return null
  const exp = experiments.value.find(e => e.id === selectedExperimentType.value)
  return exp?.interaction || null
})

// Check if experiment has specific parameter groups
const hasParameterGroup = (groupName) => {
  const params = getCurrentExperimentParams.value
  return params && params[groupName] !== undefined
}

// Computed property for UI display (used in participant registration and preview)
const showShapeParameters = computed(() => 
  hasParameterGroup('Shape Production & Order') || 
  (experimentConfig.value.specialtyCost !== undefined)
)

// Computed property to get candidate documents list for hidden profile
const candidateDocumentsList = computed(() => {
  if (selectedExperimentType.value !== 'hiddenprofile') return []
  
  // First check uploadedCandidateDocuments (most up-to-date)
  if (uploadedCandidateDocuments.value && uploadedCandidateDocuments.value.length > 0) {
    return uploadedCandidateDocuments.value
  }
  
  // Then check experimentConfig
  const docs = experimentConfig.value?.candidateDocuments
  if (!docs) return []
  
  // Handle different formats: array, object, or single value
  if (Array.isArray(docs)) {
    return docs
  } else if (typeof docs === 'object' && docs !== null) {
    // If it's an object, convert to array
    return Object.values(docs)
  } else if (typeof docs === 'string') {
    // If it's a single string, return as array
    return [docs]
  }
  
  return []
})

// Helper function to get document identifier for matching
const getDocumentIdentifier = (doc) => {
  if (!doc) return ''
  if (typeof doc === 'string') return doc
  // Use essay_id if available, otherwise fall back to other identifiers
  return doc.essay_id || doc.id || doc.filename || doc.name || JSON.stringify(doc)
}

// Helper function to get document display name
const getDocumentDisplayName = (doc) => {
  if (!doc) return ''
  if (typeof doc === 'string') return doc
  return doc.original_filename || doc.filename || doc.name || doc.title || 'Document'
}

// Helper: Convert path to config key (e.g., 'Session.Params.duration' -> 'duration', 'Session.duration' -> 'duration')
const pathToConfigKey = (path) => {
  if (!path) return null
  const parts = path.split('.')
  if (parts.length < 2) return parts[0]
  // Get the last part of the path (e.g., 'Session.Params.duration' -> 'duration')
  const key = parts[parts.length - 1]
  return key.charAt(0).toLowerCase() + key.slice(1)
}

// Helper: Get config key from param
const getConfigKey = (param) => {
  if (!param.path) {
    // Fallback to label-based key
    return param.label.toLowerCase().replace(/\s+/g, '').replace(/[^a-z0-9]/g, '')
  }
  
  return pathToConfigKey(param.path)
}

// Initialize config from params defaults
const initializeExperimentConfig = () => {
  const params = getCurrentExperimentParams.value
  if (!params) return
  
  const newConfig = {}
  const newExpanded = {}
  
  Object.keys(params).forEach((clusterName) => {
    // Create a safe key for expanded state
    const clusterKey = clusterName.toLowerCase().replace(/\s+/g, '')
    newExpanded[clusterKey] = true // Expand all sections by default
    
    params[clusterName].forEach((param) => {
      const configKey = getConfigKey(param)
      
      // Handle special cases
      if (param.path === 'Session.Params.wordList' || param.path === 'Session.wordList') {
        wordAssignmentText.value = param.default || ''
        newConfig[configKey] = param.default || ''
      } else if (param.type === 'input_list' && param.path === 'Session.Params.candidateNames') {
        // Initialize candidate names list
        const defaultList = param.default || ''
        if (typeof defaultList === 'string' && defaultList.trim()) {
          candidateNamesList.value = defaultList.split(',').map(name => name.trim()).filter(name => name)
        } else if (Array.isArray(defaultList)) {
          candidateNamesList.value = defaultList.filter(name => name)
        } else {
          candidateNamesList.value = []
        }
        newConfig[configKey] = candidateNamesList.value
      } else if (param.type === 'file' && param.path === 'Session.Params.candidateDocuments') {
        // Initialize candidate documents list
        const defaultDocs = param.default || null
        if (Array.isArray(defaultDocs)) {
          uploadedCandidateDocuments.value = defaultDocs
          newConfig[configKey] = defaultDocs
        } else if (defaultDocs !== null && defaultDocs !== undefined) {
          uploadedCandidateDocuments.value = [defaultDocs]
          newConfig[configKey] = [defaultDocs]
        } else {
          uploadedCandidateDocuments.value = []
          newConfig[configKey] = []
        }
      } else if (param.type === 'file' && param.path === 'Session.Params.maps') {
        // Initialize maps list
        const defaultMaps = param.default || null
        if (Array.isArray(defaultMaps)) {
          uploadedMaps.value = defaultMaps
          newConfig[configKey] = defaultMaps
        } else {
          uploadedMaps.value = []
          newConfig[configKey] = []
        }
      } else {
        newConfig[configKey] = param.default !== undefined ? param.default : 
          (param.type === 'number' ? 0 : 
           param.type === 'list' ? (Array.isArray(param.default) ? param.default[0] : '') : '')
      }
    })
  })
  
  experimentConfig.value = newConfig
  parameterClustersExpanded.value = newExpanded
}

// Initialize interaction config from interaction params
const initializeInteractionConfig = () => {
  const interaction = getCurrentExperimentInteraction.value
  if (!interaction) return
  
  const newConfig = {}
  const newExpanded = {}
  const newDropdowns = {}
  
  Object.keys(interaction).forEach((sectionName) => {
    // Create a safe key for expanded state
    const sectionKey = sectionName.toLowerCase().replace(/\s+/g, '')
    newExpanded[sectionKey] = true // Expand all sections by default
    
    interaction[sectionName].forEach((param) => {
      const configKey = getConfigKey(param)
      
      // Handle different types
      if (param.type === 'tiered_checkbox') {
        // Initialize tiered checkbox structure
        newConfig[configKey] = {
          enabled: param.default?.enabled !== undefined ? param.default.enabled : false,
          items: param.default?.items || []
        }
        awarenessDashboardItems.value = param.options || []
      } else if (param.type === 'boolean') {
        // Boolean type uses first option as true value, second as false
        const trueValue = param.options?.[0]?.toLowerCase().replace(/\s+/g, '_') || 'true'
        const falseValue = param.options?.[1]?.toLowerCase().replace(/\s+/g, '_') || 'false'
        newConfig[configKey] = param.default || trueValue
      } else if (param.type === 'boolean_number') {
        const defaultVal = param.default
        newConfig[configKey] = typeof defaultVal === 'object' && defaultVal !== null
          ? { enabled: defaultVal.enabled ?? false, value: defaultVal.value ?? 100 }
          : { enabled: false, value: 100 }
      } else if (param.type === 'multi_checkbox') {
        // Multi checkbox: value is array of selected option values
        const defaultVal = param.default
        newConfig[configKey] = Array.isArray(defaultVal) ? [...defaultVal] : (defaultVal ? [defaultVal] : [])
      } else if (param.type === 'list') {
        // List type - handle options array
        if (Array.isArray(param.options) && param.options.length > 0) {
          // Options is array of objects with key-value pairs
          // Try to find matching option for default value
          let defaultKey = null
          if (param.default) {
            // Find option that matches default value
            for (const option of param.options) {
              const key = Object.keys(option)[0]
              const keyNormalized = key.toLowerCase().replace(/\s+/g, '_')
              const defaultNormalized = param.default.toLowerCase().replace(/\s+/g, '_')
              if (keyNormalized === defaultNormalized || key.toLowerCase() === param.default.toLowerCase()) {
                defaultKey = keyNormalized
                break
              }
            }
          }
          // If no match found, use first option
          if (!defaultKey) {
            defaultKey = Object.keys(param.options[0])[0].toLowerCase().replace(/\s+/g, '_')
          }
          newConfig[configKey] = defaultKey
        } else {
          newConfig[configKey] = param.default || ''
        }
      } else {
        newConfig[configKey] = param.default !== undefined ? param.default : 
          (param.type === 'number' ? 0 : '')
      }
      
      // Initialize dropdown state
      newDropdowns[configKey] = false
    })
  })
  
  interactionConfig.value = newConfig
  interactionSectionsExpanded.value = newExpanded
  showCommDropdown.value = newDropdowns
}

// Preferred order for interaction sections (Information Flow first)
const INTERACTION_SECTION_ORDER = ['Information Flow', 'Action Structures', 'Awareness Dashboard', 'Agent Behaviors']

// Get interaction clusters for current experiment
const getInteractionClusters = () => {
  const interaction = getCurrentExperimentInteraction.value
  if (!interaction) return []
  
  const clusters = Object.keys(interaction).map(sectionName => ({
    name: sectionName,
    key: sectionName.toLowerCase().replace(/\s+/g, ''),
    params: interaction[sectionName]
  }))
  // Sort so Information Flow is always first
  clusters.sort((a, b) => {
    const idxA = INTERACTION_SECTION_ORDER.indexOf(a.name)
    const idxB = INTERACTION_SECTION_ORDER.indexOf(b.name)
    const orderA = idxA >= 0 ? idxA : INTERACTION_SECTION_ORDER.length
    const orderB = idxB >= 0 ? idxB : INTERACTION_SECTION_ORDER.length
    return orderA - orderB
  })
  return clusters
}

// Get awareness dashboard config for preview based on selected items
const getAwarenessDashboardPreviewConfig = computed(() => {
  if (!selectedInteractionEntry.value || !getCurrentExperimentInteraction.value) return null
  
  const clusters = getInteractionClusters()
  for (const cluster of clusters) {
    for (const param of cluster.params) {
      if (selectedInteractionEntry.value === getConfigKey(param) && param.type === 'tiered_checkbox') {
        const value = getInteractionValue(param)
        // Build bindings from selected items
        const bindings = (value?.items || []).map(itemIndex => {
          const option = param.options?.[itemIndex]
          if (!option) return null
          
          // Add default values for Money, Production, Name, Investment, and Rankings
          let defaultValue = option.value
          if (option.label === 'Money' && !defaultValue) {
            defaultValue = '100'
          } else if (option.label === 'Production' && !defaultValue) {
            defaultValue = '5'
          } else if (option.label === 'Name' && !defaultValue) {
            defaultValue = 'Jack'
          } else if (option.label === 'Investment' && !defaultValue) {
            // For investment_history, provide placeholder data
            defaultValue = [
              {
                id: 'preview-1',
                investment_amount: 50,
                investment_type: 'individual',
                timestamp: new Date().toISOString(),
                money_before: 200,
                money_after: 150
              },
              {
                id: 'preview-2',
                investment_amount: 30,
                investment_type: 'group',
                timestamp: new Date(Date.now() - 60000).toISOString(),
                money_before: 150,
                money_after: 120
              }
            ]
          } else if (option.label === 'Rankings' && !defaultValue) {
            // For rankings, provide example data (e.g., Candidate B)
            defaultValue = [
              {
                essay_id: 'document-3',
                essay_title: 'Document 3',
                rank: 1
              },
              {
                essay_id: 'document-1',
                essay_title: 'Document 1',
                rank: 2
              },
              {
                essay_id: 'document-2',
                essay_title: 'Document 2',
                rank: 3
              }
            ]
          } else if (option.label === 'Initial Vote' && !defaultValue) {
            // For initial_vote, provide example value
            defaultValue = 'Candidate B'
          } else if (option.label === 'Map Progress') {
            // For map_progress, show placeholder image
            return {
              label: option.label,
              path: option.path || 'N/A',
              control: 'map_preview',
              value: mapPreviewImg
            }
          }
          
          return {
            label: option.label,
            path: option.path || 'N/A',
            control: option.control || 'text',
            value: defaultValue || option.value
          }
        }).filter(Boolean)
        
        // Always return config, even if bindings is empty
        return {
          id: 'awareness-dashboard-preview',
          label: param.label || 'Awareness Dashboard',
          visible_if: true,
          bindings: bindings
        }
      }
    }
  }
  return null
})

// Get interaction config value
const getInteractionValue = (param) => {
  const configKey = getConfigKey(param)
  return interactionConfig.value[configKey]
}

// Set interaction config value
const setInteractionValue = (param, value) => {
  const configKey = getConfigKey(param)
  interactionConfig.value[configKey] = value
  updateExperimentConfig()
}

// Toggle boolean_number enabled state
const toggleBooleanNumberEnabled = (param) => {
  const configKey = getConfigKey(param)
  const current = interactionConfig.value[configKey]
  const next = typeof current === 'object' && current !== null
    ? { ...current, enabled: !current.enabled }
    : { enabled: true, value: 100 }
  interactionConfig.value[configKey] = next
  updateExperimentConfig()
}

// Set boolean_number value (when enabled)
const setBooleanNumberValue = (param, value) => {
  const configKey = getConfigKey(param)
  const current = interactionConfig.value[configKey]
  const next = typeof current === 'object' && current !== null
    ? { ...current, value: Math.max(1, Math.min(1000, value)) }
    : { enabled: true, value: Math.max(1, Math.min(1000, value)) }
  interactionConfig.value[configKey] = next
  updateExperimentConfig()
}

// Get list options from param
const getListOptions = (param) => {
  if (!Array.isArray(param.options)) return []
  
  return param.options.map(option => {
    if (typeof option === 'object') {
      const key = Object.keys(option)[0]
      const value = key.toLowerCase().replace(/\s+/g, '_')
      return { value, label: key, description: option[key] }
    }
    return { value: option.toLowerCase().replace(/\s+/g, '_'), label: option }
  })
}

// Get normalized value for CSS class (handles both formats: "Private Messaging" -> "private_messaging")
const getNormalizedValueForClass = (param) => {
  const value = getInteractionValue(param)
  if (!value) return ''
  
  // Get all available options for this parameter
  const options = getListOptions(param)
  if (options.length === 0) return ''
  
  // Try to find matching option by exact value match first (handles normalized format like "private_messaging")
  let matchedOption = options.find(opt => opt.value === value)
  
  // If not found, try to match by label (handles original format like "Private Messaging")
  if (!matchedOption) {
    matchedOption = options.find(opt => opt.label === value)
  }
  
  // If still not found, try case-insensitive match
  if (!matchedOption) {
    const normalizedValue = typeof value === 'string' ? value.toLowerCase().replace(/\s+/g, '_') : ''
    matchedOption = options.find(opt => 
      opt.value === normalizedValue || 
      opt.label.toLowerCase().replace(/\s+/g, '_') === normalizedValue
    )
  }
  
  // Return the normalized value from matched option, or normalize the value directly as fallback
  if (matchedOption) {
    return matchedOption.value
  }
  
  // Fallback: normalize the value directly
  return typeof value === 'string' ? value.toLowerCase().replace(/\s+/g, '_') : value
}

// Toggle dropdown for interaction param
const toggleInteractionDropdown = (param) => {
  const configKey = getConfigKey(param)
  showCommDropdown.value[configKey] = !showCommDropdown.value[configKey]
}

// Select list option
const selectListOption = (param, value) => {
  setInteractionValue(param, value)
  toggleInteractionDropdown(param)
}

// Toggle tiered checkbox enabled state
const toggleTieredCheckboxEnabled = (param) => {
  const configKey = getConfigKey(param)
  const current = interactionConfig.value[configKey] || { enabled: false, items: [] }
  interactionConfig.value[configKey] = {
    ...current,
    enabled: !current.enabled
  }
  updateExperimentConfig()
}

// Toggle tiered checkbox item
const toggleTieredCheckboxItem = (param, itemIndex) => {
  const configKey = getConfigKey(param)
  const current = interactionConfig.value[configKey] || { enabled: false, items: [] }
  const items = [...(current.items || [])]
  const index = items.indexOf(itemIndex)
  
  if (index > -1) {
    items.splice(index, 1)
  } else {
    items.push(itemIndex)
  }
  
  interactionConfig.value[configKey] = {
    ...current,
    items
  }
  updateExperimentConfig()
}

// Check if tiered checkbox item is selected
const isTieredCheckboxItemSelected = (param, itemIndex) => {
  const configKey = getConfigKey(param)
  const current = interactionConfig.value[configKey] || { enabled: false, items: [] }
  return (current.items || []).includes(itemIndex)
}

// Get multi_checkbox options (param.options has {label, value, description})
const getMultiCheckboxOptions = (param) => {
  if (!Array.isArray(param.options)) return []
  return param.options.map(opt => typeof opt === 'object' && opt.value !== undefined
    ? { label: opt.label || opt.value, value: opt.value, description: opt.description }
    : { label: String(opt), value: String(opt).toLowerCase().replace(/\s+/g, '_'), description: '' })
}

// Toggle multi_checkbox item (by value)
const toggleMultiCheckboxItem = (param, optionValue) => {
  const configKey = getConfigKey(param)
  const current = interactionConfig.value[configKey] || []
  const arr = Array.isArray(current) ? [...current] : []
  const idx = arr.indexOf(optionValue)
  if (idx > -1) {
    arr.splice(idx, 1)
  } else {
    arr.push(optionValue)
  }
  interactionConfig.value[configKey] = arr
  updateExperimentConfig()
}

// Check if multi_checkbox item is selected
const isMultiCheckboxItemSelected = (param, optionValue) => {
  const configKey = getConfigKey(param)
  const current = interactionConfig.value[configKey] || []
  return Array.isArray(current) && current.includes(optionValue)
}

// Watch for experiment type changes - handles form initialization, preview sync, and config initialization
watch(selectedExperimentType, () => {
  if (selectedExperimentType.value) {
    // Initialize participant form
    initializeParticipantForm()
    
    // Sync previewedExperiment with selectedExperimentType when it changes
    previewedExperiment.value = selectedExperimentType.value
    // Expand the selected experiment
    expandedExperiments.value.add(selectedExperimentType.value)
    
    // Initialize configs with defaults (will be overridden by loadExperimentConfig if saved config exists)
    initializeExperimentConfig()
    initializeInteractionConfig()
    
    // If session exists, try to load saved configs (will only load if current configs are empty)
    if (isSessionCreated.value && (currentSessionName.value || currentSessionId.value)) {
      loadExperimentConfig()
    }
  }
}, { immediate: true }) // Run immediately to sync on mount

// Watch for when user navigates back to experiment selection tab
watch(activeSetupTab, (newTab) => {
  if (newTab === 'experimentSelection' && selectedExperimentType.value) {
    // Restore previewedExperiment and expanded state when returning to experiment selection
    previewedExperiment.value = selectedExperimentType.value
    expandedExperiments.value.add(selectedExperimentType.value)
  }
})

const availableShapes = computed(() => ['Circle', 'Square', 'Triangle'])
const canAssignSpecialty = computed(() => {
  const assigned = participants.value.filter(p => p.specialty).map(p => p.specialty)
  return assigned.length < availableShapes.value.length
})

const canRegisterParticipant = computed(() => 
  // Temporarily disabled check for testing
  // isSessionCreated.value && 
  // participantForm.value.participantType && 
  // participantForm.value.participantCode
  true
)


// Methods
const navigateToSetupTab = (tabId) => {
  if (setupTabs.value[tabId]) {
    activeSetupTab.value = tabId
  }
}


const showCreateSessionModal = ref(false)
const showLoadSessionModal = ref(false)
// Experiment Selection
const toggleExperimentAndPreview = (expId) => {
  if (expandedExperiments.value.has(expId)) {
    expandedExperiments.value.delete(expId)
    if (previewedExperiment.value === expId) {
      previewedExperiment.value = null
    }
  } else {
    expandedExperiments.value.add(expId)
    previewedExperiment.value = expId
  }
}

const isExperimentExpanded = (expId) => expandedExperiments.value.has(expId)

const getPreviewedExperiment = () => {
  return experiments.value.find(e => e.id === previewedExperiment.value)
}

const getCurrentExperimentName = () => {
  const exp = experiments.value.find(e => e.id === selectedExperimentType.value)
  return exp?.name || 'Unknown'
}

const confirmExperimentSelection = async () => {
  if (previewedExperiment.value) {
    selectedExperimentType.value = previewedExperiment.value
    // Update the selected experiment type in researcher.vue
    updateSelectedExperimentType(previewedExperiment.value)
    initializeExperimentConfig()
    initializeInteractionConfig()

    // Update session with experiment type if session exists
    if (isSessionCreated.value && currentSessionName.value) {
      try {
        const encodedSessionName = encodeURIComponent(currentSessionName.value)
        const response = await fetch(`/api/sessions/${encodedSessionName}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            experiment_type: previewedExperiment.value,
          }),
        })

        if (!response.ok) {
          const errorText = await response.text()
          let error
          try {
            error = JSON.parse(errorText)
          } catch {
            error = { error: errorText || 'Unknown error' }
          }
          console.error('Failed to update session:', error)
          // Continue anyway - don't block user from proceeding
        } else {
          const session = await response.json()
          if (session.id) {
            currentSessionId.value = session.id
          }
        }
      } catch (error) {
        console.error('Error updating session:', error)
        // Continue anyway - don't block user from proceeding
      }
    }

    navigateToSetupTab('parameters')
  }
}

const toggleTag = (tag) => {
  const index = selectedTags.value.indexOf(tag)
  if (index > -1) {
    selectedTags.value.splice(index, 1)
  } else {
    selectedTags.value.push(tag)
  }
}

const isTagSelected = (tag) => selectedTags.value.includes(tag)

const clearAllTags = () => {
  selectedTags.value = []
}

const getFormattedExperimentDescription = (description) => {
  const desc = description
  if (!desc) return ''
  
  // Convert markdown-like formatting to HTML
  return desc
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold text
    .replace(/\n\n/g, '</p><p>') // Double line breaks become paragraph breaks
    .replace(/^(.*)$/gm, '<p>$1</p>') // Wrap each line in paragraph tags
    .replace(/<p><\/p>/g, '') // Remove empty paragraphs
}

const triggerFileUpload = () => {
  fileInputRef.value?.click()
}

const handleFileUpload = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  
  isUploadingConfig.value = true
  configValidationStatus.value = null
  validatedUploadedConfig.value = null

  try {
    const content = await file.text()
    const response = await fetch('/api/experiments/validate-upload', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        fileName: file.name,
        content,
      }),
    })

    const result = await response.json()
    if (result.valid) {
      validatedUploadedConfig.value = result.normalized_config || null
      const uploadedExperiment = validatedUploadedConfig.value?.experiment
      const expId = uploadedExperiment?.id
      const uploadedParticipant = expId ? validatedUploadedConfig.value?.participant?.[expId] : null

      if (uploadedExperiment && expId) {
        upsertExperimentConfig(uploadedExperiment)
        if (Array.isArray(uploadedParticipant)) {
          upsertParticipantTemplate(expId, uploadedParticipant)
        }
        selectedExperimentType.value = expId
        updateSelectedExperimentType(expId)

        // Re-initialize local UI state using uploaded schema source
        initializeExperimentConfig()
        initializeInteractionConfig()
        initializeParticipantForm()
      }

      const warnings = Array.isArray(result.warnings) ? result.warnings : []
      const warningText = warnings.length > 0 ? ` (warnings: ${warnings.slice(0, 2).join('; ')})` : ''
      configValidationStatus.value = {
        type: 'success',
        message: `Config validation passed and applied to current UI.${warningText}`,
      }
    } else {
      const errors = Array.isArray(result.errors) ? result.errors : []
      const firstErrors = errors.slice(0, 3).map((e) => `${e.path}: ${e.message}`)
      const overflow = errors.length > 3 ? ` ... +${errors.length - 3} more` : ''
      configValidationStatus.value = {
        type: 'error',
        message: `Validation failed: ${firstErrors.join(' | ')}${overflow}`,
      }
    }
  } catch (err) {
    configValidationStatus.value = {
      type: 'error',
      message: `Upload/validation error: ${err.message}`,
    }
  } finally {
    isUploadingConfig.value = false
    if (event?.target) {
      event.target.value = ''
    }
  }
}

// Parameters
const toggleParameterCluster = (cluster) => {
  parameterClustersExpanded.value[cluster] = !parameterClustersExpanded.value[cluster]
}

const updateExperimentConfig = async () => {
  // 每次本地参数变更时，尽量把最新 config 同步到后端 session，
  // 这样后端就会重算 participants interface 并通过 websocket 实时推给前端。
  try {
    if (!isSessionCreated.value || !currentSessionName.value) {
      // 没有有效的 session 时，只更新本地 state，不打扰用户
      return
    }

    const encodedSessionName = encodeURIComponent(currentSessionName.value)

    // 构建更新 payload，同时包含 params 和 interaction
    const updatePayload = {}
    if (experimentConfig.value && Object.keys(experimentConfig.value).length > 0) {
      updatePayload.params = experimentConfig.value
    }
    if (interactionConfig.value && Object.keys(interactionConfig.value).length > 0) {
      updatePayload.interaction = interactionConfig.value
    }

    // 如果没有任何要更新的内容，直接返回
    if (Object.keys(updatePayload).length === 0) {
      return
    }

    const response = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updatePayload),
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Failed to live-update session config:', errorText)
    } else {
      const updatedSession = await response.json()
      console.debug('Live session config updated:', updatedSession)
    }
  } catch (err) {
    console.error('Error in updateExperimentConfig:', err)
  }
}

const updateWordAssignment = () => {
  const wordListParam = getCurrentExperimentParams.value?.['Word Settings']?.[0]
  if (wordListParam) {
    setConfigValue(wordListParam, wordAssignmentText.value)
  }
}

// Get parameter clusters for current experiment
const getParameterClusters = () => {
  const params = getCurrentExperimentParams.value
  if (!params) return []
  
  return Object.keys(params).map(clusterName => ({
    name: clusterName,
    key: clusterName.toLowerCase().replace(/\s+/g, ''),
    params: params[clusterName]
  }))
}

// Get config value for a parameter
const getConfigValue = (param) => {
  const configKey = getConfigKey(param)
  return experimentConfig.value[configKey]
}

// Set config value for a parameter
const setConfigValue = (param, value) => {
  const configKey = getConfigKey(param)
  experimentConfig.value[configKey] = value
  updateExperimentConfig()
}

// Get tooltip ID for a parameter
const getTooltipId = (param) => {
  return getConfigKey(param)
}

// Handle candidate names list
const addCandidateName = () => {
  const name = candidateNameInput.value.trim()
  if (name && !candidateNamesList.value.includes(name)) {
    candidateNamesList.value.push(name)
    candidateNameInput.value = ''
    updateCandidateNames()
  }
}

const removeCandidateName = (index) => {
  candidateNamesList.value.splice(index, 1)
  updateCandidateNames()
}

const startEditCandidate = (index) => {
  editingCandidateIndex.value = index
  editingCandidateValue.value = candidateNamesList.value[index]
}

const saveCandidateName = () => {
  const name = editingCandidateValue.value.trim()
  if (name && editingCandidateIndex.value >= 0) {
    // Check for duplicates (excluding current item)
    const isDuplicate = candidateNamesList.value.some((n, i) => i !== editingCandidateIndex.value && n === name)
    if (!isDuplicate) {
      candidateNamesList.value[editingCandidateIndex.value] = name
      updateCandidateNames()
    }
    cancelEditCandidate()
  }
}

const cancelEditCandidate = () => {
  editingCandidateIndex.value = -1
  editingCandidateValue.value = ''
}

const updateCandidateNames = () => {
  const configKey = 'candidateNames'
  setConfigValue({ path: 'Session.Params.candidateNames', type: 'input_list' }, candidateNamesList.value)
  updateExperimentConfig()
}

// Handle special parameter types
const handleSpecialParam = (param, value) => {
  const configKey = getConfigKey(param)
  
  // Handle word list (input type)
  if (param.path === 'Session.Params.wordList' || param.path === 'Session.wordList') {
    wordAssignmentText.value = value
    setConfigValue(param, value)
    updateWordAssignment()
    return
  }
  
  // Handle candidate names (input_list type)
  if (param.type === 'input_list' && param.path === 'Session.Params.candidateNames') {
    if (Array.isArray(value)) {
      candidateNamesList.value = value
    } else if (typeof value === 'string' && value.trim()) {
      candidateNamesList.value = value.split(',').map(name => name.trim()).filter(name => name)
    } else {
      candidateNamesList.value = []
    }
    setConfigValue(param, candidateNamesList.value)
    updateExperimentConfig()
    return
  }
  
  // Handle essay file upload
  if (param.type === 'file') {
    // File handling is done separately via handleEssayFileUpload
    return
  }
  
  setConfigValue(param, value)
}

const handleEssayFileUpload = async (event) => {
  const files = Array.from(event.target.files || [])
  if (files.length === 0) return
  
  // Validate session exists
  if (!isSessionCreated.value || !currentSessionName.value) {
    alert('Please create or load a session first')
    return
  }
  
  try {
    // Create FormData for file upload
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })
    
    // Upload files to backend
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    const response = await fetch(`/api/sessions/${encodedSessionName}/upload_essays`, {
      method: 'POST',
      body: formData
    })
    
    if (!response.ok) {
      const error = await response.json()
      alert(`Failed to upload essays: ${error.error || 'Unknown error'}`)
      return
    }
    
    const result = await response.json()
    console.log('Essays uploaded successfully:', result)
    
    // Update uploadedEssays list with server response (use all essays from session, not just uploaded ones)
    // This ensures we show all essays, including previously uploaded ones
    if (result.essays && Array.isArray(result.essays)) {
      uploadedEssays.value = result.essays
      // Also update experimentConfig if this is for essays
      if (experimentConfig.value) {
        experimentConfig.value.essays = result.essays
      }
    } else {
      uploadedEssays.value = []
    }
    
    // Show success message
    alert(`Successfully uploaded ${result.uploaded_count} essay(s)`)
    
    // Reset file input
    if (essayFileInput.value) {
      essayFileInput.value.value = ''
    }
  } catch (error) {
    console.error('Error uploading essays:', error)
    alert(`Error uploading essays: ${error.message}`)
  }
}

const removeEssay = (index) => {
  uploadedEssays.value.splice(index, 1)
}

// Handle candidate documents upload
const handleCandidateDocumentsUpload = async (event) => {
  const files = Array.from(event.target.files || [])
  if (files.length === 0) return
  
  // Validate session exists
  if (!isSessionCreated.value || !currentSessionName.value) {
    alert('Please create or load a session first')
    return
  }
  
  try {
    // Create FormData for file upload
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })
    
    // Upload files to backend - using same endpoint as essays for now, but could be separate
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    const response = await fetch(`/api/sessions/${encodedSessionName}/upload_essays`, {
      method: 'POST',
      body: formData
    })
    
    if (!response.ok) {
      const error = await response.json()
      alert(`Failed to upload documents: ${error.error || 'Unknown error'}`)
      return
    }
    
    const result = await response.json()
    console.log('Candidate documents uploaded successfully:', result)
    
    // Update uploadedCandidateDocuments list
    if (result.essays && Array.isArray(result.essays)) {
      uploadedCandidateDocuments.value = result.essays
      // Update experimentConfig to reflect uploaded documents
      experimentConfig.value.candidateDocuments = result.essays
      updateExperimentConfig()
    } else {
      uploadedCandidateDocuments.value = []
    }
    
    // Show success message
    alert(`Successfully uploaded ${result.uploaded_count} document(s)`)
    
    // Reset file input
    if (candidateDocumentsFileInput.value) {
      const element = Array.isArray(candidateDocumentsFileInput.value) ? candidateDocumentsFileInput.value[0] : candidateDocumentsFileInput.value
      if (element && element instanceof HTMLInputElement) {
        element.value = ''
      }
    }
  } catch (error) {
    console.error('Error uploading candidate documents:', error)
    alert(`Error uploading documents: ${error.message}`)
  }
}

const removeCandidateDocument = (index) => {
  uploadedCandidateDocuments.value.splice(index, 1)
  // Update experimentConfig
  experimentConfig.value.candidateDocuments = uploadedCandidateDocuments.value
  updateExperimentConfig()
}

// Handle maps upload (images, PDF, TXT)
const handleMapsUpload = async (event) => {
  const files = Array.from(event.target.files || [])
  if (files.length === 0) return

  if (!isSessionCreated.value || !currentSessionName.value) {
    alert('Please create or load a session first')
    return
  }

  try {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })

    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    const response = await fetch(`/api/sessions/${encodedSessionName}/upload_maps`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      const error = await response.json()
      alert(`Failed to upload maps: ${error.error || 'Unknown error'}`)
      return
    }

    const result = await response.json()
    if (result.maps && Array.isArray(result.maps)) {
      uploadedMaps.value = result.maps
      if (experimentConfig.value) {
        experimentConfig.value.maps = result.maps
      }
      updateExperimentConfig()
    }
    alert(`Successfully uploaded ${result.uploaded_count} map(s)`)
    if (mapsFileInput.value) {
      mapsFileInput.value.value = ''
    }
  } catch (error) {
    console.error('Error uploading maps:', error)
    alert(`Error uploading maps: ${error.message}`)
  }
}

const removeMap = (index) => {
  uploadedMaps.value.splice(index, 1)
  if (experimentConfig.value) {
    experimentConfig.value.maps = uploadedMaps.value
  }
  updateExperimentConfig()
}

const updateMapRole = (index, role) => {
  if (uploadedMaps.value[index]) {
    uploadedMaps.value[index].role = role
    if (experimentConfig.value) {
      experimentConfig.value.maps = uploadedMaps.value
    }
    updateExperimentConfig()
  }
}

const triggerMapsUpload = () => {
  nextTick(() => {
    const inputElement = mapsFileInput.value
    const element = Array.isArray(inputElement) ? inputElement[0] : inputElement
    if (element && element instanceof HTMLInputElement) {
      element.click()
    }
  })
}

const triggerCandidateDocumentsUpload = () => {
  nextTick(() => {
    const inputElement = candidateDocumentsFileInput.value
    const element = Array.isArray(inputElement) ? inputElement[0] : inputElement
    
    if (element && element instanceof HTMLInputElement) {
      element.click()
    } else {
      console.warn('Candidate documents file input not available yet, retrying...', { inputElement, element })
      setTimeout(() => {
        const retryInput = candidateDocumentsFileInput.value
        const retryElement = Array.isArray(retryInput) ? retryInput[0] : retryInput
        if (retryElement && retryElement instanceof HTMLInputElement) {
          retryElement.click()
        } else {
          console.error('Candidate documents file input still not available after retry', { retryInput, retryElement })
        }
      }, 100)
    }
  })
}

const triggerEssayFileUpload = () => {
  // Use nextTick to ensure the element is rendered if it's in a conditional block
  nextTick(() => {
    const inputElement = essayFileInput.value
    // Handle case where ref returns an array (Vue 3 behavior)
    const element = Array.isArray(inputElement) ? inputElement[0] : inputElement
    
    if (element && element instanceof HTMLInputElement) {
      element.click()
    } else {
      console.warn('Essay file input not available yet, retrying...', { inputElement, element })
      // Retry once more after a short delay
      setTimeout(() => {
        const retryInput = essayFileInput.value
        const retryElement = Array.isArray(retryInput) ? retryInput[0] : retryInput
        if (retryElement && retryElement instanceof HTMLInputElement) {
          retryElement.click()
        } else {
          console.error('Essay file input still not available after retry', { retryInput, retryElement })
        }
      }, 100)
    }
  })
}

const confirmParamConfig = async () => {
  try {
    // Validate session exists
    if (!isSessionCreated.value || !currentSessionName.value) {
      alert('Please create or load a session first')
      return
    }

    // Validate experiment config exists
    if (!experimentConfig.value || Object.keys(experimentConfig.value).length === 0) {
      alert('No parameter configuration to save')
      return
    }

    // URL encode session name to handle special characters
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    
    const response = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        params: experimentConfig.value,
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      let error
      try {
        error = JSON.parse(errorText)
      } catch {
        error = { error: errorText || 'Unknown error' }
      }
      alert(`Failed to update session parameters: ${error.error || 'Unknown error'}`)
      return
    }

    // Successfully updated
    const updatedSession = await response.json()
    console.log('Parameters updated successfully:', updatedSession)
    
    // Navigate to next tab
    navigateToSetupTab('interactionVariables')
  } catch (error) {
    console.error('Error updating parameters:', error)
    alert(`Error updating parameters: ${error.message}`)
  }
}

const updateTooltipPosition = (event) => {
  paramTooltipPosition.value = { x: event.clientX + 10, y: event.clientY + 10 }
}

// Interaction Variables
const toggleInteractionSection = (section) => {
  interactionSectionsExpanded.value[section] = !interactionSectionsExpanded.value[section]
}

const selectInteractionEntry = (entry) => {
  selectedInteractionEntry.value = entry
}

const confirmInteractionControl = async () => {
  try {
    // Validate session exists
    if (!isSessionCreated.value || !currentSessionName.value) {
      alert('Please create or load a session first')
      return
    }

    // Validate interaction config exists
    if (!interactionConfig.value || Object.keys(interactionConfig.value).length === 0) {
      alert('No interaction configuration to save')
      return
    }

    // URL encode session name to handle special characters
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    
    const response = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        interaction: interactionConfig.value,
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      let error
      try {
        error = JSON.parse(errorText)
      } catch {
        error = { error: errorText || 'Unknown error' }
      }
      alert(`Failed to update session interaction controls: ${error.error || 'Unknown error'}`)
      return
    }

    // Successfully updated
    const updatedSession = await response.json()
    console.log('Interaction controls updated successfully:', updatedSession)
    
    // Navigate to next tab
    navigateToSetupTab('participantRegistration')
  } catch (error) {
    console.error('Error updating interaction controls:', error)
    alert(`Error updating interaction controls: ${error.message}`)
  }
}

// Participant Registration
const onRegisterParticipant = async () => {
  if (!canRegisterParticipant.value) return
  
  // Validate session exists
  if (!isSessionCreated.value || !currentSessionName.value) {
    alert('Please create or load a session first')
    return
  }
  
  // Get participant config for current experiment
  const config = getParticipantConfig.value
  if (!config) {
    alert('Please select an experiment type first')
    return
  }
  
  // Validate required fields (id is auto-generated by backend, so we don't validate it)
  const missingFields = []
  
  // Check all required fields
  Object.keys(config).forEach(key => {
    if (key !== 'id' && key !== 'experiment_params') {
      const value = participantForm.value[key]
      if (!value || value === '') {
        const fieldLabel = key === 'type' ? 'Type' : key === 'name' ? 'Display Name' : key === 'specialty' ? 'Specialty' : key
        missingFields.push(fieldLabel)
      }
    }
  })
  
  // Check persona for AI agents
  if ((participantForm.value.type === 'ai' || participantForm.value.type === 'ai_agent') && !participantForm.value.persona) {
    missingFields.push('Agent Persona')
  }
  
  if (missingFields.length > 0) {
    alert(`Please fill in all required fields: ${missingFields.join(', ')}`)
    return
  }
  
  // Build participant object based on config (excluding experiment_params and id)
  const newParticipant = {}
  Object.keys(config).forEach(key => {
    // Skip experiment_params - those are set during experiment runtime
    // Skip id - it's auto-generated by backend
    if (key !== 'experiment_params' && key !== 'id') {
      let value = participantForm.value[key]
      
      // Handle auto-assign for specialty
      if (key === 'specialty' && value === 'auto-assign') {
        // Get available specialty options (excluding 'auto-assign')
        const specialtyConfig = config.specialty
        if (specialtyConfig && specialtyConfig.options) {
          const availableOptions = specialtyConfig.options.filter(opt => opt !== 'auto-assign')
          if (availableOptions.length > 0) {
            // Randomly select one from available options
            const randomIndex = Math.floor(Math.random() * availableOptions.length)
            value = availableOptions[randomIndex]
          } else {
            value = '' // No available options
          }
        } else {
          value = '' // No config available
        }
      }
      
      if (value !== undefined && value !== null && value !== '') {
        newParticipant[key] = value
      }
    }
  })
  
  // Add persona for AI agents (required field, already validated above)
  if (newParticipant.type === 'ai' || newParticipant.type === 'ai_agent') {
    if (participantForm.value.persona) {
      newParticipant.persona = participantForm.value.persona
    }
  }
  
  // Ensure name is set (id will be auto-generated by backend)
  if (!newParticipant.name && participantForm.value.name) {
    newParticipant.name = participantForm.value.name
  }
  
  // Check for duplicate participant name (case-insensitive)
  const participantName = newParticipant.name || newParticipant.participant_name
  if (participantName) {
    const isDuplicate = participants.value.some(p => {
      const existingName = p.name || p.participant_name
      return existingName && existingName.toLowerCase() === participantName.toLowerCase()
    })
    if (isDuplicate) {
      alert(`Participant name "${participantName}" already exists. Please use a different name.`)
      return
    }
  }
  
  // Log for debugging - verify all fields are included
  console.log('Registering participant with fields:', Object.keys(newParticipant))
  console.log('Participant data:', newParticipant)
  
  // Add to local array first
  participants.value.push(newParticipant)

  try {
    // URL encode session name to handle special characters
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    
    const response = await fetch(`/api/sessions/${encodedSessionName}/participants`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        participants: participants.value,
      }),
    })

    if (!response.ok) {
      // Remove from local array if backend update failed
      participants.value.pop()
      
      const errorText = await response.text()
      let error
      try {
        error = JSON.parse(errorText)
      } catch {
        error = { error: errorText || 'Unknown error' }
      }
      const errMsg = error.error || 'Unknown error'
      alert(response.status === 409 && error.code === 'PARTICIPANT_NAME_EXISTS' ? errMsg : `Failed to register participant: ${errMsg}`)
      return
    }

    // Successfully registered
    const result = await response.json()
    console.log('Participant registered successfully:', result)
    
    // Update local participants array with backend response (includes generated IDs)
    if (result.participants && Array.isArray(result.participants)) {
      participants.value = result.participants
    }
    
    // Reset form based on current config
    initializeParticipantForm()
  } catch (error) {
    // Remove from local array if request failed
    participants.value.pop()
    console.error('Error registering participant:', error)
    alert(`Error registering participant: ${error.message}`)
  }
}

const getDisplayName = (id) => {
  const p = participants.value.find(p => p.id === id)
  return p?.name || p?.id || id
}

// Generate random agent name using real person first names only
const generateRandomAgentName = (index) => {
  const firstNames = [
    'Alex', 'Jordan', 'Taylor', 'Morgan', 'Casey', 'Riley', 'Avery', 'Quinn', 'Sage', 'River',
    'Sam', 'Jamie', 'Dakota', 'Skyler', 'Phoenix', 'Blake', 'Cameron', 'Drew', 'Emery', 'Finley',
    'Harper', 'Hayden', 'Kai', 'Logan', 'Marley', 'Parker', 'Reese', 'Rowan', 'Sawyer', 'Sloane',
    'Adrian', 'Aiden', 'Aria', 'Aurora', 'Bella', 'Benjamin', 'Carter', 'Charlotte', 'Daniel', 'Emma',
    'Ethan', 'Grace', 'Hannah', 'Isabella', 'James', 'Liam', 'Lily', 'Lucas', 'Mia', 'Noah',
    'Oliver', 'Olivia', 'Sophia', 'William', 'Zoe', 'Amelia', 'Ava', 'Chloe', 'Ella', 'Emily',
    'Abigail', 'Addison', 'Evelyn', 'Madison', 'David', 'Michael', 'Sarah', 'Jessica', 'Jennifer', 'Christopher',
    'Matthew', 'Ashley', 'Joshua', 'Amanda', 'Andrew', 'Melissa', 'Ryan', 'Michelle', 'Nicole', 'Stephanie'
  ]
  
  // Randomly select first name only
  const firstName = firstNames[Math.floor(Math.random() * firstNames.length)]
  return firstName
}

// Auto register multiple agents
const onAutoRegisterAgents = async () => {
  if (!isSessionCreated.value || !currentSessionName.value) {
    alert('Please create or load a session first')
    return
  }
  
  const config = getParticipantConfig.value
  if (!config) {
    alert('Please select an experiment type first')
    return
  }
  
  const count = parseInt(agentAutoRegistrationCount.value)
  if (!count || count < 1 || count > 100) {
    alert('Please enter a valid number between 1 and 100')
    return
  }
  
  isAutoRegistering.value = true
  
  try {
    const newParticipants = []
    // Track used names including existing participants
    const usedNames = new Set(participants.value.map(p => p.name).filter(Boolean))
    
    // Generate all participants first
    for (let i = 0; i < count; i++) {
      const newParticipant = {}
      
      // Set type to 'ai'
      newParticipant.type = 'ai'
      
      // Generate random name (ensure uniqueness)
      let name = generateRandomAgentName(i)
      let nameCounter = 1
      while (usedNames.has(name)) {
        // If name already used, add a number suffix
        name = `${name} ${nameCounter}`
        nameCounter++
      }
      usedNames.add(name)
      newParticipant.name = name
      
      // Handle specialty (for shapefactory)
      if (config.specialty) {
        const specialtyConfig = config.specialty
        if (specialtyConfig && specialtyConfig.options) {
          const availableOptions = specialtyConfig.options.filter(opt => opt !== 'auto-assign')
          if (availableOptions.length > 0) {
            const randomIndex = Math.floor(Math.random() * availableOptions.length)
            newParticipant.specialty = availableOptions[randomIndex]
          }
        }
      }
      
      // Handle role (for wordguessing)
      if (config.role) {
        const roleConfig = config.role
        if (roleConfig && roleConfig.options) {
          const randomIndex = Math.floor(Math.random() * roleConfig.options.length)
          newParticipant.role = roleConfig.options[randomIndex]
        }
      }
      
      // Handle document assignment (for hiddenprofile)
      if (selectedExperimentType.value === 'hiddenprofile') {
        const docs = candidateDocumentsList.value
        if (docs && docs.length > 0) {
          // Randomly select a document
          const randomDocIndex = Math.floor(Math.random() * docs.length)
          const selectedDoc = docs[randomDocIndex]
          
          // Initialize experiment_params if it doesn't exist
          if (!newParticipant.experiment_params) {
            newParticipant.experiment_params = {}
          }
          // Set candidate_document - this must be set before sending to backend
          newParticipant.experiment_params.candidate_document = selectedDoc
        }
      }
      
      // Generate random persona for AI agents
      const randomMBTI = getRandomMBTI()
      newParticipant.persona = generateDefaultPersona(randomMBTI, newParticipant.name)
      
      newParticipants.push(newParticipant)
    }
    
    // Add to local array first
    const previousCount = participants.value.length
    participants.value.push(...newParticipants)
    
    // Send to backend
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    const response = await fetch(`/api/sessions/${encodedSessionName}/participants`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        participants: participants.value,
      }),
    })
    
    if (!response.ok) {
      // Remove from local array if backend update failed
      participants.value = participants.value.slice(0, previousCount)
      
      const errorText = await response.text()
      let error
      try {
        error = JSON.parse(errorText)
      } catch {
        error = { error: errorText || 'Unknown error' }
      }
      alert(`Failed to register agents: ${error.error || 'Unknown error'}`)
      return
    }
    
    // Successfully registered
    const result = await response.json()
    
    // Update local participants array with backend response (includes generated IDs)
    if (result.participants && Array.isArray(result.participants)) {
      participants.value = result.participants
    }
    
    // Reset count
    agentAutoRegistrationCount.value = 1
    
    alert(`Successfully registered ${count} agent(s)!`)
  } catch (error) {
    console.error('Error auto-registering agents:', error)
    alert(`Error auto-registering agents: ${error.message}`)
  } finally {
    isAutoRegistering.value = false
  }
}

// Grouping related variables
const groups = ref({})
const newGroupName = ref('')
const selectedGroup = ref('')
const selectedParticipants = ref([])

const getParticipantGroup = (id) => {
  for (const [groupName, participantIds] of Object.entries(groups.value)) {
    if (participantIds.includes(id)) {
      return groupName
    }
  }
  return null
}

// Grouping functions (placeholder implementations)
const createGroup = () => {
  if (newGroupName.value.trim()) {
    groups.value[newGroupName.value.trim()] = []
    newGroupName.value = ''
  }
}

const deleteGroup = (groupName) => {
  delete groups.value[groupName]
}

const removeParticipantFromGroup = (groupName, participantId) => {
  const group = groups.value[groupName]
  if (group) {
    const index = group.indexOf(participantId)
    if (index > -1) {
      group.splice(index, 1)
    }
  }
}

const addParticipantsToGroup = () => {
  if (selectedGroup.value && selectedParticipants.value.length > 0) {
    if (!groups.value[selectedGroup.value]) {
      groups.value[selectedGroup.value] = []
    }
    selectedParticipants.value.forEach(id => {
      if (!groups.value[selectedGroup.value].includes(id)) {
        groups.value[selectedGroup.value].push(id)
      }
    })
    selectedParticipants.value = []
  }
}

const closeGroupingModal = () => {
  showGroupingModal.value = false
  newGroupName.value = ''
  selectedGroup.value = ''
  selectedParticipants.value = []
}

const editForm = ref({})
const originalParticipantId = ref('')

// Initialize edit form based on current experiment config
const initializeEditForm = () => {
  const config = getParticipantConfig.value
  if (!config) {
    editForm.value = {}
    return
  }
  
  const form = {}
  Object.keys(config).forEach(key => {
    // Skip experiment_params - those are runtime fields
    // Skip id - it's auto-generated by backend and should not be edited
    if (key !== 'experiment_params' && key !== 'id') {
      form[key] = config[key].default || ''
    }
  })
  // Add persona field for AI agents
  form.persona = ''
  editForm.value = form
}

const onEditParticipant = (participant) => {
  const config = getParticipantConfig.value
  if (!config) {
    alert('Please select an experiment type first')
    return
  }
  
  // Initialize form with default values from config
  initializeEditForm()
  
  // Fill in participant values (excluding experiment_params and id)
  Object.keys(config).forEach(key => {
    if (key !== 'experiment_params' && key !== 'id' && participant[key] !== undefined) {
      editForm.value[key] = participant[key]
    }
  })
  
  // Handle persona for AI agents
  if (participant.type === 'ai' || participant.type === 'ai_agent') {
    editForm.value.persona = participant.persona || ''
  }
  
  originalParticipantId.value = participant.id // Store the original id
  showEditModal.value = true
}

const onUpdateParticipantDocument = async (participantId, documentIdentifier) => {
  if (!isSessionCreated.value || !currentSessionName.value) {
    console.error('Cannot update participant document: no active session')
    return
  }
  
  try {
    // Find the participant in the local array
    const participantIndex = participants.value.findIndex(p => p.id === participantId)
    if (participantIndex === -1) {
      console.error('Participant not found:', participantId)
      return
    }
    
    // Get the current participant
    const currentParticipant = participants.value[participantIndex]
    
    // Build updated participant object with the new document assignment
    const updatedParticipant = { ...currentParticipant }
    
    // Ensure experiment_params exists
    if (!updatedParticipant.experiment_params) {
      updatedParticipant.experiment_params = {}
    }
    
    // Find the full document object from candidateDocumentsList based on identifier
    let selectedDocument = null
    if (documentIdentifier) {
      selectedDocument = candidateDocumentsList.value.find(doc => {
        const docId = getDocumentIdentifier(doc)
        return docId === documentIdentifier
      })
      
      // If not found by identifier, try to find by essay_id directly (for backward compatibility)
      if (!selectedDocument) {
        selectedDocument = candidateDocumentsList.value.find(doc => {
          if (typeof doc === 'object' && doc.essay_id) {
            return doc.essay_id === documentIdentifier
          }
          return false
        })
      }
    }
    
    // Update candidate_document with the full document object (or null if not found)
    updatedParticipant.experiment_params.candidate_document = selectedDocument || null
    
    // Update backend using PUT method (same as edit participant)
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    const response = await fetch(`/api/sessions/${encodedSessionName}/participants/${participantId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updatedParticipant)
    })
    
    if (response.ok) {
      // Update local array with response data
      const responseData = await response.json()
      if (responseData.participant) {
        participants.value[participantIndex] = responseData.participant
      } else {
        // Fallback: update local array with our changes
        participants.value[participantIndex] = updatedParticipant
      }
      console.log('Updated participant document assignment')
    } else {
      // Revert local change if backend update failed
      participants.value[participantIndex] = currentParticipant
      
      const errorText = await response.text()
      let error
      try {
        error = JSON.parse(errorText)
      } catch {
        error = { error: errorText || 'Unknown error' }
      }
      console.error('Failed to update participant document:', error)
      alert(`Failed to update document assignment: ${error.error || 'Unknown error'}`)
    }
  } catch (error) {
    console.error('Error updating participant document:', error)
    alert(`Error: ${error.message}`)
  }
}

const onDeleteParticipant = async (id) => {
  const index = participants.value.findIndex(p => p.id === id)
  if (index > -1) {
    // Remove from local array first
    participants.value.splice(index, 1)
    
    // Update backend if session exists
    if (isSessionCreated.value && currentSessionName.value) {
      try {
        const encodedSessionName = encodeURIComponent(currentSessionName.value)
        const response = await fetch(`/api/sessions/${encodedSessionName}/participants`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            participants: participants.value,
          }),
        })
        
        if (!response.ok) {
          // Revert local change if backend update failed
          const participant = participants.value[index] || null
          if (participant) {
            participants.value.splice(index, 0, participant)
          }
          const error = await response.json()
          alert(`Failed to delete participant: ${error.error || 'Unknown error'}`)
        }
      } catch (error) {
        console.error('Error deleting participant:', error)
        // Revert local change if request failed
        const participant = participants.value[index] || null
        if (participant) {
          participants.value.splice(index, 0, participant)
        }
      }
    }
  }
}

// Edit participant functions
const isSavingEdit = ref(false)

const closeEditModal = () => {
  showEditModal.value = false
  initializeEditForm()
  originalParticipantId.value = ''
}

const saveEditParticipant = async () => {
  if (!isSessionCreated.value || !currentSessionName.value) {
    alert('Session not found')
    return
  }
  
  if (!originalParticipantId.value) {
    alert('Invalid participant')
    return
  }
  
  const config = getParticipantConfig.value
  if (!config) {
    alert('Please select an experiment type first')
    return
  }
  
  // Find participant in local array
  const participantIndex = participants.value.findIndex(p => p.id === originalParticipantId.value)
  if (participantIndex === -1) {
    alert('Participant not found')
    return
  }
  
  // Build updated participant object (excluding experiment_params and id)
  const updatedParticipant = { ...participants.value[participantIndex] }
  Object.keys(config).forEach(key => {
    // Skip id and experiment_params
    if (key !== 'experiment_params' && key !== 'id' && editForm.value[key] !== undefined) {
      updatedParticipant[key] = editForm.value[key]
    }
  })
  
  // Check for duplicate participant name when editing (exclude current participant)
  const newName = updatedParticipant.name || updatedParticipant.participant_name
  if (newName) {
    const isDuplicate = participants.value.some(p => {
      if (p.id === originalParticipantId.value) return false
      const existingName = p.name || p.participant_name
      return existingName && existingName.toLowerCase() === newName.toLowerCase()
    })
    if (isDuplicate) {
      alert(`Participant name "${newName}" already exists. Please use a different name.`)
      return
    }
  }
  
  isSavingEdit.value = true
  
  try {
    // Update persona if it's an AI agent (always include if present)
    if (updatedParticipant.type === 'ai' || updatedParticipant.type === 'ai_agent') {
      updatedParticipant.persona = editForm.value.persona || ''
    }
    
    // Log for debugging - verify all fields are included
    console.log('Updating participant with fields:', Object.keys(updatedParticipant))
    console.log('Updated participant data:', updatedParticipant)
    
    // Save original for revert on failure
    const originalParticipantData = { ...participants.value[participantIndex] }
    // Update local array first
    participants.value[participantIndex] = updatedParticipant
    
    // Update backend - use PUT method for individual participant update
    const encodedSessionName = encodeURIComponent(currentSessionName.value)
    const response = await fetch(`/api/sessions/${encodedSessionName}/participants/${originalParticipantId.value}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updatedParticipant),
    })
    
    if (!response.ok) {
      // Revert local change if backend update failed
      participants.value[participantIndex] = originalParticipantData
      const errorText = await response.text()
      let error
      try {
        error = JSON.parse(errorText)
      } catch {
        error = { error: errorText || 'Unknown error' }
      }
      const errMsg = error.error || 'Unknown error'
      alert(response.status === 409 && error.code === 'PARTICIPANT_NAME_EXISTS' ? errMsg : `Failed to update participant: ${errMsg}`)
      return
    }
    
    // Update local array with response data to ensure sync
    const responseData = await response.json()
    if (responseData.participant) {
      participants.value[participantIndex] = responseData.participant
    }
    
    // Successfully updated
    closeEditModal()
  } catch (error) {
    console.error('Error updating participant:', error)
    alert(`Error updating participant: ${error.message}`)
  } finally {
    isSavingEdit.value = false
  }
}

const createSession = async () => {
  try {
    // Validate session name
    if (!sessionName.value || !sessionName.value.trim()) {
      alert('Please enter a session name')
      return
    }

    const response = await fetch('/api/sessions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        sessionName: sessionName.value.trim(),
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      let error
      try {
        error = JSON.parse(errorText)
      } catch {
        error = { error: errorText || 'Unknown error' }
      }
      
      // Check if session name already exists
      if (response.status === 409 || error.code === 'SESSION_EXISTS') {
        alert(`Session name "${sessionName.value.trim()}" already exists. Please use a different name or load the existing session.`)
        // Close create modal and open load modal
        showCreateSessionModal.value = false
        showLoadSessionModal.value = true
        return
      }
      
      alert(`Failed to create session: ${error.error || 'Unknown error'}`)
      return
    }

    const result = await response.json()
    const session_id = result.session_id || result
    currentSessionId.value = session_id
    currentSessionName.value = sessionName.value.trim()
    isSessionCreated.value = true

    // Close modal after successful creation
    showCreateSessionModal.value = false

    // Note: WebSocket session join is now managed at researcher.vue level
    // No need to join here - researcher.vue will handle it via watch

    // Navigate to experiment selection tab
    navigateToSetupTab('experimentSelection')
  } catch (error) {
    console.error('Error creating session:', error)
    alert(`Error creating session: ${error.message}`)
  }
}

const loadSessionFromName = async () => {
  try {
    // Validate session name
    if (!sessionName.value || !sessionName.value.trim()) {
      alert('Please enter a session name')
      return
    }

    // URL encode session name to handle special characters
    const encodedSessionName = encodeURIComponent(sessionName.value.trim())
    const response = await fetch(`/api/sessions/${encodedSessionName}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    })

    // Check if response is JSON before parsing
    const contentType = response.headers.get('content-type')
    if (!contentType || !contentType.includes('application/json')) {
      const text = await response.text()
      console.error('Non-JSON response:', text.substring(0, 200))
      if (response.status === 404) {
        alert('Session not found. Please check the session name.')
      } else {
        alert(`Failed to load session: Server returned non-JSON response (${response.status})`)
      }
      return
    }

    if (!response.ok) {
        sessionName.value = ''
        try {
            const error = await response.json()
            alert(`Failed to load session: ${error.error || 'Session not found'}`)
        } catch (e) {
            alert(`Failed to load session: HTTP ${response.status}`)
        }
        return
    }

    const session = await response.json()
    currentSessionId.value = session.id || session.session_id
    currentSessionName.value = session.session_name || sessionName.value.trim()
    isSessionCreated.value = true

    // Load auto_start setting from experiment_config
    if (session.experiment_config?.participant_settings?.auto_start !== undefined) {
      autoStartEnabled.value = session.experiment_config.participant_settings.auto_start
    } else {
      autoStartEnabled.value = false
    }

    // Load annotation setting from experiment_config
    if (session.experiment_config?.annotation?.enabled !== undefined) {
      annotationEnabled.value = session.experiment_config.annotation.enabled
    } else {
      annotationEnabled.value = false
    }

    // Load experiment type if it exists in the session
    if (session.experiment_type) {
      selectedExperimentType.value = session.experiment_type
      updateSelectedExperimentType(session.experiment_type)
      // Wait for watch to complete initialization before loading saved configs
      await nextTick()
      console.log('After initialization, experimentConfig:', experimentConfig.value)
      console.log('After initialization, interactionConfig:', interactionConfig.value)
    }

    // Load all experiment configs (params and interaction) from backend
    // This will override any default configs initialized by the watch above
    await loadExperimentConfig(true)
    console.log('After loading from backend, experimentConfig:', experimentConfig.value)
    console.log('After loading from backend, interactionConfig:', interactionConfig.value)

    // Close modal after successful load
    showLoadSessionModal.value = false

    // Note: WebSocket session join is now managed at researcher.vue level
    // No need to join here - researcher.vue will handle it via watch

    // Navigate to experiment selection tab (or parameters if experiment type is already set)
    if (session.experiment_type) {
      navigateToSetupTab('parameters')
    } else {
      navigateToSetupTab('experimentSelection')
    }
  } catch (error) {
    console.error('Error loading session:', error)
    alert(`Error loading session: ${error.message}`)
  }
}
</script>

<template>
  <div class="tab-col setup-tab">
    <div class="subtab-navigation">
      <div class="subtab-container">
        <div 
          v-for="(step, index) in setupWorkflowSteps" 
          :key="step.id"
          class="subtab-item"
          :class="{ 
            active: activeSetupTab === step.id,
            visible: setupTabs[step.id],
            disabled: !setupTabs[step.id],
            'first': index === 0,
            'last': index === setupWorkflowSteps.length - 1
          }"
          @click="navigateToSetupTab(step.id)"
          v-show="setupTabs[step.id]"
        >
          <div class="subtab-number">{{ index + 1 }}</div>
          <div class="subtab-label">{{ step.label }}</div>
        </div>
      </div>
    </div>

    <div class="setup-content">
      <div class="setup-tabs-container">
        <!-- Tab 1: Initial Selection -->
        <div v-if="setupTabs.initialSelection" class="setup-tab-panel" :class="{ active: activeSetupTab === 'initialSelection' }" data-tab-id="initialSelection">
          <div class="workflow-step">
            <div class="step-content">
              <div class="initial-message">
                <h2>I want to...</h2>
                <div class="initial-options">
                  <button class="initial-option-btn" @click="showLoadSessionModal = true">
                    <div class="option-icon">📂</div>
                    <div class="option-text">Load Existing Session</div>
                  </button>
                  <button class="initial-option-btn" @click="showCreateSessionModal = true">
                    <div class="option-icon">➕</div>
                    <div class="option-text">Create Session</div>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 2: Experiment Selection -->
        <div v-if="setupTabs.experimentSelection" class="setup-tab-panel experiment-selection-tab" :class="{ active: activeSetupTab === 'experimentSelection' }" data-tab-id="experimentSelection">
          <div class="workflow-step">
            <div class="step-content">
              <div class="step-header">
                <div class="step-title">Experiment Selection</div>
                <button v-if="previewedExperiment" @click="confirmExperimentSelection" class="step-btn primary">
                  Select and Configure {{ getPreviewedExperiment()?.name }}
                </button>
              </div>

              <div class="experiment-selection-layout">
                <div class="experiment-selection-left">
                  <!-- Option 1: Existing Experiments -->
                  <div class="experiment-option-section">
                    <div class="option-label">➤ Option 1: Selecting From Existing Experiments</div>
                    
                    <div class="tag-filter-section">
                      <div class="tag-filter-header">
                        <span class="tag-filter-label">Filter by tags:</span>
                        <button v-if="selectedTags.length > 0" @click="clearAllTags" class="clear-tags-btn">Clear all</button>
                      </div>
                      <div class="tag-filter-container">
                        <button
                          v-for="tag in allUniqueTags"
                          :key="tag"
                          @click="toggleTag(tag)"
                          :class="['tag-filter-btn', { active: isTagSelected(tag) }]"
                        >
                          {{ tag }}
                        </button>
                      </div>
                    </div>
                    
                    <div class="experiment-list-container">
                      <div class="experiment-list">
                        <div
                          v-for="exp in filteredExperiments"
                          :key="exp.id"
                          :class="['experiment-list-item', { selected: selectedExperimentType === exp.id }]"
                        >
                          <div 
                            class="experiment-item-header" 
                            @click="toggleExperimentAndPreview(exp.id)"
                            :class="{ previewed: previewedExperiment === exp.id }"
                          >
                            <h3 class="experiment-name">{{ exp.name }}</h3>
                            <svg class="dropdown-icon" :class="{ expanded: isExperimentExpanded(exp.id) }" viewBox="0 0 20 20" fill="currentColor">
                              <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
                            </svg>
                          </div>
                          <div v-if="isExperimentExpanded(exp.id)" class="experiment-item-content">
                            <div class="experiment-tags">
                              <span v-for="tag in exp.tags" :key="tag" class="experiment-tag">{{ tag }}</span>
                            </div>
                            <div class="experiment-description-preview" v-html="getFormattedExperimentDescription(exp.description)"></div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Option 2: Upload Config -->
                  <div class="upload-option-section">
                    <div class="option-label">➤ Option 2: Upload Customized Experiment Configuration File</div>
                    <button @click="triggerFileUpload" class="upload-config-btn" :disabled="isUploadingConfig">
                      <span v-if="isUploadingConfig">Uploading...</span>
                      <span v-else>Upload Config File</span>
                    </button>
                    <input ref="fileInputRef" type="file" accept=".json,.yaml,.yml" @change="handleFileUpload" style="display: none;" />
                    <div v-if="configValidationStatus" class="validation-status" :class="configValidationStatus.type">
                      <span class="validation-message">{{ configValidationStatus.message }}</span>
                    </div>
                  </div>
                </div>

                <!-- Right: Illustration -->
                <div v-if="previewedExperiment || selectedExperimentType" class="experiment-illustration-section">
                  <div class="illustration-header">
                    <h3>Experiment Illustration</h3>
                    <p class="illustration-subtitle">{{ previewedExperiment ? getPreviewedExperiment()?.name : getCurrentExperimentName() }}</p>
                  </div>
                  <div v-if="(previewedExperiment ? getPreviewedExperiment()?.id : selectedExperimentType) === 'shapefactory'" class="experiment-illustration">
                    <img src="../assets/shapefactory_illustration.png" alt="Shape Factory Experiment Illustration" class="illustration-image" />
                  </div>
                  <div v-else class="illustration-placeholder">
                    <div class="placeholder-content">
                      <div class="placeholder-icon"></div>
                      <p>Illustration will appear here</p>
                      <p class="placeholder-subtitle">Visual representation of the {{ previewedExperiment ? 'previewed' : 'selected' }} experiment</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 3: Parameters -->
        <div v-if="setupTabs.parameters" class="setup-tab-panel parameters-tab" :class="{ active: activeSetupTab === 'parameters' }" data-tab-id="parameters">
          <div class="workflow-step">
            <div class="step-content">
              <div class="step-title-row">
                <div class="step-title">Parameters Configuration</div>
                <button class="step-btn primary" @click="confirmParamConfig">Confirm Config</button>
              </div>

              <div class="config-section">
                <!-- Dynamically generated parameter clusters -->
                <div v-for="cluster in getParameterClusters()" :key="cluster.key" class="config-cluster">
                  <div class="cluster-title collapsible" @click="toggleParameterCluster(cluster.key)">
                    <span class="collapse-icon" :class="{ expanded: parameterClustersExpanded[cluster.key] }">▼</span>
                    <span>{{ cluster.name }}</span>
                  </div>
                  <div class="config-grid" v-show="parameterClustersExpanded[cluster.key]">
                    <div v-for="param in cluster.params" :key="getConfigKey(param)" class="config-group" :class="{ 'full-width': param.type === 'file' || param.type === 'input_list' }">
                      <label :for="getConfigKey(param)">
                        {{ param.label }}
                        <span v-if="param.description" class="tooltip-icon" @mouseenter="activeTooltip = getTooltipId(param)" @mousemove="updateTooltipPosition($event)" @mouseleave="activeTooltip = null">ⓘ</span>
                      </label>
                      <div v-if="activeTooltip === getTooltipId(param) && param.description" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">{{ param.description }}</div>
                      
                      <!-- Number input -->
                      <input 
                        v-if="param.type === 'number'" 
                        :type="param.type" 
                        :id="getConfigKey(param)" 
                        :value="getConfigValue(param)"
                        @input="setConfigValue(param, parseFloat($event.target.value) || 0)"
                        @change="updateExperimentConfig"
                        :min="param.min || 0"
                        :max="param.max || 10000"
                        :step="param.step || 1"
                      />
                      
                      <!-- Text input / Textarea (for word list) -->
                      <textarea 
                        v-else-if="param.type === 'input' && (param.path === 'Session.Params.wordList' || param.path === 'Session.wordList')"
                        :id="getConfigKey(param)"
                        v-model="wordAssignmentText"
                        placeholder="Enter words separated by commas"
                        rows="3"
                        @change="updateWordAssignment"
                      />
                      <input 
                        v-else-if="param.type === 'input'"
                        type="text"
                        :id="getConfigKey(param)"
                        :value="getConfigValue(param)"
                        @input="setConfigValue(param, $event.target.value)"
                        @change="updateExperimentConfig"
                      />
                      
                      <!-- Select / List -->
                      <select 
                        v-else-if="param.type === 'list'"
                        :id="getConfigKey(param)"
                        :value="getConfigValue(param)"
                        @change="setConfigValue(param, $event.target.value)"
                        class="config-select"
                      >
                        <option v-for="option in (Array.isArray(param.default) ? param.default : [])" :key="option" :value="option">{{ option }}</option>
                      </select>
                      
                      <!-- Input list (for candidate names) -->
                      <div v-else-if="param.type === 'input_list' && param.path === 'Session.Params.candidateNames'" class="input-list-section">
                        <div class="input-list-container">
                          <div class="input-list-input-group">
                            <input 
                              v-if="editingCandidateIndex === -1"
                              type="text"
                              v-model="candidateNameInput"
                              placeholder="Enter candidate name"
                              class="input-list-input"
                              @keyup.enter="addCandidateName"
                            />
                            <input 
                              v-else
                              type="text"
                              v-model="editingCandidateValue"
                              placeholder="Edit candidate name"
                              class="input-list-input"
                              @keyup.enter="saveCandidateName"
                              @keyup.esc="cancelEditCandidate"
                            />
                            <button 
                              v-if="editingCandidateIndex === -1"
                              type="button" 
                              class="input-list-add-btn" 
                              @click="addCandidateName"
                              :disabled="!candidateNameInput.trim()"
                            >
                              Add
                            </button>
                            <div v-else class="input-list-edit-buttons">
                              <button 
                                type="button" 
                                class="input-list-save-btn" 
                                @click="saveCandidateName"
                                :disabled="!editingCandidateValue.trim()"
                              >
                                Save
                              </button>
                              <button 
                                type="button" 
                                class="input-list-cancel-btn" 
                                @click="cancelEditCandidate"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                          <div v-if="candidateNamesList.length > 0" class="input-list-items">
                            <div 
                              v-for="(name, index) in candidateNamesList" 
                              :key="index" 
                              class="input-list-item"
                            >
                              <span class="input-list-item-text">{{ name }}</span>
                              <div class="input-list-item-actions">
                                <button 
                                  type="button" 
                                  class="input-list-edit-btn" 
                                  @click="startEditCandidate(index)"
                                  title="Edit"
                                >
                                  <i class="fa-solid fa-pencil"></i>
                                </button>
                                <button 
                                  type="button" 
                                  class="input-list-delete-btn" 
                                  @click="removeCandidateName(index)"
                                  title="Delete"
                                >
                                  <i class="fa-solid fa-times"></i>
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      <!-- File upload (for essays) -->
                      <div v-else-if="param.type === 'file' && param.path === 'Session.Params.essays'" class="essay-upload-section">
                      <div class="essay-upload-container">
                          <input 
                            type="file" 
                            ref="essayFileInput" 
                            @change="handleEssayFileUpload" 
                            accept=".pdf" 
                            multiple 
                            style="display: none;" 
                          />
                          <button 
                            type="button" 
                            class="upload-btn" 
                            @click="triggerEssayFileUpload" 
                            :disabled="!isSessionCreated"
                          >
                          <i class="fa-solid fa-upload"></i> Upload PDF Essays
                        </button>
                      </div>
                      <div v-if="uploadedEssays.length > 0" class="uploaded-essays-list">
                        <h4>Uploaded Essays:</h4>
                        <div v-for="(essay, index) in uploadedEssays" :key="essay.essay_id || essay.id" class="essay-item">
                          <div class="essay-info">
                            <i class="fa-solid fa-file-pdf"></i>
                            <span class="essay-title">{{ essay.original_filename || essay.title || essay.filename }}</span>
                          </div>
                          <button type="button" class="remove-essay-btn" @click="removeEssay(index)">
                            <i class="fa-solid fa-times"></i>
                          </button>
                        </div>
                        </div>
                      </div>
                      
                      <!-- File upload (for candidate documents) -->
                      <div v-else-if="param.type === 'file' && param.path === 'Session.Params.candidateDocuments'" class="essay-upload-section">
                      <div class="essay-upload-container">
                          <input 
                            type="file" 
                            ref="candidateDocumentsFileInput" 
                            @change="handleCandidateDocumentsUpload" 
                            accept=".pdf" 
                            multiple 
                            style="display: none;" 
                          />
                          <button 
                            type="button" 
                            class="upload-btn" 
                            @click="triggerCandidateDocumentsUpload" 
                            :disabled="!isSessionCreated"
                          >
                          <i class="fa-solid fa-upload"></i> Upload Candidate Documents
                        </button>
                      </div>
                      <div v-if="uploadedCandidateDocuments.length > 0" class="uploaded-essays-list">
                        <h4>Uploaded Documents:</h4>
                        <div v-for="(doc, index) in uploadedCandidateDocuments" :key="doc.id || doc.filename || index" class="essay-item">
                          <div class="essay-info">
                            <i class="fa-solid fa-file-pdf"></i>
                            <span class="essay-title">{{ doc.original_filename || doc.filename || doc.name || `Document ${index + 1}` }}</span>
                          </div>
                          <button type="button" class="remove-essay-btn" @click="removeCandidateDocument(index)">
                            <i class="fa-solid fa-times"></i>
                          </button>
                        </div>
                        </div>
                      </div>

                      <!-- File upload (for maps) -->
                      <div v-else-if="param.type === 'file' && param.path === 'Session.Params.maps'" class="essay-upload-section">
                        <div class="essay-upload-container">
                          <input 
                            type="file" 
                            ref="mapsFileInput" 
                            @change="handleMapsUpload" 
                            accept="image/*,.pdf,.txt" 
                            multiple 
                            style="display: none;" 
                          />
                          <button 
                            type="button" 
                            class="upload-btn" 
                            @click="triggerMapsUpload" 
                            :disabled="!isSessionCreated"
                          >
                            <i class="fa-solid fa-upload"></i> Upload Maps
                          </button>
                        </div>
                        <div v-if="uploadedMaps.length > 0" class="uploaded-essays-list">
                          <h4>Uploaded Maps:</h4>
                          <div v-for="(map, index) in uploadedMaps" :key="map.id || map.filename || index" class="essay-item map-item">
                            <div class="essay-info">
                              <i class="fa-solid fa-map"></i>
                              <span class="essay-title">{{ map.original_filename || map.filename || `Map ${index + 1}` }}</span>
                            </div>
                            <div class="map-role-select">
                              <select 
                                class="select-small" 
                                :value="map.role || 'guider'"
                                @change="updateMapRole(index, $event.target.value)"
                              >
                                <option value="guider">Guider</option>
                                <option value="follower">Follower</option>
                              </select>
                            </div>
                            <button type="button" class="remove-essay-btn" @click="removeMap(index)">
                              <i class="fa-solid fa-times"></i>
                            </button>
                          </div>
                        </div>
                      </div>
                      
                      <!-- Helper text for word list -->
                      <div v-if="param.path === 'Session.Params.wordList' || param.path === 'Session.wordList'" class="form-helper">
                        Words will be automatically assigned to hinter participants when you register them.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 4: Interaction Variables -->
        <div v-if="setupTabs.interactionVariables" class="setup-tab-panel interaction-variables-tab" :class="{ active: activeSetupTab === 'interactionVariables' }" data-tab-id="interactionVariables">
          <div class="workflow-step">
            <div class="step-content">
              <div class="step-title-row">
                <div class="step-title">Interaction Controls</div>
                <button class="step-btn primary" @click="confirmInteractionControl">Confirm Interaction Control</button>
              </div>
              
              <div class="interaction-variables-layout">
                <div class="variables-column">
                  <!-- Dynamically generated interaction clusters -->
                  <div v-for="cluster in getInteractionClusters()" :key="cluster.key" :class="[cluster.key + '-section']" class="interaction-section">
                    <div class="cluster-title collapsible" @click="toggleInteractionSection(cluster.key)">
                      <span class="collapse-icon" :class="{ expanded: interactionSectionsExpanded[cluster.key] }">▼</span>
                      <span>{{ cluster.name }}</span>
                    </div>
                    <div class="variables-grid" v-show="interactionSectionsExpanded[cluster.key]">
                      <div v-for="param in cluster.params" :key="getConfigKey(param)" class="variable-group" :class="{ 'clickable-entry': param.label === 'Communication Level' || param.label === 'Awareness Dashboard' || param.label === 'Communication Media', 'selected': selectedInteractionEntry === getConfigKey(param) }" @click="(param.type === 'list' || param.type === 'tiered_checkbox' || param.type === 'multi_checkbox') && selectInteractionEntry(getConfigKey(param))">
                        <label :for="getConfigKey(param)">
                          {{ param.label }}
                          <span v-if="param.description" class="tooltip-icon" @mouseenter="activeTooltip = getTooltipId(param)" @mousemove="updateTooltipPosition($event)" @mouseleave="activeTooltip = null">ⓘ</span>
                        </label>
                        <div v-if="activeTooltip === getTooltipId(param) && param.description" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">{{ param.description }}</div>
                        
                        <!-- List type (dropdown) -->
                        <div v-if="param.type === 'list'" class="custom-select-wrapper">
                          <div class="custom-select-trigger" @click.stop="selectInteractionEntry(getConfigKey(param)); toggleInteractionDropdown(param)">
                            <div class="selected-content">
                              <span class="selected-option" :class="getNormalizedValueForClass(param)">
                                {{ getListOptions(param).find(opt => opt.value === getInteractionValue(param))?.label || getInteractionValue(param) }}
                              </span>
                            </div>
                            <span class="dropdown-arrow">▼</span>
                          </div>
                          <div class="custom-dropdown-menu" v-if="showCommDropdown[getConfigKey(param)]">
                            <div v-for="option in getListOptions(param)" :key="option.value" class="dropdown-item" @click.stop="selectInteractionEntry(getConfigKey(param)); selectListOption(param, option.value)">
                              <div class="option-content">
                                <span class="option-tag" :class="option.value">{{ option.label }}</span>
                              </div>
                            </div>
                          </div>
                          <div class="communication-description">
                            {{ getListOptions(param).find(opt => opt.value === getInteractionValue(param))?.description || '' }}
                        </div>
                      </div>
                      
                        <!-- Boolean type (toggle switch) -->
                        <div v-else-if="param.type === 'boolean'" class="toggle-switch">
                          <input 
                            type="checkbox" 
                            :id="getConfigKey(param) + '-toggle'" 
                            :checked="getInteractionValue(param) === (param.options?.[0]?.toLowerCase().replace(/\s+/g, '_') || 'true')"
                            @change="setInteractionValue(param, $event.target.checked ? (param.options?.[0]?.toLowerCase().replace(/\s+/g, '_') || 'true') : (param.options?.[1]?.toLowerCase().replace(/\s+/g, '_') || 'false'))"
                            class="toggle-input" 
                          />
                          <label :for="getConfigKey(param) + '-toggle'" class="toggle-label">
                            <span class="toggle-text off-text">{{ param.options?.[0]?.toUpperCase() || 'ON' }}</span>
                            <span class="toggle-text on-text">{{ param.options?.[1]?.toUpperCase() || 'OFF' }}</span>
                            <span class="toggle-slider"><span class="toggle-indicator"></span></span>
                        </label>
                        </div>
                        
                        <!-- Tiered checkbox type -->
                        <div v-else-if="param.type === 'tiered_checkbox'">
                          <div class="toggle-switch" @click.stop="selectInteractionEntry(getConfigKey(param)); toggleTieredCheckboxEnabled(param)">
                            <input 
                              type="checkbox" 
                              :id="getConfigKey(param) + '-toggle'" 
                              :checked="getInteractionValue(param)?.enabled"
                              @change.stop="selectInteractionEntry(getConfigKey(param)); toggleTieredCheckboxEnabled(param)"
                              class="toggle-input" 
                            />
                            <label :for="getConfigKey(param) + '-toggle'" class="toggle-label">
                            <span class="toggle-text off-text">ON</span>
                            <span class="toggle-text on-text">OFF</span>
                            <span class="toggle-slider"><span class="toggle-indicator"></span></span>
                          </label>
                        </div>
                          <div v-if="getInteractionValue(param)?.enabled" class="awareness-options">
                          <div class="options-row">
                              <label v-for="(option, index) in param.options" :key="index" class="option-item">
                                <input 
                                  type="checkbox" 
                                  :checked="isTieredCheckboxItemSelected(param, index)"
                                  @change="toggleTieredCheckboxItem(param, index)"
                                />
                                <span>{{ option.label }}</span>
                            </label>
                      </div>
                    </div>
                  </div>
                  
                        <!-- Multi checkbox type (Communication Media) -->
                        <div v-else-if="param.type === 'multi_checkbox'" class="multi-checkbox-options">
                          <div v-for="option in getMultiCheckboxOptions(param)" :key="option.value" class="option-item">
                            <label>
                              <input 
                                type="checkbox" 
                                :checked="isMultiCheckboxItemSelected(param, option.value)"
                                @change="toggleMultiCheckboxItem(param, option.value)"
                              />
                              <span>{{ option.label }}</span>
                            </label>
                            <span v-if="option.description" class="option-desc">{{ option.description }}</span>
                          </div>
                        </div>
                        
                        <!-- Boolean number type (toggle + number input, same style as rationales) -->
                        <div v-else-if="param.type === 'boolean_number'">
                          <div class="toggle-switch" @click.stop="toggleBooleanNumberEnabled(param)">
                            <input 
                              type="checkbox" 
                              :id="getConfigKey(param) + '-bn-toggle'" 
                              :checked="getInteractionValue(param)?.enabled"
                              @change.stop="toggleBooleanNumberEnabled(param)"
                              class="toggle-input" 
                            />
                            <label :for="getConfigKey(param) + '-bn-toggle'" class="toggle-label">
                              <span class="toggle-text off-text">ON</span>
                              <span class="toggle-text on-text">OFF</span>
                              <span class="toggle-slider"><span class="toggle-indicator"></span></span>
                            </label>
                          </div>
                          <div v-if="getInteractionValue(param)?.enabled" class="boolean-number-input-wrap">
                            <input 
                              type="number" 
                              :id="getConfigKey(param) + '-value'" 
                              :value="getInteractionValue(param)?.value ?? 100"
                              @input="setBooleanNumberValue(param, parseFloat($event.target.value) || 0)"
                              @change="updateExperimentConfig"
                              min="1"
                              max="1000"
                              class="config-input-small"
                            />
                            <span class="boolean-number-suffix">words</span>
                          </div>
                        </div>
                        
                        <!-- Number type -->
                        <div v-else-if="param.type === 'number'" class="config-group">
                          <input 
                            type="number" 
                            :id="getConfigKey(param)" 
                            :value="getInteractionValue(param)"
                            @input="setInteractionValue(param, parseFloat($event.target.value) || 0)"
                            @change="updateExperimentConfig"
                            :min="param.min || 0"
                            :max="param.max || 10000"
                            :step="param.step || 1"
                          />
                    </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Preview Column -->
                <div class="preview-column">
                  <div class="section-title">Preview</div>
                  <div class="conditional-preview">
                    <template v-if="selectedInteractionEntry && getCurrentExperimentInteraction">
                      <template v-for="cluster in getInteractionClusters()" :key="cluster.key">
                        <template v-for="param in cluster.params" :key="getConfigKey(param)">
                          <!-- Communication Preview -->
                          <div v-if="selectedInteractionEntry === getConfigKey(param) && param.type === 'list'" class="preview-component">
                            <div v-if="getInteractionValue(param) === 'private_messaging'" class="panel">
                              <div class="panel-body">
                                <div class="chat-mode">
                                  <div class="message-thread">
                                    <div class="message-history">
                                      <div class="message-item other-message">
                                        <div class="message-sender">Player1</div>
                                        <div class="message-content">Hello, want to trade?</div>
                                        <div class="message-time">10:30</div>
                                      </div>
                                      <div class="message-item my-message">
                                        <div class="message-sender">Me</div>
                                        <div class="message-content">Sure, what do you need?</div>
                                        <div class="message-time">10:32</div>
                                      </div>
                                    </div>
                                  </div>
                                  <div class="message-input-area">
                                    <input type="text" placeholder="Type your message..." class="message-input" />
                                    <button class="send-btn">Send</button>
                                  </div>
                                </div>
                              </div>
                            </div>
                            <div v-else-if="getInteractionValue(param) === 'group_chat'" class="panel">
                              <div class="panel-body">
                                <div class="group-chat-mode">
                                  <div class="message-thread">
                                    <div class="message-history">
                                      <div class="message-item group-chat-message other-message">
                                        <div class="message-sender">Player1</div>
                                        <div class="message-content">Anyone want to trade circles?</div>
                                        <div class="message-time">10:30</div>
                                      </div>
                                      <div class="message-item group-chat-message my-message">
                                        <div class="message-sender">Me</div>
                                        <div class="message-content">I have circles, need squares</div>
                                        <div class="message-time">10:32</div>
                                      </div>
                                    </div>
                                  </div>
                                  <div class="message-input-area">
                                    <input type="text" placeholder="Type your group chat message..." class="message-input" />
                                    <button class="send-btn">Send</button>
                                  </div>
                                </div>
                              </div>
                            </div>
                            <div v-else class="no-preview">
                              <p>No communication preview available</p>
                            </div>
                          </div>
                          
                          <!-- Awareness Preview -->
                          <div v-else-if="selectedInteractionEntry === getConfigKey(param) && param.type === 'tiered_checkbox'" class="preview-component">
                            <BaseParticipantStatusComponent v-if="getAwarenessDashboardPreviewConfig" :config="getAwarenessDashboardPreviewConfig" />
                            <div v-else class="no-preview">
                              <p>Select information items to see preview</p>
                            </div>
                          </div>
                          <!-- Communication Media Preview -->
                          <div v-else-if="selectedInteractionEntry === getConfigKey(param) && param.type === 'multi_checkbox'" class="preview-component">
                            <div class="panel">
                              <div class="panel-body">
                                <div class="chat-mode">
                                  <div class="message-thread">
                                    <div class="message-history">
                                      <div class="message-item other-message">
                                        <div class="message-sender">Player1</div>
                                        <div class="message-content">Hello!</div>
                                        <div class="message-time">10:30</div>
                                      </div>
                                    </div>
                                  </div>
                                  <div class="message-input-area">
                                    <input type="text" placeholder="Type your message..." class="message-input" v-if="(getInteractionValue(param) || []).includes('text')" />
                                    <button v-if="(getInteractionValue(param) || []).includes('audio')" class="voice-btn" title="Voice input"><i class="fa-solid fa-microphone"></i></button>
                                    <button v-if="(getInteractionValue(param) || []).includes('meeting_room')" class="meeting-btn" title="Meeting room"><i class="fa-solid fa-users-rectangle"></i></button>
                                    <button class="send-btn">Send</button>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        </template>
                      </template>
                    </template>
                    
                    <!-- No Selection -->
                    <div v-else class="no-preview">
                      <p>Select an interaction control to see its preview</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 5: Participant Registration -->
        <div v-if="setupTabs.participantRegistration" class="setup-tab-panel" :class="{ active: activeSetupTab === 'participantRegistration' }" data-tab-id="participantRegistration">
          <div class="workflow-step">
            <div class="step-content">
              <div class="step-title-row">
                <div class="step-title">Participant Registration</div>
              </div>
              
              <div class="participants-manage">
                <div class="manage-forms">
                  <div class="form-card">
                    <div class="card-title">Individual Participant Registration</div>
                    <div class="form-grid">
                      <!-- Dynamically render fields based on participant config -->
                      <template v-if="getParticipantConfig">
                        <!-- Loop through config fields (excluding experiment_params and id) -->
                        <template v-for="(fieldConfig, fieldKey) in getParticipantConfig" :key="fieldKey">
                          <!-- Skip id field as it's auto-generated by backend -->
                          <div v-if="fieldKey !== 'id'" class="form-field-wrapper">
                            <!-- Dropdown for fields with options -->
                            <select 
                              v-if="fieldConfig.options && Array.isArray(fieldConfig.options)"
                              class="select" 
                              v-model="participantForm[fieldKey]"
                              required
                            >
                              <option value="">{{ fieldKey === 'type' ? 'Type' : fieldKey === 'specialty' ? 'Specialty' : `Select ${fieldKey}` }}</option>
                              <option 
                                v-for="option in fieldConfig.options" 
                                :key="option" 
                                :value="option"
                              >
                                {{ fieldKey === 'type' ? (option === 'ai' ? 'AI Agent' : 'Human') : 
                                   fieldKey === 'specialty' && option === 'auto-assign' ? 'Auto-Assign' :
                                   option.charAt(0).toUpperCase() + option.slice(1) }}
                              </option>
                            </select>
                            
                            <!-- Input for fields without options -->
                            <input 
                              v-else
                              class="input" 
                              v-model="participantForm[fieldKey]" 
                              :placeholder="fieldKey === 'name' ? 'Participant ID & Display Name' : fieldKey"
                              required
                            />
                          </div>
                        </template>
                        
                        <!-- Agent Persona field (only for AI type) - spans full width -->
                        <div v-if="participantForm.type === 'ai' || participantForm.type === 'ai_agent'" class="form-field-wrapper form-field-full-width">
                          <div class="form-group">
                            <label>Agent Persona</label>
                            <textarea 
                              v-model="participantForm.persona" 
                              class="form-input"
                              rows="6"
                            ></textarea>
                            <small class="form-help">A random MBTI personality has been assigned. You can edit this if needed.</small>
                          </div>
                        </div>
                        
                        <!-- Register button - always shown, aligned to right -->
                        <div class="form-field-wrapper form-field-button">
                          <button class="btn primary" @click="onRegisterParticipant" :disabled="!canRegisterParticipant">Register</button>
                        </div>
                      </template>
                      
                      <div v-else class="form-helper form-field-full-width">⚠️ Please select an experiment first</div>
                      <div v-if="!isSessionCreated" class="form-helper form-field-full-width">⚠️ Create or load a session first to enable participant registration</div>
                    </div>
                  </div>
                  
                  <!-- Agent Auto Registration -->
                  <div class="form-card" style="margin-top: 20px;">
                    <div class="card-title">Agent Auto Registration</div>
                    <div class="form-grid">
                      <template v-if="getParticipantConfig">
                        <div class="form-field-wrapper">
                          <input 
                            class="input" 
                            type="number"
                            v-model.number="agentAutoRegistrationCount" 
                            placeholder="Number of agents to register"
                            min="1"
                            max="100"
                            required
                          />
                        </div>
                        <div class="form-field-wrapper form-field-button">
                          <button 
                            class="btn primary" 
                            @click="onAutoRegisterAgents" 
                            :disabled="!isSessionCreated || !canRegisterParticipant || isAutoRegistering"
                          >
                            {{ isAutoRegistering ? 'Registering...' : 'Register' }}
                          </button>
                        </div>
                      </template>
                      <div v-else class="form-helper form-field-full-width">⚠️ Please select an experiment first</div>
                      <div v-if="!isSessionCreated" class="form-helper form-field-full-width">⚠️ Create or load a session first to enable participant registration</div>
                    </div>
                  </div>
                </div>

                <div class="table-section">
                  <div class="section-title">
                    Registered Participants
                    <button class="grouping-btn" @click="showGroupingModal = true" title="Manage participant groups">Grouping</button>
                  </div>
                  <div class="manage-table">
                    <div class="table-head">
                      <div class="th code">Display Name</div>
                      <div class="th type">Type</div>
                      <div v-if="showShapeParameters" class="th specialty">Specialty</div>
                      <div v-if="selectedExperimentType === 'wordguessing' || selectedExperimentType === 'maptask'" class="th role">Role</div>
                      <div v-if="selectedExperimentType === 'hiddenprofile'" class="th doc-assign">Doc. Assign</div>
                      <div class="th group">Group</div>
                      <div class="th actions">Actions</div>
                    </div>
                    <div class="table-body">
                      <div class="tr" v-for="p in participants" :key="p.id">
                        <div class="td code">{{ getDisplayName(p.id) }}</div>
                        <div class="td type">
                          <span :class="['type-icon', p.type]" :title="p.type === 'ai' || p.type === 'ai_agent' ? 'AI Agent' : 'Human'">
                            <i v-if="p.type === 'ai' || p.type === 'ai_agent'" class="fa-solid fa-robot"></i>
                            <i v-else class="fa-solid fa-user"></i>
                          </span>
                        </div>
                        <div v-if="showShapeParameters" class="td specialty">
                          <span class="specialty-badge">{{ p.specialty || '-' }}</span>
                        </div>
                        <div v-if="selectedExperimentType === 'wordguessing' || selectedExperimentType === 'maptask'" class="td role">
                          <span v-if="p.role" class="role-badge" :class="p.role">{{ p.role }}</span>
                          <span v-else class="no-role">-</span>
                        </div>
                        <div v-if="selectedExperimentType === 'hiddenprofile'" class="td doc-assign">
                          <select 
                            class="select-small" 
                            :value="getDocumentIdentifier(p.experiment_params?.candidate_document)"
                            @change="onUpdateParticipantDocument(p.id, $event.target.value)"
                          >
                            <option value="">Select Document</option>
                            <option 
                              v-for="(doc, index) in candidateDocumentsList" 
                              :key="getDocumentIdentifier(doc) || index" 
                              :value="getDocumentIdentifier(doc)"
                            >
                              {{ getDocumentDisplayName(doc) }}
                            </option>
                          </select>
                        </div>
                        <div class="td group">
                          <span v-if="getParticipantGroup(p.id)" class="group-badge">{{ getParticipantGroup(p.id) }}</span>
                          <span v-else class="no-group">-</span>
                        </div>
                        <div class="td actions">
                          <button class="btn-icon edit" @click="onEditParticipant(p)" title="Edit participant">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: block;">
                              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                              <path d="m18.5 2.5 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                            </svg>
                          </button>
                          <button class="btn-icon danger" @click="onDeleteParticipant(p.id)" title="Delete participant">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: block;">
                              <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Auto Start Toggle -->
                <div class="variable-group" style="margin-top: 20px;">
                  <label for="auto-start-toggle">
                    Auto Start
                  </label>
                  <div class="toggle-switch">
                    <input 
                      type="checkbox" 
                      id="auto-start-toggle"
                      :checked="autoStartEnabled"
                      @change="updateAutoStartSetting"
                      :disabled="!isSessionCreated"
                      class="toggle-input" 
                    />
                    <label for="auto-start-toggle" class="toggle-label">
                      <span class="toggle-text off-text">ENABLED</span>
                      <span class="toggle-text on-text">NOT ENABLED</span>
                      <span class="toggle-slider"><span class="toggle-indicator"></span></span>
                    </label>
                  </div>
                </div>

                <!-- In-session Annotation Toggle -->
                <div class="variable-group" style="margin-top: 20px;">
                  <label for="annotation-toggle">
                    In-session Annotation Checkpoints
                  </label>
                  <div class="toggle-switch">
                    <input 
                      type="checkbox" 
                      id="annotation-toggle"
                      :checked="annotationEnabled"
                      @change="updateAnnotationSetting"
                      :disabled="!isSessionCreated"
                      class="toggle-input" 
                    />
                    <label for="annotation-toggle" class="toggle-label">
                      <span class="toggle-text off-text">ENABLED</span>
                      <span class="toggle-text on-text">NOT ENABLED</span>
                      <span class="toggle-slider"><span class="toggle-indicator"></span></span>
                    </label>
                  </div>
                  <small class="form-help">Triggers Quick Checking pop-ups at 20-25%, 45-50%, 70-75% of session when participants perform key actions</small>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 6: MTurk Panel -->
        <div v-if="setupTabs.mturkPanel" class="setup-tab-panel" :class="{ active: activeSetupTab === 'mturkPanel' }" data-tab-id="mturkPanel">
          <div class="workflow-step">
            <div class="step-content">
              <div class="step-title-row">
                <div class="step-title">MTurk Panel (Optional)</div>
              </div>
              <MturkPanel
                :session-name="currentSessionName"
                :session-id="currentSessionId"
                :is-session-created="isSessionCreated"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Load Session Modal -->
  <div v-if="showLoadSessionModal" class="modal-overlay" @click="showLoadSessionModal = false">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>Load Session</h3>
        <button class="modal-close" @click="showLoadSessionModal = false">×</button>
      </div>
    <div class="modal-body">
      <div class="form-group">
        <label>Session Name</label>
        <input type="text" placeholder="Enter session name" class="form-input" v-model="sessionName" required />
        </div>
      </div>
      <div class="modal-footer">
        <button class="modal-btn secondary" @click="showLoadSessionModal = false">Cancel</button>
        <button class="modal-btn primary" @click="loadSessionFromName">Load</button>
      </div>
    </div>
  </div>

  <!-- Create Session Modal -->
  <div v-if="showCreateSessionModal" class="modal-overlay" @click="showCreateSessionModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create Session</h3>
          <button class="modal-close" @click="showCreateSessionModal = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Session Name</label>
            <input 
              type="text" 
              placeholder="Enter session name"
              class="form-input"
              v-model="sessionName"
              required
            />
            <small class="form-help">This session will use all current parameter settings</small>
          </div>
        </div>
        <div class="modal-footer">
          <button class="modal-btn secondary" @click="showCreateSessionModal = false">Cancel</button>
          <button 
            class="modal-btn primary" 
            @click="createSession" 
          >
            Create
          </button>
        </div>
      </div>
    </div>

    <!-- Edit Participant Modal -->
    <div v-if="showEditModal" class="modal-overlay" @click="closeEditModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Edit Participant</h3>
          <button class="modal-close" @click="closeEditModal">×</button>
        </div>
        <div class="modal-body">
          <div class="edit-form">
            <!-- Dynamically render fields based on participant config -->
            <template v-if="getParticipantConfig">
              <!-- Loop through config fields (excluding experiment_params and id) -->
              <template v-for="(fieldConfig, fieldKey) in getParticipantConfig" :key="fieldKey">
                <!-- Skip id field in edit form -->
                <div 
                  v-if="fieldKey !== 'id'"
                  class="form-group"
                >
                  <label>{{ fieldKey === 'name' ? 'Display Name' : fieldKey.charAt(0).toUpperCase() + fieldKey.slice(1) }}</label>
                  
                  <!-- Type field is read-only -->
                  <input 
                    v-if="fieldKey === 'type'"
                    type="text" 
                    :value="editForm.type === 'ai' || editForm.type === 'ai_agent' ? 'AI Agent' : 'Human'" 
                    :disabled="true"
                    class="form-input disabled"
                  />
                  
                  <!-- Dropdown for fields with options (except type) -->
                  <select 
                    v-else-if="fieldConfig.options && Array.isArray(fieldConfig.options)"
                    v-model="editForm[fieldKey]" 
                    class="form-select"
                  >
                    <option value="">{{ `Select ${fieldKey}` }}</option>
                    <option 
                      v-for="option in fieldConfig.options" 
                      :key="option" 
                      :value="option"
                    >
                      {{ option.charAt(0).toUpperCase() + option.slice(1) }}
                    </option>
                  </select>
                  
                  <!-- Input for fields without options -->
                  <input 
                    v-else
                    type="text" 
                    v-model="editForm[fieldKey]" 
                    :placeholder="`Enter ${fieldKey}`"
                    class="form-input"
                  />
                  
                  <small v-if="fieldKey === 'type'" class="form-help">Participant type cannot be changed</small>
                </div>
              </template>
              
              <!-- Agent Persona field (only for AI type) -->
              <div class="form-group" v-if="editForm.type === 'ai' || editForm.type === 'ai_agent'">
                <label>Agent Persona</label>
                <textarea 
                  v-model="editForm.persona" 
                  placeholder="Enter agent persona description (optional)"
                  class="form-input"
                  rows="6"
                ></textarea>
                <small class="form-help">The personality is randomly assigned by default.</small>
              </div>
            </template>
            
            <div v-else class="form-helper">⚠️ Please select an experiment type first</div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn secondary" @click="closeEditModal">Cancel</button>
          <button class="btn primary" @click="saveEditParticipant" :disabled="isSavingEdit">Save Changes</button>
        </div>
      </div>
    </div>

    <!-- Grouping Modal -->
    <div v-if="showGroupingModal" class="modal-overlay" @click="closeGroupingModal">
      <div class="modal-content grouping-modal" @click.stop>
        <div class="modal-header">
          <h3>Participant Grouping</h3>
          <button class="modal-close" @click="closeGroupingModal">×</button>
        </div>
        <div class="modal-body">
          <!-- Create New Group -->
          <div class="section-container">
            <h4 class="section-title">Create New Group</h4>
            <div class="form-group">
              <div class="input-group">
                <input 
                  type="text" 
                  v-model="newGroupName" 
                  placeholder="Enter group name"
                  class="form-input"
                  @keyup.enter="createGroup"
                />
                <button class="btn primary" @click="createGroup" :disabled="!newGroupName.trim()">Create</button>
              </div>
            </div>
          </div>

          <!-- Group Management -->
          <div class="section-container" v-if="Object.keys(groups).length > 0">
            <h4 class="section-title">Existing Groups</h4>
            <div class="groups-list">
              <div v-for="(participantIds, groupName) in groups" :key="groupName" class="group-item">
                <div class="group-header">
                  <span class="group-name">{{ groupName }} ({{ participantIds.length }} participants)</span>
                  <button class="btn-icon danger" @click="deleteGroup(groupName)" title="Delete group">×</button>
                </div>
                <div class="group-participants" v-if="participantIds.length > 0">
                  <div v-for="participantId in participantIds" :key="participantId" class="participant-tag">
                    {{ getDisplayName(participantId) }}
                    <button class="remove-btn" @click="removeParticipantFromGroup(groupName, participantId)">×</button>
                  </div>
                </div>
                <div v-else class="empty-group">
                  No participants in this group
                </div>
              </div>
            </div>
          </div>

          <!-- Add Participants to Group -->
          <div class="section-container">
            <h4 class="section-title">Add Participants to Group</h4>
            <div class="form-group">
              <label>Select Group</label>
              <select v-model="selectedGroup" class="form-select">
                <option value="">Choose a group...</option>
                <option v-for="groupName in Object.keys(groups)" :key="groupName" :value="groupName">{{ groupName }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>Select Participants</label>
              <div class="participants-checkboxes">
                <label v-for="participant in participants" :key="participant.id" class="checkbox-label">
                  <input 
                    type="checkbox" 
                    :value="participant.id" 
                    v-model="selectedParticipants"
                  />
                  {{ getDisplayName(participant.id) }} ({{ participant.type === 'ai' || participant.type === 'ai_agent' ? 'AI' : 'Human' }})
                </label>
              </div>
            </div>
            <div class="form-actions">
              <button 
                class="btn primary" 
                @click="addParticipantsToGroup" 
                :disabled="!selectedGroup || selectedParticipants.length === 0"
              >
                Add to Group
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
</template>

<style scoped>
/* Setup Tab Progressive Workflow Styles */
.setup-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.subtab-navigation {
  background: #f8fafc;
  padding: 8px;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f1f5f9;
  flex-shrink: 0;
}

.subtab-navigation::-webkit-scrollbar {
  height: 6px;
}

.subtab-navigation::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.subtab-navigation::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.subtab-navigation::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.subtab-container {
  display: flex;
  width: 100%;
  gap: 0;
}

.subtab-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px 8px 30px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  flex: 1;
  position: relative;
  clip-path: polygon(0% 0%, calc(100% - 25px) 0%, 100% 50%, calc(100% - 25px) 100%, 0% 100%, 25px 50%);
  margin-left: -15px;
}

.subtab-item.first {
  clip-path: polygon(0% 0%, calc(100% - 25px) 0%, 100% 50%, calc(100% - 25px) 100%, 0% 100%);
  margin-left: 0;
  padding-left: 16px;
}

.subtab-item.last {
  clip-path: polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%, 25px 50%);
  padding-right: 16px;
}

.subtab-item:hover {
  background: #f1f5f9;
  z-index: 2;
}

.subtab-item.active {
  background: #2563eb;
  color: #ffffff;
  border-color: #2563eb;
  z-index: 3;
}

.subtab-item.completed {
  background: #10b981;
  color: #ffffff;
  border-color: #10b981;
}

.subtab-item.disabled {
  background: #f8fafc;
  color: #94a3b8;
  cursor: not-allowed;
  border-color: #e2e8f0;
  opacity: 0.5;
}

.subtab-item.visible {
  opacity: 1;
}

.subtab-number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.2);
}

.subtab-item.active .subtab-number,
.subtab-item.completed .subtab-number {
  background: rgba(255, 255, 255, 0.3);
}

.subtab-item.disabled .subtab-number {
  background: #e2e8f0;
  color: #94a3b8;
}

.subtab-label {
  font-size: 14px;
  font-weight: 500;
}

.setup-content {
  flex: 1;
  padding: 12px 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.setup-tabs-container {
  display: flex;
  height: 100%;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f1f5f9;
  gap: 12px;
  align-items: stretch;
  min-height: 0;
}

.setup-tabs-container::-webkit-scrollbar {
  height: 6px;
}

.setup-tabs-container::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.setup-tabs-container::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.setup-tabs-container::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.setup-tab-panel {
  flex: 0 0 33%;
  min-width: 33%;
  max-width: 33%;
  height: 100%;
  max-height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  box-sizing: border-box;
}

/* Parameters tab - twice the width */
.setup-tab-panel.experiment-selection-tab {
  flex: 0 0 66%;
  min-width: 66%;
  max-width: 66%;
}

.setup-tab-panel.interaction-variables-tab {
  flex: 0 0 66%;
  min-width: 66%;
  max-width: 66%;
}

.setup-tab-panel.active {
  display: block;
}

/* Workflow Step Styles */
.workflow-step {
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.step-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
  padding: 0 12px;
  overflow: hidden;
}

.step-header,
.step-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.step-title {
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
  border-bottom: 2px solid #e5e7eb;
  padding-bottom: 6px;
}

.step-btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.step-btn.primary {
  background: #2563eb;
  color: white;
}

.step-btn.primary:hover {
  background: #1d4ed8;
}

/* Initial Selection */
.initial-message h2 {
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 32px;
  padding: 0 12px;
}

.initial-options {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.initial-option-btn {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: #ffffff;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
}

.initial-option-btn:hover {
  border-color: #2563eb;
  background: #f8fafc;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.option-icon {
  font-size: 24px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f3f4f6;
  border-radius: 8px;
}

.option-text {
  font-size: 16px;
  font-weight: 500;
  color: #374151;
}

/* Experiment Selection */
.experiment-selection-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  overflow-y: auto;
}

.experiment-selection-left {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.experiment-option-section,
.upload-option-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.option-label {
  font-weight: 600;
  color: #374151;
  font-size: 14px;
  text-align: left;
}

.tag-filter-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tag-filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tag-filter-label {
  font-size: 13px;
  color: #6b7280;
}

.clear-tags-btn {
  padding: 4px 8px;
  font-size: 12px;
  background: transparent;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  cursor: pointer;
  color: #6b7280;
}

.clear-tags-btn:hover {
  background: #f3f4f6;
}

.tag-filter-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-filter-btn {
  padding: 4px 12px;
  font-size: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-filter-btn:hover {
  background: #f3f4f6;
}

.tag-filter-btn.active {
  background: #2563eb;
  color: white;
  border-color: #2563eb;
}

.experiment-list-container {
  width: 100%;
}

.experiment-list {
    display: flex;
    flex-direction: column;
    max-height: 400px;
    overflow-y: auto;
    border: 1px solid #e5e7eb;
    border-radius: 0 0 8px 8px;
    background: #ffffff;
}

.experiment-list-item {
    border-bottom: 1px solid #e5e7eb;
    transition: all 0.2s ease;
    position: relative;
}

.experiment-list-item.selected {
  border-color: #2563eb;
  background: #eff6ff;
}

.experiment-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  cursor: pointer;
  background: white;
}

.experiment-item-header:hover {
  background: #f9fafb;
}

.experiment-item-header.previewed {
  background: #eff6ff;
}

.experiment-list-item:last-child {
    border-bottom: none;
}

.experiment-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.dropdown-icon {
  width: 16px;
  height: 16px;
  transition: transform 0.2s;
}

.dropdown-icon.expanded {
  transform: rotate(180deg);
}

.experiment-item-content {
  padding: 12px;
  background: #f9fafb;
  border-top: 1px solid #e5e7eb;
}

.experiment-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.experiment-tag {
  padding: 2px 8px;
  font-size: 11px;
  background: #e5e7eb;
  border-radius: 12px;
  color: #6b7280;
}

.experiment-description-preview {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
  text-align: left;
}

.upload-config-btn {
  padding: 10px 16px;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.upload-config-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.upload-config-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.validation-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  font-size: 13px;
  margin-top: 8px;
}

.validation-status.success {
  background: #d1fae5;
  color: #065f46;
}

.validation-status.error {
  background: #fee2e2;
  color: #991b1b;
}

.experiment-illustration-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  height: fit-content;
}

.illustration-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 4px 0;
}

.illustration-subtitle {
  font-size: 13px;
  color: #6b7280;
  margin: 0;
}

.experiment-illustration {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.illustration-image {
  width: 100%;
  height: auto;
  display: block;
}

.illustration-placeholder {
  border: 2px dashed #e5e7eb;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  background: #f9fafb;
}

.placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.placeholder-icon {
  width: 48px;
  height: 48px;
  background: #e5e7eb;
  border-radius: 8px;
  margin-bottom: 8px;
}

.placeholder-subtitle {
  font-size: 12px;
  color: #9ca3af;
}

/* Parameters */
.config-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 4px;

}

.config-cluster {
  border-radius: 8px;
}

.cluster-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
  color: #374151;
  border-bottom: 1px solid #e5e7eb;
}

.cluster-title.collapsible {
  cursor: pointer;
  user-select: none;
}

.cluster-title.collapsible:hover {
  background: #f3f4f6;
}

.collapse-icon {
  transition: transform 0.2s;
  font-size: 10px;
}

.collapse-icon.expanded {
  transform: rotate(180deg);
}

.config-grid {
  padding: 16px;
  flex-direction: column;
  background: white;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.config-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-group.full-width {
  grid-column: 1 / -1;
}

.config-group label {
    font-size: 10px;
    color: #6b7280;
  display: flex;
  align-items: center;
    gap: 4px;
}

.config-group input,
.config-group textarea,
.config-group select {
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 14px;
  transition: all 0.2s;
}

.config-group input:focus,
.config-group textarea:focus,
.config-group select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.config-group textarea {
  resize: vertical;
  font-family: inherit;
}

.boolean-number-input-wrap {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.boolean-number-input-wrap .config-input-small {
  width: 80px;
  padding: 6px 10px;
  font-size: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.boolean-number-suffix {
  font-size: 13px;
  color: #6b7280;
}

.config-select {
  cursor: pointer;
}

.form-helper {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.form-group label {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.form-input, .form-select {
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.form-input:focus, .form-select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.form-input.disabled {
  background-color: #f9fafb;
  color: #6b7280;
  cursor: not-allowed;
}

.tooltip-icon {
  cursor: help;
  color: #6b7280;
  font-size: 12px;
}

.custom-tooltip {
  position: fixed;
  background: #1f2937;
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  z-index: 1000;
  max-width: 250px;
  pointer-events: none;
}

/* Input List Styles */
.input-list-section {
  width: 100%;
}

.input-list-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-list-input-group {
  display: flex;
  gap: 8px;
  align-items: center;
}

.input-list-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.input-list-add-btn,
.input-list-save-btn {
  padding: 8px 16px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.input-list-add-btn:hover:not(:disabled),
.input-list-save-btn:hover:not(:disabled) {
  background: #2563eb;
}

.input-list-add-btn:disabled,
.input-list-save-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

.input-list-cancel-btn {
  padding: 8px 16px;
  background: #e5e7eb;
  color: #374151;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.input-list-cancel-btn:hover {
  background: #d1d5db;
}

.input-list-edit-buttons {
  display: flex;
  gap: 8px;
}

.input-list-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px;
  background: #f9fafb;
}

.input-list-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.input-list-item:hover {
  border-color: #3b82f6;
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.1);
}

.input-list-item-text {
  flex: 1;
  font-size: 14px;
  color: #111827;
}

.input-list-item-actions {
  display: flex;
  gap: 8px;
}

.input-list-edit-btn,
.input-list-delete-btn {
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
}

.input-list-edit-btn {
  background: #fef3c7;
  color: #d97706;
}

.input-list-edit-btn:hover {
  background: #fde68a;
}

.input-list-delete-btn {
  background: #fee2e2;
  color: #dc2626;
}

.input-list-delete-btn:hover {
  background: #fecaca;
}

.essay-upload-section {
  grid-column: 1 / -1;
}

.essay-upload-container {
  display: flex;
  gap: 8px;
}

.upload-btn {
  padding: 8px 16px;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.upload-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.uploaded-essays-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: fit-content;
}

.uploaded-essays-list h4 {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 8px 0;
}

.essay-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 6px;
}

.essay-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.essay-title {
  font-weight: 500;
}

.essay-filename {
  color: #6b7280;
  font-size: 12px;
}

.remove-essay-btn {
  padding: 4px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #dc2626;
  border-radius: 4px;
}

.remove-essay-btn:hover {
  background: #fee2e2;
}

.map-item {
  gap: 12px;
}

.map-item .map-role-select {
  flex-shrink: 0;
}

.map-item .select-small {
  min-width: 100px;
  padding: 4px 8px;
  font-size: 12px;
}

/* Interaction Variables */
.interaction-variables-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  height: 100%;
  min-height: 0;
  flex: 1;
}

.variables-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  min-height: 0;
  max-height: 100%;
}

.information-flow-section,
.action-structures-section,
.agent-behaviors-section {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.variables-grid {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: white;
}

.variable-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.variable-group.clickable-entry {
  padding: 12px;
  border: 2px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.variable-group.clickable-entry:hover {
  background: #f9fafb;
}

.variable-group.clickable-entry.selected {
  border-color: #2563eb;
  background: #eff6ff;
}

.variable-group label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  display: flex;
  align-items: center;
  gap: 6px;
}

.custom-select-wrapper {
  position: relative;
}

.custom-select-trigger {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.custom-select-trigger:hover {
  border-color: #2563eb;
}

.dropdown-arrow {
  font-size: 10px;
  color: #6b7280;
}

.custom-dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  z-index: 10;
  max-height: 200px;
  overflow-y: auto;
  text-align: left;
}

.dropdown-item {
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.dropdown-item:hover {
  background: #f9fafb;
}

.option-tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  background: #e5e7eb;
}

.communication-description {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.toggle-switch {
  display: flex;
  align-items: center;
}

.toggle-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-label {
  position: relative;
  display: inline-block;
  width: 100%;
  max-width: 200px;
  height: 32px;
  cursor: pointer;
  border-radius: 6px;
  overflow: hidden;
  border: 2px solid #e5e7eb;
  transition: border-color 0.3s ease;
  z-index: 2;
}

.toggle-input:checked + .toggle-label {
  background: #2563eb;
}

.toggle-text {
  position: absolute;
  font-size: 10px;
  font-weight: 600;
  transition: opacity 0.3s;
  z-index: 1;
}

.off-text {
  left: 12px;
  color: white;
  opacity: 0;
}

.on-text {
  right: 12px;
  color: #6b7280;
  opacity: 1;
}

.toggle-input:checked + .toggle-label .off-text {
  opacity: 1;
}

.toggle-input:checked + .toggle-label .on-text {
  opacity: 0;
}

.toggle-slider {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: transparent;
  transition: background-color 0.3s ease;
  z-index: 1;
}

.toggle-indicator {
  position: absolute;
  top: 2px;
  left: 2px;
  width: calc(50% - 2px);
  height: calc(100% - 4px);
  background-color: #ffffff;
  border-radius: 4px;
  transition: transform 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  z-index: 3;
}

.toggle-input:checked + .toggle-label .toggle-indicator {
  transform: translateX(100%);
}

.awareness-options {
  margin-top: 8px;
  padding: 8px;
  background: #f9fafb;
  border-radius: 6px;
}

.options-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  cursor: pointer;
}

.option-item input[type="checkbox"] {
  cursor: pointer;
}

.multi-checkbox-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: left;
  align-items: flex-start;
}
.multi-checkbox-options .option-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-start;
}
.multi-checkbox-options .option-item label {
  display: flex;
  align-items: center;
  gap: 8px;
}
.multi-checkbox-options .option-desc {
  font-size: 11px;
  color: #6b7280;
  margin-left: 24px;
}

.preview-column {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 100%;
  min-width: 0;
}

.section-title {
  font-weight: 800;
  color: #1f2937a6;
  font-size: 14px;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.conditional-preview {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: white;
}

.preview-component {
  height: 100%;
  padding: 12px;
}

.panel {
  /* border: 1px solid #e5e7eb;
  border-radius: 8px; */
  overflow: hidden;
}

.panel-header {
  padding: 12px 16px;
  background: #f9fafb;
  font-size: 14px;
  font-weight: 600;
  border-bottom: 1px solid #e5e7eb;
  margin: 0;
}


.chat-mode,
.group-chat-mode {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-thread {
  max-height: 200px;
  overflow-y: auto;
}

.message-history {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    border: 1px solid #dee2e6;
    border-radius: 3px;
    background: #f8f9fa;
}

.message-item {
    padding: 8px 12px;
    border-radius: 6px;
    margin-bottom: 8px;
    max-width: 80%;
    word-wrap: break-word;
    border: 1px solid #e1e5e9;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    position: relative;
}

.other-message {
    background: #f8f9fa;
    color: #333;
    align-self: flex-start;
    margin-right: 20px;
    margin-left: 0;
    border-left: 4px solid #667eea;
    text-align: left;
}

.my-message {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    align-self: flex-end;
    margin-left: 20px;
    margin-right: 0;
    box-shadow: 0 2px 6px rgba(102, 126, 234, 0.3);
  text-align: right;
}

.message-sender {
  color: #667eea;
  font-weight: 600;
  font-size: 11px;
  margin-bottom: 4px;
}

.message-content {
  font-size: 13px;
  color: #374151;
}

.my-message .message-sender {
  color: rgba(255, 255, 255, 0.9)
}

.my-message .message-content {
  color: white;
  text-align: left;
}

.my-message .message-time {
  color: rgba(255, 255, 255, 0.9);
}

.message-time {
  font-size: 10px;
  color: #666;
  align-self: flex-end;
  opacity: 0.7;
  text-align: right;
}

.message-input-area {
  display: flex;
  gap: 8px;
}

.message-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 13px;
}

.send-btn {
    background: #667eea;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.2s ease;
}

.no-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #9ca3af;
  font-size: 14px;
}

.awareness-panel {
  height: 100%;
}

.participants-status-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.participant-status-card {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  background: #f9fafb;
}

.participant-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.component-text {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.participant-specialty {
  display: flex;
  align-items: center;
  gap: 6px;
}

.shape-icon {
  width: 16px;
  height: 16px;
  border-radius: 50%;
}

.shape-icon.circle {
  background: #3b82f6;
}

.shape-icon.square {
  background: #10b981;
}

.participant-stats {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stats-row {
  display: flex;
  gap: 16px;
}

.component-module {
  display: flex;
  gap: 4px;
  font-size: 12px;
  flex-direction: column;
}

.component-num {
  font-weight: 600;
  color: #1f2937;
}

.progress-label {
  font-size: 12px;
}

/* Participant Registration */
/* Participants manage UI */
.participants-manage {
  display: flex;
  flex-direction: column;
  gap: 12px; /* Reduced from 16px */
  flex: 1; /* Added to make it fill available space */
  min-height: 0; /* Added to allow proper flex behavior */
  overflow-y: auto; /* Enable vertical scrolling */
  overflow-x: hidden; /* Prevent horizontal scrolling */
  padding-right: 4px; /* Space for scrollbar */
  scrollbar-width: thin; /* Firefox */
  scrollbar-color: #cbd5e1 #f1f5f9; /* Firefox */
}

/* Custom scrollbar for participants manage */
.participants-manage::-webkit-scrollbar {
  width: 6px;
}

.participants-manage::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.participants-manage::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.participants-manage::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.manage-forms {
  display: flex;
  flex-direction: column;
  gap: 8px; /* Further reduced from 12px */
  flex-shrink: 0; /* Prevent forms from shrinking */
  overflow: visible; /* Allow forms to be visible */
}

.form-card {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px; /* Reduced from 8px */
  padding: 10px; /* Further reduced from 12px */
}

.form-title {
  font-weight: 600;
  margin-bottom: 6px; /* Further reduced from 8px */
  font-size: 13px; /* Reduced from 14px */
  color: #374151;
}

.card-title {
  color: #1f2937c4;
  font-size: 12px;
  margin-bottom: 6px;
  font-weight: 600;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  align-items: start;
  align-content: start;
}

.form-field-wrapper {
  display: flex;
  flex-direction: column;
}

.form-field-full-width {
  grid-column: 1 / -1;
}

.form-field-button {
  grid-column: 2;
  display: flex;
  justify-content: flex-end;
  align-items: flex-end;
  align-self: end;
}

.form-row { 
  margin-bottom: 6px; /* Further reduced from 8px */
}

.form-row:has(select + button) {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 6px;
  align-items: center;
}

.form-row-split {
  display: grid;
  grid-template-columns: 1.5fr 2fr 1fr;
  gap: 6px; /* Further reduced from 8px */
}

.input, .select {
  padding: 6px 8px; /* Further reduced from 8px 10px */
  border: 1px solid #d1d5db;
  border-radius: 4px; /* Reduced from 6px */
  font-size: 12px; /* Reduced from 13px */
}

.select:disabled {
  background-color: #f9fafb;
  color: #9ca3af;
  cursor: not-allowed;
  opacity: 0.7;
}

.form-actions { 
  display: flex; 
  justify-content: flex-end;
  margin-top: 2px; /* Reduced from 4px */
}

.btn{
  padding: 6px 12px; /* Further reduced from 8px 14px */
  border: none;
  border-radius: 4px; /* Reduced from 6px */
  cursor: pointer;
  font-size: 12px; /* Reduced from 13px */
  font-weight: 600;
}

.btn.primary { 
  background: #2563eb; 
  color: #fff; 
}

.btn.danger { 
  background: #dc2626; 
  color: #fff; 
}

.manage-table {
  border: 1px solid #e5e7eb;
  border-radius: 6px; /* Reduced from 8px */
  overflow: hidden;
  background: #ffffff;
  flex: 1; /* Added to make table fill remaining space */
  min-height: 0; /* Added to allow proper flex behavior */
  display: flex; /* Added to make table body fill space */
  flex-direction: column; /* Added to stack table elements vertically */
  overflow-x: auto; /* Allow horizontal scrolling if needed */
  overflow-y: hidden;
}

.table-body {
  flex: 1; /* Added to make table body fill remaining space */
  overflow-y: auto; /* Added scroll if needed */
  overflow-x: auto; /* Allow horizontal scrolling if needed */
  min-height: 0; /* Added to allow proper flex behavior */
  scrollbar-width: thin; /* Firefox */
  scrollbar-color: #cbd5e1 #f1f5f9; /* Firefox */
}

/* Custom scrollbar for table body */
.table-body::-webkit-scrollbar {
  width: 6px;
}

.table-body::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.table-body::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.table-body::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.tr {
  display: grid;
  grid-template-columns: minmax(120px, 2fr) minmax(50px, 1fr) minmax(60px, 1fr) minmax(60px, 1fr) minmax(60px, 1fr) 50px;
  gap: 4px;
  align-items: center;
}

.table-head {
  display: grid;
  grid-template-columns: minmax(120px, 2fr) minmax(50px, 1fr) minmax(60px, 1fr) minmax(60px, 1fr) minmax(60px, 1fr) 50px;
  gap: 4px;
  align-items: center;
  background: #f8fafc;
  padding: 6px 8px;
  font-weight: 600;
  font-size: 11px;
  color: #374151;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
  text-align: left;
}

.th {
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 11px;
  color: #374151;
  justify-content: flex-start;
  min-width: 0;
  overflow: hidden;
}

.table-body .tr {
  padding: 6px 8px;
  border-bottom: 1px solid #f3f4f6;
  transition: background-color 0.15s ease;
}

.table-body .tr:hover {
  background: #f9fafb;
}

.table-body .tr:last-child {
  border-bottom: none;
}

.td { 
  display: flex; 
  align-items: center;
  font-size: 11px; /* Reduced from 12px */
  justify-content: flex-start;
  min-width: 0;
  overflow: hidden;
}

.td.code {
  font-weight: 600;
  color: #111827;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 120px;
  overflow: hidden;
}

.th.code {
  min-width: 120px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.td.type {
  font-size: 10px; /* Reduced from 11px */
  justify-content: flex-start;
}

.th.type {
  font-size: 10px;
  justify-content: flex-start;
}

.td.specialty {
  font-size: 10px; /* Reduced from 11px */
  justify-content: flex-start;
}

.th.specialty {
  font-size: 10px;
  justify-content: flex-start;
}

.td.role {
  font-size: 10px;
  justify-content: flex-start;
}

.th.role {
  font-size: 10px;
  justify-content: flex-start;
}

.td.group {
  font-size: 10px;
  justify-content: flex-start;
}

.th.group {
  font-size: 10px;
  justify-content: flex-start;
}

.td.assign {
  font-size: 10px; /* Reduced from 11px */
}

/* Type icon styling */
.type-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.type-icon.human {
  background: #dbeafe;
  color: #1e40af;
}

.type-icon.ai, .type-icon.ai_agent {
  background: #fef3c7;
  color: #d97706;
}

.type-icon:hover {
  transform: scale(1.1);
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.specialty-badge {
  padding: 1px 4px; /* Further reduced from 2px 5px */
  background: #f3f4f6;
  color: #374151;
  border-radius: 4px; /* Reduced from 5px */
  font-size: 9px; /* Reduced from 10px */
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.tag-badge {
  padding: 1px 4px; /* Further reduced from 2px 5px */
  background: #ecfdf5;
  color: #059669;
  border-radius: 4px; /* Reduced from 5px */
  font-size: 9px; /* Reduced from 10px */
  font-weight: 500;
  border: 1px solid #a7f3d0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.group-badge {
  padding: 1px 4px;
  background: #fef3c7;
  color: #d97706;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 500;
  border: 1px solid #fde68a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.no-group {
  color: #9ca3af;
  font-style: italic;
}

.no-tag {
  color: #9ca3af;
  font-size: 9px; /* Reduced from 10px */
  font-style: italic;
}

.td.tag {
  font-size: 10px; /* Reduced from 11px */
  justify-content: flex-start;
}

.td.actions {
  justify-content: center;
  gap: 4px;
  display: flex !important;
  flex-direction: row;
  min-width: 50px;
  flex-shrink: 0;
  width: 50px;
}

.th.actions {
  justify-content: center;
  min-width: 50px;
  flex-shrink: 0;
  width: 50px;
}

/* Icon button styling */
.btn-icon {
  display: flex !important;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0 !important;
  margin: 0;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s ease;
  background: transparent;
  color: #6b7280;
  flex-shrink: 0;
}

.btn-icon:hover {
  background: #fef2f2;
  color: #dc2626;
  transform: scale(1.05);
}

.btn-icon.danger {
  color: #ef4444;
}
.btn-icon.danger:hover {
  background: #fef2f2;
  color: #dc2626;
}

.btn-icon.edit {
  color: #2563eb;
}

.btn-icon.edit:hover {
  background: #eff6ff;
  color: #1d4ed8;
  transform: scale(1.05);
}

/* Improve select styling in table */
.manage-table .select,
.manage-table .select-small {
  padding: 4px 5px; /* Further reduced from 5px 6px */
  font-size: 10px; /* Reduced from 11px */
  border: 1px solid #d1d5db;
  border-radius: 3px; /* Reduced from 4px */
  background: #ffffff;
  min-width: 0;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.manage-table .select:focus,
.manage-table .select-small:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

/* Ensure doc-assign column and its select don't overflow */
.td.doc-assign {
  min-width: 0;
  overflow: hidden;
}

.td.doc-assign .select-small {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

/* Tag styles for communication options */
.selected-option.private_messaging,
.option-tag.private_messaging {
  background: #dbeafe;
  color: #1e40af;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

.selected-option.group_chat,
.option-tag.group_chat {
  background: #fef3c7;
  color: #d97706;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

.selected-option.no_chat,
.option-tag.no_chat {
  background: #f3f4f6;
  color: #374151;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

/* Negotiations option tags */
.selected-option.counter,
.option-tag.counter {
  background: #dbeafe;
  color: #1e40af;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

.selected-option.no_counter,
.option-tag.no_counter {
  background: #fef3c7;
  color: #d97706;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

/* Simultaneous Actions option tags */
.selected-option.allow,
.option-tag.allow {
  background: #d1fae5;
  color: #065f46;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

.selected-option.not_allow,
.option-tag.not_allow {
  background: #fee2e2;
  color: #dc2626;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

/* Awareness Dashboard option tags */
.selected-option.on,
.option-tag.on {
  background: #d1fae5;
  color: #065f46;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

.selected-option.off,
.option-tag.off {
  background: #f3f4f6;
  color: #374151;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

/* Rationales option tags */
.selected-option.step_wise,
.option-tag.step_wise {
  background: #dbeafe;
  color: #1e40af;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

.selected-option.intuitive,
.option-tag.intuitive {
  background: #fef3c7;
  color: #d97706;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

.selected-option.analytical,
.option-tag.analytical {
  background: #d1fae5;
  color: #065f46;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
}

.selected-option.none,
.option-tag.none {
  background: #f3f4f6;
  color: #374151;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  white-space: nowrap;
  width: fit-content;
  flex: none;
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

/* Grouping Modal Styles */
.grouping-modal {
  width: 600px;
  max-width: 90vw;
}

.grouping-modal .modal-body {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-height: calc(90vh - 120px);
  overflow-y: auto;
}

/* Ensure form inputs in grouping modal don't overflow */
.grouping-modal .form-group {
  width: 100%;
  box-sizing: border-box;
}

.grouping-modal .form-input,
.grouping-modal .form-select {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.section-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  margin: 0;
  padding-bottom: 8px;
  border-bottom: 2px solid #e5e7eb;
}

/* Input Group - Prevent overflow */
.input-group {
  display: flex;
  gap: 8px;
  align-items: stretch;
  width: 100%;
  box-sizing: border-box;
}

.input-group .form-input {
  flex: 1;
  min-width: 0;
  box-sizing: border-box;
  width: 100%;
}

.input-group .btn {
  flex-shrink: 0;
  white-space: nowrap;
  padding: 10px 20px;
}

/* Groups List */
.groups-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
  padding-right: 4px;
}

/* Custom scrollbar for groups list */
.groups-list::-webkit-scrollbar {
  width: 6px;
}

.groups-list::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.groups-list::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.groups-list::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* Group Item - Enhanced styling */
.group-item {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.group-item:hover {
  border-color: #cbd5e1;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}

.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-radius: 0;
  border-bottom: 1px solid #f3f4f6;
}

.group-name {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-name::before {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  display: inline-block;
}

.group-participants {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.participant-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #1e40af;
  transition: all 0.15s ease;
}

.participant-tag:hover {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  border-color: #93c5fd;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
}

.remove-btn {
  background: transparent;
  border: none;
  color: #ef4444;
  cursor: pointer;
  font-size: 18px;
  font-weight: 600;
  line-height: 1;
  padding: 0;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.remove-btn:hover {
  background: #fee2e2;
  color: #dc2626;
  transform: scale(1.1);
}

.empty-group {
  padding: 16px;
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
  font-style: italic;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px dashed #d1d5db;
}

/* Participants Checkboxes */
.participants-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
  padding: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.participants-checkboxes::-webkit-scrollbar {
  width: 6px;
}

.participants-checkboxes::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.participants-checkboxes::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.participants-checkboxes::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.participants-checkboxes .checkbox-label {
  padding: 8px 12px;
  border-radius: 4px;
  transition: background-color 0.15s ease;
  cursor: pointer;
}

.participants-checkboxes .checkbox-label:hover {
  background: #ffffff;
}

.participants-checkboxes .checkbox-label:has(input:checked) {
  background: #eff6ff;
  font-weight: 500;
}

/* Form Actions */
.form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.form-actions .btn {
  padding: 10px 20px;
  font-size: 14px;
}


</style>