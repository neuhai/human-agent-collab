<template>
  <div class="modal-overlay" v-if="visible">
    <div class="modal-content">
      <div class="modal-header">
        <h3>API Key Required</h3>
      </div>
      <div class="modal-body">
        <p>
          An API key for either OpenAI or Claude is required to use the AI features of this application.
        </p>
        <p>
          Please add your API key to the <code>.env</code> or <code>.env.prod</code> file in the <code>deployment</code> directory.
        </p>
      </div>
      <div class="modal-footer">
        <button class="btn primary" @click="$emit('recheck')">I have updated the AI API key</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: Boolean
})
defineEmits(['recheck'])
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 20px;
  border-radius: 8px;
  max-width: 500px;
  width: 90%;
}

.modal-header {
  margin-bottom: 10px;
}

.modal-body p {
  margin-bottom: 10px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn.primary {
  background-color: #007bff;
  color: white;
}
</style>
