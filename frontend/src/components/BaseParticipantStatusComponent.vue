<script setup>
import { computed } from 'vue'
import MapProgressDisplay from './MapProgressDisplay.vue'

const props = defineProps({
    config: {
        type: Object,
        default: () => ({
            id: '',
            label: 'Base Participant Status',
            visible_if: 'true',
            bindings: []
        })
    },
    /** Map task + Info Dashboard: follower map preview fills panel height below labels. */
    mapTaskFullHeightPreview: {
        type: Boolean,
        default: false
    }
})

const isVisible = computed(() => {
    return props.config.visible_if === 'true' || props.config.visible_if === true
})

// 分类 bindings
const nameBinding = computed(() => {
    return props.config.bindings.find(b => b.label?.toLowerCase() === 'name')
})

const specialtyShapeBinding = computed(() => {
    return props.config.bindings.find(b => b.control === 'shape')
})

const progressBinding = computed(() => {
    return props.config.bindings.find(b => b.control === 'progress')
})

const investmentHistoryBinding = computed(() => {
    return props.config.bindings.find(b => 
        b.control === 'investment_history' || 
        b.path?.includes('investment_history') ||
        b.label?.toLowerCase() === 'investment'
    )
})

const rankingsBinding = computed(() => {
    return props.config.bindings.find(b => 
        b.control === 'rankings' || 
        b.path?.includes('rankings') ||
        b.label?.toLowerCase() === 'rankings'
    )
})

const mapProgressBinding = computed(() => {
    return props.config.bindings.find(b => 
        b.control === 'map_preview' || 
        b.path?.includes('map_progress') ||
        b.label?.toLowerCase() === 'map progress'
    )
})

const otherBindings = computed(() => {
    return props.config.bindings.filter(b => {
        const label = b.label?.toLowerCase()
        const isInvestmentHistory = b.control === 'investment_history' || 
                                    b.path?.includes('investment_history') ||
                                    label === 'investment'
        const isRankings = b.control === 'rankings' || 
                          b.path?.includes('rankings') ||
                          label === 'rankings'
        const isMapProgress = b.control === 'map_preview' || 
                             b.path?.includes('map_progress') ||
                             label === 'map progress'
        return label !== 'name' && 
               b.control !== 'shape' && 
               b.control !== 'progress' &&
               !isInvestmentHistory &&
               !isRankings &&
               !isMapProgress
    })
})

// 将其他字段按两列分组
const otherBindingsRows = computed(() => {
    const rows = []
    for (let i = 0; i < otherBindings.value.length; i += 2) {
        rows.push(otherBindings.value.slice(i, i + 2))
    }
    return rows
})

// 获取进度条的值
const getProgressValue = (binding) => {
    if (binding?.control === 'progress') {
        return binding.value !== undefined ? binding.value : 50
    }
    return 0
}

// 根据任务类型获取形状类名
const getShapeClass = (value) => {
    const shape = (value || '').toLowerCase()
    if (shape === 'circle') return 'shape-circle'
    if (shape === 'triangle') return 'shape-triangle'
    if (shape === 'square') return 'shape-square'
    return 'shape-circle'
}

// 根据任务类型获取形状样式
const getShapeStyle = (value) => {
    const colorMap = {
        circle: '#ef4444',
        triangle: '#3b82f6',
        square: '#10b981'
    }
    const shape = (value || '').toLowerCase()
    const color = colorMap[shape] || '#6b7280'
    
    if (shape === 'triangle') {
        return { borderBottomColor: color }
    }
    return { backgroundColor: color }
}

const getShapeLabel = (value) => {
    if (!value) return ''
    const v = String(value)
    return v.charAt(0).toUpperCase() + v.slice(1).toLowerCase()
}

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
    if (rankingsBinding.value?.value && Array.isArray(rankingsBinding.value.value)) {
        // Sort by rank (ascending: rank 1 is best)
        return [...rankingsBinding.value.value].sort((a, b) => {
            const rankA = a.rank || 999
            const rankB = b.rank || 999
            return rankA - rankB
        })
    }
    return []
})
</script>

<template>
    <div
        v-if="isVisible"
        class="component-module"
        :class="{ 'component-module--maptask-full-preview': mapTaskFullHeightPreview && mapProgressBinding }"
    >
        <!-- 第一行：名字在左边，specialty shape 在右边 -->
        <div v-if="nameBinding || specialtyShapeBinding" class="row first-row">
            <div v-if="nameBinding" class="name-section">
                <span class="field-label">{{ nameBinding.label }}:</span>
                <span class="field-value">{{ nameBinding.value !== undefined ? nameBinding.value : (nameBinding.path || 'N/A') }}</span>
            </div>
            <div v-if="specialtyShapeBinding" class="shape-section">
                <span
                    class="shape-display"
                    :class="getShapeClass(specialtyShapeBinding.value || specialtyShapeBinding.path)"
                    :style="getShapeStyle(specialtyShapeBinding.value || specialtyShapeBinding.path)"
                ></span>
                <span class="shape-text">
                    {{ getShapeLabel(specialtyShapeBinding.value || specialtyShapeBinding.path) }}
                </span>
            </div>
        </div>

        <!-- 第二行开始：其他字段每行两列排布 -->
        <div v-for="(row, rowIndex) in otherBindingsRows" :key="rowIndex" class="row">
            <div v-for="(binding, colIndex) in row" :key="colIndex" class="component-module">
                <span class="field-label">{{ binding.label }}:</span>
                <span class="field-value">{{ binding.value !== undefined ? binding.value : (binding.path || 'N/A') }}</span>
            </div>
        </div>

        <!-- Investment History: 新起一行，全宽显示 -->
        <div v-if="investmentHistoryBinding" class="row investment-history-row">
            <div class="investment-history-section">
                <span class="field-label">{{ investmentHistoryBinding.label }}:</span>
                <div class="control-investment-history">
                    <div
                        v-if="!Array.isArray(investmentHistoryBinding.value) || investmentHistoryBinding.value.length === 0"
                        class="investment-history-empty"
                    >
                        No investment history
                    </div>
                    <div
                        v-else
                        class="investment-history-items"
                    >
                        <div
                            v-for="(investment, index) in investmentHistoryBinding.value"
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
        </div>

        <!-- Map Progress: follower's drawing for map task (guide awareness) -->
        <div
            v-if="mapProgressBinding"
            class="row map-progress-row"
            :class="{ 'map-progress-row--fill': mapTaskFullHeightPreview }"
        >
            <div class="map-progress-section">
                <span class="field-label">{{ mapProgressBinding.label }}:</span>
                <div
                    class="control-map-preview"
                    :class="{ 'control-map-preview--fill': mapTaskFullHeightPreview }"
                >
                    <MapProgressDisplay
                        v-if="mapProgressBinding.value && typeof mapProgressBinding.value === 'object'"
                        :map-progress="mapProgressBinding.value"
                        :fill-height="mapTaskFullHeightPreview"
                    />
                    <img
                        v-else-if="mapProgressBinding.value && typeof mapProgressBinding.value === 'string'"
                        :src="mapProgressBinding.value"
                        alt="Map progress preview"
                        :class="['map-preview-img', { 'map-preview-img--fill': mapTaskFullHeightPreview }]"
                    />
                    <span v-else class="map-progress-empty">No drawing yet</span>
                </div>
            </div>
        </div>

        <!-- Rankings: 新起一行，全宽显示 -->
        <div v-if="rankingsBinding" class="row rankings-row">
            <div class="rankings-section">
                <span class="field-label">{{ rankingsBinding.label }}:</span>
                <div class="control-rankings">
                    <div
                        v-if="!Array.isArray(rankingsBinding.value) || rankingsBinding.value.length === 0"
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
        </div>

        <!-- 最后一行：进度条 -->
        <div v-if="progressBinding" class="row last-row">
            <div class="progress-section">
                <span class="field-label">{{ progressBinding.label }}:</span>
                <div class="control-progress">
                    <div class="progress-bar-container">
                        <div 
                            class="progress-bar-fill" 
                            :style="{ width: `${getProgressValue(progressBinding)}%` }"
                        ></div>
                    </div>
                    <span class="progress-text">{{ getProgressValue(progressBinding) }}%</span>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.component-module {
    border: 1px solid #dee2e6;
    border-radius: 4px;
    padding: 12px;
    background: #ffffff;
    margin-bottom: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    transition: box-shadow 0.3s ease;
}

.component-module--maptask-full-preview {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    margin-bottom: 0;
}

.component-module:hover {
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}

.row {
    display: flex;
    gap: 16px;
    margin-bottom: 12px;
}

.row:last-child {
    margin-bottom: 0;
}

.first-row {
    justify-content: space-between;
    align-items: center;
}

.name-section {
    display: flex;
    align-items: center;
    gap: 8px;
}

.shape-section {
    display: flex;
    align-items: center;
    gap: 8px;
}

.field-item {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
}

.field-label {
    font-weight: 500;
    color: #374151;
    font-size: 13px;
    white-space: nowrap;
}

.field-value {
    color: #212529;
    font-size: 14px;
}

/* Shape Display */
.shape-display {
    width: 24px;
    height: 24px;
    display: inline-block;
}

.shape-display.shape-circle {
    border-radius: 50%;
}

.shape-display.shape-square {
    border-radius: 4px;
}

.shape-display.shape-triangle {
    width: 0;
    height: 0;
    border-left: 12px solid transparent;
    border-right: 12px solid transparent;
    border-bottom: 20px solid;
    background-color: transparent !important;
    border-radius: 0;
}

.shape-text {
    margin-left: 8px;
    font-size: 13px;
    color: #374151;
    font-weight: 500;
    text-transform: capitalize;
}

/* Progress Bar */
.progress-section {
    width: 100%;
    display: flex;
    flex-direction: row;
    gap: 12px;
}

.control-progress {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    margin-top: 4px;
}

.progress-bar-container {
    flex: 1;
    height: 10px;
    background: #e9ecef;
    border-radius: 10px;
    overflow: hidden;
    position: relative;
}

.progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #0066cc 0%, #0052a3 100%);
    border-radius: 10px;
    transition: width 0.3s ease;
    box-shadow: 0 2px 4px rgba(0, 102, 204, 0.2);
}

.progress-text {
    color: #495057;
    font-size: 13px;
    font-weight: 500;
    min-width: 45px;
    text-align: right;
}

/* Investment History Styles */
.investment-history-row {
    flex-direction: column;
    width: 100%;
}

.investment-history-section {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

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

/* Rankings Styles */
.rankings-row {
    flex-direction: column;
    width: 100%;
}

.rankings-section {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

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

/* Map Progress Preview */
.map-progress-row {
    flex-direction: column;
    width: 100%;
}

.map-progress-row--fill {
    flex: 1;
    min-height: 0;
    margin-bottom: 0;
}

.map-progress-section {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.component-module--maptask-full-preview .map-progress-section {
    flex: 1;
    min-height: 0;
}

.control-map-preview {
    width: 100%;
    max-width: 200px;
}

.control-map-preview--fill {
    flex: 1;
    min-height: 0;
    max-width: none;
    display: flex;
    align-items: center;
    justify-content: center;
}

.map-preview-img {
    width: 100%;
    height: auto;
    border-radius: 6px;
    border: 1px solid #e5e7eb;
}

.map-preview-img--fill {
    width: auto;
    height: auto;
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}

.map-progress-empty {
    color: #6b7280;
    font-size: 13px;
    font-style: italic;
}
</style>