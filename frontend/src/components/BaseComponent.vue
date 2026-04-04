<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import ActionDialog from './ActionDialog.vue'
import TradeForm from './TradeForm.vue'
import DocPreview from './doc_preview.vue'
import { captureActionContextSafe } from '../composables/useActionCapture.js'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  binding: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['submit'])

// Tooltip state
const showTooltip = ref(false)
const tooltipPosition = ref({ x: 0, y: 0 })

// Default descriptions based on path/control
const componentDescriptions = {
  'Participant.role': {
    'follower': 'You are the follower. You need to reproduce the map based on the guider\'s description.',
    'guider': 'You are the guider. You need to communicate with the follower to reproduce the correct route on the map.',
    'default': 'Your role in this Map Task experiment.'
  },
  'Participant.map': 'The map showing landmarks. Follower has a blank map to draw on, Guider has the route to describe.',
  'Participant.money': 'Your current money balance in the experiment.',
  'Participant.specialty': 'Your specialty shape - you can produce this shape at lower cost.',
  'Participant.inventory': 'Shapes you have completed producing.',
  'Participant.in_production': 'Shapes currently being produced.',
}

const getDescription = () => {
  if (props.binding?.description) {
    return props.binding.description
  }
  
  const path = props.binding?.path || ''
  
  // Check for role-specific descriptions
  if (path === 'Participant.role') {
    const role = props.binding?.value?.toLowerCase()
    if (role === 'follower') return componentDescriptions['Participant.role']['follower']
    if (role === 'guider') return componentDescriptions['Participant.role']['guider']
    return componentDescriptions['Participant.role']['default']
  }
  
  // Check other paths
  if (componentDescriptions[path]) {
    return componentDescriptions[path]
  }
  
  return null
}

const description = computed(() => getDescription())

const onMouseEnter = (event) => {
  if (description.value) {
    showTooltip.value = true
    tooltipPosition.value = { x: event.clientX + 10, y: event.clientY + 10 }
  }
}

const onMouseMove = (event) => {
  if (showTooltip.value) {
    tooltipPosition.value = { x: event.clientX + 10, y: event.clientY + 10 }
  }
}

const onMouseLeave = () => {
  showTooltip.value = false
}

// 为 segmented control 存储选中的值
const selectedValue = ref(null)

// 为 checkbox control 存储选中的任务
const checkedTasks = ref(new Set())

// 为 shape_production control 存储选中的形状
const selectedShape = ref('')

// 弹窗相关状态
const showDialog = ref(false)
const dialogShape = ref('')
const dialogMessage = ref('')
const dialogType = ref('confirm') // 'confirm' or 'result'
const isSubmitting = ref(false)
const dialogAction = ref('') // 存储当前的action类型，如 'submit_shape'
const dialogConfig = ref(null) // 存储弹窗配置

// 初始化选中值
if (props.binding?.control === 'segmented' && props.binding?.options && props.binding.options.length > 0) {
  selectedValue.value = props.binding.options[0]
}

// 设置选中值
const setSelectedValue = (value) => {
  selectedValue.value = value
  // 后续可以在这里触发更新事件或调用 action
}

// 切换 checkbox 状态
const toggleTask = (taskIndex, event) => {
  // 如果binding有on_check属性，触发相应的处理函数
  if (props.binding?.on_check) {
    // 阻止默认的checkbox切换行为
    if (event) {
      event.preventDefault()
      event.stopPropagation()
    }
    const task = taskList.value[taskIndex]
    if (task) {
      handleCheckboxAction(task, taskIndex)
    }
  } else {
    // 默认行为：切换checkbox状态
    if (checkedTasks.value.has(taskIndex)) {
      checkedTasks.value.delete(taskIndex)
    } else {
      checkedTasks.value.add(taskIndex)
    }
  }
}

// 获取弹窗配置（根据experiment type和action type）
const getDialogConfig = (experimentType, actionType) => {
  const configs = {
    'shapefactory': {
      'submit_shape': {
        confirmMessage: (item) => ({
          parts: [
            { text: 'Do you want to fulfill the ' },
            { type: 'shape', value: item },
            { text: ' order?' }
          ]
        }),
        successMessage: (item) => ({
          parts: [
            { text: 'You successfully fulfilled the ' },
            { type: 'shape', value: item },
            { text: ' order.' }
          ]
        }),
        errorMessage: (item) => ({
          parts: [
            { text: 'Sorry, you don\'t have ' },
            { type: 'shape', value: item },
            { text: ' in your inventory.' }
          ]
        }),
        apiEndpoint: 'submit_shape'
      }
    }
    // 可以在这里添加其他实验的配置
  }
  
  return configs[experimentType]?.[actionType] || null
}


// 处理checkbox的on_check事件
const handleCheckboxAction = (shape, taskIndex) => {
  const actionType = props.binding?.on_check
  if (!actionType) return
  
  // 获取experiment type
  let experimentType = sessionStorage.getItem('experiment_type')
  if (!experimentType) {
    try {
      const sessionStr = sessionStorage.getItem('session')
      if (sessionStr) {
        const session = JSON.parse(sessionStr)
        experimentType = session.experiment_type
      }
    } catch (e) {
      console.warn('Failed to parse session from sessionStorage', e)
    }
  }
  // 如果还是找不到，尝试从当前participant的interface配置推断，或者使用默认值
  if (!experimentType) {
    experimentType = 'shapefactory' // 默认值，可以根据实际情况调整
  }
  
  // 获取弹窗配置
  const config = getDialogConfig(experimentType, actionType)
  if (!config) {
    console.warn(`No dialog config found for experiment: ${experimentType}, action: ${actionType}`)
    return
  }
  
  // 显示确认弹窗
  dialogShape.value = shape
  dialogMessage.value = ''
  dialogType.value = 'confirm'
  dialogAction.value = actionType
  dialogConfig.value = config
  showDialog.value = true
  // 存储taskIndex以便成功后更新checkbox状态
  dialogTaskIndex.value = taskIndex
}

// 存储当前处理的taskIndex
const dialogTaskIndex = ref(-1)

// 提交action（通用函数，根据action type调用不同的API）
const submitAction = async () => {
  if (!dialogShape.value || !dialogConfig.value) return
  
  isSubmitting.value = true
  
  try {
    const sessionId = sessionStorage.getItem('session_id') || sessionStorage.getItem('session_code') || sessionStorage.getItem('session_name')
    const participantId = sessionStorage.getItem('participant_id')
    
    if (!sessionId || !participantId) {
      alert('Session or participant information not found. Please login again.')
      showDialog.value = false
      isSubmitting.value = false
      return
    }
    
    const encodedSessionId = encodeURIComponent(sessionId)
    const apiEndpoint = dialogConfig.value.apiEndpoint || dialogAction.value
    const url = `/api/sessions/${encodedSessionId}/participants/${participantId}/${apiEndpoint}`
    
    // 根据action type构建请求体
    const requestBody = {}
    if (dialogAction.value === 'submit_shape') {
      requestBody.shape = dialogShape.value
    }
    // 可以在这里添加其他action类型的请求体构建逻辑
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    })
    
    const result = await response.json()
    
    if (result.success) {
      // 成功：标记checkbox为已选中，显示成功消息
      if (dialogTaskIndex.value >= 0) {
        checkedTasks.value.add(dialogTaskIndex.value)
      }
      dialogType.value = 'result'
      dialogMessage.value = 'success' // 使用标识符
    } else {
      // 失败：显示错误消息
      if (result.error && result.error.includes('not in inventory')) {
        dialogType.value = 'result'
        dialogMessage.value = 'error_inventory' // 使用标识符
      } else {
        dialogType.value = 'result'
        dialogMessage.value = result.error || 'Failed to submit'
      }
    }
  } catch (error) {
    console.error('Error submitting action:', error)
    dialogType.value = 'result'
    dialogMessage.value = 'Failed to submit. Please try again.'
  } finally {
    isSubmitting.value = false
  }
}

// 关闭弹窗
const closeDialog = () => {
  showDialog.value = false
  dialogShape.value = ''
  dialogMessage.value = ''
  dialogType.value = 'confirm'
  dialogAction.value = ''
  dialogConfig.value = null
  dialogTaskIndex.value = -1
}

// 根据任务类型获取颜色
const getTaskColor = (taskType) => {
  const colorMap = {
    circle: '#ef4444',    // red
    triangle: '#3b82f6',  // blue
    square: '#10b981'     // green
  }
  return colorMap[taskType?.toLowerCase()] || '#6b7280' // default gray
}

// 根据任务类型获取形状类名
const getTaskShapeClass = (taskType) => {
  const shape = taskType?.toLowerCase()
  if (shape === 'circle') return 'shape-circle'
  if (shape === 'triangle') return 'shape-triangle'
  if (shape === 'square') return 'shape-square'
  return 'shape-circle' // default to circle
}

// 根据任务类型获取形状样式
const getTaskShapeStyle = (taskType) => {
  const color = getTaskColor(taskType)
  const shape = taskType?.toLowerCase()
  
  if (shape === 'triangle') {
    return {
      borderBottomColor: color
    }
  }
  
  return {
    backgroundColor: color
  }
}

// 格式化任务名称（首字母大写）
const formatTaskName = (taskType) => {
  if (!taskType) return ''
  return taskType.charAt(0).toUpperCase() + taskType.slice(1).toLowerCase()
}

// 获取可用形状列表（支持字符串数组或对象数组）
const availableShapes = computed(() => {
  if (props.binding?.control === 'shape_production') {
    const options = props.binding.options
    if (!options) return []
    
    // 如果是字符串，可能是路径，暂时返回示例数据
    if (typeof options === 'string') {
      // 后续可以从路径动态获取，现在返回示例数据
      return ['circle', 'triangle', 'square']
    }
    
    // 如果是数组
    if (Array.isArray(options)) {
      return options
    }
    
    return []
  }
  return []
})

// 格式化形状显示名称
const getShapeDisplayName = (shape) => {
  if (typeof shape === 'string') {
    return formatTaskName(shape)
  }
  if (typeof shape === 'object' && shape !== null) {
    return shape.label || shape.name || shape.value || ''
  }
  return String(shape)
}

// 获取形状的生产成本（如果配置了）
const getProductionCost = (shape) => {
  if (typeof shape === 'object' && shape !== null && shape.cost !== undefined) {
    return shape.cost
  }
  // 如果没有配置成本，返回空字符串
  return ''
}

// 格式化选项显示文本
const formatOptionText = (shape) => {
  const name = getShapeDisplayName(shape)
  const cost = getProductionCost(shape)
  if (cost !== '') {
    return `${name} (${cost})`
  }
  return name
}

// 获取形状的值（用于 v-model）
const getShapeValue = (shape) => {
  if (typeof shape === 'string') {
    return shape
  }
  if (typeof shape === 'object' && shape !== null) {
    return shape.value || shape.name || shape.label || ''
  }
  return String(shape)
}

// 处理开始生产:
// 1. participant.money减少， 2. in production倒计时+显示内容，3. production count更新，4. 生产完成进入inventory
const startProduction = async () => {
  if (!selectedShape.value) return
  
  // Get session and participant info from sessionStorage
  const sessionId = sessionStorage.getItem('session_id') || sessionStorage.getItem('session_code') || sessionStorage.getItem('session_name')
  const participantId = sessionStorage.getItem('participant_id')
  
  if (!sessionId || !participantId) {
    alert('Session or participant information not found. Please login again.')
    return
  }
  
  try {
    const encodedSessionId = encodeURIComponent(sessionId)
    const url = `/api/sessions/${encodedSessionId}/participants/${participantId}/start_production`
    console.log('[Production] Starting production request:', { url, shape: selectedShape.value })
    
    const ctx = await captureActionContextSafe()
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        shape: selectedShape.value,
        ...ctx
      })
    })
    
    console.log('[Production] Response status:', response.status, response.statusText)
    
    // Check if response is ok before parsing JSON
    if (!response.ok) {
      const errorText = await response.text()
      console.error('[Production] Error response:', errorText)
      try {
        const errorJson = JSON.parse(errorText)
        alert(errorJson.error || errorJson.message || `Failed to start production (${response.status})`)
      } catch {
        alert(`Failed to start production: ${response.status} ${response.statusText}`)
      }
      return
    }
    
    const result = await response.json()
    console.log('[Production] Success response:', result)
    
    if (!result.success) {
      alert(result.error || 'Failed to start production')
      return
    }
    
    // Success - the WebSocket update will handle UI refresh
    console.log('Production started:', result)
    
  } catch (error) {
    console.error('Error starting production:', error)
    alert('Failed to start production. Please try again.')
  }
}

// Countdown timer for each production item
const productionTimers = ref({})
let timerInterval = null

const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

const getShapeFromItem = (item) => {
  if (typeof item === 'string') return item
  if (typeof item === 'object' && item !== null) return item.shape || ''
  return ''
}

// Update timers for in_production items
const updateTimersForInProduction = () => {
  if (controlType.value === 'in_production') {
    const items = getInProductionItems.value
    items.forEach((item, index) => {
      if (typeof item === 'object' && item !== null && item.completion_time) {
        const completionTime = new Date(item.completion_time)
        const now = new Date()
        const remaining = Math.max(0, Math.floor((completionTime - now) / 1000))
        
        if (remaining > 0) {
          productionTimers.value[`in_prod_${index}`] = formatTime(remaining)
        } else {
          productionTimers.value[`in_prod_${index}`] = '0:00'
        }
      } else {
        productionTimers.value[`in_prod_${index}`] = '--:--'
      }
    })
  }
}

// Start timer when component mounts or in_production changes
onMounted(() => {
  updateTimersForInProduction()
  timerInterval = setInterval(() => {
    updateTimersForInProduction()
  }, 1000)
})

onUnmounted(() => {
  if (timerInterval) {
    clearInterval(timerInterval)
  }
})

// 获取任务列表（暂时使用模拟数据，后续从 path 获取）
const taskList = computed(() => {
  // Prefer backend-provided value for dynamic updates
  if (props.binding?.control === 'checkbox') {
    if (Array.isArray(props.binding?.value)) {
      return props.binding.value
    }
    // Fallback to existing mock data if no value is provided
    if (props.binding.path) {
      return ['circle', 'triangle', 'square', 'circle']
    }
  }
  return []
})

const controlType = computed(() => {
  if (!props.binding) {
    return 'slot' // 如果没有 binding，使用 slot
  }
  
  const control = props.binding.control || ''
  const path = props.binding.path || ''
  
  // Check if this is in_production display
  if (path.includes('in_production') || path === 'Participant.in_production') {
    return 'in_production'
  }
  
  // Check if this is inventory display (list of shapes)
  if (path === 'Participant.inventory' || path === 'Participant.inventory') {
    return 'inventory'
  }
  
  // Check if this is essays display
  if (path === 'Participant.essays' || path.includes('essays')) {
    return 'essays'
  }
  
  // Check if this is investment_history display
  if (path === 'Participant.investment_history' || path.includes('investment_history') || control === 'investment_history') {
    return 'investment_history'
  }
  
  // Check if this is rankings display
  if (path === 'Participant.rankings' || path.includes('rankings') || control === 'rankings') {
    return 'rankings'
  }

  // Map Task: role display (My Status) - must check before word_list (both can have control 'list')
  if (path === 'Participant.role') {
    return 'role_badge'
  }
  
  // Check if this is word_list display (wordguessing experiment)
  if (path === 'Participant.word_list' || path.includes('word_list') || control === 'list') {
    return 'list'
  }

  // Map Task: map display (My Tasks)
  if (path === 'Participant.map' || (path?.includes('map') && control === 'map')) {
    return 'map'
  }

  // Map Task: map toolbox (My Tasks, follower only)
  if (control === 'map_toolbox') {
    return 'map_toolbox'
  }
  
  switch (control) {
    case 'segmented':
      return 'segmented'
    case 'number':
      return 'number'
    case 'checkbox':
      return 'checkbox'
    case 'list':
      return 'list'
    case 'shape_production':
      return 'shape_production'
    case 'investment_form':
      return 'investment_form'
    case 'investment_history':
      return 'investment_history'
    case 'rankings':
      return 'rankings'
    default:
      // Check if this is an essay ranking form (has on_submit and fields)
      if (props.binding.on_submit === 'submit_essay_rank' && props.binding.fields) {
        return 'essay_ranking_form'
      }
      // 如果有 action，渲染为按钮
      if (props.binding.action) {
        return 'button'
      }
      // 默认显示文本值
      return 'text'
  }
})

// Check if binding is just an instruction (only has label, no path/control/value)
const isInstructionOnly = computed(() => {
  if (!props.binding) return false
  // If it has path, control, value, on_submit, fields, or action, it's not just an instruction
  return !props.binding.path && 
         !props.binding.control && 
         props.binding.value === undefined && 
         !props.binding.on_submit && 
         !props.binding.fields && 
         !props.binding.action &&
         !!props.binding.label
})

// Get in_production items for display
const getInProductionItems = computed(() => {
  if (controlType.value === 'in_production') {
    const value = props.binding.value
    if (Array.isArray(value)) {
      return value
    }
    return []
  }
  return []
})

// Get production count for display
// This should be the completed production count (production_number)
const getProductionCount = computed(() => {
  // Try to get from binding.countValue first (set by backend)
  if (props.binding?.countValue !== undefined && props.binding.countValue !== null) {
    return props.binding.countValue
  }
  // Fallback: try to get from binding.value if it's a number
  if (typeof props.binding?.value === 'number') {
    return props.binding.value
  }
  // Default to 0 if not set
  return 0
})

// Get max production count from Session.Params.maxProductionNum
const getMaxProductionCount = computed(() => {
  if (props.binding?.maxCount !== undefined && props.binding.maxCount !== null) {
    return props.binding.maxCount
  }
  // If maxCount is not set, don't show the "/max" part
  return null
})

// Format investment timestamp for display
const formatInvestmentTime = (timestamp) => {
  if (!timestamp) return 'N/A'
  try {
    const date = new Date(timestamp)
    if (isNaN(date.getTime())) return String(timestamp)
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    })
  } catch (e) {
    return String(timestamp)
  }
}

// Get sorted rankings (sorted by rank)
const sortedRankings = computed(() => {
  if (controlType.value === 'rankings' && props.binding?.value && Array.isArray(props.binding.value)) {
    // Sort by rank (ascending: rank 1 is best)
    return [...props.binding.value].sort((a, b) => {
      const rankA = a.rank || 999
      const rankB = b.rank || 999
      return rankA - rankB
    })
  }
  return []
})

// Essay preview state
const showEssayPreview = ref(false)
const selectedEssay = ref(null)

const viewEssay = (essay) => {
  selectedEssay.value = essay
  showEssayPreview.value = true
}

const closeEssayPreview = () => {
  showEssayPreview.value = false
  selectedEssay.value = null
}

// Essay ranking form state
const essayRankingForm = ref({
  essay_id: '',
  essay_rank: ''
})

// Get available essays for ranking form
const availableEssaysForRanking = computed(() => {
  // Check if this is an essay ranking form
  const essayNameField = props.binding?.fields?.essay_name
  if (!essayNameField) {
    return []
  }
  
  // First, try to get essays from the field's resolved options (if backend set it)
  // Backend will set options to the actual essays array, not the string 'Participant.essays'
  const fieldOptions = essayNameField.options
  if (Array.isArray(fieldOptions) && fieldOptions.length > 0) {
    console.log('[BaseComponent] Found essays from field options:', fieldOptions.length)
    return fieldOptions
  }
  
  // If options is still the string 'Participant.essays', try to get from binding value or path
  if (fieldOptions === 'Participant.essays') {
    // Try to get essays from binding value or path
    const essays = props.binding.value || []
    if (Array.isArray(essays) && essays.length > 0) {
      console.log('[BaseComponent] Found essays from binding value:', essays.length)
      return essays
    }
    
    // Try to get from sessionStorage participant interface
    try {
      const participantInterface = sessionStorage.getItem('participant_interface')
      if (participantInterface) {
        const interfaceData = JSON.parse(participantInterface)
        
        // Try My Status first
        const myStatus = interfaceData?.['My Status']?.[0]
        if (myStatus) {
          const essaysBinding = myStatus.bindings?.find(b => 
            b.path === 'Participant.essays' || b.path?.includes('essays')
          )
          if (essaysBinding?.value && Array.isArray(essaysBinding.value) && essaysBinding.value.length > 0) {
            console.log('[BaseComponent] Found essays from My Status:', essaysBinding.value.length)
            return essaysBinding.value
          }
        }
        
        // Also try My Actions (in case essays are stored there)
        const myActions = interfaceData?.['My Actions']?.[0]
        if (myActions) {
          const essaysBinding = myActions.bindings?.find(b => 
            b.path === 'Participant.essays' || b.path?.includes('essays')
          )
          if (essaysBinding?.value && Array.isArray(essaysBinding.value) && essaysBinding.value.length > 0) {
            console.log('[BaseComponent] Found essays from My Actions:', essaysBinding.value.length)
            return essaysBinding.value
          }
        }
      }
    } catch (e) {
      console.warn('[BaseComponent] Failed to parse participant interface:', e)
    }
  }
  
  // Debug: log what we found
  console.log('[BaseComponent] availableEssaysForRanking - binding:', {
    hasBinding: !!props.binding,
    hasFields: !!props.binding?.fields,
    hasEssayName: !!essayNameField,
    options: fieldOptions,
    optionsType: typeof fieldOptions,
    isArray: Array.isArray(fieldOptions),
    bindingValue: props.binding?.value
  })
  
  return []
})

// Submit essay ranking
const submitEssayRank = async () => {
  if (!essayRankingForm.value.essay_id || !essayRankingForm.value.essay_rank) {
    alert('Please select an essay and enter a rank')
    return
  }
  
  const sessionId = sessionStorage.getItem('session_id') || sessionStorage.getItem('session_code') || sessionStorage.getItem('session_name')
  const participantId = sessionStorage.getItem('participant_id')
  
  if (!sessionId || !participantId) {
    alert('Session or participant information not found. Please login again.')
    return
  }
  
  try {
    const encodedSessionId = encodeURIComponent(sessionId)
    const url = `/api/sessions/${encodedSessionId}/participants/${participantId}/submit_essay_rank`
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        essay_id: essayRankingForm.value.essay_id,
        essay_rank: parseInt(essayRankingForm.value.essay_rank)
      })
    })
    
    const result = await response.json()
    
    if (result.success) {
      console.log('[BaseComponent] Essay ranking submitted successfully:', result)
      alert(`Essay ranked successfully! Rank: ${essayRankingForm.value.essay_rank}`)
      // Reset form
      essayRankingForm.value = {
        essay_id: '',
        essay_rank: ''
      }
      // Emit submit event for parent component
      emit('submit', {
        action: 'submit_essay_rank',
        values: {
          essay_id: result.ranking.essay_id,
          essay_rank: result.ranking.rank
        }
      })
    } else {
      console.error('[BaseComponent] Essay ranking submission failed:', result.error)
      alert(result.error || 'Failed to submit essay ranking')
    }
  } catch (error) {
    console.error('[BaseComponent] Error submitting essay ranking:', error)
    alert('Error submitting essay ranking. Please try again.')
  }
}
</script>

<template>
  <!-- Shape Production Control has special layout: label on first row, controls on second row, count on third row -->
  <div v-if="binding && controlType === 'shape_production'" class="component-module shape-production-module">
    <div class="shape-production-label-row">
      <span class="component-text">{{ title }}:</span>
    </div>
    <div class="shape-production-controls-row">
      <select 
        v-model="selectedShape" 
        class="production-select"
        :disabled="binding.disabled"
      >
        <option value="">{{ binding.placeholder || 'Choose a shape...' }}</option>
        <option 
          v-for="shape in availableShapes" 
          :key="getShapeValue(shape)" 
          :value="getShapeValue(shape)"
        >
          {{ formatOptionText(shape) }}
        </option>
      </select>
      <button 
        v-if="binding.showButton !== false"
        @click="startProduction" 
        class="production-button" 
        :disabled="!selectedShape || binding.disabled"
      >
        {{ binding.buttonLabel || 'Start Production' }}
      </button>
    </div>
    <div class="shape-production-count-row">
      <span class="production-count-label">Production Count:</span>
      <span class="production-count">
        {{ getProductionCount }}{{ getMaxProductionCount ? `/${getMaxProductionCount}` : '' }}
      </span>
    </div>
  </div>
  
  <!-- Investment Form has its own layout (no title, TradeForm handles it) -->
  <div v-else-if="binding && controlType === 'investment_form'" class="component-module" style="flex-direction: column;">
    <TradeForm
      :config="binding"
      :selected-participant="null"
      :participants="{}"
      :my-participant="null"
      @submit="(data) => emit('submit', data)"
    />
  </div>
  
  <!-- Essay Ranking Form -->
  <div v-else-if="binding && controlType === 'essay_ranking_form'" class="component-module essay-ranking-form" style="flex-direction: column;">
    <div class="essay-ranking-form-content">
      <div class="essay-ranking-field">
        <label class="essay-ranking-label">Essay:</label>
        <select 
          v-model="essayRankingForm.essay_id" 
          class="essay-ranking-select"
        >
          <option value="">Select an essay...</option>
          <option 
            v-for="essay in availableEssaysForRanking" 
            :key="essay.essay_id || essay.id"
            :value="essay.essay_id || essay.id"
          >
            {{ essay.title || essay.original_filename || 'Untitled' }}
          </option>
        </select>
      </div>
      <div class="essay-ranking-field">
        <label class="essay-ranking-label">Rank:</label>
        <input
          v-model="essayRankingForm.essay_rank"
          type="number"
          class="essay-ranking-input"
          :min="binding.fields?.essay_rank?.min || 1"
          :max="availableEssaysForRanking.length || binding.fields?.essay_rank?.max || 10"
          placeholder="Enter rank"
        />
      </div>
      <button 
        @click="submitEssayRank" 
        class="essay-ranking-submit"
        :disabled="!essayRankingForm.essay_id || !essayRankingForm.essay_rank"
      >
        Submit Ranking
      </button>
    </div>
  </div>
  
  <!-- Investment History has its own layout (no title, full-width list) -->
  <div v-else-if="binding && controlType === 'investment_history'" class="component-module" style="flex-direction: column; align-items: stretch;">
    <div class="control-investment-history">
      <div
        v-if="!Array.isArray(binding.value) || binding.value.length === 0"
        class="investment-history-empty"
      >
        No investment history
      </div>
      <div
        v-else
        class="investment-history-items"
      >
        <div
          v-for="(investment, index) in binding.value"
          :key="investment.id || index"
          class="investment-history-item"
        >
          <div class="investment-header">
            <span class="investment-type">{{ investment.investment_type || 'N/A' }}</span>
            <span class="investment-amount">${{ investment.investment_amount || 0 }}</span>
          </div>
          <div class="investment-details">
            <span class="investment-timestamp">{{ formatInvestmentTime(investment.timestamp) }}</span>
            <span class="investment-money">Money: ${{ investment.money_before }} → ${{ investment.money_after }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <!-- Rankings Display (list of essay rankings) -->
  <div v-else-if="binding && controlType === 'rankings'" class="component-module" style="flex-direction: column; align-items: stretch;">
    <div class="control-rankings">
      <div
        v-if="!Array.isArray(binding.value) || binding.value.length === 0"
        class="rankings-empty"
      >
        No rankings yet
      </div>
      <div
        v-else
        class="rankings-items"
      >
        <div
          v-for="(ranking, index) in sortedRankings"
          :key="ranking.essay_id || index"
          class="ranking-item"
        >
          <div class="ranking-header">
            <span class="ranking-essay-title">{{ ranking.essay_title || ranking.essay_id || 'Untitled' }}</span>
            <span class="ranking-rank">Rank: {{ ranking.rank }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <!-- Other controls use standard layout -->
  <div v-else class="component-module" :class="{ 
    'has-shape-production': controlType === 'shape_production',
    'has-in-production': controlType === 'in_production',
    'has-essays': controlType === 'essays',
    'has-list': controlType === 'list',
    'instruction-only': isInstructionOnly
  }">
    <!-- For instruction-only bindings, just show the label without colon and content -->
    <span v-if="isInstructionOnly" class="component-text instruction-text">
      {{ binding.label }}
    </span>
    <template v-else>
      <span v-if="title" class="component-text" @mouseenter="onMouseEnter" @mousemove="onMouseMove" @mouseleave="onMouseLeave">
        {{ title }}:<span v-if="description" class="tooltip-icon">ⓘ</span>
      </span>
      <!-- Tooltip popup -->
      <div
        v-if="showTooltip && description"
        class="tooltip-popup"
        :style="{ left: tooltipPosition.x + 'px', top: tooltipPosition.y + 'px' }"
      >
        {{ description }}
      </div>
      <span class="component-content" :class="{ 'no-title': !title }">
      <!-- 如果有 binding，根据 control 类型渲染 -->
      <template v-if="binding">
        <!-- Segmented Control -->
        <div v-if="controlType === 'segmented'" class="control-segmented">
          <button
            v-for="(option, optIndex) in binding.options"
            :key="optIndex"
            class="segmented-option"
            :class="{ active: selectedValue === option }"
            @click="setSelectedValue(option)"
          >
            {{ option }}
          </button>
        </div>
        
        <!-- Number Input -->
        <input
          v-else-if="controlType === 'number'"
          type="number"
          class="control-number"
          :min="binding.min !== undefined ? binding.min : 0"
          :max="binding.max !== undefined ? binding.max : undefined"
          :placeholder="binding.label"
        />

        <!-- In Production Display -->
        <div
          v-else-if="controlType === 'in_production'"
          class="control-in-production"
        >
          <div
            v-if="getInProductionItems.length === 0"
            class="in-production-empty"
          >
            No items in production
          </div>
          <div
            v-for="(item, index) in getInProductionItems"
            :key="index"
            class="in-production-item"
          >
            <span
              class="task-shape"
              :class="getTaskShapeClass(getShapeFromItem(item))"
              :style="getTaskShapeStyle(getShapeFromItem(item))"
            ></span>
            <span class="in-production-shape-name">
              {{ formatTaskName(getShapeFromItem(item)) }}
            </span>
            <span class="in-production-timer">
              {{ productionTimers[`in_prod_${index}`] || '--:--' }}
            </span>
          </div>
        </div>

        <!-- Role Badge (Map Task: My Role) -->
        <div
          v-else-if="controlType === 'role_badge'"
          class="control-role-badge"
        >
          <span class="role-badge" :class="(binding.value || '').toLowerCase()">
            {{ (binding.value || '—') }}
          </span>
        </div>

        <!-- Single Shape Display (e.g., My Specialty) -->
        <div
          v-else-if="binding.control === 'shape'"
          class="control-shape-display"
        >
          <span
            class="task-shape"
            :class="getTaskShapeClass(binding.value || binding.path)"
            :style="getTaskShapeStyle(binding.value || binding.path)"
          ></span>
          <span class="task-label">
            {{ formatTaskName(binding.value || binding.path) }}
          </span>
        </div>
        
        <!-- Checkbox List (for tasks) -->
        <div v-else-if="controlType === 'checkbox'" class="control-checkbox-list">
          <label
            v-for="(task, taskIndex) in taskList"
            :key="taskIndex"
            class="checkbox-item"
          >
            <input
              type="checkbox"
              class="checkbox-input"
              :checked="checkedTasks.has(taskIndex)"
              @change="(e) => toggleTask(taskIndex, e)"
            />
            <span
              class="task-shape"
              :class="getTaskShapeClass(task)"
              :style="getTaskShapeStyle(task)"
            ></span>
            <span class="task-label">{{ formatTaskName(task) }}</span>
          </label>
        </div>
        
        <!-- Button -->
        <button
          v-else-if="controlType === 'button'"
          class="control-button"
          @click="() => {}"
        >
          {{ binding.label }}
        </button>
        
        <!-- Inventory Display (list of shapes) -->
        <div
          v-else-if="controlType === 'inventory'"
          class="control-inventory"
        >
          <div
            v-if="!Array.isArray(binding.value) || binding.value.length === 0"
            class="inventory-empty"
          >
            No items in inventory
          </div>
          <div
            v-else
            class="inventory-items"
          >
            <div
              v-for="(shape, index) in binding.value"
              :key="index"
              class="inventory-item"
            >
              <span
                class="task-shape"
                :class="getTaskShapeClass(shape)"
                :style="getTaskShapeStyle(shape)"
              ></span>
              <span class="inventory-shape-name">
                {{ formatTaskName(shape) }}
              </span>
            </div>
          </div>
        </div>
        
        <!-- Essays Display (list of essays) -->
        <div
          v-else-if="controlType === 'essays'"
          class="control-essays"
        >
          <div
            v-if="!Array.isArray(binding.value) || binding.value.length === 0"
            class="essays-empty"
          >
            No essays available
          </div>
          <div
            v-else
            class="essays-items"
          >
            <div
              v-for="essay in binding.value"
              :key="essay.essay_id || essay.id"
              class="essay-item"
              @click="viewEssay(essay)"
              :class="{ 'selected': selectedEssay?.essay_id === essay.essay_id }"
            >
              <div class="essay-content">
                <i class="fa-solid fa-file-pdf" style="color: #dc2626; margin-right: 8px;"></i>
                <span class="essay-title">{{ essay.original_filename || essay.title || essay.filename || 'Untitled' }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- List Display (for word_list and other simple lists) -->
        <div
          v-else-if="controlType === 'list'"
          class="control-list"
        >
          <div
            v-if="!Array.isArray(binding.value) || binding.value.length === 0"
            class="list-empty"
          >
            No items available
          </div>
          <div
            v-else
            class="list-items"
          >
            <div
              v-for="(item, index) in binding.value"
              :key="index"
              class="list-item"
            >
              <span class="list-item-text">{{ item }}</span>
            </div>
          </div>
        </div>
        
        <!-- Default Text Display -->
        <span v-else class="control-text">
          {{ binding.value !== undefined ? binding.value : (binding.path || 'N/A') }}
        </span>
      </template>
      
      <!-- 如果没有 binding，使用 slot -->
      <slot v-else></slot>
      </span>
    </template>
  </div>
  
  <!-- Generic Action Dialog -->
  <ActionDialog
    :show="showDialog"
    :dialog-type="dialogType"
    :dialog-config="dialogConfig"
    :dialog-item="dialogShape"
    :dialog-message="dialogMessage"
    :is-submitting="isSubmitting"
    :format-item-name="formatTaskName"
    :get-item-shape-class="getTaskShapeClass"
    :get-item-shape-style="getTaskShapeStyle"
    @close="closeDialog"
    @submit="submitAction"
  />
  
  <!-- Essay Preview Dialog -->
  <DocPreview
    :show="showEssayPreview"
    :essay="selectedEssay"
    @close="closeEssayPreview"
  />
</template>

<style scoped>
.component-module {
  border: 1px solid #dee2e6;
  border-radius: 4px;
  padding: 8px;
  background: #ffffff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  transition: box-shadow 0.3s ease;
}

.component-module:hover {
  box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}

.component-module.has-shape-production {
  align-items: flex-start;
}

.component-module.has-shape-production .component-text {
  padding-top: 4px;
}

.component-module.has-in-production {
  flex-direction: column;
  align-items: stretch;
}

.component-module.has-in-production .component-text {
  margin-bottom: 8px;
}

.component-module.has-in-production .component-content {
  width: 100%;
  text-align: left;
}

.component-module.has-essays {
  flex-direction: column;
  align-items: stretch;
}

.component-module.has-essays .component-text {
  margin-bottom: 8px;
}

.component-module.has-essays .component-content {
  width: 100%;
  text-align: left;
}

.component-module.has-list {
  flex-direction: column;
  align-items: flex-start;
}

.component-module.has-list .component-text {
  margin-bottom: 8px;
}

.component-module.has-list .component-content {
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
}

.component-module.instruction-only {
  flex-direction: column;
  align-items: flex-start;
}

.component-module.instruction-only .instruction-text {
  width: 100%;
  font-weight: 400;
  color: #374151;
  line-height: 1.5;
}

.component-text {
  font-weight: 500;
  color: #374151;
  font-size: 13px;
  margin: 0;
  padding: 0;
  line-height: 1.3;
}

.component-content {
  color: #212529;
  flex: 1;
  text-align: right;
}

.component-content.no-title {
  width: 100%;
}

/* Support for numeric values */
.component-content :deep(.component-num) {
  font-weight: 500;
  color: #0066cc;
}

/* Control Styles */
.control-segmented {
  display: flex;
  gap: 4px;
  background: #e9ecef;
  padding: 2px;
  border-radius: 4px;
}

.segmented-option {
  flex: 1;
  padding: 6px 12px;
  border: none;
  background: transparent;
  border-radius: 3px;
  cursor: pointer;
  font-size: 13px;
  color: #495057;
  transition: all 0.2s;
}

.segmented-option:hover {
  background: rgba(255, 255, 255, 0.5);
}

.segmented-option.active {
  background: #ffffff;
  color: #0066cc;
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.control-number {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 14px;
  color: #212529;
}

.control-number:focus {
  outline: none;
  border-color: #0066cc;
  box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.1);
}

.control-button {
  padding: 8px 16px;
  background: #0066cc;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.control-button:hover {
  background: #0052a3;
}

.control-button:active {
  background: #003d7a;
}

.control-text {
  color: #212529;
  font-size: 14px;
}

/* Checkbox List Styles */
.control-checkbox-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}

.checkbox-item:hover {
  background: #f9fafb;
  border-color: #d1d5db;
}

.checkbox-input {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #0066cc;
  flex-shrink: 0;
  border-radius: 3px;
  border: 1px solid #d1d5db;
}

.task-shape {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  display: inline-block;
  margin-right: 8px;
}

.task-shape.shape-circle {
  border-radius: 50%;
}

.task-shape.shape-square {
  border-radius: 2px;
}

.task-shape.shape-triangle {
  width: 0;
  height: 0;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-bottom: 14px solid;
  background-color: transparent !important;
  border-radius: 0;
}

.task-label {
  color: #374151;
  font-size: 14px;
  font-weight: 400;
  flex: 1;
}

.control-shape-display {
  gap: 8px;
}

.control-shape-display .task-label {
  flex: none;
}

.control-role-badge {
  display: inline-flex;
}

.control-role-badge .role-badge {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  text-transform: capitalize;
}

.control-role-badge .role-badge.guider {
  background: #dbeafe;
  color: #1d4ed8;
}

.control-role-badge .role-badge.follower {
  background: #d1fae5;
  color: #047857;
}

/* Shape Production Control Styles - Special Layout */
.shape-production-module {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: stretch;
}

.shape-production-label-row {
  width: 100%;
  text-align: left;
}

.shape-production-label-row .component-text {
  font-weight: 500;
  color: #374151;
  font-size: 13px;
  margin: 0;
  padding: 0;
  line-height: 1.3;
}

.shape-production-controls-row {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.shape-production-count-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #6b7280;
}

.production-count-label {
  font-weight: 500;
  color: #374151;
  margin: 0;
}

/* Legacy styles for backward compatibility */
.control-shape-production {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.production-controls-row {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.production-select {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 14px;
  color: #212529;
  background-color: #ffffff;
  cursor: pointer;
  transition: all 0.2s;
}

.production-select:hover:not(:disabled) {
  border-color: #adb5bd;
}

.production-select:focus {
  outline: none;
  border-color: #0066cc;
  box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.1);
}

.production-select:disabled {
  background-color: #e9ecef;
  cursor: not-allowed;
  opacity: 0.6;
}

.production-button {
  padding: 8px 16px;
  background: #0066cc;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
  flex-shrink: 0;
}

.production-button:hover:not(:disabled) {
  background: #0052a3;
}

.production-button:active:not(:disabled) {
  background: #003d7a;
}

.production-button:disabled {
  background: #adb5bd;
  cursor: not-allowed;
  opacity: 0.6;
}

.production-count-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #6b7280;
}

.production-count-row label {
  font-weight: 500;
  color: #374151;
  margin: 0;
}

.production-count {
  font-weight: 500;
  color: #0066cc;
}

/* In Production Display Styles */
.control-in-production {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  align-items: stretch;
}

.in-production-empty {
  color: #6b7280;
  font-size: 13px;
  font-style: italic;
  padding: 8px;
}

.in-production-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.in-production-item:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.in-production-shape-name {
  flex: 1;
  color: #374151;
  font-size: 14px;
  font-weight: 400;
}

.in-production-timer {
  font-weight: 600;
  color: #0066cc;
  font-size: 14px;
  font-family: 'Courier New', monospace;
  min-width: 50px;
  text-align: right;
}

/* Inventory Display Styles */
.control-inventory {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.inventory-empty {
  color: #6b7280;
  font-size: 13px;
  font-style: italic;
  padding: 8px;
}

.inventory-items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.inventory-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.inventory-item:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.inventory-shape-name {
  color: #374151;
  font-size: 13px;
  font-weight: 400;
}

/* Investment History Display Styles */
.control-investment-history {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.investment-history-empty {
  color: #6b7280;
  font-size: 13px;
  font-style: italic;
  padding: 8px;
}

.investment-history-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.investment-history-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.investment-history-item:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.investment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.investment-type {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  text-transform: capitalize;
  padding: 2px 8px;
  background: #e5e7eb;
  border-radius: 4px;
}

.investment-amount {
  font-size: 14px;
  font-weight: 600;
  color: #0066cc;
}

.investment-details {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
}

.investment-timestamp {
  font-family: 'Courier New', monospace;
}

.investment-money {
  color: #059669;
}

/* Rankings Display Styles */
.control-rankings {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.rankings-empty {
  color: #6b7280;
  font-size: 13px;
  font-style: italic;
  padding: 8px;
}

.rankings-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ranking-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.ranking-item:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.ranking-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.ranking-essay-title {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  flex: 1;
}

.ranking-rank {
  font-size: 14px;
  font-weight: 600;
  color: #0066cc;
  padding: 2px 8px;
  background: #eff6ff;
  border-radius: 4px;
  white-space: nowrap;
}

/* Essays Display Styles */
.control-essays {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.essays-empty {
  color: #6b7280;
  font-size: 13px;
  font-style: italic;
  padding: 8px;
}

.essays-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.essay-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.essay-item:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.essay-item.selected {
  background: #eff6ff;
  border-color: #3b82f6;
}

.control-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.list-empty {
  color: #6b7280;
  font-size: 13px;
  font-style: italic;
  padding: 8px;
}

.list-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.list-item-text {
  font-size: 14px;
  color: #111827;
}

.essay-content {
  display: flex;
  align-items: center;
  flex: 1;
}

.essay-title {
  color: #374151;
  font-size: 14px;
  font-weight: 400;
}

/* Essay Ranking Form Styles */
.essay-ranking-form {
  align-items: stretch;
}

.essay-ranking-form-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.essay-ranking-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.essay-ranking-label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.essay-ranking-select,
.essay-ranking-input {
  padding: 8px 12px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 14px;
  color: #212529;
  background-color: #ffffff;
}

.essay-ranking-select:focus,
.essay-ranking-input:focus {
  outline: none;
  border-color: #0066cc;
  box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.1);
}

.essay-ranking-submit {
  padding: 10px 16px;
  background: #0066cc;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  margin-top: 4px;
}

.essay-ranking-submit:hover:not(:disabled) {
  background: #0052a3;
}

.essay-ranking-submit:disabled {
  background: #adb5bd;
  cursor: not-allowed;
  opacity: 0.6;
}

/* Tooltip styles */
.tooltip-icon {
  margin-left: 4px;
  color: #6b7280;
  font-size: 12px;
  cursor: help;
}

.tooltip-popup {
  position: fixed;
  z-index: 9999;
  background: #1f2937;
  color: #ffffff;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  max-width: 280px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  pointer-events: none;
  line-height: 1.4;
}

</style>

