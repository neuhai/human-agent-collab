<script setup>
import { computed } from 'vue'
import Panel from '../components/Panel.vue'
import BaseParticipantStatusComponent from '../components/BaseParticipantStatusComponent.vue'

const props = defineProps({
    config: {
        type: Object,
        default: () => ({
            id: '',
            label: 'Info Dashboard',
            description: '',
            visible_if: 'true',
            bindings: []
        })
    },
    participants: {
        type: Array,
        default: () => []
    }
})

const isVisible = computed(() => {
    return props.config.visible_if === 'true' || props.config.visible_if === true
})

// Get my participant ID
const myParticipantId = computed(() => {
    return sessionStorage.getItem('participant_id')
})

// Filter out myself and get other participants
const otherParticipants = computed(() => {
    if (!props.participants || !Array.isArray(props.participants)) {
        return []
    }
    return props.participants.filter(p => {
        const pId = p?.id || p?.participant_id
        return pId && pId !== myParticipantId.value
    })
})

// Build config for each other participant based on the template config
const participantConfigs = computed(() => {
    return otherParticipants.value.map(participant => {
        // Build bindings for this participant using the template bindings
        const bindings = props.config.bindings.map(binding => {
            const path = binding.path
            if (!path || !path.startsWith('Participant.')) {
                return binding
            }
            
            // Extract field name from path (e.g., 'Participant.name' -> 'name')
            const fieldName = path.split('.').slice(1).join('.')
            
            // Get value from participant object (check both top-level and experiment_params)
            let value = participant[fieldName]
            if (value === undefined && participant.experiment_params) {
                value = participant.experiment_params[fieldName]
            }
            
            return {
                ...binding,
                value: value
            }
        })
        
        return {
            ...props.config,
            bindings: bindings,
            participant: participant
        }
    })
})
</script>

<template>
    <Panel v-if="isVisible" :header="config.label || 'Info Dashboard'" :description="config.description || ''">
        <div v-if="participantConfigs.length === 0" class="empty-message">
            No other participants in this session
        </div>
        <div v-else class="participants-list">
            <BaseParticipantStatusComponent 
                v-for="(participantConfig, index) in participantConfigs" 
                :key="participantConfig.participant?.id || index"
                :config="participantConfig" 
            />
        </div>
    </Panel>
</template>

<style scoped>
.participants-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.empty-message {
    padding: 20px;
    text-align: center;
    color: #6b7280;
    font-size: 14px;
}
</style>

<style scoped>
</style>