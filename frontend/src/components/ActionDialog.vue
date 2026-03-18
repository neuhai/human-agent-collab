<script setup>
import { computed } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  dialogType: {
    type: String,
    default: 'confirm' // 'confirm', 'result', or 'vote'
  },
  dialogConfig: {
    type: Object,
    default: null
  },
  dialogItem: {
    type: String,
    default: ''
  },
  dialogMessage: {
    type: String,
    default: ''
  },
  isSubmitting: {
    type: Boolean,
    default: false
  },
  // 用于格式化item的函数
  formatItemName: {
    type: Function,
    default: (item) => item
  },
  // 用于获取shape class的函数
  getItemShapeClass: {
    type: Function,
    default: () => ''
  },
  // 用于获取shape style的函数
  getItemShapeStyle: {
    type: Function,
    default: () => ({})
  },
  // For vote mode
  label: {
    type: String,
    default: ''
  },
  voteLabel: {
    type: String,
    default: 'Please select your preferred candidate'
  },
  voteOptions: {
    type: Array,
    default: () => []
  },
  selectedValue: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['close', 'submit', 'update:selectedValue'])

// 渲染消息部分（支持文本和shape icon）
const renderMessageParts = (messageConfig) => {
  if (!messageConfig || !messageConfig.parts) return []
  return messageConfig.parts
}

// 处理关闭
const handleClose = () => {
  emit('close')
}

// 处理提交
const handleSubmit = () => {
  emit('submit')
}

// 处理选择值变化
const handleValueChange = (event) => {
  emit('update:selectedValue', event.target.value)
}
</script>

<template>
  <div v-if="show" class="dialog-overlay" @click.self="handleClose">
    <div class="dialog-content">
      <!-- Vote Mode -->
      <div v-if="dialogType === 'vote'" class="dialog-vote">
        <div v-if="label" class="dialog-header">
          <h3>{{ label }}</h3>
        </div>
        <div class="dialog-body">
          <div class="vote-form">
            <label>{{ voteLabel }}</label>
            <select 
              :value="selectedValue" 
              @change="handleValueChange"
              class="vote-select"
            >
              <option value="">Select a candidate</option>
              <option v-for="option in voteOptions" :key="option" :value="option">{{ option }}</option>
            </select>
          </div>
        </div>
        <div class="dialog-buttons">
          <button @click="handleSubmit" :disabled="!selectedValue || isSubmitting" class="dialog-btn dialog-btn-yes">
            {{ isSubmitting ? 'Submitting...' : 'Submit' }}
          </button>
          <button @click="handleClose" :disabled="isSubmitting" class="dialog-btn dialog-btn-no">
            Cancel
          </button>
        </div>
      </div>
      <!-- Confirm Mode -->
      <div v-else-if="dialogType === 'confirm' && dialogConfig" class="dialog-confirm">
        <div class="dialog-message">
          <template v-for="(part, index) in renderMessageParts(dialogConfig.confirmMessage(dialogItem))" :key="index">
            <span v-if="part.type === 'shape'">
              <span
                class="task-shape dialog-shape"
                :class="getItemShapeClass(part.value)"
                :style="getItemShapeStyle(part.value)"
              ></span>
              <span>{{ formatItemName(part.value) }}</span>
            </span>
            <span v-else>{{ part.text }}</span>
          </template>
        </div>
        <div class="dialog-buttons">
          <button @click="handleSubmit" :disabled="isSubmitting" class="dialog-btn dialog-btn-yes">
            {{ isSubmitting ? 'Submitting...' : 'Yes' }}
          </button>
          <button @click="handleClose" :disabled="isSubmitting" class="dialog-btn dialog-btn-no">
            No
          </button>
        </div>
      </div>
      <!-- Result Mode -->
      <div v-else-if="dialogType === 'result' && dialogConfig" class="dialog-result">
        <div class="dialog-message">
          <template v-if="dialogMessage === 'success'">
            <template v-for="(part, index) in renderMessageParts(dialogConfig.successMessage(dialogItem))" :key="index">
              <span v-if="part.type === 'shape'">
                <span
                  class="task-shape dialog-shape"
                  :class="getItemShapeClass(part.value)"
                  :style="getItemShapeStyle(part.value)"
                ></span>
                <span>{{ formatItemName(part.value) }}</span>
              </span>
              <span v-else>{{ part.text }}</span>
            </template>
          </template>
          <template v-else-if="dialogMessage === 'error_inventory'">
            <template v-for="(part, index) in renderMessageParts(dialogConfig.errorMessage(dialogItem))" :key="index">
              <span v-if="part.type === 'shape'">
                <span
                  class="task-shape dialog-shape"
                  :class="getItemShapeClass(part.value)"
                  :style="getItemShapeStyle(part.value)"
                ></span>
                <span>{{ formatItemName(part.value) }}</span>
              </span>
              <span v-else>{{ part.text }}</span>
            </template>
          </template>
          <template v-else>
            {{ dialogMessage }}
          </template>
        </div>
        <div class="dialog-buttons">
          <button @click="handleClose" class="dialog-btn dialog-btn-ok">
            OK
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Dialog Styles */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.dialog-content {
  background: #ffffff;
  border-radius: 8px;
  padding: 24px;
  min-width: 400px;
  max-width: 500px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.dialog-confirm,
.dialog-result,
.dialog-vote {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dialog-header {
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 16px;
}

.dialog-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.dialog-body {
  flex: 1;
}

.vote-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vote-form label {
  font-size: 16px;
  font-weight: 500;
  color: #111827;
}

.vote-select {
  padding: 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  width: 100%;
}

.dialog-message {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 16px;
  color: #374151;
  text-align: center;
  line-height: 1.5;
  flex-wrap: wrap;
}

.dialog-shape {
  width: 20px;
  height: 20px;
  margin: 0 4px;
}

.dialog-shape.shape-triangle {
  width: 0;
  height: 0;
  border-left: 10px solid transparent;
  border-right: 10px solid transparent;
  border-bottom: 18px solid;
  background-color: transparent !important;
}

.dialog-buttons {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.dialog-btn {
  padding: 10px 24px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 80px;
}

.dialog-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.dialog-btn-yes {
  background: #0066cc;
  color: white;
}

.dialog-btn-yes:hover:not(:disabled) {
  background: #0052a3;
}

.dialog-btn-no {
  background: #e5e7eb;
  color: #374151;
}

.dialog-btn-no:hover:not(:disabled) {
  background: #d1d5db;
}

.dialog-btn-ok {
  background: #0066cc;
  color: white;
}

.dialog-btn-ok:hover {
  background: #0052a3;
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
</style>

