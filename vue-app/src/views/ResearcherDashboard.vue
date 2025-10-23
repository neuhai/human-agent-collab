<template>
  <div class="researcher-container">
    <!-- TOP CONTROL BUTTONS -->
    <div class="top-controls">
      <div class="timer-display">
        <div class="timer-value">{{ timerDisplay }}</div>
        <div v-if="isSessionRegistered" class="current-session-display">
          <div class="session-label">Session: {{ currentSessionCode }}</div>
        </div>
      </div>
      
      

      <div class="control-buttons">
        <button 
          class="control-rect start" 
          :class="{ 'paused': experimentStatus === 'paused' }"
          @click="toggleExperiment"
          :disabled="!isSessionRegistered || !canStartExperiment"
          title="Start experiment (requires active session)"
        >
          <span class="button-icon">{{ startButtonIcon }}</span>
          <span class="button-text">{{ startButtonText }}</span>
        </button>
        <button 
          class="control-rect reset" 
          @click="resetTimer"
          :disabled="!isSessionRegistered || experimentStatus === 'waiting'"
          title="Reset timer and clear game data (requires active session)"
        >
          <span class="button-text">Reset</span>
        </button>
        <button class="control-rect end" @click="resetExperiment"
          :disabled="!isSessionRegistered || !canStartExperiment"
          title="End experiment and delete session (requires active session)">END</button>
      </div>
    </div>

    <!-- MAIN SECTION HEADERS (CLICKABLE TABS) -->
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

    <!-- CONTENT GRID: 4 COLUMNS; RENDER ONLY THE ACTIVE TAB CONTENT -->
    <div class="tab-group-card">
      <!-- <div class="group-header">{{ activeTabTitle }}</div> -->
      <div class="tab-content-grid" :class="{ 
        'monitor-mode': activeTab === 'monitor',
        'setup-mode': activeTab === 'setup',
        'analysis-mode': activeTab === 'analysis'
      }">
        <!-- Setup Tab: Progressive Workflow -->
        <div class="tab-col setup-tab" v-if="activeTab === 'setup'">
          <!-- Subtabs Navigation -->
          <div class="subtab-navigation">
            <div class="subtab-container">
              <div 
                v-for="(step, index) in setupWorkflowSteps" 
                :key="step.id"
                class="subtab-item"
                :class="{ 
                  active: activeSetupTab === step.id,
                  visible: setupTabs[step.id],
                  disabled: !setupTabs[step.id]
                }"
                @click="navigateToSetupTab(step.id)"
                v-show="setupTabs[step.id]"
              >
                <div class="subtab-number">{{ index + 1 }}</div>
                <div class="subtab-label">{{ step.label }}</div>
              </div>
            </div>
          </div>

          <!-- Setup Content - Side by Side Tabs -->
          <div class="setup-content">
            <div class="setup-tabs-container">
              <!-- Tab 1: Initial Selection -->
              <div v-if="setupTabs.initialSelection" class="setup-tab-panel" :class="{ active: activeSetupTab === 'initialSelection' }" data-tab-id="initialSelection">
                <div class="workflow-step">
                  <div class="step-content">
                    <div class="initial-message">
                      <h2>I want to...</h2>
                      <div class="initial-options">
                        <button 
                          class="initial-option-btn"
                          @click="loadExistingSession"
                        >
                          <div class="option-icon">📂</div>
                          <div class="option-text">Load Existing Session</div>
                        </button>
                        <button 
                          class="initial-option-btn"
                          @click="showCreateSessionModal = true"
                        >
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
                      <button 
                        v-if="previewedExperiment"
                        @click="confirmExperimentSelection"
                        class="step-btn primary"
                      >
                        Select and Configure {{ getPreviewedExperiment()?.name }}
                      </button>
                  </div>
              
                    <!-- Two-column layout for experiment selection -->
                    <div class="experiment-selection-layout">
                      <!-- Left section: Current experiment selection content -->
                      <div class="experiment-selection-left">
                        <div class="experiment-option-section">
                          <div class="option-label">Option 1: Selecting From Existing Experiments</div>
                          
                          <!-- Tag Filter Section -->
                          <div class="tag-filter-section">
                            <div class="tag-filter-header">
                              <span class="tag-filter-label">Filter by tags:</span>
                              <button 
                                v-if="selectedTags.length > 0" 
                                @click="clearAllTags" 
                                class="clear-tags-btn"
                              >
                                Clear all
                              </button>
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
                                  <svg 
                                    class="dropdown-icon" 
                                    :class="{ expanded: isExperimentExpanded(exp.id) }"
                                    viewBox="0 0 20 20" 
                                    fill="currentColor"
                                  >
                                    <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
                                  </svg>
                                </div>
                                <div 
                                  v-if="isExperimentExpanded(exp.id)"
                                  class="experiment-item-content"
                                >
                                  <div class="experiment-tags">
                                    <span
                                      v-for="tag in exp.tags"
                                      :key="tag"
                                      class="experiment-tag"
                                    >
                                      {{ tag }}
                                    </span>
                                  </div>
                                  <div class="experiment-description-preview" v-html="getFormattedExperimentDescription(exp.description)">
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
              <!-- Upload Template Config File Section -->
                        <div class="upload-option-section">
                          <div class="option-label">Option 2: Upload Customized Experiment Configuration File</div>
                  <button 
                    @click="triggerFileUpload" 
                    class="upload-config-btn"
                    :disabled="isUploadingConfig"
                    title="Upload custom experiment configuration file (JSON or YAML/ECL format)"
                  >
                    <span v-if="isUploadingConfig">Uploading...</span>
                    <span v-else>Upload Config File</span>
                  </button>
                <input 
                  ref="fileInputRef"
                  type="file" 
                  accept=".json,.yaml,.yml"
                  @change="handleFileUpload"
                  style="display: none;"
                />
                <!-- Validation Status -->
                <div v-if="configValidationStatus" class="validation-status" :class="configValidationStatus.type">
                  <span class="validation-icon">{{ configValidationStatus.type === 'error' ? '❌' : '✅' }}</span>
                  <span class="validation-message">{{ configValidationStatus.message }}</span>
                </div>
                </div>
              </div>
              
              
              
                      <!-- Right section: Experiment Illustration (show when experiment is previewed or selected) -->
                      <div v-if="previewedExperiment || selectedExperimentType" class="experiment-illustration-section">
                        <div class="illustration-header">
                          <h3>Experiment Illustration</h3>
                          <p class="illustration-subtitle">
                            {{ previewedExperiment ? getPreviewedExperiment()?.name : getCurrentExperimentName() }}
                          </p>
              </div>
                        <!-- Show actual illustration for Shape Factory, placeholder for others -->
                        <div v-if="(previewedExperiment ? getPreviewedExperiment()?.id : selectedExperimentType) === 'shapefactory'" class="experiment-illustration">
                          <img src="@/assets/shapefactory_illustration.png" alt="Shape Factory Experiment Illustration" class="illustration-image" />
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
                <button 
                    class="step-btn primary"
                    @click="proceedToInteractionVariables"
                  >
                    Confirm Config
                  </button>
              </div>

              <div class="config-section">
                <!-- General Settings (always shown) -->
                <div class="config-cluster">
                  <div class="cluster-title collapsible" @click="toggleParameterCluster('generalSettings')">
                    <span class="collapse-icon" :class="{ expanded: parameterClustersExpanded.generalSettings }">▼</span>
                    <span>General Settings</span>
                  </div>
                  <div class="config-grid" v-show="parameterClustersExpanded.generalSettings">
                    <div class="config-group">
                        <label for="session-duration">Session Duration (minutes)</label>
                      <input 
                        type="number" 
                        id="session-duration" 
                        v-model="experimentConfig.sessionDuration" 
                        min="5" 
                        max="120" 
                        step="5" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                  </div>
                </div>

                <!-- WordGuessing Settings -->
                <div v-if="selectedExperimentType === 'wordguessing'" class="config-cluster">
                  <div class="cluster-title collapsible" @click="toggleParameterCluster('wordguessing')">
                    <span class="collapse-icon" :class="{ expanded: parameterClustersExpanded.wordguessing }">▼</span>
                    <span>WordGuessing Settings</span>
                  </div>
                  <div class="config-grid" v-show="parameterClustersExpanded.wordguessing">
                    <div class="config-group">
                      <label for="word-assignment">Word Assignment</label>
                      <textarea 
                        id="word-assignment" 
                        v-model="wordAssignmentText" 
                        placeholder="Enter words separated by commas (e.g., apple, banana, cherry)"
                        rows="3"
                        @change="updateWordAssignment"
                      ></textarea>
                      <div class="form-helper">
                        Words will be automatically assigned to hinter participants when you register them. Use the session duration setting above to control the game length.
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Money Settings -->
                <div v-if="showMoneyParameters" class="config-cluster">
                  <div class="cluster-title collapsible" @click="toggleParameterCluster('money')">
                    <span class="collapse-icon" :class="{ expanded: parameterClustersExpanded.money }">▼</span>
                    <span>Money</span>
                  </div>
                  <div class="config-grid" v-show="parameterClustersExpanded.money">
                    <div class="config-group">
                        <label for="starting-money">Participant Initial Money ($)</label>
                      <input 
                        type="number" 
                        id="starting-money" 
                        v-model="experimentConfig.startingMoney" 
                        min="50" 
                        max="5000" 
                        step="10" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                    <div v-if="showShapeParameters" class="config-group">
                        <label for="regular-cost">Regular Shape Production Cost ($)</label>
                      <input 
                        type="number" 
                        id="regular-cost" 
                        v-model="experimentConfig.regularCost" 
                        min="1" 
                        max="100" 
                        step="1" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                    <div v-if="showShapeParameters" class="config-group">
                        <label for="specialty-cost">Specialty Production Cost ($)</label>
                      <input 
                        type="number" 
                        id="specialty-cost" 
                        v-model="experimentConfig.specialtyCost" 
                        min="1" 
                        max="100" 
                        step="1" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                    <div v-if="showTradeParameters" class="config-group">
                        <label for="min-trade-price">Min. Trade Price ($)</label>
                      <input 
                        type="number" 
                        id="min-trade-price" 
                        v-model="experimentConfig.minTradePrice" 
                        min="1" 
                        max="100" 
                        step="1" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                    <div v-if="showTradeParameters" class="config-group">
                      <label for="max-trade-price">Max. Trade Price ($)</label>
                      <input 
                        type="number" 
                        id="max-trade-price" 
                        v-model="experimentConfig.maxTradePrice" 
                        min="1" 
                        max="200" 
                        step="1" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                    <div v-if="showMoneyParameters" class="config-group">
                      <label for="incentive-money">Order Incentive ($/shape fulfilled)</label>
                      <input 
                        type="number" 
                        id="incentive-money" 
                        v-model="experimentConfig.incentiveMoney" 
                        min="1" 
                        max="1000" 
                        step="1" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                  </div>
                </div>

                <!-- Shape Production & Order -->
                <div v-if="showProductionParameters" class="config-cluster">
                  <div class="cluster-title collapsible" @click="toggleParameterCluster('shapeProduction')">
                    <span class="collapse-icon" :class="{ expanded: parameterClustersExpanded.shapeProduction }">▼</span>
                    <span>Shape Production & Order</span>
                  </div>
                  <div class="config-grid" v-show="parameterClustersExpanded.shapeProduction">
                    <div class="config-group">
                      <label for="production-time">Production Time (sec)
                        <span 
                          class="tooltip-icon" 
                          @mouseenter="activeTooltip = 'productionTime'" 
                          @mousemove="updateTooltipPosition($event)"
                          @mouseleave="activeTooltip = null"
                        >ⓘ</span>
                      </label>
                      <div v-if="activeTooltip === 'productionTime'" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">
                        Time required to produce one shape.
                      </div>
                      <input 
                        type="number" 
                        id="production-time" 
                        v-model="experimentConfig.productionTime" 
                        min="1" 
                        max="600" 
                        step="1" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                    <div class="config-group">
                      <label for="max-production-num"># Max Production
                        <span 
                          class="tooltip-icon" 
                          @mouseenter="activeTooltip = 'maxProductionNum'" 
                          @mousemove="updateTooltipPosition($event)"
                          @mouseleave="activeTooltip = null"
                        >ⓘ</span>
                      </label>
                      <div v-if="activeTooltip === 'maxProductionNum'" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">
                        Maximum total number of shapes a participant can produce (specialty and non-specialty combined).
                      </div>
                      <input 
                        type="number" 
                        id="max-production-num" 
                        v-model="experimentConfig.maxProductionNum" 
                        min="1" 
                        max="1000" 
                        step="1" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                    <div class="config-group">
                      <label for="shape-order-number"># Shape Order
                        <span 
                          class="tooltip-icon" 
                          @mouseenter="activeTooltip = 'shapeOrder'" 
                          @mousemove="updateTooltipPosition($event)"
                          @mouseleave="activeTooltip = null"
                        >ⓘ</span>
                      </label>
                      <div v-if="activeTooltip === 'shapeOrder'" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">
                        Number of shapes required to complete one order.
                      </div>
                      <input 
                        type="number" 
                        id="shape-order-number" 
                        v-model="experimentConfig.shapesPerOrder" 
                        min="1" 
                        max="50" 
                        step="1" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                    <div class="config-group">
                      <label for="num-shape-types"># Shape Types
                        <span 
                          class="tooltip-icon" 
                          @mouseenter="activeTooltip = 'shapeTypes'" 
                          @mousemove="updateTooltipPosition($event)"
                          @mouseleave="activeTooltip = null"
                        >ⓘ</span>
                      </label>
                      <div v-if="activeTooltip === 'shapeTypes'" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">
                        Number of distinct shape categories in the game.
                      </div>
                      <input 
                        type="number" 
                        id="num-shape-types" 
                        v-model="experimentConfig.numShapeTypes" 
                        min="1" 
                        max="5" 
                        step="1" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                  </div>
                </div>

                <!-- Experiment-specific parameters -->
                <div v-if="getCurrentExperimentSpecificParams().length > 0" class="config-cluster">
                  <div class="cluster-title collapsible" @click="toggleParameterCluster('experimentSpecific')">
                    <span class="collapse-icon" :class="{ expanded: parameterClustersExpanded.experimentSpecific }">▼</span>
                    <span>{{ getCurrentExperimentName() }} Specific</span>
                  </div>
                  <div class="config-grid" v-show="parameterClustersExpanded.experimentSpecific">
                    <div 
                      v-for="param in getCurrentExperimentSpecificParams()" 
                      :key="param.key"
                      class="config-group"
                    >
                      <label :for="param.key">{{ param.label }}</label>
                      <!-- Select input for dropdown parameters -->
                      <select 
                        v-if="param.type === 'select'"
                        :id="param.key" 
                        v-model="experimentConfig[param.key]" 
                        @change="updateExperimentConfig"
                        class="config-select"
                      >
                        <option 
                          v-for="option in param.options" 
                          :key="option.value" 
                          :value="option.value"
                        >
                          {{ option.label }}
                        </option>
                      </select>
                      <!-- Regular input for number/text parameters -->
                      <input 
                        v-else
                        :type="param.type" 
                        :id="param.key" 
                        v-model="experimentConfig[param.key]" 
                        :min="param.min" 
                        :max="param.max" 
                        :step="param.step" 
                        @change="updateExperimentConfig" 
                      />
                    </div>
                  </div>
                </div>
              </div>

              <!-- Essay Ranking Parameters -->
              <div v-if="showEssayParameters" class="config-cluster">
                <div class="cluster-title collapsible" @click="toggleParameterCluster('essayRanking')">
                  <span class="collapse-icon" :class="{ expanded: parameterClustersExpanded.essayRanking }">▼</span>
                  <span>Essay Ranking Settings</span>
                </div>
                <div class="config-grid" v-show="parameterClustersExpanded.essayRanking">
                  <div class="config-group">
                    <label for="essay_number">Number of Essays</label>
                    <input 
                      type="number" 
                      id="essay_number" 
                      v-model="experimentConfig.essay_number" 
                      min="1" 
                      max="20" 
                      step="1" 
                      @change="updateExperimentConfig" 
                    />
                  </div>
                  <div class="config-group">
                    <label for="score_scale">Score Scale</label>
                    <select 
                      id="score_scale" 
                      v-model="experimentConfig.score_scale" 
                      @change="updateExperimentConfig"
                      class="config-select"
                    >
                      <option value="1-5">1 to 5</option>
                      <option value="1-7">1 to 7</option>
                      <option value="1-10">1 to 10</option>
                      <option value="0-10">0 to 10</option>
                    </select>
                  </div>
                  
                  <!-- Essay Upload Section -->
                  <div class="config-group essay-upload-section full-width">
                    <label>Upload Essays (PDF)</label>
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
                        @click="() => ($refs.essayFileInput as HTMLInputElement)?.click()"
                        :disabled="!isSessionRegistered"
                      >
                        <i class="fa-solid fa-upload"></i> Upload PDF Essays
                      </button>
                    </div>
                    
                    <!-- Uploaded Essays List -->
                    <div v-if="uploadedEssays.length > 0" class="uploaded-essays-list">
                      <h4>Uploaded Essays:</h4>
                      <div 
                        v-for="(essay, index) in uploadedEssays" 
                        :key="essay.id"
                        class="essay-item"
                      >
                        <div class="essay-info">
                          <i class="fa-solid fa-file-pdf"></i>
                          <span class="essay-title">{{ essay.title }}</span>
                          <span class="essay-filename">({{ essay.filename }})</span>
                        </div>
                        <button 
                          type="button" 
                          class="remove-essay-btn"
                          @click="removeEssay(index)"
                          title="Remove essay"
                        >
                          <i class="fa-solid fa-times"></i>
                        </button>
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
                  <button 
                    class="step-btn primary"
                    @click="proceedToParticipantRegistration"
                  >
                    Confirm Interaction Control
                  </button>
                </div>
                
                <!-- Split Layout: Variables on left, Preview on right -->
                <div class="interaction-variables-layout">
                  <!-- Left Column: Interaction Variables -->
                  <div class="variables-column">
                
              <!-- Information Flow Section -->
              <div class="information-flow-section">
                <div class="cluster-title collapsible" @click="toggleInteractionSection('informationFlow')">
                  <span class="collapse-icon" :class="{ expanded: interactionSectionsExpanded.informationFlow }">▼</span>
                  <span>Information Flow</span>
                </div>
                <div class="variables-grid" v-show="interactionSectionsExpanded.informationFlow">
                <div class="variable-group clickable-entry" 
                     :class="{ selected: selectedInteractionEntry === 'communication' }"
                     @click="selectInteractionEntry('communication')">
                    <label for="communication-level">
                      Communication Level
                      <span 
                        class="tooltip-icon" 
                        @mouseenter="activeTooltip = 'communicationLevel'" 
                        @mousemove="updateTooltipPosition($event)"
                        @mouseleave="activeTooltip = null"
                      >ⓘ</span>
                    </label>
                    <div v-if="activeTooltip === 'communicationLevel'" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">
                      Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed.
                    </div>
                  <div class="custom-select-wrapper">
                    <div class="custom-select-trigger" @click.stop="ensureInteractionSelected('communication'); toggleCommDropdown()">
                      <div class="selected-content">
                        <span class="selected-option" :class="interactionConfig.communicationLevel">
                          {{ getCommunicationModeLabel(interactionConfig.communicationLevel) }}
                        </span>
                      </div>
                      <span class="dropdown-arrow">▼</span>
                    </div>
                    <div class="custom-dropdown-menu" v-if="showCommDropdown">
                      <div 
                        class="dropdown-item" 
                        v-for="option in commOptions" 
                        :key="option.value"
                        @click.stop="ensureInteractionSelected('communication'); selectCommOption(option.value)"
                      >
                        <div class="option-content">
                          <span class="option-tag" :class="option.value">{{ option.label }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <!-- Communication Level Description -->
                  <div class="communication-description">
                    {{ getCommunicationModeDescription(interactionConfig.communicationLevel) }}
                  </div>
                </div>
                  
                <div class="variable-group clickable-entry" 
                     :class="{ selected: selectedInteractionEntry === 'awareness' }"
                     @click="selectInteractionEntry('awareness')">
                    <label for="awareness-dashboard">
                      Awareness Dashboard
                      <span 
                        class="tooltip-icon" 
                        @mouseenter="activeTooltip = 'awarenessDashboard'" 
                        @mousemove="updateTooltipPosition($event)"
                        @mouseleave="activeTooltip = null"
                      >ⓘ</span>
                    </label>
                    <div v-if="activeTooltip === 'awarenessDashboard'" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">
                      Participants see others' money and order progress in real time when enabled.
                      </div>
                    <div class="toggle-switch" @click.stop="ensureInteractionSelected('awareness')">
                      <input 
                        type="checkbox" 
                        id="awareness-dashboard-toggle"
                        v-model="interactionConfig.awarenessDashboard"
                        true-value="on"
                        false-value="off"
                        class="toggle-input"
                        @change="ensureInteractionSelected('awareness')"
                      />
                      <label for="awareness-dashboard-toggle" class="toggle-label">
                        <span class="toggle-text off-text">ON</span>
                        <span class="toggle-text on-text">OFF</span>
                        <span class="toggle-slider">
                          <span class="toggle-indicator"></span>
                        </span>
                      </label>
                    </div>
                    <!-- Awareness Dashboard Options (shown when ON) -->
                    <div v-if="interactionConfig.awarenessDashboard === 'on'" class="awareness-options">
                      <div class="options-row">
                        <label class="option-item" v-if="currentExperimentInterfaceConfig?.awarenessDashboard.showMoney !== false">
                          <input type="checkbox" v-model="awarenessDisplayOptions.money" />
                          <span>Money</span>
                        </label>
                        <label class="option-item" v-if="currentExperimentInterfaceConfig?.awarenessDashboard.showProductionCount !== false">
                          <input type="checkbox" v-model="awarenessDisplayOptions.production" />
                          <span>Production Count</span>
                        </label>
                        <label class="option-item" v-if="currentExperimentInterfaceConfig?.awarenessDashboard.showOrderProgress !== false">
                          <input type="checkbox" v-model="awarenessDisplayOptions.orders" />
                          <span>Order Progress</span>
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- Action Structures Section -->
              <div v-if="currentExperimentInterfaceConfig?.actionStructures.enabled !== false" class="action-structures-section">
                <div class="cluster-title collapsible" @click="toggleInteractionSection('actionStructures')">
                  <span class="collapse-icon" :class="{ expanded: interactionSectionsExpanded.actionStructures }">▼</span>
                  <span>Action Structures</span>
                </div>
                <div class="variables-grid" v-show="interactionSectionsExpanded.actionStructures">
                <!-- Negotiations -->
                <div class="variable-group">
                    <label for="negotiations">
                      Negotiations
                      <span 
                        class="tooltip-icon" 
                        @mouseenter="activeTooltip = 'negotiations'" 
                        @mousemove="updateTooltipPosition($event)"
                        @mouseleave="activeTooltip = null"
                      >ⓘ</span>
                    </label>
                    <div v-if="activeTooltip === 'negotiations'" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">
                      Counter: Participants can make counter-offers. No Counter: Offers can only be accepted or rejected.
                      </div>
                    <div class="toggle-switch">
                      <input 
                        type="checkbox" 
                        id="negotiations-toggle"
                        v-model="interactionConfig.negotiations"
                        true-value="counter"
                        false-value="no_counter"
                        class="toggle-input"
                      />
                      <label for="negotiations-toggle" class="toggle-label">
                        <span class="toggle-text off-text">COUNTER</span>
                        <span class="toggle-text on-text">NO COUNTER</span>
                        <span class="toggle-slider">
                          <span class="toggle-indicator"></span>
                        </span>
                      </label>
                  </div>
                </div>
                
                <!-- Simultaneous Actions -->
                <div class="variable-group">
                    <label for="simultaneous-actions">
                      Simultaneous Actions
                      <span 
                        class="tooltip-icon" 
                        @mouseenter="activeTooltip = 'simultaneousActions'" 
                        @mousemove="updateTooltipPosition($event)"
                        @mouseleave="activeTooltip = null"
                      >ⓘ</span>
                    </label>
                    <div v-if="activeTooltip === 'simultaneousActions'" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">
                      Allow: Multiple offers can be made at once. Not Allow: Each offer must be resolved before a new one begins.
                      </div>
                    <div class="toggle-switch">
                      <input 
                        type="checkbox" 
                        id="simultaneous-actions-toggle"
                        v-model="interactionConfig.simultaneousActions"
                        true-value="allow"
                        false-value="not_allow"
                        class="toggle-input"
                      />
                      <label for="simultaneous-actions-toggle" class="toggle-label">
                        <span class="toggle-text off-text">ALLOWED</span>
                        <span class="toggle-text on-text">NOT ALLOWED</span>
                        <span class="toggle-slider">
                          <span class="toggle-indicator"></span>
                        </span>
                      </label>
                    </div>
                        </div>
                  
                  
                </div>
              </div>
              
              <!-- Agent Behaviors Section -->
              <div class="agent-behaviors-section">
                <div class="cluster-title collapsible" @click="toggleInteractionSection('agentBehaviors')">
                  <span class="collapse-icon" :class="{ expanded: interactionSectionsExpanded.agentBehaviors }">▼</span>
                  <span>Agent Behaviors</span>
                </div>
                <div class="variables-grid" v-show="interactionSectionsExpanded.agentBehaviors">
                <div class="variable-group">
                  <div class="config-group">
                    <label for="agent-perception-time">Agent Perception Time Window (sec)
                      <span 
                        class="tooltip-icon" 
                        @mouseenter="activeTooltip = 'agentPerceptionTime'" 
                        @mousemove="updateTooltipPosition($event)"
                        @mouseleave="activeTooltip = null"
                      >ⓘ</span>
                    </label>
                    <div v-if="activeTooltip === 'agentPerceptionTime'" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">
                      Frequency (in seconds) at which agents update their view of the game state.
                    </div>
                    <input 
                      type="number" 
                      id="agent-perception-time" 
                      v-model="experimentConfig.agentPerceptionTimeWindow" 
                      min="1" 
                      max="300" 
                      step="1" 
                      @change="updateExperimentConfig" 
                    />
                  </div>
                </div>
                  
                <div class="variable-group">
                    <label for="agent-rationales">
                      Rationales
                      <span 
                        class="tooltip-icon" 
                        @mouseenter="activeTooltip = 'rationales'" 
                        @mousemove="updateTooltipPosition($event)"
                        @mouseleave="activeTooltip = null"
                      >ⓘ</span>
                    </label>
                    <div v-if="activeTooltip === 'rationales'" class="custom-tooltip" :style="{ left: paramTooltipPosition.x + 'px', top: paramTooltipPosition.y + 'px' }">
                      Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning.
                    </div>
                    <div class="toggle-switch">
                      <input 
                        type="checkbox" 
                        id="agent-rationales-toggle"
                        v-model="interactionConfig.rationales"
                        true-value="step_wise"
                        false-value="none"
                        class="toggle-input"
                      />
                      <label for="agent-rationales-toggle" class="toggle-label">
                        <span class="toggle-text off-text">STEP-WISE</span>
                        <span class="toggle-text on-text">NONE</span>
                        <span class="toggle-slider">
                          <span class="toggle-indicator"></span>
                        </span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>
                  </div>

                  <!-- Right Column: Conditional Preview -->
                  <div class="preview-column">
                    <div class="section-title">Preview</div>
                    <div class="conditional-preview">
                      <!-- Communication Level Preview -->
                      <div v-if="selectedInteractionEntry === 'communication'" class="preview-component">
                        <!-- Chat Mode Preview -->
                        <div v-if="interactionConfig.communicationLevel === 'chat'" class="panel">
                          <!-- <h3 class="panel-header">Direct Messages</h3> -->
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
                                    <div class="message-sender">You</div>
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
                        
                        <!-- Broadcast Mode Preview -->
                        <div v-else-if="interactionConfig.communicationLevel === 'broadcast'" class="panel">
                          <!-- <h3 class="panel-header">Public Messages</h3> -->
                          <div class="panel-body">
                            <div class="broadcast-mode">
                              <!-- <div class="broadcast-info">
                                <h4>Public Message Pool</h4>
                                <p>All participants can see and send messages in a group.</p>
                              </div> -->
                              <div class="message-thread">
                                <div class="message-history">
                                  <div class="message-item broadcast-message other-message">
                                    <div class="message-sender">Player1</div>
                                    <div class="message-content">Anyone want to trade circles?</div>
                                    <div class="message-time">10:30</div>
                                  </div>
                                  <div class="message-item broadcast-message other-message">
                                    <div class="message-sender">Player2</div>
                                    <div class="message-content">I have circles, need squares</div>
                                    <div class="message-time">10:32</div>
                                  </div>
                                </div>
                              </div>
                              <div class="message-input-area">
                                <input type="text" placeholder="Type your broadcast message..." class="message-input" />
                                <button class="send-btn">Broadcast</button>
                              </div>
                            </div>
                          </div>
                        </div>

                        <!-- No Chat Mode -->
                        <div v-else class="no-preview">
                          <p>No communication preview available</p>
                            </div>
                          </div>

                      <!-- Awareness Dashboard Preview -->
                      <div v-else-if="selectedInteractionEntry === 'awareness' && interactionConfig.awarenessDashboard === 'on'" class="preview-component" :key="`awareness-${selectedExperimentType}`">
                        <div class="panel awareness-panel">
                          <h3 class="panel-header">All Participant Status</h3>
                          <div class="panel-body">
                            <div class="participants-status-grid">
                              <div class="participant-status-card">
                                <div class="participant-header">
                                  <div class="component-text">Player1</div>
                                  <div 
                                    v-if="selectedExperimentType === 'shapefactory' || (selectedExperimentType.startsWith('custom_') && experimentConfig.specialtyCost !== undefined)"
                                    class="participant-specialty">
                                    <span class="shape-icon circle"></span>
                                    <span class="component-text">Circle</span>
                                  </div>
                                      </div>
                                <div class="participant-stats">
                                  <div v-if="currentExperimentInterfaceConfig?.awarenessDashboard.showMoney || currentExperimentInterfaceConfig?.awarenessDashboard.showProductionCount" class="stats-row">
                                    <div v-if="currentExperimentInterfaceConfig?.awarenessDashboard.showMoney" class="component-module">
                                      <span class="component-text">Money:</span>
                                      <span class="component-num">$300</span>
                                    </div>
                                    <div v-if="currentExperimentInterfaceConfig?.awarenessDashboard.showProductionCount" class="component-module">
                                      <span class="component-text">Production:</span>
                                      <span class="component-num">2/6</span>
                                    </div>
                                  </div>
                                  <div v-if="currentExperimentInterfaceConfig?.awarenessDashboard.showOrderProgress" class="progress-label">
                                    <span class="component-text">Orders: 1/3</span>
                                  </div>
                                </div>
                                  </div>
                              <div class="participant-status-card">
                                <div class="participant-header">
                                  <div class="component-text">Player2</div>
                                  <div 
                                    v-if="selectedExperimentType === 'shapefactory' || (selectedExperimentType.startsWith('custom_') && experimentConfig.specialtyCost !== undefined)"
                                    class="participant-specialty">
                                    <span class="shape-icon square"></span>
                                    <span class="component-text">Square</span>
                                  </div>
                                              </div>
                                <div class="participant-stats">
                                  <div v-if="currentExperimentInterfaceConfig?.awarenessDashboard.showMoney || currentExperimentInterfaceConfig?.awarenessDashboard.showProductionCount" class="stats-row">
                                    <div v-if="currentExperimentInterfaceConfig?.awarenessDashboard.showMoney" class="component-module">
                                      <span class="component-text">Money:</span>
                                      <span class="component-num">$250</span>
                                    </div>
                                    <div v-if="currentExperimentInterfaceConfig?.awarenessDashboard.showProductionCount" class="component-module">
                                      <span class="component-text">Production:</span>
                                      <span class="component-num">1/6</span>
                                    </div>
                                  </div>
                                  <div v-if="currentExperimentInterfaceConfig?.awarenessDashboard.showOrderProgress" class="progress-label">
                                    <span class="component-text">Orders: 0/3</span>
                                  </div>
                                </div>
                                              </div>
                                            </div>
                                          </div>
                                        </div>
                                      </div>
                                      
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
                  <!-- Individual Participant Registration Form -->
                  <div class="manage-forms">
                    <div class="form-card">
                      <div class="card-title">Individual Participant Registration</div>
                      <div class="form-grid">
                        <div class="form-row">
                          <div class="form-row-split">
                            <select class="select" v-model="participantForm.participantType">
                              <option value="">Type</option>
                              <option value="human">Human</option>
                              <option value="ai">AI Agent</option>
                            </select>
                            <input class="input" v-model="participantForm.participantCode" placeholder="Participant ID & Display Name" />
                          </div>
                        </div>
                        <!-- WordGuessing Role Selection -->
                        <div class="form-row" v-if="selectedExperimentType === 'wordguessing'">
                          <select class="select" v-model="participantForm.wordguessingRole">
                            <option value="">Select role</option>
                            <option value="guesser">Guesser</option>
                            <option value="hinter">Hinter</option>
                          </select>
                        </div>
                        <div class="form-row" v-if="participantForm.participantType === 'ai'">
                          <select 
                            v-if="selectedExperimentType === 'shapefactory' || (selectedExperimentType.startsWith('custom_') && experimentConfig.specialtyCost !== undefined)"
                            class="select" 
                            v-model="participantForm.specialty" 
                            :disabled="!canAssignSpecialty"
                          >
                            <option value="">Auto specialty</option>
                            <option v-for="s in availableShapes" :key="s" :value="s">{{ s }}</option>
                          </select>
                          <button class="btn primary" @click="onRegisterParticipant" :disabled="!canRegisterParticipant">Register</button>
                        </div>
                        <div class="form-row" v-if="participantForm.participantType === 'human'">
                          <select 
                            v-if="selectedExperimentType === 'shapefactory' || (selectedExperimentType.startsWith('custom_') && experimentConfig.specialtyCost !== undefined)"
                            class="select" 
                            v-model="participantForm.specialty" 
                            :disabled="!canAssignSpecialty"
                          >
                            <option value="">Auto specialty</option>
                            <option v-for="s in availableShapes" :key="s" :value="s">{{ s }}</option>
                          </select>
                          <button class="btn primary" @click="onRegisterParticipant" :disabled="!canRegisterParticipant">Register</button>
                        </div>
                        <div v-if="!isSessionRegistered" class="form-helper">
                          ⚠️ Create or load a session first to enable participant registration
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="table-section">
                    <div class="section-title">
                      Registered Participants
                      <button 
                        class="grouping-btn" 
                        @click="showGroupingModal = true"
                        title="Manage participant groups"
                      >
                        Grouping
                      </button>
                    </div>
                    <div class="manage-table">
                      <div class="table-head">
                        <div class="th code">Display Name</div>
                        <div class="th type">Type</div>
                        <div 
                          v-if="selectedExperimentType === 'shapefactory' || (selectedExperimentType.startsWith('custom_') && experimentConfig.specialtyCost !== undefined)"
                          class="th specialty">Specialty</div>
                        <div 
                          v-if="selectedExperimentType === 'wordguessing'"
                          class="th role">Role</div>
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
                          <div 
                            v-if="selectedExperimentType === 'shapefactory' || (selectedExperimentType.startsWith('custom_') && experimentConfig.specialtyCost !== undefined)"
                            class="td specialty">
                            <span class="specialty-badge">{{ p.specialty }}</span>
                          </div>
                          <div 
                            v-if="selectedExperimentType === 'wordguessing'"
                            class="td role">
                            <span v-if="p.role" class="role-badge" :class="p.role">{{ p.role }}</span>
                            <span v-else class="no-role">-</span>
                          </div>
                          <div class="td group">
                            <span v-if="getParticipantGroup(p.id)" class="group-badge">{{ getParticipantGroup(p.id) }}</span>
                            <span v-else class="no-group">-</span>
                          </div>
                          <div class="td actions">
                            <button class="btn-icon edit" @click="onEditParticipant(p)" title="Edit participant">
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                <path d="m18.5 2.5 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                              </svg>
                            </button>
                            <button class="btn-icon danger" @click="onDeleteParticipant(p.id)" title="Delete participant">
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                              </svg>
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                      </div>
                    </div>
                  </div>
                </div>
          </div>
        </div>
        <!-- Column 2: Monitor Participants / Analysis Behavioral Logs -->
        <div class="tab-col" v-if="activeTab === 'monitor' || activeTab === 'analysis'">
          <div class="col-body">
            <div class="block-title">
              <template v-if="activeTab === 'monitor'">
                Participants
                <div class="indicators">
                  <span class="online-indicator">{{ onlineCount }} online</span>
                  <span class="online-indicator">{{ participants.length }} total</span>
              </div>
            </template>
              <template v-else-if="activeTab === 'analysis'">Behavioral Logs</template>
            </div>
            <!-- Monitor: Participants Status -->
            <template v-if="activeTab === 'monitor'">
              <ParticipantsList
                :participants="participants"
                :online-count="onlineCount"
                :total-orders="participants.reduce((sum, p) => sum + p.orders_completed, 0)"
              />
            </template>
            <!-- Analysis: Behavioral Logs -->
            <template v-else-if="activeTab === 'analysis'">
              <div class="behavioral-logs">
                <!-- Left Column: Controls and Statistics -->
                <div class="left-column">
                  <!-- Controls Section -->
                  <div class="controls-section">
                    <!-- Participants Dropdown -->
                    <div class="control-group">
                      <label>Participants</label>
                      <div class="custom-select-wrapper">
                        <div class="custom-select-trigger" @click="toggleParticipantsDropdown">
                          <div class="selected-content">
                            <span class="selected-option">{{ getParticipantsDropdownLabel() }}</span>
                          </div>
                          <span class="dropdown-arrow">▼</span>
                        </div>
                        <div class="custom-dropdown-menu" v-if="showParticipantsDropdown">
                          <div class="dropdown-item" @click="selectAllParticipants">
                            <div class="option-content">
                              <span class="option-tag">All Participants</span>
                            </div>
                          </div>
                          <div 
                            class="dropdown-item" 
                            v-for="participant in sessionStatisticsData?.participants || []" 
                            :key="participant.participant_code"
                            @click="toggleParticipantSelection(participant.participant_code)"
                          >
                            <div class="option-content">
                              <input 
                                type="checkbox" 
                                :checked="isParticipantSelected(participant.participant_code)"
                                @click.stop
                                @change="toggleParticipantSelection(participant.participant_code)"
                                class="participant-checkbox"
                              />
                              <span class="participant-name">{{ getDisplayName(participant.participant_code) }}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Checkboxes -->
                    <div class="control-group">
                      <label>Data Types</label>
                      <div class="checkbox-group">
                        <label class="checkbox-label">
                          <input 
                            type="checkbox" 
                            v-model="behavioralLogsForm.showTrades"
                            class="checkbox-input"
                          />
                          <span class="checkbox-text">Trades</span>
                        </label>
                        <label class="checkbox-label">
                          <input 
                            type="checkbox" 
                            v-model="behavioralLogsForm.showMessages"
                            class="checkbox-input"
                          />
                          <span class="checkbox-text">Messages</span>
                        </label>
                      </div>
                    </div>
                  </div>

                  <!-- Statistics Section -->
                  <div class="statistics-section">
                    <div class="section-title">
                      Session Statistics
                      <button 
                        class="refresh-btn" 
                        @click="loadSessionStatistics"
                        :disabled="isLoadingSessionStatistics"
                        title="Refresh statistics"
                      >
                        <span v-if="isLoadingSessionStatistics">⟳</span>
                        <span v-else>⟳</span>
                      </button>
                    </div>
                    <div v-if="isLoadingSessionStatistics" class="loading-message">
                      Loading session statistics...
                    </div>
                    <div v-else-if="!sessionStatisticsData" class="no-data-message">
                      No session statistics available. Please ensure a session is loaded.
                    </div>
                    <div v-else class="stats-container">
                      <!-- General Statistics -->
                      <div class="stats-category">
                        <div class="category-header">General</div>
                        <div class="stats-list">
                          <div class="stat-item">
                            <span class="stat-label">Average Money Balance</span>
                            <span class="stat-value">${{ sessionStatistics.averageMoney }}</span>
                          </div>
                          <div v-if="filteredParticipants.length > 1" class="stat-item">
                            <span class="stat-label">Highest Wealth</span>
                            <span class="stat-value">${{ sessionStatistics.highestWealth }} ({{ sessionStatistics.highestWealthParticipant }})</span>
                          </div>
                          <div v-if="filteredParticipants.length > 1" class="stat-item">
                            <span class="stat-label">Lowest Wealth</span>
                            <span class="stat-value">${{ sessionStatistics.lowestWealth }} ({{ sessionStatistics.lowestWealthParticipant }})</span>
                          </div>
                        </div>
                      </div>
                      
                      <!-- Trade Statistics -->
                      <div v-if="behavioralLogsForm.showTrades" class="stats-category">
                        <div class="category-header">Trade</div>
                        <div class="stats-list">
                          <div class="stat-item">
                            <span class="stat-label">Total Successful Trades</span>
                            <span class="stat-value">{{ sessionStatistics.totalTrades }}</span>
                          </div>
                          <div class="stat-item">
                            <span class="stat-label">Avg Successful Trades</span>
                            <span class="stat-value">{{ sessionStatistics.averageTrades }}</span>
                          </div>
                          <div class="stat-item">
                            <span class="stat-label">Average Trade Price</span>
                            <span class="stat-value">${{ sessionStatistics.averageTradePrice }}</span>
                          </div>
                          <div class="stat-item">
                            <span class="stat-label">Price Range</span>
                            <span class="stat-value">${{ sessionStatistics.minTradePrice }} - ${{ sessionStatistics.maxTradePrice }}</span>
                          </div>
                        </div>
                      </div>
                      
                      <!-- Message Statistics -->
                      <div v-if="behavioralLogsForm.showMessages" class="stats-category">
                        <div class="category-header">Message</div>
                        <div class="stats-list">
                          <div class="stat-item">
                            <span class="stat-label">Total Messages</span>
                            <span class="stat-value">{{ sessionStatistics.totalMessages }}</span>
                          </div>
                          <div class="stat-item">
                            <span class="stat-label">Avg Messages per User</span>
                            <span class="stat-value">{{ sessionStatistics.averageMessages }}</span>
                          </div>
                          <div class="stat-item">
                            <span class="stat-label">Avg Message Length (All)</span>
                            <span class="stat-value">{{ sessionStatistics.averageMessageLength }}</span>
                          </div>
                          <div class="stat-item">
                            <span class="stat-label">Avg Message Length (Human)</span>
                            <span class="stat-value">{{ sessionStatistics.averageMessageLengthPerHuman }}</span>
                          </div>
                          <div class="stat-item">
                            <span class="stat-label">Messages per Trade</span>
                            <span class="stat-value">{{ sessionStatistics.averageMessagesPerTrade }}</span>
                          </div>
                          <div class="stat-item">
                            <span class="stat-label">Avg Response Latency</span>
                            <span class="stat-value">{{ sessionStatistics.averageMessageResponseLatency }}s</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Right Column: Charts -->
                <div class="right-column">
                  <div class="charts-section">
                    <div class="section-title">Charts</div>
                    <div class="charts-grid">
                      <!-- Chart 1: Trade Timeline (when trades are selected) -->
                      <div v-if="behavioralLogsForm.showTrades" class="chart-container">
                        <div class="chart-title">
                          <span class="chart-title-text">Trade Timeline</span>
                          <div class="chart-legend">
                            <span class="legend-item">
                              <span class="legend-color completed"></span>
                              Completed Trades
                            </span>
                            <span class="legend-item">
                              <span class="legend-color pending"></span>
                              Pending Offers
                            </span>
                          </div>
                        </div>
                        <div class="chart-placeholder">
                          <div v-if="timelineDataByParticipant.length === 0" class="chart-no-data">
                            <div class="no-data-message">
                              <div class="no-data-icon">Chart</div>
                              <div class="no-data-text">No trade data available for selected participants</div>
                            </div>
                          </div>
                                                                                                                                      <div v-else class="timeline-container">
                             <!-- Y-axis label -->
                             <div class="y-axis-label">Participants</div>
                             
                             <!-- Timeline rows -->
                             <div class="timeline-rows">
                               <div 
                                 v-for="[participant, trades] in timelineDataByParticipant" 
                                  :key="participant"
                                  class="timeline-row"
                                 >
                                   <div class="participant-label">{{ participant }}</div>
                                   <div class="timeline-bars">
                                     <div 
                                       v-for="(trade, index) in trades" 
                                       :key="`${participant}-${index}`"
                                       class="timeline-bar"
                                       :style="{ 
                                         left: getTimelinePosition(trade.firstTradeTime) + '%',
                                         width: trade.isCompleted ? getTimelineWidth(trade.firstTradeTime, trade.lastTradeTime) + '%' : '2px'
                                       }"
                                       :class="{ 
                                         completed: trade.isCompleted,
                                         pending: !trade.isCompleted
                                       }"
                                       @mouseenter="showTimelineTooltip($event, trade, participant, index)"
                                       @mouseleave="hideTooltip"
                                     >
                                     </div>
                                   </div>
                                 </div>
                               </div>
                               
                               <!-- X-axis with time labels and label below -->
                               <div class="timeline-x-axis">
                                 <div class="x-axis-labels">
                                   <span class="x-label start">0:00</span>
                                   <span class="x-label middle">{{ getMiddleTimeLabel() }}</span>
                                   <span class="x-label end">{{ getEndTimeLabel() }}</span>
                                 </div>
                                 <div class="x-axis-label">Time</div>
                               </div>
                             </div>
                        </div>
                      </div>

                      <!-- Chart 2: Trade Numbers (when trades are selected) -->
                      <div v-if="behavioralLogsForm.showTrades" class="chart-container">
                        <div class="chart-title">
                          Trade Numbers by Participant
                        </div>
                        <div class="chart-placeholder">
                          <div v-if="chartData.participantChartData.length === 0" class="chart-no-data">
                            <div class="no-data-message">
                              <div class="no-data-icon">Chart</div>
                              <div class="no-data-text">No trade data available for selected participants</div>
                            </div>
                          </div>
                          <div v-else class="google-chart-container">
                            <div id="trades-bar-chart" class="google-chart"></div>
                          </div>
                        </div>
                      </div>
                      
                      <!-- Chart 3: Number of Sent Messages (when messages are selected) -->
                      <div v-if="behavioralLogsForm.showMessages" class="chart-container">
                        <div class="chart-title">
                          Number of Sent Messages by Participant
                        </div>
                        <div class="chart-placeholder">
                          <div v-if="chartData.participantChartData.length === 0" class="chart-no-data">
                            <div class="no-data-message">
                              <div class="no-data-icon">Chart</div>
                              <div class="no-data-text">No message data available for selected participants</div>
                            </div>
                          </div>
                          <div v-else class="google-chart-container">
                            <div id="messages-bar-chart" class="google-chart"></div>
                          </div>
                        </div>
                      </div>
                      
                      <!-- No data selected message -->
                      <div v-if="!behavioralLogsForm.showTrades && !behavioralLogsForm.showMessages" class="no-data-selected">
                        <div class="no-data-message">
                          <div class="no-data-icon">Chart</div>
                          <div class="no-data-text">Please select at least one data type to view charts</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            

          </div>
        </div>

        <!-- Column 3: Trades (for Monitor tab) / Export Data (for Analysis tab) -->
        <div class="tab-col" v-if="activeTab === 'monitor' || activeTab === 'analysis'">
          <div class="col-body">
            <div class="block-title">
              <template v-if="activeTab === 'monitor'">
                Trades
                <div class="indicators">
                  <span class="online-indicator">{{ totalTrades }} completed</span>
                  <span class="online-indicator pending">{{ pendingTrades }} pending</span>
                </div>
              </template>
              <template v-else-if="activeTab === 'analysis'">Export Data</template>
            </div>
            <!-- Monitor: Trades -->
            <template v-if="activeTab === 'monitor'">
              <TradesFeed
                :pending-offers="pendingOffers"
                :completed-trades="completedTrades"
                :total-trades="totalTrades"
                :pending-trades="pendingTrades"
              />
            </template>
            <!-- Analysis: Export Data -->
            <template v-else-if="activeTab === 'analysis'">
              <div class="export-form">
                <div class="form-group">
                  <label for="data-type">Data to Export</label>
                  <select 
                    class="select" 
                    v-model="exportForm.dataType"
                    id="data-type"
                  >
                    <option value="all">All Data (Complete session export)</option>
                    <option value="participants">Participants Data</option>
                    <option value="trades">Trades Data</option>
                    <option value="messages">Messages Data</option>
                    <option value="logs">System Logs</option>
                  </select>
                </div>
                
                <div class="form-group">
                  <label for="file-format">File Format</label>
                  <select 
                    class="select" 
                    v-model="exportForm.fileFormat"
                    id="file-format"
                  >
                    <option value="json">JSON</option>
                    <option value="csv">CSV</option>
                    <option value="excel">Excel (.xlsx)</option>
                  </select>
                </div>
                
                <div class="form-actions">
                  <button 
                    class="btn primary" 
                    @click="exportData"
                    :disabled="!isSessionRegistered"
                  >
                    Export Data
                  </button>
                </div>
                
                <div v-if="!isSessionRegistered" class="form-helper">
                  ⚠️ Create or load a session first to enable data export
                </div>
              </div>
            </template>
            <!-- Default: Placeholder -->
            <template v-else>
              <div class="placeholder">Content will appear here.</div>
            </template>
          </div>
        </div>



        <!-- Column 4: Real-Time Monitor (only for monitor tab) -->
        <div class="tab-col" v-if="activeTab === 'monitor'">
          <div class="col-body">
            <div class="block-title">
              Conversations
              <div class="indicators">
                <span class="online-indicator">{{ messages.length }} messages</span>
                <span class="online-indicator">{{ activeConversations }} conversations</span>
              </div>
            </div>
            <!-- Monitor: Conversations -->
            <ConversationView
              :participants="participants"
              :messages="messages"
              :total-messages="messages.length"
              :active-conversations="activeConversations"
              :communication-level="interactionConfig.communicationLevel"
            />
          </div>
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
            <div class="form-group">
              <label>Participant Code</label>
              <input 
                type="text" 
                v-model="editForm.participantCode" 
                placeholder="Enter participant code"
                class="form-input"
              />
            </div>
            <div class="form-group">
              <label>Type</label>
              <input 
                type="text" 
                :value="editForm.participantType === 'ai' || editForm.participantType === 'ai_agent' ? 'AI Agent' : 'Human'" 
                :disabled="true"
                class="form-input disabled"
              />
              <small class="form-help">Participant type cannot be changed</small>
            </div>
            <div 
              v-if="selectedExperimentType === 'shapefactory' || (selectedExperimentType.startsWith('custom_') && experimentConfig.specialtyCost !== undefined)"
              class="form-group">
              <label>Specialty Shape</label>
              <select v-model="editForm.specialty" class="form-select">
                <option value="">Auto specialty</option>
                <option v-for="shape in availableShapes" :key="shape" :value="shape">{{ shape }}</option>
              </select>
            </div>
            <div class="form-group" v-if="editForm.participantType === 'ai' || editForm.participantType === 'ai_agent'">
              <label>Agent Persona</label>
              <textarea 
                v-model="editForm.persona" 
                placeholder="Enter agent persona description (optional)"
                class="form-input"
                rows="6"
              ></textarea>
              <small class="form-help">The personality is randomly assigned by default.</small>
            </div>
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
        <div class="modal-footer">
          <button class="btn secondary" @click="closeGroupingModal">Close</button>
        </div>
      </div>
    </div>

    <!-- Create Session Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click="closeCreateModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create Session</h3>
          <button class="modal-close" @click="closeCreateModal">×</button>
        </div>
        <div class="modal-body">
          <!-- Session Type Selection -->
          <div class="form-group">
            <label>Session Type</label>
            <div class="session-type-selector">
              <label class="radio-label">
                <input 
                  type="radio" 
                  v-model="createSessionForm.sessionType" 
                  value="new"
                  class="radio-input"
                />
                <span class="radio-text">Create New Session</span>
              </label>
              <label class="radio-label">
                <input 
                  type="radio" 
                  v-model="createSessionForm.sessionType" 
                  value="template"
                  class="radio-input"
                />
                <span class="radio-text">Load from Template</span>
              </label>
            </div>
          </div>

          <!-- New Session Form -->
          <div v-if="createSessionForm.sessionType === 'new'" class="create-session-form">
            <div class="form-group">
              <label>Session ID</label>
              <input 
                type="text" 
                v-model="createSessionForm.sessionId" 
                placeholder="ession ID"
                class="form-input"
              />
            </div>
            <div class="form-group">
              <label>Session Duration (minutes)</label>
              <input 
                type="number" 
                v-model="createSessionForm.sessionDuration" 
                placeholder="15"
                class="form-input"
              />
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input 
                  type="checkbox" 
                  v-model="createSessionForm.saveAsTemplate"
                  class="checkbox-input"
                />
                Save current experiment parameters as a template
              </label>
            </div>
            <div v-if="createSessionForm.saveAsTemplate" class="form-group">
              <label>Template Name</label>
              <input 
                type="text" 
                v-model="createSessionForm.templateName" 
                placeholder="Enter template name (optional)"
                class="form-input"
              />
              <small class="form-help">If left empty, will use session ID as template name</small>
            </div>
          </div>

          <!-- Template Selection Form -->
          <div v-if="createSessionForm.sessionType === 'template'" class="load-template-form">
            <div class="form-group">
              <label>Select Template</label>
              <div class="template-selection-container">
                <select v-model="createSessionForm.selectedTemplate" class="form-select">
                  <option value="">{{ availableTemplates.length > 0 ? `Choose a template... (${availableTemplates.length} available)` : 'No templates available' }}</option>
                  <option v-for="template in availableTemplates" :key="template.template_id" :value="template.session_id">
                    {{ template.session_id }}{{ template.is_default ? ' (Default)' : '' }}
                  </option>
                </select>
                <button 
                  v-if="createSessionForm.selectedTemplate && !isDefaultTemplate(createSessionForm.selectedTemplate)"
                  type="button"
                  class="btn-icon danger delete-template-btn"
                  @click="deleteSelectedTemplate"
                  title="Delete this template"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  </svg>
                </button>
              </div>
              <small class="form-help">
                💡 Select a template to load its configuration. Default templates (marked with "Default") cannot be deleted.
              </small>
            </div>
            <div class="form-group">
              <label>Session ID</label>
              <input 
                type="text" 
                v-model="createSessionForm.sessionId" 
                placeholder="Session ID"
                class="form-input"
              />
            </div>
            <div class="form-group">
              <label>Session Duration (minutes)</label>
              <input 
                type="number" 
                v-model="createSessionForm.sessionDuration" 
                placeholder="15"
                class="form-input"
              />
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn secondary" @click="closeCreateModal">Cancel</button>
          <button 
            class="btn primary" 
            @click="createSession" 
            :disabled="!canCreateSession || isCreatingSession"
          >
            <span v-if="isCreatingSession">Creating...</span>
            <span v-else>{{ createSessionForm.sessionType === 'template' ? 'Load & Create' : 'Create Session' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Load Session Modal -->
    <div v-if="showLoadModal" class="modal-overlay" @click="closeLoadModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Load Session</h3>
          <button class="modal-close" @click="closeLoadModal">×</button>
        </div>
        <div class="modal-body">
          <div class="load-session-form">
            <div class="form-group">
              <label>Session ID</label>
              <input 
                type="text" 
                v-model="loadSessionForm.sessionId" 
                placeholder="Session ID"
                class="form-input"
              />
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn secondary" @click="closeLoadModal">Cancel</button>
          <button class="btn primary" @click="loadSession" :disabled="!loadSessionForm.sessionId || isLoadingSession">
            <span v-if="isLoadingSession">Loading...</span>
            <span v-else>Load Session</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Create Session Modal -->
    <div v-if="showCreateSessionModal" class="modal-overlay" @click="closeCreateSessionModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create Session</h3>
          <button class="modal-close" @click="closeCreateSessionModal">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Session Name</label>
            <input 
              type="text" 
              v-model="createSessionFromParamsForm.sessionName" 
              placeholder="Enter session name"
              class="form-input"
            />
            <small class="form-help">This session will use all current parameter settings</small>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn secondary" @click="closeCreateSessionModal">Cancel</button>
          <button 
            class="btn primary" 
            @click="createSessionFromParameters" 
            :disabled="!createSessionFromParamsForm.sessionName.trim() || isCreatingSessionFromParams"
          >
            <span v-if="isCreatingSessionFromParams">Creating...</span>
            <span v-else>Create Session</span>
          </button>
        </div>
      </div>
    </div>



    <!-- Save Template Modal -->
    <div v-if="showSaveTemplateModal" class="modal-overlay" @click="closeSaveTemplateModal">
      <div class="modal-content template-modal" @click.stop>
        <div class="modal-header">
          <h3>Save Template</h3>
          <button class="modal-close" @click="closeSaveTemplateModal">×</button>
        </div>
        <div class="modal-body">
          <div class="save-template-form">
            <div class="form-group">
              <label for="template-name">Template Name</label>
              <input 
                type="text" 
                id="template-name"
                v-model="saveTemplateForm.templateName"
                placeholder="Enter template name"
                class="form-input"
                maxlength="20"
              />
              <small class="form-help">Template name must be 20 characters or less</small>
            </div>
          </div>
          
          <!-- Templates Management Section -->
          <div class="templates-management-section">
            <div class="templates-header">
              <h4>Manage Existing Templates</h4>
                              <button 
                  @click="loadAvailableTemplates" 
                  class="refresh-templates-btn"
                  title="Refresh templates list"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
                    <path d="M21 3v5h-5"/>
                    <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
                    <path d="M3 21v-5h5"/>
                  </svg>
                </button>
            </div>
            
            <div v-if="availableTemplates.length > 0" class="templates-list">
              <div 
                v-for="template in availableTemplates" 
                :key="template.template_id"
                class="template-item"
                :class="{ 'default-template': template.is_default }"
              >
                <span class="template-name">{{ template.session_id }}{{ template.is_default ? ' (Default)' : '' }}</span>
                                  <div class="template-actions">
                    <button 
                      v-if="!template.is_default"
                      @click="deleteTemplateInModal(template.session_id)"
                      class="template-action-btn delete"
                      title="Delete this template"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </button>
                  </div>
              </div>
            </div>
            <div v-else class="no-templates-message">
              No templates available yet. Save your first template above!
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn secondary" @click="skipSaveTemplate">Skip</button>
          <button 
            class="btn primary" 
            @click="saveTemplateFromParameters"
            :disabled="!saveTemplateForm.templateName.trim() || isSavingTemplate"
          >
            <span v-if="isSavingTemplate">Saving...</span>
            <span v-else>Save Template</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Custom Experiment Modal -->
    <div v-if="showCustomExperimentModal" class="modal-overlay" @click="closeCustomExperimentModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add Custom Experiment</h3>
          <button class="modal-close-btn" @click="closeCustomExperimentModal">&times;</button>
        </div>
        <div class="modal-body">
          <div class="validation-success">
            <span class="validation-icon">✅</span>
            <span class="validation-message">Configuration file validation passed!</span>
          </div>
          <div class="experiment-name-section">
            <label for="modal-experiment-name">Experiment Name:</label>
            <input 
              type="text" 
              id="modal-experiment-name"
              v-model="customExperimentName"
              :placeholder="experimentNamePlaceholder"
              class="modal-experiment-name-input"
              @keyup.enter="addCustomExperiment"
            />
          </div>
        </div>
        <div class="modal-footer">
          <button 
            @click="closeCustomExperimentModal"
            class="modal-cancel-btn"
          >
            Cancel
          </button>
          <button 
            @click="addCustomExperiment"
            :disabled="!customExperimentName.trim()"
            class="modal-confirm-btn"
          >
            Add to Experiment List
          </button>
        </div>
      </div>
    </div>


    </div>
  
  <!-- Tooltip for timeline chart -->
  <div 
    v-if="tooltipVisible" 
    class="timeline-tooltip"
    :style="{ left: tooltipPosition.x + 'px', top: tooltipPosition.y + 'px' }"
  >
    <div class="tooltip-title">{{ tooltipData.title }}</div>
    <div class="tooltip-content" v-html="tooltipData.content"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import ParticipantsList from '@/components/ParticipantsList.vue'
import TradesFeed from '@/components/TradesFeed.vue'
import ConversationView from '@/components/ConversationView.vue'
import { BACKEND_URL } from '@/config.js'
// @ts-ignore
import io from 'socket.io-client'
// Declare global google variable for Google Charts
declare global {
  interface Window {
    google: any
  }
}

// Types
interface Participant {
  id: string
  type: string
  specialty: string
  status: string
  money: number
  orders_completed: number
  trades_made: number
  shapes_bought: number
  shapes_sold: number
  login_time: string | null
  inventory?: Record<string, number>
  specialty_shapes_available?: number
  specialty_shapes_sold?: number
  tag?: string // Added tag to Participant interface
  persona?: string // Added persona to Participant interface
  mbti_type?: string // Added MBTI type to Participant interface
  session_code?: string
  role?: string // Added role for wordguessing experiments
  current_round?: number // Added current_round for wordguessing experiments
  score?: number // Added score for wordguessing experiments
  internal_id?: string // Added internal_id (actual participant code)
}

interface Trade {
  from: string
  to: string
  shape: string
  quantity: number
  price: number
  status: string
  timestamp: Date
}

// MBTI Personality Profiles (matching backend)
const MBTI_PROFILES: Record<string, { name: string; description: string; behavior: string; communication: string }> = {
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
const generateDefaultPersona = (mbtiType: string, participantCode: string): string => {
  const profile = MBTI_PROFILES[mbtiType]
  if (!profile) {
    return `Your nickname in this experiment is ${participantCode}. You need to behave like a real human participant in this experiment.`
  }
  
  return `Your nickname in this experiment is ${participantCode}. You need to behave like a real human participant in this experiment. Generally speaking, you are a "${profile.name}" in your daily life. Your MBTI personality is ${mbtiType}.

${profile.description}.

Your personality influences how you approach trading, communication, and decision-making. Stay true to your personality type in all interactions.`
}

interface Message {
  from: string
  to: string
  content: string
  timestamp: Date
}

interface ExperimentConfig {
  roundDuration: number
  startingMoney: number
  specialtyCost?: number
  regularCost?: number
  minTradePrice: number
  maxTradePrice: number
  productionTime?: number
  maxProductionNum?: number
  sessionDuration: number | null
  sessionId: string
  shapesPerOrder?: number
  agentPerceptionTimeWindow?: number
  incentiveMoney?: number
  numShapeTypes?: number
  // Experiment-specific parameters
  competitionLevel?: number
  collaborationBonus?: number
  riskFactor?: number
  Decision_Type?: string
  essay_number?: number
  score_scale?: string
  // Awareness dashboard configuration
  awarenessDashboardConfig?: {
    showMoney: boolean
    showProductionCount: boolean
    showOrderProgress: boolean
  }
  // Experiment interface configuration
  experimentInterfaceConfig?: any
  // WordGuessing specific fields
  wordList?: string[]
}

// Experiment selection types
interface ExperimentParameter {
  key: string
  label: string
  type: 'number' | 'text' | 'select'
  min?: number
  max?: number
  step?: number
  defaultValue: number | string
  options?: { value: string | number; label: string }[]
}

interface ExperimentInterfaceConfig {
  awarenessDashboard: {
    enabled: boolean
    showMoney: boolean
    showProductionCount: boolean
    showOrderProgress: boolean
  }
  actionStructures: {
    enabled: boolean
  }
  participantInterface: {
    myStatus: {
      enabled: boolean
      showMoney: boolean
      showInventory: boolean
    }
    myAction: {
      type: string
      showTradeForm: boolean
      showProductionForm: boolean
      showOrderForm: boolean
    }
    myTask: {
      enabled: boolean
      type?: string
      instruction?: string
    }
    trade: {
      enabled: boolean
      showTradeHistory: boolean
    }
    socialPanel: {
      showTradeTab: boolean
      showChatTab: boolean
    }
  }
}

interface ExperimentTemplate {
  id: string
  name: string
  description: string
  tags: string[]
  defaultConfig: Partial<ExperimentConfig>
  specificParams: ExperimentParameter[]
  interfaceConfig?: ExperimentInterfaceConfig
}

// Router
const router = useRouter()

// Reactive state
const sessionId = ref('')
const experimentStatus = ref<'waiting' | 'running' | 'paused' | 'completed'>('waiting')
const timeRemaining = ref(0)
const timerInterval = ref<number | null>(null)

// Data arrays
const participants = ref<Participant[]>([])
const pendingOffers = ref<Trade[]>([])
const completedTrades = ref<Trade[]>([])
const timelineTradesData = ref<any>({ completed_trades: [], pending_offers: [] })
const messages = ref<Message[]>([])

// WebSocket connection for real-time updates
let socket: any = null
const isConnected = ref(false)

const registrationMessage = ref('')
const registrationMessageType = ref<'success' | 'error'>('success')

// Human participant registration
const experimentConfig = ref<ExperimentConfig>({
  roundDuration: 15,  // Now matches sessionDuration since we only use session time
  startingMoney: 200,
  specialtyCost: 15,
  regularCost: 40,
  minTradePrice: 15,
  maxTradePrice: 100,
  productionTime: 30,
  maxProductionNum: 3,
  sessionDuration: 15,  // Set to 15 minutes as default
  sessionId: '',
  shapesPerOrder: 4,
  agentPerceptionTimeWindow: 15,
  incentiveMoney: 60,
  numShapeTypes: 3,
  // Awareness dashboard configuration
  awarenessDashboardConfig: {
    showMoney: true,
    showProductionCount: true,
    showOrderProgress: true
  },
  // Experiment interface configuration
  experimentInterfaceConfig: {},
  // WordGuessing specific fields
  wordList: []
})

// Essay upload state
const uploadedEssays = ref<Array<{
  id: string
  filename: string
  title: string
  file: File
}>>([])

// Experiment selection state
const selectedExperimentType = ref('')

// Interface configuration state
const currentInterfaceConfig = ref<ExperimentInterfaceConfig | null>(null)

// Template loading state
const templateLoadInput = ref('')

// Parameter clusters collapse state
const parameterClustersExpanded = ref({
  generalSettings: true,  // Always expanded by default
  money: false,
  shapeProduction: false,
  experimentSpecific: false,
  essayRanking: false,
  wordguessing: true  // Expanded by default for wordguessing
})

// WordGuessing word assignment
const wordAssignmentText = ref('')

// Interaction sections collapse state
const interactionSectionsExpanded = ref({
  informationFlow: true,  // Always expanded by default
  actionStructures: true,
  agentBehaviors: true
})

// Save template state
const showSaveTemplateModal = ref(false)
const isSavingTemplate = ref(false)
const saveTemplateForm = ref({
  templateName: ''
})


// Upload config file state
const fileInputRef = ref<HTMLInputElement>()
const isUploadingConfig = ref(false)
const configValidationStatus = ref<{ type: 'success' | 'error', message: string } | null>(null)
const customExperimentName = ref('')
const customExperimentAdded = ref(false)
const uploadedConfigData = ref<any>(null)
const showCustomExperimentModal = ref(false)
const experimentNamePlaceholder = ref('')
const isClosingModal = ref(false)
const customExperiments = ref<ExperimentTemplate[]>([])

// Filter state
const selectedTags = ref<string[]>([])

// Experiment expansion state
const expandedExperiments = ref<Set<string>>(new Set())

// Track which experiment is being previewed (not selected)
const previewedExperiment = ref<string | null>(null)

// Agent registration state
const agentRegistrationForm = ref({
  numAgents: 1,
  namingType: '' as '' | 'player_x' | 'real_names'
})

// Create session state
const showCreateSessionModal = ref(false)
const isCreatingSessionFromParams = ref(false)
const createSessionFromParamsForm = ref({
  sessionName: ''
})

// Available experiment templates
const availableExperiments: ExperimentTemplate[] = [
  {
    id: 'shapefactory',
    name: 'Shape Factory',
    description: '**Procedures**: Each participant can produce shapes, buy&sell shapes, and chat with others. Each one is assigned a specialty shape that can be cheaply produced.\n\n**Constraints**: shape production limit; time limit.\n\n**Goal**: Maximize individual profit.',
    tags: ['Coordination', 'Trade'],
    defaultConfig: {
      startingMoney: 200,
      specialtyCost: 15,
      regularCost: 40,
      minTradePrice: 15,
      maxTradePrice: 100,
      productionTime: 30,
      maxProductionNum: 3,
      sessionDuration: 15,
      shapesPerOrder: 4,
      agentPerceptionTimeWindow: 15,
      incentiveMoney: 60,
      numShapeTypes: 3
    },
    specificParams: [],
    interfaceConfig: {
      // Researcher Dashboard Interface Elements
      awarenessDashboard: {
        enabled: true,
        showMoney: true,
        showProductionCount: true,
        showOrderProgress: true
      },
      actionStructures: {
        enabled: true
      },
      // Participant Interface Elements
      participantInterface: {
        socialPanel: {
          showTradeTab: true,
          showChatTab: true
        },
        myStatus: {
          enabled: true,
          showMoney: true,
          showInventory: true
        },
        myAction: {
          type: 'shapefactory',
          showTradeForm: true,
          showProductionForm: true,
          showOrderForm: true
        },
        myTask: {
          enabled: true,
          type: 'shapefactory'
        },
        trade: {
          enabled: true,
          showTradeHistory: true
        }
      }
    }
  },
  {
    id: 'daytrader',
    name: 'DayTrader',
    description: '**Setup:** Market-style investment game where participants can invest individually with safe returns or collectively with higher risk shared across the group.\n\n**Communication:** Occurs through assigned media channels.\n\n**Goal:** Optimize gains by balancing individual safety with group risk.',
    tags: ['Social Dilemma', 'Trade'],
    defaultConfig: {
      startingMoney: 200,
      minTradePrice: 15,
      maxTradePrice: 100,
      sessionDuration: 15,
    },
    specificParams: [
    ],
    interfaceConfig: {
      // Researcher Dashboard Interface Elements
      awarenessDashboard: {
        enabled: true,
        showMoney: true,
        showProductionCount: false,
        showOrderProgress: false
      },
      actionStructures: {
        enabled: false
      },
      // Participant Interface Elements
      participantInterface: {
        myStatus: {
          enabled: true,
          showMoney: true,
          showInventory: false
        },
        myAction: {
          type: 'daytrader',
          showTradeForm: true,
          showProductionForm: false,
          showOrderForm: false
        },
        myTask: {
          enabled: false
        },
        trade: {
          enabled: true,
          showTradeHistory: true
        },
        socialPanel: {
          showTradeTab: false,
          showChatTab: true
        }
      }
    }
  },
  {
    id: 'essayranking',
    name: 'Essay Ranking',
    description: '**Setup:** Participants read and discuss essays, then vote to produce a collective ranking.\n\n**AI Integration:** In some settings, AI agents contribute votes or reasoning alongside humans.\n\n**Goal:** Reach consensus on rankings.',
    tags: ['Collaborative Decision Making'],
    defaultConfig: {
      sessionDuration: 15,
    },
    specificParams: [
      {
        key: 'essay_number',
        label: 'Number of Essays',
        type: 'number',
        min: 1,
        max: 5,
        step: 1,
        defaultValue: 3
      }
    ],
    interfaceConfig: {
      // Researcher Dashboard Interface Elements
      awarenessDashboard: {
        enabled: false,
        showMoney: false,
        showProductionCount: false,
        showOrderProgress: false
      },
      actionStructures: {
        enabled: false
      },
      participantInterface: {
        myStatus: {
          enabled: true,
          showMoney: false,
          showInventory: true
        },
        myAction: {
          type: 'essayranking',
          showTradeForm: false,
          showProductionForm: false,
          showOrderForm: false
        },
        myTask: {
          enabled: true,
          type: 'essayranking',
          instruction: 'Please review and rank the three essays. You may also use the group chat to discuss your thoughts with other participants.'
        },
        trade: {
          enabled: false,
          showTradeHistory: false
        },
        socialPanel: {
          showTradeTab: false,
          showChatTab: true
        }
      }
    }
  },
  {
    id: 'wordguessing',
    name: 'Word-Guessing Game',
    description: '**Setup:** one participant tries to guess a word the other participant is thinking of, and the other participant only provides one word hint each round.\n\n**Goal:** investigate people\'s mental models of AI',
    tags: ['Turn-Taking'],
    defaultConfig: {
      sessionDuration: 15,
    },
    specificParams: [],
    interfaceConfig: {
      // Researcher Dashboard Interface Elements
      awarenessDashboard: {
        enabled: false,
        showMoney: false,
        showProductionCount: false,
        showOrderProgress: false
      },
      actionStructures: {
        enabled: false
      },
      participantInterface: {
        myStatus: {
          enabled: false,
          showMoney: false,
          showInventory: false
        },
        myAction: {
          type: 'disabled',
          showTradeForm: false,
          showProductionForm: false,
          showOrderForm: false
        },
        myTask: {
          enabled: true,
          type: 'wordguessing',
          instruction: 'Please guess the word the other participant is thinking of. You may also use the group chat to discuss your thoughts with other participants.'
        },
        trade: {
          enabled: false,
          showTradeHistory: false
        },
        socialPanel: {
          showTradeTab: false,
          showChatTab: true
        }
      }
    }
  }
]

// Computed property for all available experiments
const allAvailableExperiments = computed(() => {
  return [...availableExperiments, ...customExperiments.value]
})

// Computed property for current experiment's interface configuration
const currentExperimentInterfaceConfig = computed(() => {
  if (!selectedExperimentType.value) return null
  
  const experiment = allAvailableExperiments.value.find(exp => exp.id === selectedExperimentType.value)
  return experiment?.interfaceConfig || null
})

// Computed property for filtered experiments based on selected tags
const filteredExperiments = computed(() => {
  if (selectedTags.value.length === 0) {
    return allAvailableExperiments.value
  }
  
  return allAvailableExperiments.value.filter(experiment => {
    return selectedTags.value.every(tag => experiment.tags?.includes(tag))
  })
})

// Computed property for all unique tags across all experiments
const allUniqueTags = computed(() => {
  const tagSet = new Set<string>()
  allAvailableExperiments.value.forEach(experiment => {
    experiment.tags?.forEach(tag => tagSet.add(tag))
  })
  return Array.from(tagSet).sort()
})

// Tag filter functions
const toggleTag = (tag: string) => {
  const index = selectedTags.value.indexOf(tag)
  if (index > -1) {
    selectedTags.value.splice(index, 1)
  } else {
    selectedTags.value.push(tag)
  }
}

const clearAllTags = () => {
  selectedTags.value = []
}

const isTagSelected = (tag: string) => {
  return selectedTags.value.includes(tag)
}

// Watch for changes in filtered experiments and clear selection if current experiment is filtered out
watch(filteredExperiments, (newFilteredExperiments) => {
  if (selectedExperimentType.value && !newFilteredExperiments.find(exp => exp.id === selectedExperimentType.value)) {
    selectedExperimentType.value = ''
  }
})


// Interaction configuration
type CommunicationLevel = 'chat' | 'broadcast' | 'no_chat'
type AwarenessToggle = 'on' | 'off'
type NegotiationType = 'counter' | 'no_counter'
type SimultaneousActions = 'allow' | 'not_allow'
type RationalesType = 'step_wise' | 'none'

const interactionConfig = ref<{ 
  communicationLevel: CommunicationLevel; 
  awarenessDashboard: AwarenessToggle;
  negotiations: NegotiationType;
  simultaneousActions: SimultaneousActions;
  rationales: RationalesType;
  tradingEnabled: boolean;
}>({
  communicationLevel: 'chat',
  awarenessDashboard: 'on',
  negotiations: 'counter',
  simultaneousActions: 'allow',
  rationales: 'step_wise',
  tradingEnabled: true
})

// Auto-save experiment config to database when settings change
watch(experimentConfig, async (newConfig) => {
  if (currentSessionCode.value && isSessionRegistered.value) {
    try {
      await saveExperimentConfigToDatabase(newConfig)
    } catch (error) {
      console.error('Failed to auto-save experiment config:', error)
    }
  }
}, { deep: true })

// Auto-save interaction config to database when settings change
watch(interactionConfig, async (newConfig) => {
  if (currentSessionCode.value && isSessionRegistered.value) {
    try {
      await saveInteractionConfigToDatabase(newConfig)
    } catch (error) {
      console.error('Failed to auto-save interaction config:', error)
    }
  }
}, { deep: true })

// Custom dropdown state for communication level
const showCommDropdown = ref(false)
const showNegotiationsDropdown = ref(false)
const showSimultaneousActionsDropdown = ref(false)
const showAwarenessDashboardDropdown = ref(false)
const showRationalesDropdown = ref(false)

// Preview tab state
const previewCurrentTab = ref<'trade' | 'messages' | 'broadcast'>('trade')

// Communication options for the dropdown
const commOptions: { value: CommunicationLevel; label: string }[] = [
  { value: 'chat', label: 'Private Messaging' },
  { value: 'broadcast', label: 'Group Chat' },
  { value: 'no_chat', label: 'No Chat' }
]

// Negotiations options for the dropdown
const negotiationsOptions: { value: NegotiationType; label: string; description: string }[] = [
  { value: 'counter', label: 'Counter', description: 'Participants can make counter-offers instead of only accepting or rejecting.' },
  { value: 'no_counter', label: 'No Counter', description: 'Offers can only be accepted or rejected as presented.' }
]

// Simultaneous Actions options for the dropdown
const simultaneousActionsOptions: { value: SimultaneousActions; label: string; description: string }[] = [
  { value: 'allow', label: 'Allow', description: 'Multiple offers can be made at once.' },
  { value: 'not_allow', label: 'Not Allow', description: 'Each offer must be resolved before a new one begins.' }
]

// Awareness Dashboard options for the dropdown
const awarenessDashboardOptions: { value: AwarenessToggle; label: string; description: string }[] = [
  { value: 'on', label: 'On', description: 'Participants see others\' money and order progress in real time.' },
  { value: 'off', label: 'Off', description: 'Participants only see others\' names, with no status information.' }
]

// Rationales options for the dropdown
const rationalesOptions: { value: RationalesType; label: string; description: string }[] = [
  { value: 'step_wise', label: 'Step-wise', description: 'Agents explain each decision with reasoning.' },
  { value: 'none', label: 'None', description: 'Agents act without providing reasoning.' }
]

// Methods for custom dropdowns
const toggleCommDropdown = () => {
  showCommDropdown.value = !showCommDropdown.value
}

const selectCommOption = (value: CommunicationLevel) => {
  interactionConfig.value.communicationLevel = value
  showCommDropdown.value = false
}

const toggleNegotiationsDropdown = () => {
  showNegotiationsDropdown.value = !showNegotiationsDropdown.value
}

const selectNegotiationsOption = (value: NegotiationType) => {
  interactionConfig.value.negotiations = value
  showNegotiationsDropdown.value = false
}

const toggleSimultaneousActionsDropdown = () => {
  showSimultaneousActionsDropdown.value = !showSimultaneousActionsDropdown.value
}

const selectSimultaneousActionsOption = (value: SimultaneousActions) => {
  interactionConfig.value.simultaneousActions = value
  showSimultaneousActionsDropdown.value = false
}

const toggleAwarenessDashboardDropdown = () => {
  showAwarenessDashboardDropdown.value = !showAwarenessDashboardDropdown.value
}

const selectAwarenessDashboardOption = (value: AwarenessToggle) => {
  interactionConfig.value.awarenessDashboard = value
  showAwarenessDashboardDropdown.value = false
}

const toggleRationalesDropdown = () => {
  showRationalesDropdown.value = !showRationalesDropdown.value
}

// Toggle parameter cluster collapse state
const toggleParameterCluster = (clusterKey: string) => {
  parameterClustersExpanded.value[clusterKey] = !parameterClustersExpanded.value[clusterKey]
}

// Update word assignment for wordguessing
const updateWordAssignment = () => {
  if (selectedExperimentType.value === 'wordguessing') {
    const words = wordAssignmentText.value
      .split(',')
      .map(word => word.trim())
      .filter(word => word.length > 0)
    
    experimentConfig.value.wordList = words
    updateExperimentConfig()
  }
}

// Check if there are hinter participants
const hasHinters = computed(() => {
  return participants.value.some(p => p.role === 'hinter')
})

// Assign words to all hinter participants
const assignWordsToHinters = async () => {
  if (!wordAssignmentText.value.trim() || selectedExperimentType.value !== 'wordguessing') {
    return
  }

  const words = wordAssignmentText.value
    .split(',')
    .map(word => word.trim())
    .filter(word => word.length > 0)

  if (words.length === 0) {
    alert('Please enter at least one word')
    return
  }

  const hinters = participants.value.filter(p => p.role === 'hinter')
  if (hinters.length === 0) {
    alert('No hinter participants found')
    return
  }

  try {
    // Assign words to each hinter
    for (const hinter of hinters) {
      const response = await fetch('/api/wordguessing/researcher/assign-words', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          participant_code: hinter.internal_id, // Use internal_id (actual participant code)
          session_code: currentSessionCode.value,
          words: words
        })
      })

      const result = await response.json()
      if (!response.ok) {
        console.error(`Failed to assign words to ${hinter.id}:`, result)
        alert(`Failed to assign words to ${hinter.id}: ${result.error}`)
        return
      }
    }

    alert(`Successfully assigned words to ${hinters.length} hinter(s): ${hinters.map(h => h.id).join(', ')}`)
    
    // Refresh participants to show updated data
    await loadParticipants()
    
  } catch (error) {
    console.error('Error assigning words:', error)
    alert('Failed to assign words: ' + error.message)
  }
}

// Assign words to a specific hinter participant
const assignWordsToSpecificHinter = async (participantCode: string) => {
  if (!wordAssignmentText.value.trim() || selectedExperimentType.value !== 'wordguessing') {
    return
  }

  const words = wordAssignmentText.value
    .split(',')
    .map(word => word.trim())
    .filter(word => word.length > 0)

  if (words.length === 0) {
    console.log('No words to assign to new hinter')
    return
  }

  try {
    const response = await fetch('/api/wordguessing/researcher/assign-words', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        participant_code: participantCode,
        session_code: currentSessionCode.value,
        words: words
      })
    })

    const result = await response.json()
    if (response.ok) {
      console.log(`Successfully assigned words to new hinter ${participantCode}:`, words)
    } else {
      console.error(`Failed to assign words to ${participantCode}:`, result)
    }
    
  } catch (error) {
    console.error('Error assigning words to new hinter:', error)
  }
}

// Toggle interaction section collapse state
const toggleInteractionSection = (sectionKey: string) => {
  interactionSectionsExpanded.value[sectionKey] = !interactionSectionsExpanded.value[sectionKey]
}

// Selected interaction control entry for preview
const selectedInteractionEntry = ref<string | null>(null)

// Handle clicking on interaction control entries
const selectInteractionEntry = (entryKey: string) => {
  selectedInteractionEntry.value = selectedInteractionEntry.value === entryKey ? null : entryKey
}

// Ensure an entry is selected (no toggle off)
const ensureInteractionSelected = (entryKey: string) => {
  selectedInteractionEntry.value = entryKey
}

// Awareness dashboard display options
const awarenessDisplayOptions = ref({
  money: true,
  production: true,
  orders: true
})

// Watch for changes in awareness display options and update experiment config
watch(awarenessDisplayOptions, (newOptions) => {
  if (experimentConfig.value) {
    experimentConfig.value.awarenessDashboardConfig = {
      showMoney: newOptions.money,
      showProductionCount: newOptions.production,
      showOrderProgress: newOptions.orders
    }
    console.log('🔧 Updated experiment config awareness dashboard:', experimentConfig.value.awarenessDashboardConfig)
  }
}, { deep: true })

const selectRationalesOption = (value: RationalesType) => {
  interactionConfig.value.rationales = value
  showRationalesDropdown.value = false
}

const updateInteractionConfig = () => {
  // This method can be used to trigger any updates when interaction config changes
  console.log('Interaction config updated:', interactionConfig.value)
}

// Setup workflow navigation methods
const loadExistingSession = () => {
  console.log('Load existing session clicked')
  showLoadModal.value = true
}

const openLoadModal = () => {
  showLoadModal.value = true
}

const startCreateSession = () => {
  console.log('Create session clicked')
  setupTabs.value.experimentSelection = true
  activeSetupTab.value = 'experimentSelection'
}

const proceedToParameters = () => {
  if (selectedExperimentType.value) {
    activeSetupTab.value = 'parameters'
  }
}

// Auto-switch to parameters tab when experiment is selected
const onExperimentSelect = (experimentId: string) => {
  selectedExperimentType.value = experimentId
  onExperimentTypeChange()
  // Auto-switch to parameters tab
  activeSetupTab.value = 'parameters'
}

const proceedToInteractionVariables = () => {
  activeSetupTab.value = 'interactionVariables'
  scrollToLatestTab()
}

const proceedToParticipantRegistration = () => {
  activeSetupTab.value = 'participantRegistration'
  scrollToLatestTab()
}

const completeSetup = () => {
  console.log('Setup completed')
  // TODO: Implement setup completion logic
  // Could switch to monitor tab or show success message
}

const navigateToSetupTab = (tabId: string) => {
  // Only allow navigation to visible tabs
  if (setupTabs.value[tabId]) {
    activeSetupTab.value = tabId
    scrollToTab(tabId)
  }
}

// Function to scroll to the rightmost (latest) tab
const scrollToLatestTab = () => {
  nextTick(() => {
    const container = document.querySelector('.setup-tabs-container')
    if (container) {
      // Scroll to the rightmost position to show the latest tab
      container.scrollTo({
        left: container.scrollWidth,
        behavior: 'smooth'
      })
    }
  })
}

// Function to scroll to a specific tab
const scrollToTab = (tabId: string) => {
  nextTick(() => {
    const container = document.querySelector('.setup-tabs-container')
    const tabElement = document.querySelector(`.setup-tab-panel[data-tab-id="${tabId}"]`)
    
    if (container && tabElement) {
      // Calculate the position to scroll to
      const containerRect = container.getBoundingClientRect()
      const tabRect = tabElement.getBoundingClientRect()
      const relativeLeft = tabRect.left - containerRect.left
      const containerWidth = containerRect.width
      const tabWidth = tabRect.width
      
      // Calculate scroll position to center the tab in the container
      const scrollLeft = container.scrollLeft + relativeLeft - (containerWidth - tabWidth) / 2
      
      container.scrollTo({
        left: Math.max(0, scrollLeft),
        behavior: 'smooth'
      })
    }
  })
}

const goBackToExperimentSelection = () => {
  activeSetupTab.value = 'experimentSelection'
}

const goBackToParameters = () => {
  activeSetupTab.value = 'parameters'
}

const goBackToInteractionVariables = () => {
  activeSetupTab.value = 'interactionVariables'
}

// Behavioral logs methods
const toggleParticipantsDropdown = () => {
  showParticipantsDropdown.value = !showParticipantsDropdown.value
}

const selectAllParticipants = () => {
  behavioralLogsForm.value.selectedParticipants = 'all'
  showParticipantsDropdown.value = false
}

const toggleParticipantSelection = (participantId: string) => {
  console.log('Toggle participant selection:', {
    participantId,
    currentSelection: behavioralLogsForm.value.selectedParticipants
  })
  
  if (behavioralLogsForm.value.selectedParticipants === 'all') {
    behavioralLogsForm.value.selectedParticipants = [participantId]
    console.log('Changed from all to specific:', [participantId])
  } else {
    const currentSelection = behavioralLogsForm.value.selectedParticipants as string[]
    if (currentSelection.includes(participantId)) {
      behavioralLogsForm.value.selectedParticipants = currentSelection.filter(id => id !== participantId)
      console.log('Removed participant:', participantId, 'New selection:', behavioralLogsForm.value.selectedParticipants)
    } else {
      behavioralLogsForm.value.selectedParticipants = [...currentSelection, participantId]
      console.log('Added participant:', participantId, 'New selection:', behavioralLogsForm.value.selectedParticipants)
    }
  }
  
  console.log('Final selection:', behavioralLogsForm.value.selectedParticipants)
}

const isParticipantSelected = (participantId: string) => {
  if (behavioralLogsForm.value.selectedParticipants === 'all') {
    return true
  }
  return (behavioralLogsForm.value.selectedParticipants as string[]).includes(participantId)
}

const getParticipantsDropdownLabel = () => {
  if (behavioralLogsForm.value.selectedParticipants === 'all') {
    return 'All Participants'
  }
  const selected = behavioralLogsForm.value.selectedParticipants as string[]
  if (selected.length === 0) {
    return 'Select Participants'
  }
  if (selected.length === 1) {
    return selected[0]
  }
  return `${selected.length} participants selected`
}

// Load session statistics from backend
const loadSessionStatistics = async () => {
  if (!isSessionRegistered.value || !currentSessionCode.value) {
    sessionStatisticsData.value = null
    return
  }

  isLoadingSessionStatistics.value = true
  
  try {
    const response = await fetch(`/api/session-statistics?session_code=${encodeURIComponent(currentSessionCode.value)}`)
    
    if (!response.ok) {
      throw new Error(`Failed to load session statistics: ${response.status}`)
    }
    
    const result = await response.json()
    
    if (result.success && result.statistics) {
      sessionStatisticsData.value = result.statistics
      console.log('✅ Session statistics loaded:', result.statistics)
      
      // Render charts if we're on the analysis tab
      if (activeTab.value === 'analysis') {
        nextTick(() => {
          renderAllCharts()
        })
      }
    } else {
      throw new Error(result.error || 'Failed to load session statistics')
    }
  } catch (error) {
    console.error('❌ Error loading session statistics:', error)
    sessionStatisticsData.value = null
  } finally {
    isLoadingSessionStatistics.value = false
  }
}

// Watch for changes in interaction config and save to backend
watch(interactionConfig, async (newConfig) => {
  try {
    // Only update if we have an active session
    if (!isSessionRegistered.value || !currentSessionCode.value) {
      console.log('⚠️ No active session - skipping interaction config update')
      return
    }
    
    // Update the experiment config with interaction settings
    const updatedConfig = {
      ...experimentConfig.value,
      session_code: currentSessionCode.value, // Ensure session code is included
      communicationLevel: newConfig.communicationLevel,
      awarenessDashboard: newConfig.awarenessDashboard,
      negotiations: newConfig.negotiations,
      simultaneousActions: newConfig.simultaneousActions,
      rationales: newConfig.rationales
    }
    
    console.log('🔄 Updating interaction config for session:', currentSessionCode.value, {
      communicationLevel: newConfig.communicationLevel,
      awarenessDashboard: newConfig.awarenessDashboard,
      negotiations: newConfig.negotiations,
      simultaneousActions: newConfig.simultaneousActions,
      rationales: newConfig.rationales
    })
    
    const response = await fetch('/api/experiment/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updatedConfig)
    })
    
    if (!response.ok) {
      console.error('Failed to update interaction config')
    } else {
      console.log('✅ Interaction config updated successfully for session:', currentSessionCode.value)
    }
  } catch (error) {
    console.error('Error updating interaction config:', error)
  }
}, { deep: true })


// Helper functions for communication mode display
const getCommunicationModeLabel = (mode: CommunicationLevel) => {
  switch (mode) {
    case 'chat':
      return 'Private Messaging'
    case 'broadcast':
      return 'Group Chat'
    case 'no_chat':
      return 'No Chat'
    default:
      return 'Unknown Mode'
  }
}

const getCommunicationModeDescription = (mode: CommunicationLevel) => {
  switch (mode) {
    case 'chat':
      return 'Participants can send private one-to-one messages'
    case 'broadcast':
      return 'All participants can see and send messages in a group'
    case 'no_chat':
      return 'Messaging disabled; no communication possible'
    default:
      return 'Unknown communication mode'
  }
}

// Helper functions for negotiations
const getNegotiationsLabel = (type: NegotiationType) => {
  switch (type) {
    case 'counter':
      return 'Counter'
    case 'no_counter':
      return 'No Counter'
    default:
      return 'Unknown negotiation type'
  }
}

const getNegotiationsDescription = (type: NegotiationType) => {
  switch (type) {
    case 'counter':
      return 'Participants can make counter-offers instead of only accepting or rejecting'
    case 'no_counter':
      return 'Offers can only be accepted or rejected as presented'
    default:
      return 'Unknown negotiation type'
  }
}

// Helper functions for simultaneous actions
const getSimultaneousActionsLabel = (type: SimultaneousActions) => {
  switch (type) {
    case 'allow':
      return 'Allow'
    case 'not_allow':
      return 'Not Allow'
    default:
      return 'Unknown action type'
  }
}

const getSimultaneousActionsDescription = (type: SimultaneousActions) => {
  switch (type) {
    case 'allow':
      return 'Multiple offers can be made at once'
    case 'not_allow':
      return 'Each offer must be resolved before a new one begins'
    default:
      return 'Unknown action type'
  }
}

// Helper functions for awareness dashboard
const getAwarenessDashboardLabel = (type: AwarenessToggle) => {
  switch (type) {
    case 'on':
      return 'On'
    case 'off':
      return 'Off'
    default:
      return 'Unknown awareness type'
  }
}

const getAwarenessDashboardDescription = (type: AwarenessToggle) => {
  switch (type) {
    case 'on':
      return 'Participants see others\' money and order progress in real time'
    case 'off':
      return 'Participants only see others\' names, with no status information'
    default:
      return 'Unknown awareness type'
  }
}

// Helper functions for rationales
const getRationalesLabel = (type: RationalesType) => {
  switch (type) {
    case 'step_wise':
      return 'Step-wise'
    case 'none':
      return 'None'
    default:
      return 'Unknown rationale type'
  }
}

const getRationalesDescription = (type: RationalesType) => {
  switch (type) {
    case 'step_wise':
      return 'Agents explain each decision with reasoning'
    case 'none':
      return 'Agents act without providing reasoning'
    default:
      return 'Unknown rationale type'
  }
}

// Computed properties for parameter visibility
const showShapeParameters = computed(() => {
  if (selectedExperimentType.value === 'shapefactory') return true
  if (selectedExperimentType.value.startsWith('custom_')) {
    const experiment = allAvailableExperiments.value.find(exp => exp.id === selectedExperimentType.value)
    return experiment && (experiment.defaultConfig.specialtyCost !== undefined || experiment.defaultConfig.regularCost !== undefined)
  }
  return false
})

const showMoneyParameters = computed(() => {
  if (['shapefactory', 'daytrader', 'essayranking'].includes(selectedExperimentType.value)) return true
  if (selectedExperimentType.value.startsWith('custom_')) {
    const experiment = allAvailableExperiments.value.find(exp => exp.id === selectedExperimentType.value)
    return experiment && (experiment.defaultConfig.startingMoney !== undefined || experiment.defaultConfig.incentiveMoney !== undefined)
  }
  return false
})
const showTradeParameters = computed(() => {
  if (['shapefactory', 'daytrader', 'essayranking'].includes(selectedExperimentType.value)) return true
  if (selectedExperimentType.value.startsWith('custom_')) {
    const experiment = allAvailableExperiments.value.find(exp => exp.id === selectedExperimentType.value)
    return experiment && (experiment.defaultConfig.minTradePrice !== undefined || experiment.defaultConfig.maxTradePrice !== undefined)
  }
  return false
})

const showProductionParameters = computed(() => {
  if (selectedExperimentType.value === 'shapefactory') return true
  if (selectedExperimentType.value.startsWith('custom_')) {
    const experiment = allAvailableExperiments.value.find(exp => exp.id === selectedExperimentType.value)
    return experiment && (experiment.defaultConfig.productionTime !== undefined || experiment.defaultConfig.maxProductionNum !== undefined || experiment.defaultConfig.shapesPerOrder !== undefined)
  }
  return false
})

const showAgentParameters = computed(() => {
  if (['shapefactory', 'daytrader'].includes(selectedExperimentType.value)) return true
  if (selectedExperimentType.value.startsWith('custom_')) {
    const experiment = allAvailableExperiments.value.find(exp => exp.id === selectedExperimentType.value)
    return experiment && (experiment.defaultConfig.agentPerceptionTimeWindow !== undefined)
  }
  return false
})

const showEssayParameters = computed(() => {
  if (selectedExperimentType.value === 'essayranking') return true
  if (selectedExperimentType.value.startsWith('custom_')) {
    const experiment = allAvailableExperiments.value.find(exp => exp.id === selectedExperimentType.value)
    return experiment && (experiment.defaultConfig.essay_number !== undefined || experiment.defaultConfig.score_scale !== undefined)
  }
  return false
})







// Computed properties
const onlineCount = computed(() => 
  participants.value.filter((p: Participant) => p.status === 'online').length
)

const canStartExperiment = computed(() => {
  // For development: allow starting with fewer participants
  // For production: ensure minimum participants are online
  if (experimentStatus.value === 'waiting') {
    // return onlineCount.value >= 5
    return onlineCount.value >= 0 // Reduced to 1 for easier testing
  }
  // Allow pausing when running and resuming when paused
  return experimentStatus.value === 'running' || experimentStatus.value === 'paused'
})

const totalAgents = computed(() => 
  participants.value.filter((p: Participant) => p.type === 'ai').length
)

const activeAgents = computed(() => 
  participants.value.filter((p: Participant) => p.type === 'ai' && p.status === 'online').length
)

const pendingTrades = computed(() => pendingOffers.value.length)

const totalTrades = computed(() => completedTrades.value.length)

const activeConversations = computed(() => {
  const conversationPairs = new Set()
  messages.value.forEach((msg: Message) => {
    const pair = [msg.from, msg.to].sort().join('-')
    conversationPairs.add(pair)
  })
  return conversationPairs.size
})

// Behavioral logs state
const sessionStatisticsData = ref(null)
const isLoadingSessionStatistics = ref(false)

// Behavioral logs computed properties
const sessionStatistics = computed(() => {
  if (!sessionStatisticsData.value) {
    return {
      totalParticipants: 0,
      totalTrades: 0,
      averageTrades: 0,
      totalMessages: 0,
      averageMessages: 0,
      averageMoney: 0,
      averageOrdersCompleted: 0,
      averageTradePrice: 0,
      minTradePrice: 0,
      maxTradePrice: 0,
      mostWealthyParticipant: '',
      mostWealthyParticipantMoney: 0,
      mostActiveParticipant: '',
      averageMessageLength: 0,
      averageMessagesPerHuman: 0,
      averageMessageLengthPerHuman: 0,
      averageMessageResponseLatency: 0,
      highestWealth: 0,
      highestWealthParticipant: '',
      lowestWealth: 0,
      lowestWealthParticipant: '',
      averageMessagesPerTrade: 0
    }
  }

  const stats = sessionStatisticsData.value
  
  // Calculate most active participant (trades + messages)
  let mostActiveParticipant = ''
  if (stats.participants && stats.participants.length > 0) {
    const mostActive = stats.participants.reduce((max, p) => {
      const activity = (p.total_trades || 0) + (p.total_messages_sent || 0)
      const maxActivity = (max.total_trades || 0) + (max.total_messages_sent || 0)
      return activity > maxActivity ? p : max
    })
    mostActiveParticipant = getDisplayName(mostActive.participant_code)
  }
  
  return {
    totalParticipants: stats.total_participants || 0,
    totalTrades: stats.total_trades || 0,
    averageTrades: Math.round((stats.average_trades_per_participant || 0) * 10) / 10,
    totalMessages: stats.total_messages || 0,
    averageMessages: Math.round((stats.average_messages_per_participant || 0) * 10) / 10,
    averageMoney: Math.round(stats.average_money || 0),
    averageOrdersCompleted: Math.round((stats.average_orders_completed || 0) * 10) / 10,
    averageTradePrice: Math.round(stats.average_trade_price || 0),
    minTradePrice: Math.round(stats.min_trade_price || 0),
    maxTradePrice: Math.round(stats.max_trade_price || 0),
    mostWealthyParticipant: getDisplayName(stats.most_wealthy_participant || ''),
    mostWealthyParticipantMoney: Math.round(stats.most_wealthy_participant_money || 0),
    mostActiveParticipant: mostActiveParticipant,
    averageMessageLength: Math.round(stats.average_message_length || 0),
    averageMessagesPerHuman: Math.round((stats.average_messages_per_human || 0) * 10) / 10,
    averageMessageLengthPerHuman: Math.round(stats.average_message_length_per_human || 0),
    averageMessageResponseLatency: Math.round((stats.average_message_response_latency || 0) * 10) / 10,
    highestWealth: Math.round(stats.highest_wealth || 0),
    highestWealthParticipant: getDisplayName(stats.highest_wealth_participant || ''),
    lowestWealth: Math.round(stats.lowest_wealth || 0),
    lowestWealthParticipant: getDisplayName(stats.lowest_wealth_participant || ''),
    averageMessagesPerTrade: Math.round((stats.average_messages_per_trade || 0) * 10) / 10
  }
})

const filteredParticipants = computed(() => {
  if (!sessionStatisticsData.value || !sessionStatisticsData.value.participants) {
    return []
  }
  
  if (behavioralLogsForm.value.selectedParticipants === 'all') {
    return sessionStatisticsData.value.participants
  }
  return sessionStatisticsData.value.participants.filter(p => 
    behavioralLogsForm.value.selectedParticipants.includes(p.participant_code)
  )
})

const chartData = computed(() => {
  if (!sessionStatisticsData.value || !sessionStatisticsData.value.participants) {
    return {
      timeChartData: [],
      participantChartData: [],
      showTrades: behavioralLogsForm.value.showTrades,
      showMessages: behavioralLogsForm.value.showMessages
    }
  }

  const allParticipants = sessionStatisticsData.value.participants
  const selectedParticipants = behavioralLogsForm.value.selectedParticipants === 'all' 
    ? allParticipants 
    : allParticipants.filter(p => behavioralLogsForm.value.selectedParticipants.includes(p.participant_code))

  // Time-based chart data showing individual trade durations
  const timeChartData = []
  
  // Get completed trades and pending offers data for timeline
  const completedTradesForTimeline = timelineTradesData.value.completed_trades || []
  const pendingOffersForTimeline = timelineTradesData.value.pending_offers || []
  
  // Debug: Log the raw trade data
  console.log('Raw trade data for timeline processing:', {
    completedTradesCount: completedTradesForTimeline.length,
    pendingOffersCount: pendingOffersForTimeline.length,
    completedTradesSample: completedTradesForTimeline.slice(0, 3).map(t => ({
      id: t.id,
      from: t.from,
      to: t.to,
      shape: t.shape,
      timestamp: t.timestamp
    })),
    pendingOffersSample: pendingOffersForTimeline.slice(0, 3).map(t => ({
      id: t.id,
      from: t.from,
      to: t.to,
      shape: t.shape,
      timestamp: t.timestamp
    }))
  })
  
  // Group trades by participant
  const tradesByParticipant = new Map()
  
  // Debug logging for trade data
  const normalizedSelectedParticipants = behavioralLogsForm.value.selectedParticipants === 'all' ? 
    'all' : 
    behavioralLogsForm.value.selectedParticipants.map(p => normalizeParticipantCode(p))
  
  console.log('Trade data for timeline processing:', {
    completedTrades: completedTradesForTimeline.map(t => ({ from: t.from, to: t.to, id: t.id })),
    pendingOffers: pendingOffersForTimeline.map(t => ({ from: t.from, to: t.to, id: t.id })),
    selectedParticipants: behavioralLogsForm.value.selectedParticipants,
    normalizedSelectedParticipants: normalizedSelectedParticipants,
    allParticipants: allParticipants.map(p => p.participant_code),
    selectedParticipantCodes: behavioralLogsForm.value.selectedParticipants === 'all' ? 'all' : behavioralLogsForm.value.selectedParticipants,
    timelineTradesDataRaw: timelineTradesData.value
  })
  
  // Add completed trades (filtered by selected participants)
  completedTradesForTimeline.forEach(trade => {
    const seller = trade.from
    const buyer = trade.to
    
    // Debug: Log the exact participant codes and normalization
    const normalizedSeller = normalizeParticipantCode(seller)
    const normalizedBuyer = normalizeParticipantCode(buyer)
    
    console.log('Processing completed trade:', {
      tradeId: trade.id,
      originalSeller: seller,
      originalBuyer: buyer,
      normalizedSeller: normalizedSeller,
      normalizedBuyer: normalizedBuyer,
      selectedParticipants: behavioralLogsForm.value.selectedParticipants,
      isSellerInSelected: behavioralLogsForm.value.selectedParticipants.includes(normalizedSeller),
      isBuyerInSelected: behavioralLogsForm.value.selectedParticipants.includes(normalizedBuyer)
    })
    
    // Check if either seller or buyer is in selected participants
    // Normalize selected participants to match trade data format (remove _test1 suffix)
    const normalizedSelectedParticipants = behavioralLogsForm.value.selectedParticipants === 'all' ? 
      'all' : 
      behavioralLogsForm.value.selectedParticipants.map(p => normalizeParticipantCode(p))
    
    const isSellerSelected = behavioralLogsForm.value.selectedParticipants === 'all' || 
                            normalizedSelectedParticipants.includes(normalizedSeller)
    const isBuyerSelected = behavioralLogsForm.value.selectedParticipants === 'all' || 
                           normalizedSelectedParticipants.includes(normalizedBuyer)
    
    if (isSellerSelected || isBuyerSelected) {
      // Add trade to seller's timeline
      if (isSellerSelected) {
        if (!tradesByParticipant.has(seller)) {
          tradesByParticipant.set(seller, [])
        }
        tradesByParticipant.get(seller).push({ ...trade, isCompleted: true, role: 'seller' })
        console.log('Added trade to seller timeline:', seller)
      }
      
      // Add trade to buyer's timeline
      if (isBuyerSelected) {
        if (!tradesByParticipant.has(buyer)) {
          tradesByParticipant.set(buyer, [])
        }
        tradesByParticipant.get(buyer).push({ ...trade, isCompleted: true, role: 'buyer' })
        console.log('Added trade to buyer timeline:', buyer)
      }
    } else {
      console.log('Trade not included - neither seller nor buyer selected:', {
        tradeId: trade.id,
        seller: seller,
        buyer: buyer,
        normalizedSeller: normalizedSeller,
        normalizedBuyer: normalizedBuyer
      })
    }
  })
  
  // Add pending offers (filtered by selected participants)
  pendingOffersForTimeline.forEach(trade => {
    const seller = trade.from
    const buyer = trade.to
    
    // Debug: Log the exact participant codes and normalization
    const normalizedSeller = normalizeParticipantCode(seller)
    const normalizedBuyer = normalizeParticipantCode(buyer)
    
    console.log('Processing pending offer:', {
      tradeId: trade.id,
      originalSeller: seller,
      originalBuyer: buyer,
      normalizedSeller: normalizedSeller,
      normalizedBuyer: normalizedBuyer,
      selectedParticipants: behavioralLogsForm.value.selectedParticipants,
      isSellerInSelected: behavioralLogsForm.value.selectedParticipants.includes(normalizedSeller),
      isBuyerInSelected: behavioralLogsForm.value.selectedParticipants.includes(normalizedBuyer)
    })
    
    // Check if either seller or buyer is in selected participants
    // Normalize selected participants to match trade data format (remove _test1 suffix)
    const normalizedSelectedParticipants = behavioralLogsForm.value.selectedParticipants === 'all' ? 
      'all' : 
      behavioralLogsForm.value.selectedParticipants.map(p => normalizeParticipantCode(p))
    
    const isSellerSelected = behavioralLogsForm.value.selectedParticipants === 'all' || 
                            normalizedSelectedParticipants.includes(normalizedSeller)
    const isBuyerSelected = behavioralLogsForm.value.selectedParticipants === 'all' || 
                           normalizedSelectedParticipants.includes(normalizedBuyer)
    
    if (isSellerSelected || isBuyerSelected) {
      // Add trade to seller's timeline
      if (isSellerSelected) {
        if (!tradesByParticipant.has(seller)) {
          tradesByParticipant.set(seller, [])
        }
        tradesByParticipant.get(seller).push({ ...trade, isCompleted: false, role: 'seller' })
        console.log('Added pending offer to seller timeline:', seller)
      }
      
      // Add trade to buyer's timeline
      if (isBuyerSelected) {
        if (!tradesByParticipant.has(buyer)) {
          tradesByParticipant.set(buyer, [])
        }
        tradesByParticipant.get(buyer).push({ ...trade, isCompleted: false, role: 'buyer' })
        console.log('Added pending offer to buyer timeline:', buyer)
      }
    } else {
      console.log('Pending offer not included - neither seller nor buyer selected:', {
        tradeId: trade.id,
        seller: seller,
        buyer: buyer,
        normalizedSeller: normalizedSeller,
        normalizedBuyer: normalizedBuyer
      })
    }
  })
  
  // Create timeline entries for each trade
  tradesByParticipant.forEach((trades, participant) => {
    trades.forEach((trade, index) => {
      // Convert timestamps to relative time from session start (0:00)
      const sessionStartTime = getSessionStartTime()
      const startTime = new Date(trade.timestamp).getTime() - sessionStartTime
      let endTime
      
      if (trade.isCompleted) {
        // For completed trades, use agreed_timestamp or completed_timestamp
        if (trade.agreed_timestamp) {
          endTime = new Date(trade.agreed_timestamp).getTime() - sessionStartTime
        } else if (trade.completed_timestamp) {
          endTime = new Date(trade.completed_timestamp).getTime() - sessionStartTime
        } else {
          endTime = startTime // Fallback to start time if no end time
        }
      } else {
        // For pending offers, don't set an end time - they are ongoing
        endTime = null
      }
      
      // Debug logging for timestamp processing
      console.log('Processing trade timestamps:', {
        participant: participant,
        tradeId: trade.id,
        timestamp: trade.timestamp,
        agreed_timestamp: trade.agreed_timestamp,
        completed_timestamp: trade.completed_timestamp,
        startTime: new Date(startTime).toLocaleString(),
        endTime: endTime ? new Date(endTime).toLocaleString() : 'Pending (No end time)',
        duration: endTime ? Math.round((endTime - startTime) / 1000) + ' seconds' : 'Ongoing'
      })
      
      const tradeData = {
        participant: getDisplayName(participant),
        participantCode: participant, // Keep original participant code for debugging
        tradeId: trade.id,
        tradeIndex: index + 1,
        firstTradeTime: startTime,
        lastTradeTime: endTime,
        totalTrades: trades.length,
        shape: trade.shape,
        quantity: trade.quantity,
        price: trade.price,
        offerType: trade.offer_type,
        isCompleted: trade.isCompleted,
        status: trade.status,
        role: trade.role || 'unknown'
      }
      
      timeChartData.push(tradeData)
      

    })
  })
  
  // Sort by participant name and then by trade timestamp
  timeChartData.sort((a, b) => {
    if (a.participant !== b.participant) {
      return a.participant.localeCompare(b.participant)
    }
    return a.firstTradeTime - b.firstTradeTime
  })
  

  // Participant-based chart data (x: participants, y: trades or messages)
  const participantChartData = selectedParticipants.map(p => {
    return {
      participant: getDisplayName(p.participant_code),
      trades: p.number_successful_trades || 0,
      messages: p.number_messages || 0
    }
  })

  return {
    timeChartData,
    participantChartData,
    showTrades: behavioralLogsForm.value.showTrades,
    showMessages: behavioralLogsForm.value.showMessages
  }
})

// Computed property to group timeline data by participant for display
const timelineDataByParticipant = computed(() => {
  const grouped = new Map()
  
  chartData.value.timeChartData.forEach(tradeData => {
    const participant = tradeData.participant
    if (!grouped.has(participant)) {
      grouped.set(participant, [])
    }
    grouped.get(participant).push(tradeData)
  })
  
  // Convert to array and sort by participant name
  return Array.from(grouped.entries()).sort(([a], [b]) => a.localeCompare(b))
})



const canRegisterParticipant = computed(() => {
  const hasCode = participantForm.value.participantCode.trim() !== ''
  const hasSession = isSessionRegistered.value
  
  // For wordguessing experiments, require role selection
  if (selectedExperimentType.value === 'wordguessing') {
    const hasRole = participantForm.value.wordguessingRole.trim() !== ''
    if (participantForm.value.participantType === 'human') {
      return hasCode && hasSession && hasRole
    } else if (participantForm.value.participantType === 'ai') {
      return hasCode && hasSession && hasRole
    }
  } else {
    if (participantForm.value.participantType === 'human') {
      return hasCode && hasSession
    } else if (participantForm.value.participantType === 'ai') {
      return hasCode && hasSession
    }
  }
  
  return false
})

const canAssignSpecialty = computed(() => {
  // Only allow specialty assignment for Shape Factory experiments
  const isShapeFactory = selectedExperimentType.value === 'shapefactory' || (
    selectedExperimentType.value.startsWith('custom_') && 
    experimentConfig.value.specialtyCost !== undefined
  )
  return participantForm.value.participantCode.trim() !== '' && isShapeFactory
})

const canCreateSession = computed(() => {
  if (!createSessionForm.value.sessionId.trim()) return false
  
  if (createSessionForm.value.sessionType === 'template') {
    return createSessionForm.value.selectedTemplate.trim() !== ''
  }
  
  return true
})

const startButtonIcon = computed(() => {
  switch (experimentStatus.value) {
    case 'waiting': return '▶'
    case 'running': return '⏸'
    case 'paused': return '▶'
    case 'completed': return '✓'
    default: return '▶'
  }
})

const startButtonText = computed(() => {
  switch (experimentStatus.value) {
    case 'waiting': return 'Start'
    case 'running': return 'Pause'
    case 'paused': return 'Resume'
    case 'completed': return 'Completed'
    default: return 'Start'
  }
})

// Title for the group wrapper based on active tab
const activeTabTitle = computed(() => {
  switch (activeTab.value) {
    case 'setup':
      return 'Setup'
    case 'monitor':
      return 'Real-Time Monitor'
    case 'analysis':
      return 'Result Analysis'
    default:
      return ''
  }
})

const experimentStatusText = computed(() => {
  switch (experimentStatus.value) {
    case 'waiting': return 'Waiting for Participants'
    case 'running': return 'Experiment Running'
    case 'paused': return 'Experiment Paused'
    case 'completed': return 'Experiment Completed'
    default: return 'Not Started'
  }
})

const timerDisplay = computed(() => {
  if (!isSessionRegistered.value) return 'No Active Session'
  if (experimentStatus.value === 'waiting') return 'Experiment Not Started'
  if (experimentStatus.value === 'completed') return 'Experiment Completed'
  
  const minutes = Math.floor(timeRemaining.value / 60)
  const seconds = timeRemaining.value % 60
  return `Time: ${minutes}:${seconds.toString().padStart(2, '0')}`
})

// Local countdown timer for smooth real-time updates
const localTimerInterval = ref<number | null>(null)
const lastWebSocketTimerUpdate = ref<number>(0)
const timerUpdateThreshold = 2000 // 2 seconds - if we got a WebSocket update within this time, don't let local timer overwrite it

const startLocalTimer = () => {
  if (localTimerInterval.value) {
    clearInterval(localTimerInterval.value)
  }
  
  localTimerInterval.value = window.setInterval(() => {
    // Only update if experiment is running and we have time remaining
    if (experimentStatus.value === 'running' && timeRemaining.value > 0) {
      // Check if we've received a recent WebSocket update
      const timeSinceLastWebSocketUpdate = Date.now() - lastWebSocketTimerUpdate.value
      const hasRecentWebSocketUpdate = timeSinceLastWebSocketUpdate < timerUpdateThreshold
      
      if (!hasRecentWebSocketUpdate) {
        // No recent WebSocket update, use local countdown
        timeRemaining.value = Math.max(0, timeRemaining.value - 1)
        
        // If timer reaches 0, update status
        if (timeRemaining.value === 0) {
          experimentStatus.value = 'completed'
          console.log('⏰ Local timer reached 0, experiment completed')
        }
      }
    }
  }, 1000) // Update every second
  
  console.log('⏰ Local countdown timer started')
}

const stopLocalTimer = () => {
  if (localTimerInterval.value) {
    clearInterval(localTimerInterval.value)
    localTimerInterval.value = null
    console.log('⏰ Local countdown timer stopped')
  }
}

// Session validation state
const isSessionRegistered = ref(false)
const currentSessionCode = ref('')
const sessionValidationMessage = ref('')
const sessionValidationMessageType = ref<'info' | 'error'>('info')

// Computed property for current session code - ensures consistency
const activeSessionCode = computed(() => {
  // Only use the registered session code
  if (isSessionRegistered.value && currentSessionCode.value) {
    return currentSessionCode.value
  }
  // If no session is registered, return empty string
  return ''
})

// Removed selectedTemplate computed property as it's no longer needed

// Watch for session registration changes to refresh participants
watch(isSessionRegistered, async (newValue, oldValue) => {
  if (newValue !== oldValue) {
    console.log('🔄 Session registration state changed, refreshing participants')
    await loadParticipants()
  }
})

// Watch for session code changes to refresh participants and statistics
watch(currentSessionCode, async (newValue, oldValue) => {
  if (newValue !== oldValue) {
    console.log('🔄 Session code changed, refreshing participants and statistics')
    await loadParticipants()
    await loadSessionStatistics()
  }
})

// Watch for session ID input changes to check session status
watch(() => experimentConfig.value.sessionId, async (newValue, oldValue) => {
  if (newValue !== oldValue && newValue.trim() !== '') {
    console.log('🔄 Session ID input changed, checking session status')
    await checkSessionStatus()
  }
})

// New: Active tab state (single-tab view)
const activeTab = ref<'setup' | 'monitor' | 'analysis'>('setup')

// Setup workflow state - individual tab visibility
const setupTabs = ref({
  initialSelection: true,      // Always visible initially
  experimentSelection: false,  // Appears when user chooses create session
  parameters: false,          // Appears when experiment is selected
  interactionVariables: false, // Appears when parameters are configured
  participantRegistration: false // Appears when interaction variables are set
})

// Current active tab
const activeSetupTab = ref('initialSelection')

// Setup workflow steps configuration
const setupWorkflowSteps = ref([
  { id: 'initialSelection', label: 'Initial Selection' },
  { id: 'experimentSelection', label: 'Experiment Selection' },
  { id: 'parameters', label: 'Parameters' },
  { id: 'interactionVariables', label: 'Interaction Controls' },
  { id: 'participantRegistration', label: 'Participant Registration' }
])

// Watch for active tab changes to load statistics when analysis tab is selected
watch(activeTab, async (newValue, oldValue) => {
  if (newValue === 'analysis' && oldValue !== 'analysis') {
    console.log('🔄 Analysis tab selected, loading session statistics')
    await loadSessionStatistics()
    // Render charts after statistics are loaded
    nextTick(() => {
      renderAllCharts()
    })
  }
})

// New: Participant management state
const availableShapes = ['circle', 'square', 'triangle', 'diamond', 'pentagon']

const participantForm = ref({ 
  participantType: '', 
  participantCode: '', 
  specialty: '',
  wordguessingRole: ''
})

// Session registration state
const isRegisteringSession = ref(false)
const sessionRegistrationMessage = ref('')
const sessionRegistrationMessageType = ref<'success' | 'error'>('success')

// Session management state
const showCreateModal = ref(false)
const showLoadModal = ref(false)
const isCreatingSession = ref(false)
const isLoadingSession = ref(false)


const createSessionForm = ref({
  sessionType: 'new',
  sessionId: '',
  sessionDuration: 15,
  saveAsTemplate: false,
  templateName: '',
  selectedTemplate: ''
})

const loadSessionForm = ref({
  sessionId: ''
})

// Export form state
const exportForm = ref({
  dataType: 'all' as 'all' | 'participants' | 'trades' | 'messages' | 'logs',
  fileFormat: 'json' as 'json' | 'csv' | 'excel'
})

// Behavioral logs state
const behavioralLogsForm = ref({
  selectedParticipants: 'all' as 'all' | string[],
  showTrades: true,
  showMessages: true
})

const showParticipantsDropdown = ref(false)

// Watch for chart data changes to re-render charts
watch(chartData, () => {
  if (activeTab.value === 'analysis') {
    renderAllCharts()
  }
}, { deep: true })

// Watch for behavioral logs form changes to re-render charts
watch(behavioralLogsForm, () => {
  if (activeTab.value === 'analysis') {
    renderAllCharts()
  }
}, { deep: true })

const availableTemplates = ref<any[]>([])

// Tooltip state: track which tooltip is active so only one shows at a time
const activeTooltip = ref<string | null>(null)
const paramTooltipPosition = ref({ x: 0, y: 0 })

// Function to update tooltip position based on mouse position
const updateTooltipPosition = (event: MouseEvent) => {
  paramTooltipPosition.value = {
    x: event.clientX + 10,
    y: event.clientY - 10
  }
}

// Utility function to extract display name from participant code
const getDisplayName = (participantCode: string): string => {
  if (!participantCode) return ''
  // Remove session ID suffix (everything after the last underscore)
  const parts = participantCode.split('_')
  if (parts.length > 1) {
    // Remove the last part (session ID) and join the rest
    return parts.slice(0, -1).join('_')
  }
  return participantCode
}

// Utility function to normalize participant code for comparison
const normalizeParticipantCode = (participantCode: string): string => {
  if (!participantCode) return ''
  // Remove session ID suffix (everything after the last underscore)
  const parts = participantCode.split('_')
  if (parts.length > 1) {
    // Remove the last part (session ID) and join the rest
    return parts.slice(0, -1).join('_')
  }
  return participantCode
}

const participantTabAssignment = ref<Record<string, 'setting' | 'monitor' | 'analysis' | ''>>({})

const loadAssignmentsFromStorage = () => {
  try {
    const raw = localStorage.getItem('participantTabAssignment')
    if (raw) participantTabAssignment.value = JSON.parse(raw)
  } catch {}
}

const saveAssignmentsToStorage = () => {
  localStorage.setItem('participantTabAssignment', JSON.stringify(participantTabAssignment.value))
}

const onAssignTab = (participantCode: string, tabKey: string) => {
  participantTabAssignment.value[participantCode] = (tabKey as any) || ''
  saveAssignmentsToStorage()
}

const getAgentType = (participantCode: string) => {
  // All agents now use basic_agent type
  return 'basic_agent'
}
const onRegisterParticipant = async () => {
  if (!participantForm.value.participantCode) return
  
  // Check if session is registered first
  if (!isSessionRegistered.value) {
    sessionValidationMessage.value = 'Please register a session before adding participants'
    sessionValidationMessageType.value = 'error'
    return
  }
  
  try {
    if (participantForm.value.participantType === 'human') {
      // Register human participant
      const requestBody: any = {
        participant_code: participantForm.value.participantCode,
        session_code: activeSessionCode.value,
        specialty_shape: participantForm.value.specialty || undefined
      }
      
      // Add wordguessing role if experiment is wordguessing
      if (selectedExperimentType.value === 'wordguessing' && participantForm.value.wordguessingRole) {
        requestBody.wordguessingRole = participantForm.value.wordguessingRole
      }
      
      const res = await fetch('/api/participants/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      })
      const result = await res.json()
      if (res.ok && result.success) {
        // If this is a hinter participant and we have words to assign, assign them now
        if (selectedExperimentType.value === 'wordguessing' && 
            participantForm.value.wordguessingRole === 'hinter' && 
            wordAssignmentText.value.trim()) {
          await assignWordsToSpecificHinter(participantForm.value.participantCode)
        }
        
        participantForm.value = { participantType: '', participantCode: '', specialty: '', wordguessingRole: '' }
        await loadParticipants()
      } else {
        alert(result.error ? String(result.error) : 'Failed to register human participant')
      }
    } else if (participantForm.value.participantType === 'ai') {
      // Register AI agent
      const requestBody: any = {
        participant_code: participantForm.value.participantCode,
        session_code: activeSessionCode.value
      }
      
      // Add specialty for ShapeFactory experiments
      if (selectedExperimentType.value === 'shapefactory' || 
          (selectedExperimentType.value.startsWith('custom_') && experimentConfig.value.specialtyCost !== undefined)) {
        requestBody.specialty_shape = participantForm.value.specialty || undefined
      }
      
      // Add wordguessing role for WordGuessing experiments
      if (selectedExperimentType.value === 'wordguessing') {
        requestBody.wordguessingRole = participantForm.value.wordguessingRole
      }
      
      const res = await fetch('/api/agents/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      })
      const result = await res.json()
      if (res.ok && result.success) {
        participantForm.value = { participantType: '', participantCode: '', specialty: '', wordguessingRole: '' }
        await loadParticipants()
      } else {
        alert(result.error ? String(result.error) : 'Failed to register agent')
      }
    }
  } catch (e:any) {
    alert(e.message ? String(e.message) : 'Failed to register participant')
  }
}

const onUpdateSpecialty = async (participantCode: string, specialty: string) => {
  try {
    const res = await fetch('/api/participants/update', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        participant_code: participantCode, 
        session_code: activeSessionCode.value, 
        update_data: { specialty_shape: specialty }
      })
    })
    if (!res.ok) throw new Error('Failed to update specialty')
    await loadParticipants()
  } catch (e:any) {
    alert(e.message)
  }
}

const onDeleteParticipant = async (participantCode: string) => {
  if (!confirm(`Delete participant ${participantCode}?`)) return
  
  // Find the participant to get their session code
  const participant = participants.value.find(p => p.id === participantCode)
  if (!participant) {
    alert('Participant not found')
    return
  }
  
  // Use the participant's actual session code
  const sessionCode = participant.session_code || activeSessionCode.value
  
  try {
    const res = await fetch('/api/participants/delete', {
      method: 'DELETE', 
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        participant_code: participantCode, 
        session_code: sessionCode 
      })
    })
    const result = await res.json()
    if (!res.ok || !result.success) throw new Error(result.error || 'Failed to delete participant')
    await loadParticipants()
  } catch (e:any) {
    alert(e.message)
  }
}

const registerSession = async () => {
  if (!experimentConfig.value.sessionId.trim()) {
    sessionRegistrationMessage.value = 'Please enter a session code'
    sessionRegistrationMessageType.value = 'error'
    return
  }

  // Note: experiment_type can be null initially and set later

  isRegisteringSession.value = true
  sessionRegistrationMessage.value = ''

  try {
    const response = await fetch('/api/sessions/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_code: experimentConfig.value.sessionId,
        researcher_id: 'researcher',
        experiment_type: selectedExperimentType.value || null,
        experiment_config: experimentConfig.value
      })
    })

    const result = await response.json()

    if (response.ok && result.success) {
      sessionRegistrationMessage.value = result.message
      sessionRegistrationMessageType.value = 'success'
      
      // Update session validation state
      isSessionRegistered.value = true
      currentSessionCode.value = experimentConfig.value.sessionId
      sessionValidationMessage.value = `Session "${experimentConfig.value.sessionId}" is registered and ready for participants`
      sessionValidationMessageType.value = 'info'
      
      // Update the session ID to the registered one
      sessionId.value = experimentConfig.value.sessionId
      
      console.log('Session registered successfully:', result.session)
      
      // Register for the newly registered session
      registerForSession()
      
      // Clear session validation message after 3 seconds
      setTimeout(() => {
        sessionValidationMessage.value = ''
      }, 3000)
    } else {
      sessionRegistrationMessage.value = result.error || 'Failed to register session'
      sessionRegistrationMessageType.value = 'error'
      
      // Update session validation state
      isSessionRegistered.value = false
      currentSessionCode.value = ''
      sessionValidationMessage.value = result.error || 'Session registration failed'
      sessionValidationMessageType.value = 'error'
    }
  } catch (error: any) {
    console.error('Error registering session:', error)
    sessionRegistrationMessage.value = `Registration failed: ${error.message}`
    sessionRegistrationMessageType.value = 'error'
    
    // Update session validation state
    isSessionRegistered.value = false
    currentSessionCode.value = ''
    sessionValidationMessage.value = `Registration failed: ${error.message}`
    sessionValidationMessageType.value = 'error'
  } finally {
    isRegisteringSession.value = false
    
    // Clear message after 5 seconds
    setTimeout(() => {
      sessionRegistrationMessage.value = ''
    }, 5000)
  }
}

// Methods
const generateSessionId = () => {
  return Math.random().toString(36).substr(2, 8).toUpperCase()
}

const updateExperimentConfig = async () => {
  console.log('Experiment config updated:', experimentConfig.value)
  try {
    // Include session_code in the request body
    const requestBody = {
      ...experimentConfig.value,
      session_code: activeSessionCode.value
    }
    
    console.log('Sending config update with session_code:', activeSessionCode.value)
    
    const response = await fetch('/api/experiment/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody)
    })
    
    if (!response.ok) {
      throw new Error('Failed to update config')
    }
    
    console.log('Config updated successfully')
    
  } catch (error: any) {
    console.error('Error updating config:', error)
    alert(`Failed to update configuration: ${error.message}`)
  }
}

const updateSessionExperimentType = async () => {
  try {
    if (!isSessionRegistered.value || !currentSessionCode.value || !selectedExperimentType.value) {
      console.log('⚠️ No active session or experiment type - skipping experiment type update')
      return
    }
    
    const response = await fetch('/api/sessions/update-experiment-type', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_code: currentSessionCode.value,
        experiment_type: selectedExperimentType.value
      })
    })
    
    console.log('🔧 Sending experiment type update:', {
      session_code: currentSessionCode.value,
      experiment_type: selectedExperimentType.value
    })
    
    if (response.ok) {
      const result = await response.json()
      console.log('✅ Session experiment type updated successfully:', result)
    } else {
      const errorData = await response.json()
      console.error('❌ Failed to update session experiment type:', errorData)
    }
  } catch (error) {
    console.error('❌ Error updating session experiment type:', error)
  }
}

// Auto-save functions for real-time config updates
const saveExperimentConfigToDatabase = async (config: any) => {
  try {
    const requestBody = {
      ...config,
      session_code: currentSessionCode.value
    }
    
    const response = await fetch('/api/experiment/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody)
    })

    if (response.ok) {
      console.log('✅ Experiment config auto-saved')
    } else {
      console.error('❌ Failed to auto-save experiment config')
    }
  } catch (error) {
    console.error('Error auto-saving experiment config:', error)
  }
}

const saveInteractionConfigToDatabase = async (config: any) => {
  try {
    const requestBody = {
      ...config,
      session_code: currentSessionCode.value
    }
    
    const response = await fetch('/api/interaction/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody)
    })

    if (response.ok) {
      console.log('✅ Interaction config auto-saved')
    } else {
      console.error('❌ Failed to auto-save interaction config')
    }
  } catch (error) {
    console.error('Error auto-saving interaction config:', error)
  }
}

const toggleExperiment = () => {
  console.log('Toggle experiment called, current status:', experimentStatus.value)
  console.log('Button text:', startButtonText.value)
  
  if (experimentStatus.value === 'waiting') {
    console.log('Starting experiment...')
    startExperiment()
  } else if (experimentStatus.value === 'paused') {
    console.log('Resuming experiment...')
    resumeExperiment()
  } else if (experimentStatus.value === 'running') {
    console.log('Pausing experiment...')
    pauseExperiment()
  }
}

const startExperiment = async () => {
  
  try {
    const requestBody = { session_code: activeSessionCode.value }
    console.log('🔍 Request body:', requestBody)
    
    const response = await fetch('/api/experiment/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody)
    })
    
    if (response.ok) {
      console.log('Experiment started successfully')
      console.log('Waiting for WebSocket status update...')
      
      // Fallback: check timer state after a short delay if WebSocket update doesn't come
      setTimeout(async () => {
        if (experimentStatus.value !== 'running') {
          console.log('WebSocket update not received, checking timer state manually...')
          try {
            const sessionCode = activeSessionCode.value
            console.log('🔍 Fallback check - session code:', sessionCode)
            const timerResponse = await fetch(`/api/experiment/timer-state?session_code=${encodeURIComponent(sessionCode)}`)
            const timerData = await timerResponse.json()
            console.log('🔍 Fallback check - timer data:', timerData)
            if (timerData.experiment_status === 'running') {
              experimentStatus.value = 'running'
              timeRemaining.value = timerData.time_remaining
              lastWebSocketTimerUpdate.value = Date.now()
              startLocalTimer() // Start local timer for smooth countdown
              console.log('Status updated via fallback mechanism')
            } else {
              console.log('🔍 Fallback check - experiment not running, status:', timerData.experiment_status)
            }
          } catch (error) {
            console.error('Fallback timer state check failed:', error)
          }
        }
      }, 1000) // Check after 1 second
    } else {
      console.error('Failed to start experiment')
      experimentStatus.value = 'waiting'
    }
  } catch (error) {
    console.error('Error starting experiment:', error)
    experimentStatus.value = 'waiting'
  }
}

const pauseExperiment = async () => {
  console.log('Pause experiment called, current status:', experimentStatus.value)
  try {
    const response = await fetch('/api/experiment/pause', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ session_code: activeSessionCode.value })
    })
    
    if (response.ok) {
      console.log('Experiment paused successfully')
      console.log('Waiting for WebSocket status update...')
      
      // Fallback: check timer state after a short delay if WebSocket update doesn't come
      setTimeout(async () => {
        if (experimentStatus.value !== 'paused') {
          console.log('WebSocket update not received, checking timer state manually...')
          try {
            const sessionCode = activeSessionCode.value
            const timerResponse = await fetch(`/api/experiment/timer-state?session_code=${encodeURIComponent(sessionCode)}`)
            const timerData = await timerResponse.json()
            if (timerData.experiment_status === 'paused') {
              experimentStatus.value = 'paused'
              stopLocalTimer() // Stop local timer when paused
              console.log('Status updated via fallback mechanism')
            }
          } catch (error) {
            console.error('Fallback timer state check failed:', error)
          }
        }
      }, 1000) // Check after 1 second
    } else {
      console.error('Failed to pause experiment')
    }
  } catch (error) {
    console.error('Error pausing experiment:', error)
  }
}

const resumeExperiment = async () => {
  console.log('Resume experiment called, current status:', experimentStatus.value)
  try {
    const response = await fetch('/api/experiment/resume', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ session_code: activeSessionCode.value })
    })
    
    if (response.ok) {
      console.log('Experiment resumed successfully')
      console.log('Waiting for WebSocket status update...')
      
      // Fallback: check timer state after a short delay if WebSocket update doesn't come
      setTimeout(async () => {
        if (experimentStatus.value !== 'running') {
          console.log('WebSocket update not received, checking timer state manually...')
          try {
            const sessionCode = activeSessionCode.value
            const timerResponse = await fetch(`/api/experiment/timer-state?session_code=${encodeURIComponent(sessionCode)}`)
            const timerData = await timerResponse.json()
            if (timerData.experiment_status === 'running') {
              experimentStatus.value = 'running'
              timeRemaining.value = timerData.time_remaining
              lastWebSocketTimerUpdate.value = Date.now()
              startLocalTimer() // Start local timer for smooth countdown
              console.log('Status updated via fallback mechanism')
            }
          } catch (error) {
            console.error('Fallback timer state check failed:', error)
          }
        }
      }, 1000) // Check after 1 second
    } else {
      console.error('Failed to resume experiment')
      experimentStatus.value = 'paused'
    }
  } catch (error) {
    console.error('Error resuming experiment:', error)
    experimentStatus.value = 'paused'
  }
}

const resetExperiment = async () => {
  // Show confirmation dialog
  const confirmed = confirm('⚠️ WARNING: This will delete all current session data including uploaded essays and rankings. \nAre you sure you want to proceed?')
  
  if (!confirmed) {
    console.log('❌ Reset cancelled by user')
    return
  }
  
  try {
    console.log('🔄 Resetting experiment...')
    
    // Immediately clear data arrays for instant feedback
    participants.value = []
    pendingOffers.value = []
    completedTrades.value = []
    messages.value = []
    
    console.log('✅ Cleared frontend data arrays')
    
    const response = await fetch('/api/experiment/reset', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_code: activeSessionCode.value
      })
    })
    
    if (response.ok) {
      const result = await response.json()
      console.log('✅ Experiment reset successfully:', result)
      
      // Update experiment status immediately
      experimentStatus.value = 'waiting'
      stopLocalTimer() // Stop local timer when reset
      
      // Update session state since session was deleted
      isSessionRegistered.value = false
      currentSessionCode.value = ''
      sessionValidationMessage.value = 'Session was deleted during reset. Please register a new session before adding participants.'
      sessionValidationMessageType.value = 'error'
      
      // Clear uploaded essays
      uploadedEssays.value = []
      
      // Refresh data from server to ensure consistency
      await loadInitialData()
      
      console.log('✅ Reset complete - all data cleared and refreshed')
    } else {
      console.error('❌ Failed to reset experiment')
      // Restore data if reset failed
      await loadInitialData()
    }
  } catch (error) {
    console.error('❌ Error resetting experiment:', error)
    // Restore data if reset failed
    await loadInitialData()
  }
}

const resetTimer = async () => {
  // Show confirmation dialog with detailed information
  const confirmed = confirm(
    'This will reset the game status.\n' +
    'Are you sure you want to proceed?'
  )
  
  if (!confirmed) {
    return
  }
  
  try {
    
    // Immediately clear data arrays for instant feedback
    pendingOffers.value = []
    completedTrades.value = []
    messages.value = []
    uploadedEssays.value = []
    
    
    const response = await fetch('/api/experiment/timer-reset', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_code: activeSessionCode.value
      })
    })
    
    if (response.ok) {
      const result = await response.json()
      console.log('✅ Timer reset successfully:', result)
      
      // Update experiment status immediately
      experimentStatus.value = 'waiting'
      stopLocalTimer() // Stop local timer when reset
      
      // Update timer display
      if (result.timer_state) {
        timeRemaining.value = result.timer_state.time_remaining
        lastWebSocketTimerUpdate.value = Date.now()
      }
      
      // Refresh data from server to ensure consistency
      await loadInitialData()
      
      console.log('✅ Timer reset complete - game data cleared and timer reset')
    } else {
      const errorData = await response.json()
      console.error('❌ Failed to reset timer:', errorData)
      alert(`Failed to reset timer: ${errorData.error ? String(errorData.error) : 'Unknown error'}`)
      // Restore data if reset failed
      await loadInitialData()
    }
  } catch (error) {
    console.error('❌ Error resetting timer:', error)
    alert(`Error resetting timer: ${error instanceof Error ? error.message : 'Unknown error'}`)
    // Restore data if reset failed
    await loadInitialData()
  }
}

const exportData = async () => {
  try {
    // Show loading state
    console.log('📊 Starting comprehensive session export...')
    
    // Get session code
    const sessionCode = activeSessionCode.value || sessionId.value
    
    if (!sessionCode) {
      alert('No active session to export. Please register a session first.')
      return
    }
    
    // Call the backend export endpoint to get the zip file
    const response = await fetch('/api/export/session-logs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_code: sessionCode
      })
    })
    
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || 'Failed to export session logs')
    }
    
    // Get the zip file as a blob
    const zipBlob = await response.blob()
    
    // Create download link
    const url = URL.createObjectURL(zipBlob)
    const link = document.createElement('a')
    link.href = url
    
    // Get filename from response headers or create default
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = `shape_factory_session_${sessionCode}_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.zip`
    
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="(.+)"/)
      if (filenameMatch) {
        filename = filenameMatch[1]
      }
    }
    
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    URL.revokeObjectURL(url)
    
    alert(`✅ Session export completed successfully!\n\nSession: ${sessionCode}\nFile: ${filename}\n\nThis zip file contains:\n• Complete session summary (JSON)\n• All participant logs (human & agent)\n• LLM interaction logs\n• Memory logs\n• All raw log files`)
    
  } catch (error) {
    console.error('❌ Error exporting session logs:', error)
    alert(`❌ Failed to export session logs: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

const logout = () => {
  if (confirm('Are you sure you want to logout? Any unsaved data will be lost.')) {
    router.push('/')
  }
}

// Agent registration function
const registerAgent = async () => {
  if (!canRegisterParticipant.value) {
    alert('Please fill in all agent fields')
    return
  }
  
  try {
    console.log('Registering new agent:', participantForm.value)
    
    const response = await fetch('/api/agents/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        participant_code: participantForm.value.participantCode,
        session_code: activeSessionCode.value,
        specialty_shape: participantForm.value.specialty || undefined
      })
    })
    
    const result = await response.json()
    console.log('Agent registration response:', result)
    
    if (result.success) {
      // Show success message
      registrationMessage.value = `✅ Agent ${participantForm.value.participantCode} registered successfully!`
      registrationMessageType.value = 'success'
      
      // Clear form
      participantForm.value = { participantType: '', participantCode: '', specialty: '', wordguessingRole: '' }
      
      // Refresh participant list to show new agent
      await loadParticipants()
      
      console.log(`Successfully registered agent ${participantForm.value.participantCode}`)
    } else {
      // Show error message
      registrationMessage.value = `❌ Registration failed: ${result.error}`
      registrationMessageType.value = 'error'
      console.error('Agent registration failed:', result.error)
    }
    
    // Clear message after 5 seconds
    setTimeout(() => {
      registrationMessage.value = ''
    }, 5000)
    
  } catch (error: any) {
    console.error('Error registering agent:', error)
    registrationMessage.value = `❌ Registration failed: ${error.message}`
    registrationMessageType.value = 'error'
    
    // Clear message after 5 seconds
    setTimeout(() => {
      registrationMessage.value = ''
    }, 5000)
  }
}

const refreshData = async () => {
  console.log('Refreshing all data...')
  try {
    await Promise.all([
      loadParticipants(),
      loadTrades(),
      loadMessages(),
      // loadSessionMetrics()
    ])
    console.log('All data refreshed successfully.')
  } catch (error) {
    console.error('Error refreshing data:', error)
  }
}

const reconnectWebSocket = () => {
  console.log('Attempting to reconnect WebSocket...')
  if (socket) {
    socket.disconnect()
  }
  setTimeout(() => {
    initializeWebSocket()
  }, 1000)
}

const registerForSession = () => {
  if (socket && activeSessionCode.value) {
    socket.emit('register_researcher', { session_id: activeSessionCode.value })
    console.log(`📡 Registered as researcher for session: ${activeSessionCode.value}`)
    
    socket.emit('subscribe_to_updates', { sessionId: activeSessionCode.value })
    console.log(`📡 Subscribed to updates for session: ${activeSessionCode.value}`)
    
    // Load initial data for the session
    loadInitialData()
    
    // Check timer state for the session
    const timerUrl = `/api/experiment/timer-state?session_code=${encodeURIComponent(activeSessionCode.value)}`
    fetch(timerUrl)
      .then(response => response.json())
      .then(data => {
        console.log('Session timer state:', data)
        timeRemaining.value = data.time_remaining
        lastWebSocketTimerUpdate.value = Date.now()
        
        switch (data.experiment_status) {
          case 'running':
            experimentStatus.value = 'running'
            startLocalTimer()
            break
          case 'paused':
            experimentStatus.value = 'paused'
            break
          case 'completed':
            experimentStatus.value = 'completed'
            break
          case 'idle':
            experimentStatus.value = 'waiting'
            break
        }
      })
      .catch(error => console.error('Error fetching session timer state:', error))
  }
}

const loadInitialData = async () => {
  try {
    // Only load data if we have an active session
    if (!isSessionRegistered.value || !currentSessionCode.value) {
      console.log('⚠️ No active session - skipping initial data load')
      return
    }
    
    // Load all data from database
    await Promise.all([
      loadParticipants(),
      loadTrades(),
      loadMessages(),
      loadExperimentConfig(), // Load experiment config to get communication level
      loadSessionExperimentType() // Load session's experiment type
    ])
    
    console.log('Initial data loaded successfully for session:', currentSessionCode.value)
  } catch (error) {
    console.error('Error loading initial data:', error)
  }
}

// Data loading functions
const loadExperimentConfig = async () => {
  try {
    // Only load config if we have an active session
    if (!isSessionRegistered.value || !currentSessionCode.value) {
      console.log('⚠️ No active session - skipping experiment config load')
      return
    }
    
    const response = await fetch(`/api/experiment/config?session_code=${encodeURIComponent(currentSessionCode.value)}`)
    if (!response.ok) {
      throw new Error('Failed to load experiment config')
    }
    const data = await response.json()
    if (data.success && data.config) {
      // Preserve the null sessionDuration value to show placeholder
      const currentSessionDuration = experimentConfig.value.sessionDuration
      experimentConfig.value = { ...experimentConfig.value, ...data.config }
      // Restore null sessionDuration if it was null before
      if (currentSessionDuration === null) {
        experimentConfig.value.sessionDuration = null
      }
      // Also update interaction config if available
      if (data.config.communicationLevel) {
        interactionConfig.value.communicationLevel = data.config.communicationLevel
      }
      if (data.config.awarenessDashboard) {
        interactionConfig.value.awarenessDashboard = data.config.awarenessDashboard
      }
      
      // Restore wordguessing parameters if they exist
      if (data.config.wordList && Array.isArray(data.config.wordList)) {
        wordAssignmentText.value = data.config.wordList.join(', ')
        console.log('✅ Restored wordguessing word list:', data.config.wordList)
      }
      
      console.log('✅ Session-specific experiment config loaded:', {
        communicationLevel: data.config.communicationLevel,
        awarenessDashboard: data.config.awarenessDashboard,
        wordList: data.config.wordList
      })
    }
  } catch (error) {
    console.error('Error loading experiment config:', error)
  }
}

const loadSessionExperimentType = async () => {
  try {
    // Only load experiment type if we have an active session
    if (!isSessionRegistered.value || !currentSessionCode.value) {
      console.log('⚠️ No active session - skipping experiment type load')
      return
    }
    
    const response = await fetch(`/api/session/current?session_code=${encodeURIComponent(currentSessionCode.value)}`)
    if (!response.ok) {
      throw new Error('Failed to load session experiment type')
    }
    
    const data = await response.json()
    console.log('Session data loaded:', data)
    
    // Set the experiment type as selected if it exists
    if (data.experiment_type) {
      let experimentType = data.experiment_type
      
      // No more legacy experiment type mapping needed
      
      // Check if this experiment type exists in our available experiments
      const experiment = allAvailableExperiments.value.find(exp => exp.id === experimentType)
      if (experiment) {
        selectedExperimentType.value = experimentType
        // Also set as previewed so the "Select and Configure" button shows
        previewedExperiment.value = experimentType
        // Expand the experiment item to show it as selected
        expandedExperiments.value.add(experimentType)
        console.log('🔧 Loaded session experiment type:', experimentType)
        
        // Apply the experiment configuration
        onExperimentTypeChange()
        
        // Load experiment-specific data
        if (experimentType === 'essayranking') {
          await loadSessionEssays()
        }
      } else {
        console.warn('🔧 Unknown experiment type in session:', experimentType)
      }
    }
    
  } catch (error) {
    console.error('Error loading session experiment type:', error)
  }
}

const loadSessionEssays = async () => {
  try {
    if (!isSessionRegistered.value || !currentSessionCode.value) {
      console.log('⚠️ No active session - skipping essay load')
      return
    }
    
    const response = await fetch(`/api/essayranking/get-essays?session_code=${encodeURIComponent(currentSessionCode.value)}`)
    if (!response.ok) {
      console.log('No essays found for this session or error loading essays')
      return
    }
    
    const data = await response.json()
    if (data.success && data.essays && Array.isArray(data.essays)) {
      // Convert database essays to UI format
      uploadedEssays.value = data.essays.map((essay: any) => ({
        id: essay.essay_id,
        filename: essay.filename,
        title: essay.title,
        file: null // We don't have the original file, just the content
      }))
      console.log('✅ Loaded essays from session:', uploadedEssays.value.length, 'essays')
    }
  } catch (error) {
    console.error('Error loading session essays:', error)
  }
}

const loadParticipants = async () => {
  try {
    // Only load participants if we have a registered session
    if (!isSessionRegistered.value || !currentSessionCode.value) {
      participants.value = []
      console.log('⚠️ No registered session - clearing participants list')
      return
    }
    
    const response = await fetch(`/api/participants?session_code=${encodeURIComponent(currentSessionCode.value)}`)
    if (!response.ok) {
      throw new Error('Failed to load participants')
    }
    const data = await response.json()
    
    // Filter participants by current session code on frontend as backup
    const filteredData = data.filter((p: Participant) => 
      p.session_code === currentSessionCode.value
    )
    
    participants.value = filteredData
    // console.log(`✅ Loaded ${filteredData.length} participants for session ${currentSessionCode.value}`)
    // console.log('DEBUG: Participant types:', filteredData.map(p => ({ id: p.id, type: p.type })))
  } catch (error) {
    console.error('Error loading participants:', error)
    participants.value = [] // Clear participants on error
  }
}
const loadTrades = async () => {
  try {
    // Only load trades if we have a registered session
    if (!isSessionRegistered.value || !currentSessionCode.value) {
      pendingOffers.value = []
      completedTrades.value = []
      console.log('⚠️ No registered session - clearing trades list')
      return
    }
    
    const response = await fetch(`/api/trades?session_code=${encodeURIComponent(currentSessionCode.value)}`)
    if (!response.ok) {
      throw new Error('Failed to load trades')
    }
    const data = await response.json()
    console.log('Trades data received:', data)
    
    // Map backend data to frontend expected format for TradesFeed component
    const mapTradeData = (trade: any) => ({
      id: trade.id,
      from: trade.from,
      to: trade.to,
      shape: trade.shape,
      quantity: trade.quantity,
      price: parseFloat(trade.price),
      status: trade.status,
      timestamp: new Date(trade.timestamp), // Convert to Date for TradesFeed
      offer_type: trade.offer_type
    })
    
    // Map backend data to frontend expected format for timeline processing
    const mapTradeDataForTimeline = (trade: any) => ({
      id: trade.id,
      from: trade.from,
      to: trade.to,
      shape: trade.shape,
      quantity: trade.quantity,
      price: parseFloat(trade.price),
      status: trade.status,
      timestamp: trade.timestamp, // Keep as string for timeline processing
      agreed_timestamp: trade.agreed_timestamp,
      completed_timestamp: trade.completed_timestamp,
      offer_type: trade.offer_type
    })
    
    // Handle the new API structure with separate arrays
    pendingOffers.value = (data.pending_offers || []).map(mapTradeData)
    completedTrades.value = (data.completed_trades || []).map(mapTradeData)
    
    // Store raw data for timeline processing
    timelineTradesData.value = data
    
    console.log('Trades processed:', { pending: pendingOffers.value.length, completed: completedTrades.value.length })
    console.log('Timeline data stored:', {
      completed: timelineTradesData.value.completed_trades?.length || 0,
      pending: timelineTradesData.value.pending_offers?.length || 0
    })
  } catch (error) {
    console.error('Error loading trades:', error)
  }
}

const loadMessages = async () => {
  try {
    // Only load messages if we have a registered session
    if (!isSessionRegistered.value || !currentSessionCode.value) {
      messages.value = []
      console.log('⚠️ No registered session - clearing messages list')
      return
    }
    
    const response = await fetch(`/api/messages?session_code=${encodeURIComponent(currentSessionCode.value)}`)
    if (!response.ok) {
      throw new Error('Failed to load messages')
    }
    const data = await response.json()
    console.log('Messages data received:', data)
    // Map backend fields to frontend expected fields
    messages.value = data.map((msg: any) => ({
      id: msg.message_id,
      from: msg.sender,
      to: msg.recipient,
      content: msg.content,
      timestamp: new Date(msg.timestamp)
    }))
    console.log('Messages processed:', messages.value.length)
  } catch (error) {
    console.error('Error loading messages:', error)
  }
}

const loadSessionMetrics = async () => {
  try {
    const response = await fetch('/api/data')
    if (!response.ok) {
      throw new Error('Failed to load session metrics')
    }
    const data = await response.json()
    // console.log('Session metrics loaded:', data)
  } catch (error) {
    console.error('Error loading session metrics:', error)
  }
}

const initializeWebSocket = () => {
  try {
    // Connect to WebSocket server with better configuration
    socket = io(BACKEND_URL, {
      transports: ['websocket', 'polling'],
      timeout: 60000, // Match server ping_timeout
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      // Add these options for better SSL handling
      secure: false, // Set to false for local development
      rejectUnauthorized: false,
      // Force WebSocket transport for better performance
      forceNew: true
    })
    
    socket.on('connect', () => {
      console.log('✅ Connected to WebSocket server')
      isConnected.value = true
      
      // Send heartbeat response to confirm connection
      socket?.emit('heartbeat_response', { timestamp: new Date().toISOString() })
      
      // Only register for session if we have an active session
      if (activeSessionCode.value) {
        socket?.emit('register_researcher', { session_id: activeSessionCode.value })
        console.log(`📡 Registered as researcher for session: ${activeSessionCode.value}`)
        
        // Subscribe to real-time updates
        socket?.emit('subscribe_to_updates', { sessionId: activeSessionCode.value })
        console.log(`📡 Subscribed to updates for session: ${activeSessionCode.value}`)
      } else {
        console.log('⚠️ No active session - skipping WebSocket registration')
      }
      
      // Join researcher room for targeted broadcasts
      socket?.emit('join_researcher_room')
      console.log('📡 Joined researcher room')
      
      // Only request timer state if we have an active session
      const sessionCode = activeSessionCode.value
      if (sessionCode) {
        const timerUrl = `/api/experiment/timer-state?session_code=${encodeURIComponent(sessionCode)}`
        
        fetch(timerUrl)
          .then(response => response.json())
          .then(data => {
            console.log('Initial timer state:', data)
            timeRemaining.value = data.time_remaining
            lastWebSocketTimerUpdate.value = Date.now() // Record initial state
            
            switch (data.experiment_status) {
              case 'running':
                experimentStatus.value = 'running'
                console.log('✅ Experiment status set to running from initial timer state')
                // Start local timer for smooth countdown
                startLocalTimer()
                break
              case 'paused':
                experimentStatus.value = 'paused'
                console.log('⏸️ Experiment status set to paused from initial timer state')
                break
              case 'completed':
                experimentStatus.value = 'completed'
                console.log('✅ Experiment status set to completed from initial timer state')
                break
              case 'idle':
                experimentStatus.value = 'waiting'
                console.log('⏳ Experiment status set to waiting from initial timer state')
                break
            }
            console.log(`Current experiment status: ${experimentStatus.value}, time remaining: ${timeRemaining.value}`)
          })
          .catch(error => console.error('Error fetching timer state:', error))
      } else {
        console.log('⚠️ No active session - skipping timer state check')
      }
    })
    
    socket.on('disconnect', (reason: string) => {
      console.log('❌ Disconnected from WebSocket server, reason:', reason)
      isConnected.value = false
    })
    
    socket.on('connect_error', (error: any) => {
      console.error('❌ WebSocket connection error:', error)
      isConnected.value = false
    })
    
    socket.on('reconnect', (attemptNumber: number) => {
      console.log(`🔄 Reconnected to WebSocket server (attempt ${attemptNumber})`)
      isConnected.value = true
      
      // Re-register and re-subscribe after reconnection
      const sessionCode = activeSessionCode.value
      if (sessionCode) {
        socket?.emit('register_researcher', { session_id: sessionCode })
        socket?.emit('subscribe_to_updates', { sessionId: sessionCode })
        socket?.emit('join_researcher_room')
        
        // Refresh timer state after reconnection
        fetch(`/api/experiment/timer-state?session_code=${encodeURIComponent(sessionCode)}`)
          .then(response => response.json())
          .then(data => {
            console.log('🔄 Refreshed timer state after reconnection:', data)
            timeRemaining.value = data.time_remaining
            lastWebSocketTimerUpdate.value = Date.now()
            
            switch (data.experiment_status) {
              case 'running':
                experimentStatus.value = 'running'
                startLocalTimer()
                break
              case 'paused':
                experimentStatus.value = 'paused'
                stopLocalTimer()
                break
              case 'completed':
                experimentStatus.value = 'completed'
                stopLocalTimer()
                break
              case 'idle':
                experimentStatus.value = 'waiting'
                stopLocalTimer()
                break
            }
          })
          .catch(error => console.error('Error refreshing timer state after reconnection:', error))
      }
    })
    
    socket.on('reconnect_error', (error: any) => {
      console.error('❌ WebSocket reconnection error:', error)
    })
    
    // Listen for server heartbeat and respond
    socket.on('heartbeat', (data: any) => {
      console.log('💓 Server heartbeat received:', data)
      socket?.emit('heartbeat_response', { timestamp: new Date().toISOString() })
    })
    
    // Listen for real-time updates
    
    socket.on('new_message', (message: any) => {
      console.log('New message received:', message)
      loadMessages() // Refresh messages data
    })
    
    socket.on('config_updated', (config: any) => {
      console.log('Config updated:', config)
      // Update local config if needed
      if (config.communicationLevel) {
        interactionConfig.value.communicationLevel = config.communicationLevel
      }
      if (config.awarenessDashboard) {
        interactionConfig.value.awarenessDashboard = config.awarenessDashboard
      }
      console.log('✅ Interaction config updated via WebSocket:', {
        communicationLevel: config.communicationLevel,
        awarenessDashboard: config.awarenessDashboard
      })
    })
    
    socket.on('experiment_started', (data: any) => {
      console.log('Experiment started:', data)
      experimentStatus.value = 'running'
      loadParticipants() // Refresh participant data
    })
    
    socket.on('experiment_paused', (data: any) => {
      console.log('Experiment paused:', data)
      experimentStatus.value = 'paused'
    })
    
    socket.on('experiment_resumed', (data: any) => {
      console.log('Experiment resumed:', data)
      experimentStatus.value = 'running'
    })
    
    socket.on('experiment_reset', (data: any) => {
      console.log('Experiment reset:', data)
      experimentStatus.value = 'waiting'
      stopLocalTimer() // Stop local timer when reset
      
      // Update session state since session was deleted
      isSessionRegistered.value = false
      currentSessionCode.value = ''
      sessionValidationMessage.value = 'Session was deleted during reset. Please register a new session before adding participants.'
      sessionValidationMessageType.value = 'error'
      
      // Explicitly clear all data arrays
      participants.value = []
      pendingOffers.value = []
      completedTrades.value = []
      messages.value = []
      uploadedEssays.value = []
      
      console.log('✅ Cleared all data arrays and uploaded essays on reset')
      
      // Also refresh from server to ensure consistency
      loadInitialData()
      
      // Specifically refresh trades data to ensure UI is updated
      setTimeout(() => {
        loadTrades()
      }, 500) // Small delay to ensure backend has processed the reset
    })
    
    socket.on('timer_reset', (data: any) => {
      console.log('Timer reset:', data)
      experimentStatus.value = 'waiting'
      stopLocalTimer() // Stop local timer when reset
      
      // Clear game data arrays but keep participants
      pendingOffers.value = []
      completedTrades.value = []
      messages.value = []
      uploadedEssays.value = []
      
      console.log('✅ Cleared game data arrays and uploaded essays on timer reset')
      
      // Refresh data from server to ensure consistency
      loadInitialData()
      
      // Specifically refresh trades data to ensure UI is updated
      setTimeout(() => {
        loadTrades()
      }, 500) // Small delay to ensure backend has processed the reset
    })
    
    socket.on('agents_toggled', (data: any) => {
      console.log('Agents toggled:', data)
      // agentsActive.value = data.active // This line is removed
      loadParticipants() // Refresh participant data
    })
    
    // Listen for real participant connection events
    socket.on('participant_connected', (data: any) => {
      console.log('🟢 Participant connected event received:', data)
      
      // Immediately update participant status for instant feedback
      const participantIndex = participants.value.findIndex((p: Participant) => p.id === data.participant_code)
      if (participantIndex !== -1) {
        participants.value[participantIndex].status = 'online'
        participants.value[participantIndex].login_time = new Date().toLocaleTimeString()
        console.log(`✅ Updated ${data.participant_code} status to online immediately`)
      }
      
      // Also refresh the full participant list to get complete data
      setTimeout(() => {
        loadParticipants()
      }, 100) // Small delay to ensure backend has processed the change
    })
    
    socket.on('participant_disconnected', (data: any) => {
      console.log('🔴 Participant disconnected event received:', data)
      
      // Immediately update participant status for instant feedback
      const participantIndex = participants.value.findIndex((p: Participant) => p.id === data.participant_code)
      if (participantIndex !== -1) {
        participants.value[participantIndex].status = 'offline'
        console.log(`✅ Updated ${data.participant_code} status to offline immediately`)
      }
      
      // Also refresh the full participant list to get complete data
      setTimeout(() => {
        loadParticipants()
      }, 100) // Small delay to ensure backend has processed the change
    })

    // General participant status update listener
    socket.on('participant_status_update', (data: any) => {
      console.log('🔄 Participant status update received:', data)
      // Always refresh participant list when status changes
      loadParticipants()
    })

    // Listen for production events
    socket.on('production_started', (data: any) => {
      console.log('Production started:', data)
      loadParticipants() // Refresh to update participant activity
    })

    // Listen for order fulfillment events
    socket.on('orders_fulfilled', (data: any) => {
      console.log('Orders fulfilled:', data)
      loadParticipants() // Refresh to update participant scores and activity
    })

    // Listen for trade offer events
    socket.on('new_trade_offer', (data: any) => {
      console.log('New trade offer created:', data)
      loadTrades() // Refresh trades data to show new offers
    })

    socket.on('trade_offer_response', (data: any) => {
      console.log('Trade offer response:', data)
      loadTrades() // Refresh trades data to show response status
    })

    // Listen for trade completion events
    socket.on('trade_completed', (data: any) => {
      console.log('Trade completed:', data)
      loadTrades() // Refresh trades data
      loadParticipants() // Refresh participant data (money/stats updated)
    })

    // Listen for trade negotiation events
    socket.on('trade_offer_negotiated', (data: any) => {
      console.log('Trade offer negotiated:', data)
      loadTrades() // Refresh trades data to show updated prices
    })

    // Listen for participant status updates (money, orders, etc.)
    socket.on('participant_status_update', (data: any) => {
      console.log('Participant status update received:', data)
      loadParticipants() // Refresh participant data immediately
    })

    // Listen for money updates
    socket.on('money_updated', (data: any) => {
      console.log('Money updated:', data)
      loadParticipants() // Refresh participant data immediately
    })
    
    // Listen for agent auto-configuration events
    socket.on('agents_auto_configured', (data: any) => {
      console.log('Agents auto-configured:', data)
      
      // agentsActive.value = data.auto_activated // This line is removed
      if (data.agents_created === 0 && data.participant_mix === 'all_human') {
        // agentsActive.value = false // This line is removed
      }
      
      // Refresh participant data to show changes
      loadParticipants()
    })
    
    socket.on('agent_auto_config_error', (data: any) => {
      console.error('Agent auto-config error:', data)
      // agentsActive.value = false // This line is removed
    })

    // New WebSocket listeners for async agent activation
    socket.on('agents_activation_complete', (data: any) => {
      console.log('Agent activation completed:', data)
      if (data.success) {
        // agentsActive.value = true // This line is removed
        loadParticipants() // Refresh participant list
        if (data.agents_activated > 0) {
          console.log(`✅ Successfully activated ${data.agents_activated}/${data.total_agents} agents`)
        } else {
          console.log(`ℹ️ Agent activation completed with no new activations (agents may already be active)`)
        }
      } else {
        // Actual failure with errors
        const errorMessage = data.errors 
          ? (Array.isArray(data.errors) ? data.errors.join('; ') : data.errors)
          : data.message || 'Unknown error'
        alert(`Failed to activate agents: ${errorMessage}`)
        console.error('Agent activation failed:', data)
      }
    })

    socket.on('agents_activation_error', (data: any) => {
      console.error('Agent activation error:', data)
      alert(`Agent activation failed: ${data.error}`)
    })

    // WebSocket listener for agent deactivation
    socket.on('agents_deactivated', (data: any) => {
      console.log('Agents deactivated:', data)
      if (data.success) {
        // agentsActive.value = false // This line is removed
        const agentCount = data.agents_deactivated
        // alert(`Successfully deactivated ${agentCount} AI agents!`)
        loadParticipants() // Refresh participant list to show offline status
      } else {
        alert(`Failed to deactivate agents`)
      }
    })

    // WebSocket listener for agent reset
    socket.on('agents_reset', (data: any) => {
      console.log('Agents reset:', data)
      if (data.success) {
        // agentsActive.value = false // This line is removed
        const agentCount = data.agents_removed
        // alert(`Successfully reset ${agentCount} AI agents!`)
        loadParticipants() // Refresh participant list
      }
    })

    // WebSocket listener for agent activation progress
    socket.on('agent_activation_progress', (data: any) => {
      console.log('Agent activation progress:', data)
      // Show progress in the UI - could add a progress bar later
      const progressMessage = `Activating agents: ${data.activated_count}/${data.total_agents} ready`
      console.log(`🤖 ${progressMessage}`)
      // Refresh participant list to show newly activated agents
      loadParticipants()
    })

    // WebSocket listeners for agent setup completion
    socket.on('agents_setup_complete', (data: any) => {
      console.log('Agent setup completed:', data)
      // Setup completion is logged but activation completion will show the final message
    })

    socket.on('agents_setup_error', (data: any) => {
      console.error('Agent setup error:', data)
      alert(`Agent setup failed: ${data.error}`)
    })
    
    // Socket connection management
    socket.on('timer_update', (data: any) => {
      console.log('🕐 Timer update received via WebSocket:', data)
      
      // Only process timer updates for the current session
      const currentSessionCode = activeSessionCode.value
      if (data.session_code && data.session_code !== currentSessionCode) {
        console.log(`⏱️ Ignoring timer update for different session: ${data.session_code} (current: ${currentSessionCode})`)
        return
      }
      
      timeRemaining.value = data.time_remaining
      lastWebSocketTimerUpdate.value = Date.now() // Record when we got this update
      
      // Update experiment status based on server state
      const oldStatus = experimentStatus.value
      switch (data.experiment_status) {
        case 'running':
          experimentStatus.value = 'running'
          console.log('✅ Experiment status updated to running via WebSocket')
          // Start local timer for smooth countdown
          startLocalTimer()
          break
        case 'paused':
          experimentStatus.value = 'paused'
          console.log('⏸️ Experiment status updated to paused via WebSocket')
          // Stop local timer when paused
          stopLocalTimer()
          break
        case 'completed':
          experimentStatus.value = 'completed'
          console.log('✅ Experiment status updated to completed via WebSocket')
          // Stop local timer when completed
          stopLocalTimer()
          break
        case 'idle':
          experimentStatus.value = 'waiting'
          console.log('⏳ Experiment status updated to waiting via WebSocket')
          // Stop local timer when waiting
          stopLocalTimer()
          break
      }
      
      if (oldStatus !== experimentStatus.value) {
        console.log(`🔄 Experiment status changed from '${oldStatus}' to '${experimentStatus.value}'`)
        console.log(`Button text should now be: ${startButtonText.value}`)
      } else {
        console.log(`⏱️ Timer updated: ${data.time_remaining}s remaining, status: ${data.experiment_status}`)
      }
    })
    
  } catch (error) {
    console.error('WebSocket connection error:', error)
  }
}

const setupPeriodicUpdates = () => {
  // Refresh data every 2 seconds for real-time updates
  const updateInterval = setInterval(() => {
    // Only update data if we have an active session
    if (!isSessionRegistered.value || !currentSessionCode.value) {
      return
    }
    // Only refresh periodically once the experiment has started or is paused
    if (experimentStatus.value === 'running' || experimentStatus.value === 'paused') {
      // Update participants and messages during active phases
      loadParticipants()
      loadMessages()
      
      // Only update trades when experiment is running to avoid unnecessary API calls
      if (experimentStatus.value === 'running') {
        loadTrades()
        // loadSessionMetrics()
      }
    }
  }, 2000) 
  
  // Store interval for cleanup
  return updateInterval
}

// Lifecycle hooks
let updateInterval: ReturnType<typeof setInterval> | null = null
let handleResize: (() => void) | null = null
let handleVisibilityChange: (() => void) | null = null

onMounted(async () => {
  // Start with a clean slate - no session loaded
  console.log('🚀 Researcher dashboard starting with clean slate')
  
  // Clear any existing session state
  isSessionRegistered.value = false
  currentSessionCode.value = ''
  sessionId.value = ''
  experimentConfig.value.sessionId = ''
  
  // Clear all data arrays
  participants.value = []
  pendingOffers.value = []
  completedTrades.value = []
  messages.value = []
  
  // Set default session validation message
  sessionValidationMessage.value = 'Please create a new session or load an existing session to begin.'
  sessionValidationMessageType.value = 'info'
  
  loadAssignmentsFromStorage()
  // Initialize WebSocket connection
  initializeWebSocket()
  // Load available templates (but no session data)
  await loadAvailableTemplates()
  // Setup periodic updates (but they won't load data without a session)
  updateInterval = setupPeriodicUpdates()
  
  // Add click outside handler for dropdown
  document.addEventListener('click', (event) => {
    const target = event.target as HTMLElement
    if (!target.closest('.custom-select-wrapper')) {
      showCommDropdown.value = false
      showNegotiationsDropdown.value = false
      showSimultaneousActionsDropdown.value = false
      showAwarenessDashboardDropdown.value = false
      showRationalesDropdown.value = false
      showParticipantsDropdown.value = false
    }
  })
  
  // Add page visibility change handler to refresh timer when tab becomes visible
  handleVisibilityChange = () => {
    if (!document.hidden) {
      console.log('🔄 Tab became visible, refreshing timer state...')
      // Refresh timer state when tab becomes visible
      const sessionCode = activeSessionCode.value
      if (sessionCode) {
        fetch(`/api/experiment/timer-state?session_code=${encodeURIComponent(sessionCode)}`)
          .then(response => response.json())
          .then(data => {
            console.log('🔄 Refreshed timer state after tab visibility change:', data)
            timeRemaining.value = data.time_remaining
            lastWebSocketTimerUpdate.value = Date.now()
            
            // Update experiment status
            switch (data.experiment_status) {
              case 'running':
                experimentStatus.value = 'running'
                startLocalTimer()
                break
              case 'paused':
                experimentStatus.value = 'paused'
                stopLocalTimer()
                break
              case 'completed':
                experimentStatus.value = 'completed'
                stopLocalTimer()
                break
              case 'idle':
                experimentStatus.value = 'waiting'
                stopLocalTimer()
                break
            }
          })
          .catch(error => console.error('Error refreshing timer state:', error))
      }
    }
  }
  
  document.addEventListener('visibilitychange', handleVisibilityChange)
  
  // Add resize listener to recalculate chart heights
  handleResize = () => {
    // Force recomputation of chart heights when window is resized
    console.log('🔄 Window resized, recalculating chart heights')
    // Re-render charts when window is resized
    if (activeTab.value === 'analysis') {
      renderAllCharts()
    }
  }
  
  window.addEventListener('resize', handleResize)
  
  // Initialize Google Charts
  console.log('✅ Google Charts package loaded')
})

onUnmounted(() => {
  // Clean up timer
  if (timerInterval.value) {
    clearInterval(timerInterval.value)
  }
  
  // Clean up local timer
  stopLocalTimer()
  
  // Clean up update interval
  if (updateInterval) {
    clearInterval(updateInterval)
  }
  
  // Clean up event listeners
  if (handleResize) {
    window.removeEventListener('resize', handleResize)
  }
  if (handleVisibilityChange) {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  }
  
  // Clean up WebSocket connection
  if (socket) {
    socket.disconnect()
  }
})

const checkSessionStatus = async () => {
  try {
    // Only check the specific session code that the user has entered
    const sessionCode = experimentConfig.value.sessionId
    
    if (!sessionCode || sessionCode.trim() === '') {
      // No session code entered
      isSessionRegistered.value = false
      currentSessionCode.value = ''
      sessionValidationMessage.value = 'Please create a new session or load an existing session to begin.'
      sessionValidationMessageType.value = 'info'
      console.log('❌ No session code entered')
      return
    }
    
    const response = await fetch('/api/sessions/check', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_code: sessionCode
      })
    })

    const result = await response.json()

    if (response.ok && result.success && result.exists) {
      // Session exists but don't automatically load it
      // User needs to explicitly load it
      sessionValidationMessage.value = `Session "${sessionCode}" exists. Please use "Load Session" to load it.`
      sessionValidationMessageType.value = 'info'
      console.log(`ℹ️ Session "${sessionCode}" exists but not loaded`)
    } else {
      // Session does not exist
      isSessionRegistered.value = false
      currentSessionCode.value = ''
      sessionValidationMessage.value = `Session "${sessionCode}" does not exist. Please create it first.`
      sessionValidationMessageType.value = 'error'
      console.log(`❌ Session "${sessionCode}" does not exist`)
    }
  } catch (error: any) {
    isSessionRegistered.value = false
    currentSessionCode.value = ''
    sessionValidationMessage.value = 'Unable to check session status. Please create a new session or load an existing session.'
    sessionValidationMessageType.value = 'error'
    console.error('❌ Error checking session status:', error)
  }
}

// New: Participant management state
const editForm = ref({
  participantCode: '',
  participantType: '',
  specialty: '',
  tag: '',
  persona: '',
  mbti_type: ''
})
const originalParticipantCode = ref('') // Track the original code
const showEditModal = ref(false)
const isSavingEdit = ref(false)

// Grouping functionality
const showGroupingModal = ref(false)
const groups = ref<Record<string, string[]>>({}) // groupName -> participantIds[]
const newGroupName = ref('')
const selectedGroup = ref('')
const selectedParticipants = ref<string[]>([])

// Grouping functions
const createGroup = () => {
  if (newGroupName.value.trim() && !groups.value[newGroupName.value.trim()]) {
    groups.value[newGroupName.value.trim()] = []
    newGroupName.value = ''
  }
}

const deleteGroup = (groupName: string) => {
  if (confirm(`Delete group "${groupName}"?`)) {
    delete groups.value[groupName]
    if (selectedGroup.value === groupName) {
      selectedGroup.value = ''
      selectedParticipants.value = []
    }
  }
}

const addParticipantsToGroup = () => {
  if (selectedGroup.value && selectedParticipants.value.length > 0) {
    // Remove participants from other groups first
    Object.keys(groups.value).forEach(groupName => {
      groups.value[groupName] = groups.value[groupName].filter(id => !selectedParticipants.value.includes(id))
    })
    
    // Add to selected group
    const existingParticipants = groups.value[selectedGroup.value] || []
    const allParticipants = [...existingParticipants, ...selectedParticipants.value]
    groups.value[selectedGroup.value] = allParticipants.filter((id, index) => allParticipants.indexOf(id) === index)
    selectedParticipants.value = []
  }
}

const removeParticipantFromGroup = (groupName: string, participantId: string) => {
  groups.value[groupName] = groups.value[groupName].filter(id => id !== participantId)
}

const closeGroupingModal = () => {
  showGroupingModal.value = false
  newGroupName.value = ''
  selectedGroup.value = ''
  selectedParticipants.value = []
}

// Get group name for a participant
const getParticipantGroup = (participantId: string) => {
  for (const [groupName, participantIds] of Object.entries(groups.value)) {
    if (participantIds.includes(participantId)) {
      return groupName
    }
  }
  return null
}

const onEditParticipant = (participant: Participant) => {
  const mbtiType = participant.mbti_type || 'INTJ' // Default to INTJ if no MBTI type
  const defaultPersona = generateDefaultPersona(mbtiType, getDisplayName(participant.id))
  
  editForm.value = {
    participantCode: getDisplayName(participant.id),
    participantType: participant.type,
    specialty: participant.specialty,
    tag: participant.tag || '',
    persona: participant.persona || defaultPersona,
    mbti_type: mbtiType
  }
  originalParticipantCode.value = participant.id // Store the original code
  showEditModal.value = true
}

const updatePersonaFromMBTI = () => {
  if (editForm.value.mbti_type) {
    const defaultPersona = generateDefaultPersona(editForm.value.mbti_type, editForm.value.participantCode)
    editForm.value.persona = defaultPersona
  }
}

const saveEditParticipant = async () => {
  isSavingEdit.value = true
  try {
    // Find the original participant using the stored original code
    const originalParticipant = participants.value.find(p => p.id === originalParticipantCode.value)
    if (!originalParticipant) {
      alert('Original participant not found')
      return
    }

    // Check if participant code has changed
    const codeChanged = originalParticipantCode.value !== editForm.value.participantCode

    if (codeChanged) {
      // If code changed, we need to create a new participant and delete the old one
      // First, check if the new code already exists
      const existingParticipant = participants.value.find(p => p.id === editForm.value.participantCode)
      if (existingParticipant) {
        alert('A participant with this code already exists')
        return
      }

      // Create new participant with the new code
      if (originalParticipant.type === 'ai' || originalParticipant.type === 'ai_agent') {
        // Register new AI agent
        const res = await fetch('/api/agents/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            participant_code: editForm.value.participantCode,
            agent_type: 'basic_agent', // Default agent type
            session_code: activeSessionCode.value,
            specialty_shape: editForm.value.specialty || undefined,
            tag: editForm.value.tag || undefined,
            persona: editForm.value.persona || undefined,
            mbti_type: editForm.value.mbti_type || undefined
          })
        })
        const result = await res.json()
        if (!res.ok || !result.success) {
          throw new Error(result.error || 'Failed to create new agent')
        }
      } else {
        // Register new human participant
        const res = await fetch('/api/participants/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            participant_code: editForm.value.participantCode,
            session_code: activeSessionCode.value,
            specialty_shape: editForm.value.specialty || undefined,
            tag: editForm.value.tag || undefined,
            persona: editForm.value.persona || undefined,
            mbti_type: editForm.value.mbti_type || undefined
          })
        })
        const result = await res.json()
        if (!res.ok || !result.success) {
          throw new Error(result.error || 'Failed to create new participant')
        }
      }

      // Delete the old participant
      const deleteRes = await fetch('/api/participants/delete', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          participant_code: originalParticipantCode.value,
          session_code: activeSessionCode.value
        })
      })
      const deleteResult = await deleteRes.json()
      if (!deleteRes.ok || !deleteResult.success) {
        console.warn('Failed to delete old participant:', deleteResult.error)
      }

      alert('Participant code changed successfully!')
    } else {
      // If code hasn't changed, just update the other fields
      const res = await fetch('/api/participants/update', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          participant_code: editForm.value.participantCode,
          session_code: activeSessionCode.value,
          update_data: {
            specialty_shape: editForm.value.specialty,
            tag: editForm.value.tag,
            persona: editForm.value.persona,
            mbti_type: editForm.value.mbti_type
          }
        })
      })
      const result = await res.json()
      if (!res.ok || !result.success) {
        throw new Error(result.error || 'Failed to update participant')
      }
      alert('Participant updated successfully!')
    }

    showEditModal.value = false
    await loadParticipants()
  } catch (e:any) {
    alert('Error updating participant: ' + e.message)
  } finally {
    isSavingEdit.value = false
  }
}

const closeEditModal = () => {
  showEditModal.value = false
}

// Session management methods
const closeCreateModal = () => {
  showCreateModal.value = false
  createSessionForm.value = {
    sessionType: 'new',
    sessionId: '',
    sessionDuration: 15,
    saveAsTemplate: false,
    templateName: '',
    selectedTemplate: ''
  }
}

const closeLoadModal = () => {
  showLoadModal.value = false
  loadSessionForm.value = {
    sessionId: ''
  }
}

const createSession = async () => {
  if (!createSessionForm.value.sessionId.trim()) return
  
  isCreatingSession.value = true
  
  try {
    // Load template parameters if template mode is selected
    if (createSessionForm.value.sessionType === 'template') {
      if (!createSessionForm.value.selectedTemplate.trim()) {
        alert('Please select a template')
        return
      }
      
      const templateResponse = await fetch(`/api/session-templates/${createSessionForm.value.selectedTemplate.trim()}/load?researcher_id=researcher`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      })
      
      const templateResult = await templateResponse.json()
      
      if (templateResponse.ok && templateResult.success) {
        
        // Update the experiment config with the loaded template
        experimentConfig.value = { ...experimentConfig.value, ...templateResult.config }
        
        // Update interaction config if present
        if (templateResult.config.communicationLevel) {
          interactionConfig.value.communicationLevel = templateResult.config.communicationLevel
        }
        if (templateResult.config.awarenessDashboard) {
          interactionConfig.value.awarenessDashboard = templateResult.config.awarenessDashboard
        }
        
      } else {
        alert(`Failed to load template: ${templateResult.error ? String(templateResult.error) : 'Unknown error'}`)
        return
      }
    }
    
    // Update experiment config with session ID and duration
    experimentConfig.value.sessionId = createSessionForm.value.sessionId.trim()
    experimentConfig.value.sessionDuration = createSessionForm.value.sessionDuration
    
    // Register the session
    const response = await fetch('/api/sessions/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_code: createSessionForm.value.sessionId.trim(),
        researcher_id: 'researcher',
        experiment_type: selectedExperimentType.value,
        experiment_config: experimentConfig.value
      })
    })

    let result
    try {
      result = await response.json()
    } catch (jsonError) {
      console.error('Failed to parse JSON response:', jsonError)
      const responseText = await response.text()
      console.error('Response text:', responseText)
      throw new Error(`Server returned invalid JSON. Status: ${response.status}, Response: ${responseText}`)
    }

    if (response.ok && result.success) {
      // Update session validation state
      isSessionRegistered.value = true
      currentSessionCode.value = createSessionForm.value.sessionId.trim()
      sessionValidationMessage.value = `Session "${createSessionForm.value.sessionId.trim()}" is registered and ready for participants`
      sessionValidationMessageType.value = 'info'
      
      // Save current interaction variables to the new session
      const sessionCode = createSessionForm.value.sessionId.trim()
      const currentInteractionConfig = {
        ...experimentConfig.value,
        session_code: sessionCode,
        communicationLevel: interactionConfig.value.communicationLevel,
        awarenessDashboard: interactionConfig.value.awarenessDashboard
      }
      
      console.log('🔄 Saving interaction variables to new session:', sessionCode, {
        communicationLevel: interactionConfig.value.communicationLevel,
        awarenessDashboard: interactionConfig.value.awarenessDashboard
      })
      
      const configResponse = await fetch('/api/experiment/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(currentInteractionConfig)
      })
      
      if (configResponse.ok) {
        console.log('✅ Interaction variables saved to new session')
      } else {
        console.error('❌ Failed to save interaction variables to new session')
      }
      
      // Save as template if requested
      if (createSessionForm.value.saveAsTemplate) {
        const templateName = createSessionForm.value.templateName.trim() || createSessionForm.value.sessionId.trim()
        await saveSessionParameters(templateName)
      }
      
      // Close modal and refresh data
      closeCreateModal()
      
      // Small delay to ensure configuration is saved before registering
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // Register for the new session
      registerForSession()
      
      // Switch to setup tab and show all subtabs
      activeTab.value = 'setup'
      setupTabs.value.experimentSelection = true
      setupTabs.value.parameters = true
      setupTabs.value.interactionVariables = true
      setupTabs.value.participantRegistration = true
      activeSetupTab.value = 'experimentSelection'
      scrollToTab('experimentSelection')
      
      console.log('Session operation completed:', result.session)
      
      // Check if session was created or updated
      if (result.message && result.message.includes('updated')) {
        alert(`Session "${createSessionForm.value.sessionId.trim()}" already exists and has been updated with new parameters. You can now use this session.`)
      } else {
        alert(`Session "${createSessionForm.value.sessionId.trim()}" created successfully!`)
      }
    } else {
      alert(result.error ? String(result.error) : 'Failed to create session')
    }
  } catch (error: any) {
    console.error('Error creating session:', error)
    alert(`Failed to create session: ${error.message}`)
  } finally {
    isCreatingSession.value = false
  }
}

const loadSession = async () => {
  if (!loadSessionForm.value.sessionId.trim()) {
    alert('Please enter a Session ID first')
    return
  }
  
  isLoadingSession.value = true
  
  try {
    // Set the session ID
    experimentConfig.value.sessionId = loadSessionForm.value.sessionId.trim()
    
    // Check if session exists
    const checkResponse = await fetch('/api/sessions/check', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_code: loadSessionForm.value.sessionId.trim()
      })
    })

    const checkResult = await checkResponse.json()

    if (checkResponse.ok && checkResult.success && checkResult.exists) {
      // Session exists and is registered
      isSessionRegistered.value = true
      currentSessionCode.value = loadSessionForm.value.sessionId.trim()
      sessionValidationMessage.value = `Session "${loadSessionForm.value.sessionId.trim()}" is registered and ready for participants`
      sessionValidationMessageType.value = 'info'
      
      // Close modal and refresh data
      closeLoadModal()
      
      // Register for the loaded session
      registerForSession()
      
      // Show all subtabs since session is already set up
      setupTabs.value.experimentSelection = true
      setupTabs.value.parameters = true
      setupTabs.value.interactionVariables = true
      setupTabs.value.participantRegistration = true
      activeSetupTab.value = 'experimentSelection'
      scrollToTab('experimentSelection')
      
      console.log(`Session "${loadSessionForm.value.sessionId.trim()}" loaded successfully`)
    } else {
      alert(`Session "${loadSessionForm.value.sessionId.trim()}" not found. Please create it first.`)
    }
  } catch (error: any) {
    console.error('Error loading session:', error)
    alert(`Failed to load session: ${error.message}`)
  } finally {
    isLoadingSession.value = false
  }
}



const loadAvailableTemplates = async () => {
  try {
    const response = await fetch('/api/session-templates', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    
    const result = await response.json()
    
    if (response.ok && result.success) {
      // Use all templates - they are identified by session_id
      const templates = result.templates || []
      availableTemplates.value = templates
      console.log('✅ Loaded templates:', templates.length, 'templates')
      templates.forEach((template: any, index: number) => {
        console.log(`  Template ${index + 1}: ${template.session_id} (ID: ${template.template_id})`)
      })
    } else {
      console.warn('❌ Failed to load templates:', result.error)
      availableTemplates.value = []
    }
  } catch (error: any) {
    console.error('Error loading templates:', error)
    availableTemplates.value = []
  }
}

const saveSessionParameters = async (templateName: string) => {
  try {
    console.log('🔄 Saving template with name:', templateName)
    
    // Prepare the template configuration to save (no need to update backend config first)
    const templateConfig = {
      ...experimentConfig.value,
      communicationLevel: interactionConfig.value.communicationLevel,
      awarenessDashboard: interactionConfig.value.awarenessDashboard
    }
    
    // Then save as template
    const requestBody = {
      session_id: templateName,
      researcher_id: 'researcher',
      template_config: templateConfig
    }
    console.log('📤 Sending template save request:', requestBody)
    
    const response = await fetch('/api/session-templates', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody)
    })
    
    const result = await response.json()
    
    if (response.ok && result.success) {
      console.log('✅ Session parameters saved successfully:', result.message)
      // Refresh the templates list
      await loadAvailableTemplates()
    } else {
      console.warn('❌ Failed to save session parameters:', result.error)
    }
  } catch (error: any) {
    console.error('Error saving session parameters:', error)
  }
}

const isDefaultTemplate = (sessionId: string) => {
  const template = availableTemplates.value.find(t => t.session_id === sessionId)
  return template?.is_default === true
}

const deleteSelectedTemplate = async () => {
  const selectedTemplate = createSessionForm.value.selectedTemplate
  if (!selectedTemplate) return
  
  // Check if it's a default template
  if (isDefaultTemplate(selectedTemplate)) {
    alert('Cannot delete default templates')
    return
  }
  
  if (!confirm(`Are you sure you want to delete template "${selectedTemplate}"? This action cannot be undone.`)) {
    return
  }
  
  try {
    console.log('🗑️ Deleting template:', selectedTemplate)
    
    const response = await fetch(`/api/session-templates/${selectedTemplate}?researcher_id=researcher`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    
    const result = await response.json()
    
    if (response.ok && result.success) {
      console.log('✅ Template deleted successfully:', result.message)
      // Clear the selected template
      createSessionForm.value.selectedTemplate = ''
      // Refresh the templates list
      await loadAvailableTemplates()
    } else {
      console.error('❌ Failed to delete template:', result.error)
      alert(`Failed to delete template: ${result.error}`)
    }
  } catch (error: any) {
    console.error('Error deleting template:', error)
    alert(`Error deleting template: ${error.message}`)
  }
}

// Experiment selection methods
const onExperimentTypeChange = async () => {
  if (!selectedExperimentType.value) {
    return
  }
  
  const selectedExperiment = allAvailableExperiments.value.find(exp => exp.id === selectedExperimentType.value)
  if (!selectedExperiment) {
    return
  }
  
  // Apply the default configuration for the selected experiment
  experimentConfig.value = {
    ...experimentConfig.value,
    ...selectedExperiment.defaultConfig
  }
  
  // Set default values for experiment-specific parameters
  selectedExperiment.specificParams.forEach(param => {
    if (experimentConfig.value[param.key as keyof ExperimentConfig] === undefined) {
      ;(experimentConfig.value as any)[param.key] = param.defaultValue
    }
  })
  
  // Initialize interface configuration based on experiment
  if (selectedExperiment.interfaceConfig) {
    currentInterfaceConfig.value = selectedExperiment.interfaceConfig
    
    // Set experiment interface configuration in experiment config
    experimentConfig.value.experimentInterfaceConfig = selectedExperiment.interfaceConfig
    
    // Initialize awareness display options based on experiment config
    if (selectedExperiment.interfaceConfig.awarenessDashboard) {
      console.log('Updating awareness display options for experiment:', selectedExperiment.id)
      console.log('Interface config awareness dashboard:', selectedExperiment.interfaceConfig.awarenessDashboard)
      
      awarenessDisplayOptions.value = {
        money: selectedExperiment.interfaceConfig.awarenessDashboard.showMoney,
        production: selectedExperiment.interfaceConfig.awarenessDashboard.showProductionCount,
        orders: selectedExperiment.interfaceConfig.awarenessDashboard.showOrderProgress
      }
      
      console.log('Updated awareness display options:', awarenessDisplayOptions.value)
      
      // Force a re-render of the awareness dashboard
      await nextTick()
      console.log('Awareness dashboard should now be updated')
    }
  } else {
    currentInterfaceConfig.value = null
    experimentConfig.value.experimentInterfaceConfig = {}
  }
  
  // Update the backend if we have an active session

  console.log('🔧 Checking session status for experiment type update:', {
    isSessionRegistered: isSessionRegistered.value,
    currentSessionCode: currentSessionCode.value,
    selectedExperimentType: selectedExperimentType.value
  })
  
  if (isSessionRegistered.value && currentSessionCode.value) {
    console.log('🔧 Session is registered, updating experiment type...')
    updateExperimentConfig()
    updateSessionExperimentType()
  } else {
    console.log('🔧 Session not registered or no session code, skipping experiment type update')
  }
  
  // Stay on experiment selection tab - user needs to manually proceed to parameters
  console.log('Experiment type changed to:', selectedExperimentType.value)
  console.log('Updated config:', experimentConfig.value)
  console.log('Interface config:', currentInterfaceConfig.value)
  
  // Notify participants to reconfigure their interfaces
  if (socket && activeSessionCode.value) {
    socket.emit('experiment_type_changed', {
      session_code: activeSessionCode.value,
      experiment_type: selectedExperimentType.value
    })
    console.log('🔧 Notified participants of experiment type change:', selectedExperimentType.value)
  }
}

// Test functions for debugging awareness dashboard
const testDayTraderAwareness = async () => {
  console.log('Testing DayTrader awareness configuration...')
  const daytraderExperiment = allAvailableExperiments.value.find(exp => exp.id === 'daytrader')
  if (daytraderExperiment && daytraderExperiment.interfaceConfig?.awarenessDashboard) {
    awarenessDisplayOptions.value = {
      money: daytraderExperiment.interfaceConfig.awarenessDashboard.showMoney,
      production: daytraderExperiment.interfaceConfig.awarenessDashboard.showProductionCount,
      orders: daytraderExperiment.interfaceConfig.awarenessDashboard.showOrderProgress
    }
    console.log('Applied DayTrader awareness config:', awarenessDisplayOptions.value)
    
    // Also update the current interface config
    currentInterfaceConfig.value = daytraderExperiment.interfaceConfig
    console.log('Updated current interface config:', currentInterfaceConfig.value)
    
    // Force a re-render
    await nextTick()
    console.log('Awareness dashboard should now be updated with DayTrader config')
  }
}

const testShapeFactoryAwareness = () => {
  console.log('Testing Shape Factory awareness configuration...')
  const shapefactoryExperiment = allAvailableExperiments.value.find(exp => exp.id === 'shapefactory')
  if (shapefactoryExperiment && shapefactoryExperiment.interfaceConfig?.awarenessDashboard) {
    awarenessDisplayOptions.value = {
      money: shapefactoryExperiment.interfaceConfig.awarenessDashboard.showMoney,
      production: shapefactoryExperiment.interfaceConfig.awarenessDashboard.showProductionCount,
      orders: shapefactoryExperiment.interfaceConfig.awarenessDashboard.showOrderProgress
    }
    console.log('Applied Shape Factory awareness config:', awarenessDisplayOptions.value)
  }
}

const forceRefreshAwareness = async () => {
  console.log('Force refreshing awareness dashboard...')
  console.log('Current selected experiment type:', selectedExperimentType.value)
  console.log('Current awareness display options:', awarenessDisplayOptions.value)
  console.log('Current interface config:', currentExperimentInterfaceConfig.value)
  
  // Force a re-render by updating the key
  await nextTick()
  console.log('Awareness dashboard force refreshed')
}

const getCurrentExperimentDescription = () => {
  if (!selectedExperimentType.value) {
    return ''
  }
  
  const selectedExperiment = allAvailableExperiments.value.find(exp => exp.id === selectedExperimentType.value)
  return selectedExperiment?.description || ''
}

const getFormattedExperimentDescription = (description?: string) => {
  const desc = description || getCurrentExperimentDescription()
  if (!desc) return ''
  
  // Convert markdown-like formatting to HTML
  return desc
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold text
    .replace(/\n\n/g, '</p><p>') // Double line breaks become paragraph breaks
    .replace(/^(.*)$/gm, '<p>$1</p>') // Wrap each line in paragraph tags
    .replace(/<p><\/p>/g, '') // Remove empty paragraphs
}

const toggleExperimentAndPreview = (experimentId: string) => {
  // Toggle expansion
  if (expandedExperiments.value.has(experimentId)) {
    expandedExperiments.value.delete(experimentId)
    // If this was the previewed experiment and we're collapsing it, clear preview
    if (previewedExperiment.value === experimentId) {
      previewedExperiment.value = null
    }
  } else {
    expandedExperiments.value.add(experimentId)
    // Set as previewed when expanding
    previewedExperiment.value = experimentId
    
    // If this is a different experiment than currently selected, allow changing
    if (selectedExperimentType.value && selectedExperimentType.value !== experimentId) {
      console.log('🔧 User is previewing a different experiment, allowing change from', selectedExperimentType.value, 'to', experimentId)
    }
  }
}

const confirmExperimentSelection = () => {
  if (previewedExperiment.value) {
    selectedExperimentType.value = previewedExperiment.value
    onExperimentTypeChange()
    // Auto-switch to parameters tab
    activeSetupTab.value = 'parameters'
  }
}

const getPreviewedExperiment = () => {
  if (!previewedExperiment.value) {
    return null
  }
  
  return allAvailableExperiments.value.find(exp => exp.id === previewedExperiment.value)
}

const toggleExperimentExpansion = (experimentId: string) => {
  if (expandedExperiments.value.has(experimentId)) {
    expandedExperiments.value.delete(experimentId)
  } else {
    expandedExperiments.value.add(experimentId)
  }
}

const isExperimentExpanded = (experimentId: string) => {
  return expandedExperiments.value.has(experimentId)
}

const getCurrentExperimentName = () => {
  if (!selectedExperimentType.value) {
    return ''
  }
  
  const selectedExperiment = allAvailableExperiments.value.find(exp => exp.id === selectedExperimentType.value)
  return selectedExperiment?.name || ''
}

const getCurrentExperimentSpecificParams = () => {
  if (!selectedExperimentType.value) {
    return []
  }
  
  const selectedExperiment = allAvailableExperiments.value.find(exp => exp.id === selectedExperimentType.value)
  return selectedExperiment?.specificParams || []
}

// Template loading methods


const loadTemplateInModal = async (templateName: string) => {
  if (!confirm(`Are you sure you want to load template "${templateName}"? This will replace your current configuration.`)) {
    return
  }
  
  try {
    console.log('🔄 Loading template in modal:', templateName)
    
    const response = await fetch(`/api/session-templates/${templateName}/load?researcher_id=researcher`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    
    const result = await response.json()
    
    if (response.ok && result.success) {
      console.log('✅ Template loaded successfully:', result.config)
      
      // Apply the loaded configuration to experiment config
      if (result.config) {
        // Apply experiment configuration
        experimentConfig.value = { ...experimentConfig.value, ...result.config }
        
        // Update interaction config if present
        if (result.config.communicationLevel) {
          interactionConfig.value.communicationLevel = result.config.communicationLevel
        }
        if (result.config.awarenessDashboard) {
          interactionConfig.value.awarenessDashboard = result.config.awarenessDashboard
        }
        
        // Only update the backend if there's an active session
        if (isSessionRegistered.value && activeSessionCode.value) {
          await updateExperimentConfig()
        }
        
        console.log('✅ Template configuration applied successfully')
        alert(`✅ Template "${templateName}" loaded and applied successfully!`)
        
        // Close the modal after loading
        closeSaveTemplateModal()
      }
    } else {
      console.error('❌ Failed to load template:', result.error)
      alert(`Failed to load template: ${result.error ? String(result.error) : 'Unknown error'}`)
    }
  } catch (error: any) {
    console.error('Error loading template:', error)
    alert(`Error loading template: ${error.message}`)
  }
}

const deleteTemplateInModal = async (templateName: string) => {
  if (!confirm(`Are you sure you want to delete template "${templateName}"? This action cannot be undone.`)) {
    return
  }
  
  try {
    console.log('🗑️ Deleting template in modal:', templateName)
    
    const response = await fetch(`/api/session-templates/${templateName}?researcher_id=researcher`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    
    const result = await response.json()
    
    if (response.ok && result.success) {
      console.log('✅ Template deleted successfully:', result.message)
      alert(`✅ Template "${templateName}" deleted successfully!`)
      // Refresh the templates list
      await loadAvailableTemplates()
    } else {
      console.error('❌ Failed to delete template:', result.error)
      alert(`Failed to delete template: ${result.error}`)
    }
  } catch (error: any) {
    console.error('Error deleting template:', error)
    alert(`Error deleting template: ${error.message}`)
  }
}

const loadTemplateFromInput = async () => {
  if (!templateLoadInput.value.trim()) {
    alert('Please enter a template name')
    return
  }
  
  if (!confirm(`Are you sure you want to load template "${templateLoadInput.value.trim()}"? This will replace your current configuration.`)) {
    return
  }
  
  try {
    console.log('🔄 Loading template:', templateLoadInput.value)
    
    const response = await fetch(`/api/session-templates/${templateLoadInput.value.trim()}/load?researcher_id=researcher`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    
    const result = await response.json()
    
    if (response.ok && result.success) {
      console.log('✅ Template loaded successfully:', result.config)
      
      // Apply the loaded configuration to experiment config
      if (result.config) {
        // Apply experiment configuration
        experimentConfig.value = { ...experimentConfig.value, ...result.config }
        
        // Update interaction config if present
        if (result.config.communicationLevel) {
          interactionConfig.value.communicationLevel = result.config.communicationLevel
        }
        if (result.config.awarenessDashboard) {
          interactionConfig.value.awarenessDashboard = result.config.awarenessDashboard
        }
        
        // Only update the backend if there's an active session
        if (isSessionRegistered.value && activeSessionCode.value) {
          await updateExperimentConfig()
        }
        
        console.log('✅ Template configuration applied successfully')
        alert(`✅ Template "${templateLoadInput.value}" loaded and applied successfully!`)
      }
      
      // Clear the input
      templateLoadInput.value = ''
    } else {
      console.error('❌ Failed to load template:', result.error)
      alert(`Failed to load template: ${result.error ? String(result.error) : 'Unknown error'}`)
    }
  } catch (error: any) {
    console.error('Error loading template:', error)
    alert(`Error loading template: ${error.message}`)
  }
}

// Upload config file methods
const triggerFileUpload = () => {
  fileInputRef.value?.click()
}

const validateConfigFile = (configData: any): { isValid: boolean, message: string } => {
  try {
    // Basic structure validation
    if (!configData || typeof configData !== 'object') {
      return { isValid: false, message: 'Invalid JSON structure' }
    }

    // Check if this is the new format with experimentTemplate and interfaceElements
    if (configData.experimentTemplate && configData.interfaceElements) {
      return validateNewFormat(configData)
    }
    
    // Legacy format validation (for backward compatibility)
    return validateLegacyFormat(configData)
  } catch (error) {
    return { isValid: false, message: `Validation error: ${error}` }
  }
}
const validateNewFormat = (configData: any): { isValid: boolean, message: string } => {
  // Validate experimentTemplate section
  const template = configData.experimentTemplate
  if (!template) {
    return { isValid: false, message: 'Missing experimentTemplate section' }
  }

  // Check required experimentTemplate fields
  const requiredTemplateFields = ['id', 'name', 'description', 'defaultConfig', 'specificParams']
  const missingTemplateFields = requiredTemplateFields.filter(field => !template[field])
  
  if (missingTemplateFields.length > 0) {
    return { isValid: false, message: `experimentTemplate missing fields: ${missingTemplateFields.join(', ')}` }
  }

  // Validate defaultConfig
  if (!template.defaultConfig || typeof template.defaultConfig !== 'object') {
    return { isValid: false, message: 'experimentTemplate.defaultConfig must be an object' }
  }

  // Validate specificParams
  if (!Array.isArray(template.specificParams)) {
    return { isValid: false, message: 'experimentTemplate.specificParams must be an array' }
  }

  // Validate each specific parameter
  for (let i = 0; i < template.specificParams.length; i++) {
    const param = template.specificParams[i]
    const requiredParamFields = ['key', 'label', 'type', 'defaultValue']
    const missingParamFields = requiredParamFields.filter(field => !param[field])
    
    if (missingParamFields.length > 0) {
      return { isValid: false, message: `specificParams[${i}] missing fields: ${missingParamFields.join(', ')}` }
    }

    // Validate options for select type
    if (param.type === 'select' && (!param.options || !Array.isArray(param.options))) {
      return { isValid: false, message: `specificParams[${i}] of type 'select' must have options array` }
    }

    // Validate min/max for number type
    if (param.type === 'number') {
      if (param.min === undefined || param.max === undefined || param.step === undefined) {
        return { isValid: false, message: `specificParams[${i}] of type 'number' must have min, max, and step` }
      }
    }
  }

  // Validate interfaceElements section
  const interfaceElements = configData.interfaceElements
  if (!interfaceElements) {
    return { isValid: false, message: 'Missing interfaceElements section' }
  }

  // Check for required interface sections
  const requiredInterfaceSections = ['Type_Shape', 'Participant', 'Factory', 'Task']
  const missingInterfaceSections = requiredInterfaceSections.filter(section => !interfaceElements[section])
  
  if (missingInterfaceSections.length > 0) {
    return { isValid: false, message: `interfaceElements missing sections: ${missingInterfaceSections.join(', ')}` }
  }

  // Validate Type_Shape section
  if (interfaceElements.Type_Shape) {
    const shapeFields = ['Name', 'Color', 'Cost', 'SpecialtyCost', 'TimeCost', 'Status']
    const missingShapeFields = shapeFields.filter(field => !interfaceElements.Type_Shape[field])
    
    if (missingShapeFields.length > 0) {
      return { isValid: false, message: `Type_Shape missing fields: ${missingShapeFields.join(', ')}` }
    }
  }

  // Validate Participant section
  if (interfaceElements.Participant) {
    const participantFields = ['Name', 'Type', 'Wealth', 'SpecialtyShape', 'Inventory', 'Order']
    const missingParticipantFields = participantFields.filter(field => !interfaceElements.Participant[field])
    
    if (missingParticipantFields.length > 0) {
      return { isValid: false, message: `Participant missing fields: ${missingParticipantFields.join(', ')}` }
    }
  }

  // Validate Factory section
  if (interfaceElements.Factory !== true && interfaceElements.Factory !== false) {
    return { isValid: false, message: 'Factory must be true or false' }
  }

  // Validate Task section
  if (interfaceElements.Task !== true && interfaceElements.Task !== false) {
    return { isValid: false, message: 'Task must be true or false' }
  }

  // Validate optional sections
  if (interfaceElements['My Status']) {
    const myStatusFields = ['Participant.Wealth', 'Participant.Inventory']
    const missingMyStatusFields = myStatusFields.filter(field => !interfaceElements['My Status'][field])
    
    if (missingMyStatusFields.length > 0) {
      return { isValid: false, message: `My Status missing fields: ${missingMyStatusFields.join(', ')}` }
    }
  }

  if (interfaceElements['My Task']) {
    const myTaskFields = ['Participant.Orders']
    const missingMyTaskFields = myTaskFields.filter(field => !interfaceElements['My Task'][field])
    
    if (missingMyTaskFields.length > 0) {
      return { isValid: false, message: `My Task missing fields: ${missingMyTaskFields.join(', ')}` }
    }
  }


  if (interfaceElements.Trade) {
    const tradeFields = ['TradeType']
    const missingTradeFields = tradeFields.filter(field => !interfaceElements.Trade[field])
    
    if (missingTradeFields.length > 0) {
      return { isValid: false, message: `Trade missing fields: ${missingTradeFields.join(', ')}` }
    }
  }

  return { isValid: true, message: 'Configuration file is valid' }
}

const validateLegacyFormat = (configData: any): { isValid: boolean, message: string } => {
  // Check for required top-level sections
  const requiredSections = ['Type_Shape', 'Participant', 'Factory', 'Task']
  const missingSections = requiredSections.filter(section => !configData[section])
  
  if (missingSections.length > 0) {
    return { isValid: false, message: `Missing required sections: ${missingSections.join(', ')}` }
  }

  // Validate Type_Shape section
  if (configData.Type_Shape) {
    const shapeFields = ['Name', 'Color', 'Cost', 'SpecialtyCost', 'TimeCost', 'Status']
    const missingShapeFields = shapeFields.filter(field => !configData.Type_Shape[field])
    
    if (missingShapeFields.length > 0) {
      return { isValid: false, message: `Type_Shape missing fields: ${missingShapeFields.join(', ')}` }
    }
  }

  // Validate Participant section
  if (configData.Participant) {
    const participantFields = ['Name', 'Type', 'Wealth', 'SpecialtyShape', 'Inventory', 'Order']
    const missingParticipantFields = participantFields.filter(field => !configData.Participant[field])
    
    if (missingParticipantFields.length > 0) {
      return { isValid: false, message: `Participant missing fields: ${missingParticipantFields.join(', ')}` }
    }
  }

  // Validate Factory section
  if (configData.Factory !== true && configData.Factory !== false) {
    return { isValid: false, message: 'Factory must be true or false' }
  }

  // Validate Task section
  if (configData.Task !== true && configData.Task !== false) {
    return { isValid: false, message: 'Task must be true or false' }
  }

  // Validate optional sections
  if (configData['My Status']) {
    const myStatusFields = ['Participant.Wealth', 'Participant.Inventory']
    const missingMyStatusFields = myStatusFields.filter(field => !configData['My Status'][field])
    
    if (missingMyStatusFields.length > 0) {
      return { isValid: false, message: `My Status missing fields: ${missingMyStatusFields.join(', ')}` }
    }
  }

  if (configData['My Task']) {
    const myTaskFields = ['Participant.Orders']
    const missingMyTaskFields = myTaskFields.filter(field => !configData['My Task'][field])
    
    if (missingMyTaskFields.length > 0) {
      return { isValid: false, message: `My Task missing fields: ${missingMyTaskFields.join(', ')}` }
    }
  }


  if (configData.Trade) {
    const tradeFields = ['TradeType']
    const missingTradeFields = tradeFields.filter(field => !configData.Trade[field])
    
    if (missingTradeFields.length > 0) {
      return { isValid: false, message: `Trade missing fields: ${missingTradeFields.join(', ')}` }
    }
  }

  return { isValid: true, message: 'Configuration file is valid (legacy format)' }
}

const handleFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  
  if (!file) {
    return
  }

  isUploadingConfig.value = true
  configValidationStatus.value = null
  customExperimentName.value = ''
  customExperimentAdded.value = false

  try {
    const text = await file.text()
    const fileName = file.name.toLowerCase()
    
    // Check if this is an ECL file (YAML)
    if (fileName.endsWith('.yaml') || fileName.endsWith('.yml')) {
      await handleECLFileUpload(text, file.name)
    } else {
      // Handle JSON configuration file
      const configData = JSON.parse(text)
      
      // Validate the configuration
      const validation = validateConfigFile(configData)
      
      if (validation.isValid) {
        uploadedConfigData.value = configData
        
        // Set the experiment name placeholder from the config file
        if (configData.experimentTemplate?.name) {
          experimentNamePlaceholder.value = configData.experimentTemplate.name
          customExperimentName.value = configData.experimentTemplate.name
        } else {
          experimentNamePlaceholder.value = 'Enter experiment name'
          customExperimentName.value = ''
        }
        
        // Show the modal for experiment name input
        showCustomExperimentModal.value = true
        
        console.log('✅ Config file validation passed')
      } else {
        configValidationStatus.value = {
          type: 'error',
          message: `Validation Failed: ${validation.message}`
        }
        console.error('❌ Config file validation failed:', validation.message)
      }
    }
  } catch (error: any) {
    configValidationStatus.value = {
      type: 'error',
      message: `Error reading file: ${error.message}`
    }
    console.error('❌ Error reading config file:', error)
  } finally {
    isUploadingConfig.value = false
    // Reset file input
    if (target) {
      target.value = ''
    }
  }
}

// Essay upload functions
const handleEssayFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const files = target.files
  
  if (!files || files.length === 0) {
    return
  }

  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    
    // Validate file type
    if (!file.type.includes('pdf')) {
      alert(`File ${file.name} is not a PDF. Please upload only PDF files.`)
      continue
    }
    
    // Generate unique ID for the essay
    const essayId = `essay_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    
    // Prompt user for essay title
    const title = prompt(`Enter a title/display name for "${file.name}":`)
    if (!title || title.trim() === '') {
      alert('Essay title is required. Please try again.')
      continue
    }
    
    // Add to uploaded essays list
    uploadedEssays.value.push({
      id: essayId,
      filename: file.name,
      title: title.trim(),
      file: file
    })
  }
  
  // Reset file input
  if (target) {
    target.value = ''
  }
  
  // Assign essays to session if we have a session
  if (currentSessionCode.value && uploadedEssays.value.length > 0) {
    await assignEssaysToSession()
  }
}

const removeEssay = (index: number) => {
  uploadedEssays.value.splice(index, 1)
  
  // Update session if we have one
  if (currentSessionCode.value) {
    assignEssaysToSession()
  }
}

const assignEssaysToSession = async () => {
  if (!currentSessionCode.value) {
    console.warn('No active session to assign essays to')
    return
  }
  
  try {
    // Create FormData to send files
    const formData = new FormData()
    formData.append('session_code', currentSessionCode.value)
    
    // Add essay metadata
    const essaysMetadata = uploadedEssays.value.map(essay => ({
      essay_id: essay.id,
      title: essay.title,
      filename: essay.filename
    }))
    formData.append('essays_metadata', JSON.stringify(essaysMetadata))
    
    // Add PDF files
    uploadedEssays.value.forEach((essay, index) => {
      if (essay.file) {
        formData.append(`essay_file_${index}`, essay.file, essay.filename)
      }
    })
    
    const response = await fetch('/api/essayranking/assign-essays', {
      method: 'POST',
      body: formData
    })
    
    if (response.ok) {
      const result = await response.json()
      console.log('✅ Essays assigned to session:', result)
      
      // Show warnings if any
      if (result.warnings && result.warnings.length > 0) {
        console.warn('⚠️ PDF extraction warnings:', result.warnings)
        alert(`Essays assigned successfully, but with ${result.warnings.length} extraction warnings. Check console for details.`)
      } else {
        alert(`✅ Successfully assigned ${result.essays_assigned ? String(result.essays_assigned) : uploadedEssays.value.length} essays to session!`)
      }
    } else {
      const error = await response.json()
      console.error('❌ Failed to assign essays:', error)
      alert(`Failed to assign essays: ${error.error ? String(error.error) : 'Unknown error'}`)
    }
  } catch (error) {
    console.error('❌ Error assigning essays:', error)
    alert('Error assigning essays to session')
  }
}

const handleECLFileUpload = async (eclContent: string, fileName: string) => {
  try {
    // Send ECL content to backend for validation and processing
    const response = await fetch('/api/experiment/ecl/validate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ecl_content: eclContent
      })
    })
    
    const result = await response.json()
    
    if (result.success && result.is_valid) {
      // ECL validation successful
      configValidationStatus.value = {
        type: 'success',
        message: 'ECL configuration is valid and ready to apply'
      }
      
      // Store the ECL configuration for later use
      uploadedConfigData.value = {
        ecl_config: result.experiment_config,
        ui_config: result.ui_config,
        ecl_content: eclContent,
        file_name: fileName
      }
      
      // Set experiment name from ECL config
      const experimentName = result.experiment_config?.ecl_config?.title || 
                           result.experiment_config?.ecl_config?.experiment_id || 
                           'ECL Custom Experiment'
      
      experimentNamePlaceholder.value = experimentName
      customExperimentName.value = experimentName
      
      // Show the modal for experiment name input
      showCustomExperimentModal.value = true
      
      console.log('✅ ECL file validation passed')
      console.log('ECL Config:', result.experiment_config)
      console.log('UI Config:', result.ui_config)
    } else {
      // ECL validation failed
      const errorMessage = result.errors?.join(', ') || result.error || 'Unknown validation error'
      configValidationStatus.value = {
        type: 'error',
        message: `ECL Validation Failed: ${errorMessage}`
      }
      console.error('❌ ECL file validation failed:', result.errors)
    }
  } catch (error: any) {
    configValidationStatus.value = {
      type: 'error',
      message: `Error processing ECL file: ${error.message}`
    }
    console.error('❌ Error processing ECL file:', error)
  }
}

const addCustomExperiment = () => {
  if (!customExperimentName.value.trim() || !uploadedConfigData.value) {
    alert('Please enter a name for the experiment and ensure config data is available')
    return
  }

  try {
    let newExperiment: ExperimentTemplate

    // Check if this is an ECL configuration
    if (uploadedConfigData.value.ecl_config) {
      // Create ECL-based experiment
      const eclConfig = uploadedConfigData.value.ecl_config
      newExperiment = {
        id: `ecl_${Date.now()}`,
        name: customExperimentName.value.trim(),
        description: eclConfig.ecl_config?.description || 'ECL-based custom experiment',
        tags: ['ECL', 'Custom'],
        defaultConfig: {
          ...experimentConfig.value,
          ...eclConfig,
          experiment_type: 'ecl_custom'
        },
        specificParams: []
      }
      
      console.log('📋 Using ECL config:', eclConfig)
      console.log('🔧 Final ECL experiment config:', newExperiment.defaultConfig)
    } else if (uploadedConfigData.value.experimentTemplate) {
      // Use the uploaded experiment template data
      const template = uploadedConfigData.value.experimentTemplate
      newExperiment = {
        id: template.id || `custom_${Date.now()}`,
        name: customExperimentName.value.trim() || template.name,
        description: template.description || 'Custom experiment configuration uploaded by user',
        tags: template.tags || ['Custom'],
        defaultConfig: {
          // Start with current experiment config as base
          ...experimentConfig.value,
          // Override with uploaded config values
          ...template.defaultConfig
        },
        specificParams: template.specificParams || []
      }
      
      console.log('📋 Using uploaded config:', template.defaultConfig)
      console.log('🔧 Final experiment config:', newExperiment.defaultConfig)
    } else {
      // Legacy format - create basic template
      newExperiment = {
        id: `custom_${Date.now()}`,
        name: customExperimentName.value.trim(),
        description: 'Custom experiment configuration uploaded by user',
        tags: ['Custom'],
        defaultConfig: {
          ...experimentConfig.value,
          sessionDuration: 15
        },
        specificParams: []
      }
    }

    // Mark as added
    customExperimentAdded.value = true
    
    console.log('✅ Custom experiment added:', newExperiment)
    
    // Close modal and clear form
    closeCustomExperimentModal()
    
    // Defer all reactive updates until after modal is closed
    nextTick(() => {
      setTimeout(() => {
        // Add to custom experiments (reactive)
        customExperiments.value.push(newExperiment)
        
        // Set as selected experiment
        selectedExperimentType.value = newExperiment.id
        console.log('🎯 Selected experiment type:', selectedExperimentType.value)
        
        // Apply the default configuration
        console.log('🔄 Before applying config:', experimentConfig.value)
        console.log('📋 New experiment config:', newExperiment.defaultConfig)
        
        experimentConfig.value = {
          ...experimentConfig.value,
          ...newExperiment.defaultConfig
        }
        
        console.log('✅ After applying config:', experimentConfig.value)
        
        // Show success message
        alert(`✅ Custom experiment "${newExperiment.name}" added successfully!`)
      }, 100)
    })
    
  } catch (error: any) {
    console.error('❌ Error adding custom experiment:', error)
    alert(`Error adding custom experiment: ${error.message}`)
  }
}

const closeCustomExperimentModal = () => {
  if (isClosingModal.value) {
    console.log('🔒 Modal already closing, skipping...')
    return
  }
  
  console.log('🔒 Closing custom experiment modal')
  isClosingModal.value = true
  
  try {
    // Remove event listener first
    document.removeEventListener('keydown', handleEscapeKey)
    
    // Clear state immediately
    configValidationStatus.value = null
    customExperimentName.value = ''
    uploadedConfigData.value = null
    experimentNamePlaceholder.value = ''
    
    // Close modal last
    showCustomExperimentModal.value = false
    
    console.log('✅ Modal closed successfully')
  } catch (error) {
    console.error('❌ Error closing modal:', error)
    // Force close modal even if there's an error
    showCustomExperimentModal.value = false
  } finally {
    // Reset flag after a delay
    setTimeout(() => {
      isClosingModal.value = false
    }, 200)
  }
}

// Handle escape key to close modal
const handleEscapeKey = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && showCustomExperimentModal.value) {
    closeCustomExperimentModal()
  }
}

// Single watcher for modal state changes
watch(showCustomExperimentModal, (newValue) => {
  if (newValue) {
    // Modal is opening, add event listener
    document.addEventListener('keydown', handleEscapeKey)
  }
})

// Save template methods
const closeSaveTemplateModal = () => {
  showSaveTemplateModal.value = false
  saveTemplateForm.value.templateName = ''
}

const openSaveTemplateModal = async () => {
  showSaveTemplateModal.value = true
  // Load available templates when opening the modal
  await loadAvailableTemplates()
}

const skipSaveTemplate = () => {
  closeSaveTemplateModal()
  proceedToInteractionVariables()
}

const saveTemplateFromParameters = async () => {
  if (!saveTemplateForm.value.templateName.trim()) {
    alert('Please enter a template name')
    return
  }
  
  isSavingTemplate.value = true
  
  try {
    console.log('🔄 Saving template:', saveTemplateForm.value.templateName)
    
    // Prepare the template configuration to save (no need to update backend config first)
    const templateConfig = {
      ...experimentConfig.value,
      communicationLevel: interactionConfig.value.communicationLevel,
      awarenessDashboard: interactionConfig.value.awarenessDashboard
    }
    
    console.log('📤 Template config to save:', templateConfig)
    
    // Then save as template
    const requestBody = {
      session_id: saveTemplateForm.value.templateName.trim(),
      researcher_id: 'researcher',
      template_config: templateConfig
    }
    
    console.log('📤 Sending template save request:', requestBody)
    
    const response = await fetch('/api/session-templates', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody)
    })
    
    console.log('📥 Response status:', response.status)
    
    const result = await response.json()
    console.log('📥 Response data:', result)
    
    if (response.ok && result.success) {
      console.log('✅ Template saved successfully:', result.message)
      
      // Show success message
      const templateName = saveTemplateForm.value.templateName
      saveTemplateForm.value.templateName = ''
      
      // Refresh the templates list to show the new template
      await loadAvailableTemplates()
      
      // Show success message
      alert(`✅ Template "${templateName}" saved successfully!`)
      
      // Close modal and proceed to next step
      closeSaveTemplateModal()
      proceedToInteractionVariables()
    } else {
      console.error('❌ Failed to save template:', result.error)
      alert(`Failed to save template: ${result.error ? String(result.error) : 'Unknown error'}`)
    }
  } catch (error: any) {
    console.error('Error saving template:', error)
    alert(`Error saving template: ${error.message}`)
  } finally {
    isSavingTemplate.value = false
  }
}

// Create session modal methods
const closeCreateSessionModal = () => {
  showCreateSessionModal.value = false
  createSessionFromParamsForm.value.sessionName = ''
}





const onNamingTypeChange = async () => {
  if (!agentRegistrationForm.value.numAgents || !agentRegistrationForm.value.namingType || !isSessionRegistered.value) {
    return
  }

  try {
    const numAgents = agentRegistrationForm.value.numAgents
    const namingType = agentRegistrationForm.value.namingType
    
    // Generate agent names based on naming type
    const agentNames = []
    for (let i = 1; i <= numAgents; i++) {
      if (namingType === 'player_x') {
        agentNames.push(`Player ${i}`)
      } else {
        // Use real human names (you can expand this list)
        const realNames = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank', 'Grace', 'Henry', 'Ivy', 'Jack', 'Kate', 'Liam', 'Mia', 'Noah', 'Olivia', 'Paul', 'Quinn', 'Ruby', 'Sam', 'Tina']
        agentNames.push(realNames[i - 1] || `Agent ${i}`)
      }
    }

    // Register each agent
    for (const agentName of agentNames) {
      const response = await fetch('/api/agents/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          participant_code: agentName,
          session_code: activeSessionCode.value,
          specialty_shape: undefined, // Auto-assign specialty
          tag: undefined
        })
      })
      
      if (!response.ok) {
        const result = await response.json()
        console.error(`Failed to register agent ${agentName}:`, result.error)
      }
    }

    // Reset the naming type selection and refresh participants
    agentRegistrationForm.value.namingType = ''
    await loadParticipants()
    
    alert(`Successfully registered ${numAgents} agents!`)
  } catch (error) {
    console.error('Error registering multiple agents:', error)
    alert('Failed to register agents. Please try again.')
  }
}

// Create session from parameters
const createSessionFromParameters = async () => {
  if (!createSessionFromParamsForm.value.sessionName.trim()) {
    alert('Please enter a session name')
    return
  }
  
  isCreatingSessionFromParams.value = true
  
  try {
    // Use the provided session name
    const sessionId = createSessionFromParamsForm.value.sessionName.trim()
    
    // Register the session
    const response = await fetch('/api/sessions/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_code: sessionId,
        researcher_id: 'researcher',
        experiment_type: selectedExperimentType.value,
        experiment_config: experimentConfig.value
      })
    })

    let result
    try {
      result = await response.json()
    } catch (jsonError) {
      console.error('Failed to parse JSON response:', jsonError)
      const responseText = await response.text()
      console.error('Response text:', responseText)
      throw new Error(`Server returned invalid JSON. Status: ${response.status}, Response: ${responseText}`)
    }

    if (response.ok && result.success) {
      // Update session validation state
      isSessionRegistered.value = true
      currentSessionCode.value = sessionId
      sessionValidationMessage.value = `Session "${sessionId}" is registered and ready for participants`
      sessionValidationMessageType.value = 'info'
      
      // Save current parameters to the new session
      const sessionCode = sessionId
      const currentConfig = {
        ...experimentConfig.value,
        session_code: sessionCode,
        communicationLevel: interactionConfig.value.communicationLevel,
        awarenessDashboard: interactionConfig.value.awarenessDashboard
      }
      
      const configResponse = await fetch('/api/experiment/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(currentConfig)
      })
      
      if (configResponse.ok) {
        console.log('✅ Parameters saved to new session')
      } else {
        console.error('❌ Failed to save parameters to new session')
      }
      
      // Close modal and clear form
      closeCreateSessionModal()
      
      // Register for the new session
      registerForSession()
      
      // Switch to setup tab and show all subtabs
      activeTab.value = 'setup'
      setupTabs.value.experimentSelection = true
      setupTabs.value.parameters = true
      setupTabs.value.interactionVariables = true
      setupTabs.value.participantRegistration = true
      activeSetupTab.value = 'experimentSelection'
      scrollToTab('experimentSelection')
      
      console.log('✅ Session operation completed:', result.session)
      
      // Check if session was created or updated
      if (result.message && result.message.includes('updated')) {
        alert(`Session "${sessionId}" already exists and has been updated with new parameters. You can now use this session.`)
      } else {
        alert(`Session "${sessionId}" created successfully! Switched to Session Setup tab.`)
      }
    } else {
      alert(result.error ? String(result.error) : 'Failed to create session')
    }
  } catch (error: any) {
    console.error('Error creating session:', error)
    alert(`Failed to create session: ${error.message}`)
  } finally {
    isCreatingSessionFromParams.value = false
  }
}



// Timeline label functions
const getTimelineStartLabel = () => {
  const allTimes = chartData.value.timeChartData
    .filter(data => data.firstTradeTime && data.lastTradeTime)
    .flatMap(data => [data.firstTradeTime, data.lastTradeTime])
  
  if (allTimes.length === 0) return '0 min'
  
  return '0 min'
}

const getTimelineEndLabel = () => {
  const allTimes = chartData.value.timeChartData
    .filter(data => data.firstTradeTime && data.lastTradeTime)
    .flatMap(data => [data.firstTradeTime, data.lastTradeTime])
  
  if (allTimes.length === 0) return '0 min'
  
  // Use configured session duration instead of actual trade end time
  const sessionDurationMinutes = experimentConfig.value.sessionDuration || 15
  const minutes = Math.floor(sessionDurationMinutes)
  const seconds = Math.round((sessionDurationMinutes - minutes) * 60)
  
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

// Tooltip state



const renderTradesBarChart = () => {
  if (!chartData.value.participantChartData.length) return
  
  // Use the standard Google Charts loading method
  if (typeof window.google !== 'undefined' && window.google.charts) {
    window.google.charts.load('current', { packages: ['corechart'] })
    window.google.charts.setOnLoadCallback(() => {
      try {
        const data = new window.google.visualization.DataTable()
        data.addColumn({ type: 'string', id: 'Participant' })
        data.addColumn({ type: 'number', id: 'Trades' })
        
        chartData.value.participantChartData.forEach(item => {
          data.addRow([item.participant, item.trades])
        })
        
        const options = {
          height: 150,
          width: '100%',
          backgroundColor: '#ffffff',
          colors: ['#10b981'],
          hAxis: {
            title: 'Number of Trades',
            minValue: 0,
            showTextEvery: 1,
            textStyle: {
              fontSize: 11
            },
            gridlines: {
              count: 5
            }
          },
          vAxis: {
            title: 'Participants'
          },
          bars: 'horizontal',
          legend: { position: 'none' },
          chartArea: {
            left: '20%',
            right: '10%',
            top: '2%',
            bottom: '20%'
          }
        }
        
        const chart = new window.google.visualization.BarChart(document.getElementById('trades-bar-chart'))
        chart.draw(data, options)
      } catch (error) {
        console.error('Error rendering trades bar chart:', error)
      }
    })
  } else {
    console.error('Google Charts not available')
  }
}

const renderMessagesBarChart = () => {
  if (!chartData.value.participantChartData.length) return
  
  // Use the standard Google Charts loading method
  if (typeof window.google !== 'undefined' && window.google.charts) {
    window.google.charts.load('current', { packages: ['corechart'] })
    window.google.charts.setOnLoadCallback(() => {
      try {
        const data = new window.google.visualization.DataTable()
        data.addColumn({ type: 'string', id: 'Participant' })
        data.addColumn({ type: 'number', id: 'Messages' })
        
        chartData.value.participantChartData.forEach(item => {
          data.addRow([item.participant, item.messages])
        })
        
        const options = {
          height: 150,
          width: '100%',
          backgroundColor: '#ffffff',
          colors: ['#8b5cf6'],
          hAxis: {
            title: 'Number of Messages',
            minValue: 0,
            showTextEvery: 1,
            textStyle: {
              fontSize: 11
            },
            gridlines: {
              count: 5
            }
          },
          vAxis: {
            title: 'Participants'
          },
          bars: 'horizontal',
          legend: { position: 'none' },
          chartArea: {
            left: '20%',
            right: '10%',
            top: '2%',
            bottom: '20%'
          }
        }
        
        const chart = new window.google.visualization.BarChart(document.getElementById('messages-bar-chart'))
        chart.draw(data, options)
      } catch (error) {
        console.error('Error rendering messages bar chart:', error)
      }
    })
  } else {
    console.error('Google Charts not available')
  }
}
  // Render all charts when data changes
  const renderAllCharts = () => {
    nextTick(() => {
      if (behavioralLogsForm.value.showTrades) {
        renderTradesBarChart()
      }
      if (behavioralLogsForm.value.showMessages) {
        renderMessagesBarChart()
      }
    })
  }

  // Tooltip state for timeline chart
  const tooltipVisible = ref(false)
  const tooltipData = ref<{ title: string; content: string }>({ title: '', content: '' })
  const tooltipPosition = ref<{ x: number; y: number }>({ x: 0, y: 0 })

  // Helper function to get session start time
  const getSessionStartTime = () => {
    // If we have an active session, use the session start time
    if (isSessionRegistered.value && currentSessionCode.value) {
      // For now, use the earliest trade timestamp as session start
      // In a real implementation, you might get this from the session data
      const allTradeTimes = timelineTradesData.value.completed_trades
        .concat(timelineTradesData.value.pending_offers)
        .map(trade => new Date(trade.timestamp).getTime())
      
      if (allTradeTimes.length > 0) {
        return Math.min(...allTradeTimes)
      }
    }
    
    // Fallback: use current time minus session duration
    const sessionDuration = experimentConfig.value.sessionDuration || 15
    return Date.now() - (sessionDuration * 60 * 1000)
  }

  // Custom timeline chart functions
  const getTimelinePosition = (startTime: number) => {
    if (!chartData.value.timeChartData.length) return 10
    
    // Use session duration from experiment config for proper time scaling
    const sessionDuration = experimentConfig.value.sessionDuration
    if (sessionDuration) {
      // Convert session duration to milliseconds
      const sessionDurationMs = sessionDuration * 60 * 1000
      // Calculate position based on session start (0:00) to session end
      // startTime is now relative to session start (0), so we can use it directly
      const position = (startTime / sessionDurationMs) * 80 + 10 // 10% margin on each side
      return Math.min(Math.max(position, 10), 90) // Clamp between 10% and 90%
    }
    
    // Fallback: if no session duration, use the trade data range
    const allTimes = chartData.value.timeChartData.flatMap(trade => [
      trade.firstTradeTime,
      trade.lastTradeTime
    ]).filter(time => time !== null) // Filter out null times for pending trades
    
    if (allTimes.length === 0) return 10 // Default to 10% margin
    
    const maxTime = Math.max(...allTimes)
    if (maxTime === 0) return 10 // Default to 10% margin
    
    // startTime is now relative to 0, so position is based on maxTime
    const position = (startTime / maxTime) * 80 + 10 // 10% margin on each side
    return Math.min(Math.max(position, 10), 90) // Clamp between 10% and 90%
  }

  const getTimelineWidth = (startTime: number, endTime: number | null) => {
    if (!chartData.value.timeChartData.length) return 0.5
    
    // For pending trades (no end time), return a minimal width
    if (endTime === null) return 0.5 // 0.5% width for pending trades
    
    // Use session duration from experiment config for proper time scaling
    const sessionDuration = experimentConfig.value.sessionDuration
    if (sessionDuration) {
      // Convert session duration to milliseconds
      const sessionDurationMs = sessionDuration * 60 * 1000
      // Calculate width based on session duration
      // startTime and endTime are now relative to session start (0)
      const duration = endTime - startTime
      const width = (duration / sessionDurationMs) * 80 // 80% of available width
      return Math.max(width, 0.5) // Minimum width of 0.5%
    }
    
    // Fallback: if no session duration, use the trade data range
    const allTimes = chartData.value.timeChartData.flatMap(trade => [
      trade.firstTradeTime,
      trade.lastTradeTime
    ]).filter(time => time !== null) // Filter out null times
    
    if (allTimes.length === 0) return 0.5 // Default to 0.5% width
    
    const maxTime = Math.max(...allTimes)
    if (maxTime === 0) return 0.5 // Default to 0.5% width
    
    // startTime and endTime are now relative to 0, so width is based on maxTime
    const duration = endTime - startTime
    const width = (duration / maxTime) * 80 // 80% of available width
    return Math.max(width, 0.5) // Minimum width of 0.5%
  }

  const showTimelineTooltip = (event: MouseEvent, trade: any, participant: string, index: number) => {
    const startTime = new Date(trade.firstTradeTime).toLocaleTimeString()
    
    let tooltipContent = `Start: ${startTime}<br>`
    
    if (trade.isCompleted && trade.lastTradeTime) {
      const endTime = new Date(trade.lastTradeTime).toLocaleTimeString()
      const duration = Math.round((trade.lastTradeTime - trade.firstTradeTime) / 1000)
      tooltipContent += `End: ${endTime}<br>Duration: ${duration}s<br>`
    } else {
      tooltipContent += `Status: Pending (Ongoing)<br>`
    }
    
    tooltipContent += `Shape: ${trade.shape}<br>Quantity: ${trade.quantity}<br>Price: ${trade.price}`
    
    tooltipData.value = {
      title: `${participant} - ${trade.isCompleted ? 'Completed Trade' : 'Pending Offer'} ${index + 1}`,
      content: tooltipContent
    }
    
    tooltipVisible.value = true
    tooltipPosition.value = { x: event.clientX, y: event.clientY }
  }

  const hideTooltip = () => {
    tooltipVisible.value = false
  }

  // Time label functions for x-axis
  const getMiddleTimeLabel = () => {
    // Use session duration from experiment config if available
    const sessionDuration = experimentConfig.value.sessionDuration
    if (sessionDuration) {
      const middleTime = sessionDuration / 2
      const minutes = Math.floor(middleTime / 60)
      const seconds = Math.floor(middleTime % 60)
      return `${minutes}:${seconds.toString().padStart(2, '0')}`
    }
    
    // Fallback to trade data if no session duration
    if (!chartData.value.timeChartData.length) return '0:00'
    
    const allTimes = chartData.value.timeChartData.flatMap(trade => [
      trade.firstTradeTime,
      trade.lastTradeTime
    ]).filter(time => time !== null) // Filter out null times for pending trades
    
    if (allTimes.length === 0) return '0:00'
    
    const maxTime = Math.max(...allTimes)
    if (maxTime === 0) return '0:00'
    
    // Since timestamps are now relative to session start (0), middle time is maxTime/2
    const middleTime = maxTime / 2
    
    // Convert milliseconds to proper time format
    const totalSeconds = Math.floor(middleTime / 1000)
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }

  const getEndTimeLabel = () => {
    // Use session duration from experiment config if available
    const sessionDuration = experimentConfig.value.sessionDuration
    if (sessionDuration) {
      const minutes = Math.floor(sessionDuration / 60)
      const seconds = Math.floor(sessionDuration % 60)
      return `${minutes}:${seconds.toString().padStart(2, '0')}`
    }
    
    // Fallback to trade data if no session duration
    if (!chartData.value.timeChartData.length) return '0:00'
    
    const allTimes = chartData.value.timeChartData.flatMap(trade => [
      trade.firstTradeTime,
      trade.lastTradeTime
    ]).filter(time => time !== null) // Filter out null times for pending trades
    
    if (allTimes.length === 0) return '0:00'
    
    const maxTime = Math.max(...allTimes)
    if (maxTime === 0) return '0:00'
    
    // Since timestamps are now relative to session start (0), maxTime represents the session duration
    // Convert milliseconds to proper time format
    const totalSeconds = Math.floor(maxTime / 1000)
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }
</script>

<style scoped>
/* Make entire dashboard fill the viewport height */
.researcher-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 20px;
  background: #f9fafb;
  overflow: hidden; /* Prevent body scroll */
}

/* Make the area under tabs fill the remaining viewport height */
.researcher-container > .tab-group-card {
  flex: 1;
  min-height: 0; /* Allow flex item to shrink */
}

/* TOP CONTROL BUTTONS */
.top-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 20px;
  padding: 10px 20px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}


.timer-display {
  display: flex;
  flex-direction: row;
  gap: 4px;
  min-width: 200px;
}

.timer-label {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.timer-value {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  background: #f9fafb;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  text-align: center;
}

.current-session-display {
  display: flex;
  align-items: center;
  margin-left: 12px;
  background: #eef7ff;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}

.current-session-display .session-label {
  font-size: 14px;
  font-weight: 600;
  color: #3065d6;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  text-align: center;
}

.control-buttons {
  display: flex;
  gap: 12px;
  align-items: center;
}

.control-rect {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  min-width: 120px;
  justify-content: center;
}

.control-rect:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.control-rect:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.control-rect.start {
  background: #2e7d32;
  color: #fff;
}

.control-rect.start:hover:not(:disabled) {
  background: #1b5e20;
}

.control-rect.start.paused {
  background: #f57c00;
}

.control-rect.start.paused:hover:not(:disabled) {
  background: #e65100;
}

.control-rect.reset {
  background: #f57c00;
  color: #fff;
}

.control-rect.reset:hover:not(:disabled) {
  background: #e65100;
}

.control-rect.end {
  background: #d32f2f;
  color: #fff;
}

.control-rect.end:hover:not(:disabled) {
  background: #b71c1c;
}

.button-icon {
  font-size: 16px;
  line-height: 1;
}

.button-text {
  font-size: 14px;
  font-weight: 600;
}

/* HEADER TABS */
.tab-header-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 0; /* connect with content card */
  position: relative; /* for z-index layering */
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
  grid-template-columns: 1fr 1fr 1.5fr;
}

.tab-content-grid.session-mode {
  grid-template-columns: 1fr 1fr;
}

.tab-content-grid.analysis-mode {
  grid-template-columns: 2fr 1fr;
}

.tab-content-grid.setup-mode {
  grid-template-columns: 1fr;
  gap: 0;
}

/* Experiment Setting Layout */
.experiment-setting-layout {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 20px;
  height: 100%;
  min-height: 0;
}

.experiment-selection-panel {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.selection-title {
  font-weight: 700;
  color: #111827;
  font-size: 14px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
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

.experiment-list-item:last-child {
  border-bottom: none;
}

.experiment-list-item:hover {
  background: #f9fafb;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.step-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}


.experiment-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  cursor: pointer;
  min-height: 48px;
}

.experiment-item-header.previewed {
  background: #f0f9ff;
  border-left: 4px solid #0ea5e9;
}

.experiment-name {
  font-size: 15px;
  font-weight: 500;
  color: #1f2937;
  margin: 0;
  flex: 1;
}

.dropdown-icon {
  width: 16px;
  height: 16px;
  color: #6b7280;
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.dropdown-icon.expanded {
  transform: rotate(180deg);
}

.experiment-item-content {
  padding: 0 16px 8px 16px;
  border-top: 1px solid #f3f4f6;
  padding-top: 8px;
}

.experiment-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 12px;
}

.experiment-tag {
  background: #f3f4f6;
  color: #6b7280;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 12px;
  white-space: nowrap;
}

.experiment-description-preview {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.4;
}

.experiment-description-preview p {
  margin: 0 0 6px 0;
}

.experiment-description-preview p:last-child {
  margin-bottom: 0;
}

.experiment-description-preview strong {
  color: #374151;
  font-weight: 600;
}


/* Tag Filter Section */
.tag-filter-section {
  /* margin-bottom: 16px; */
  padding: 12px;
  background: #f8fafc;
  /* border: 1px solid #e2e8f0; */
  border-radius: 8px 8px 0 0;
}

.tag-filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.tag-filter-label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.clear-tags-btn {
  background: none;
  border: none;
  color: #6b7280;
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
  padding: 2px 4px;
  border-radius: 4px;
  transition: color 0.15s ease;
}

.clear-tags-btn:hover {
  color: #374151;
}

.tag-filter-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-filter-btn {
  background: #ffffff;
  border: 1px solid #d1d5db;
  color: #6b7280;
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.tag-filter-btn:hover {
  background: #f3f4f6;
  border-color: #9ca3af;
  color: #374151;
}

.tag-filter-btn.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #ffffff;
}

.tag-filter-btn.active:hover {
  background: #1d4ed8;
  border-color: #1d4ed8;
}

/* Upload Config Section */
.upload-config-section {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.upload-description {
  margin-bottom: 16px;
  padding: 12px;
  background: #f1f5f9;
  border-radius: 6px;
  border-left: 4px solid #3b82f6;
}

.upload-description p {
  margin: 0 0 8px 0;
  color: #475569;
  font-size: 14px;
}

.upload-description ul {
  margin: 0;
  padding-left: 20px;
  color: #64748b;
  font-size: 13px;
}

.upload-description li {
  margin-bottom: 4px;
}

.upload-config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-label {
  font-weight: 600;
  color: #374151;
  font-size: 14px;
}

.upload-config-btn {
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.upload-config-btn:hover:not(:disabled) {
  background: #2563eb;
}

.upload-config-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

.validation-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-radius: 6px;
  margin-top: 12px;
  font-size: 14px;
}

.validation-status.success {
  background: #d1fae5;
  border: 1px solid #a7f3d0;
  color: #065f46;
}

.validation-status.error {
  background: #fee2e2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.validation-status.success {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #16a34a;
}

.validation-icon {
  font-size: 16px;
}

.validation-message {
  font-weight: 500;
}

.custom-experiment-form {
  margin-top: 12px;
  padding: 12px;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 6px;
}

.experiment-name-input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.experiment-name-input-group label {
  font-weight: 600;
  color: #374151;
  font-size: 13px;
}

.experiment-name-input {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 14px;
  transition: border-color 0.15s ease;
}

.experiment-name-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.add-experiment-btn {
  background: #10b981;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease;
  align-self: flex-start;
}

.add-experiment-btn:hover:not(:disabled) {
  background: #059669;
}

.add-experiment-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

/* Modal Styles */
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
  border-radius: 8px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.modal-close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #6b7280;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background-color 0.15s ease;
}

.modal-close-btn:hover {
  background: #f3f4f6;
  color: #374151;
}

.modal-body {
  padding: 24px;
}

.validation-success {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #d1fae5;
  border: 1px solid #a7f3d0;
  border-radius: 6px;
  margin-bottom: 20px;
  color: #065f46;
}

.validation-success .validation-icon {
  font-size: 20px;
}

.validation-success .validation-message {
  font-weight: 500;
  font-size: 14px;
}

.experiment-name-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.experiment-name-section label {
  font-weight: 600;
  color: #374151;
  font-size: 14px;
}

.modal-experiment-name-input {
  padding: 12px 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.modal-experiment-name-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid #e5e7eb;
}

.modal-cancel-btn {
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.modal-cancel-btn:hover {
  background: #e5e7eb;
}

.modal-confirm-btn {
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.modal-confirm-btn:hover:not(:disabled) {
  background: #2563eb;
}

.modal-confirm-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

.parameters-panel {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.parameters-title {
  font-weight: 700;
  color: #111827;
  font-size: 14px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
}

/* Template Loading Section */
.template-loading-section {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.template-loading-header h4 {
  font-weight: 700;
  color: #111827;
  font-size: 14px;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
}

.template-loading-controls {
  display: flex;
  gap: 8px;
  align-items: center;
}

.template-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.template-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.template-load-btn {
  padding: 8px 16px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.template-load-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.template-load-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}



.templates-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.templates-title {
  font-weight: 600;
  color: #374151;
  font-size: 14px;
}

.refresh-templates-btn {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.refresh-templates-btn:hover {
  background-color: #e5e7eb;
}

.templates-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  transition: all 0.2s;
}

.template-item:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.1);
}

.template-item.default-template {
  background: #fef3c7;
  border-color: #f59e0b;
}

.template-name {
  font-weight: 500;
  color: #374151;
}

.template-actions {
  display: flex;
  gap: 6px;
}

.template-action-btn {
  background: none;
  border: none;
  font-size: 14px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.template-action-btn.load:hover {
  background-color: #dbeafe;
}

.template-action-btn.delete:hover {
  background-color: #fee2e2;
}

.no-templates-message {
  text-align: center;
  color: #6b7280;
  font-style: italic;
  padding: 20px;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px dashed #d1d5db;
}

/* Template Modal Styles */
.template-modal {
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
}

.templates-management-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e5e7eb;
}

.templates-management-section h4 {
  margin: 0 0 15px 0;
  color: #374151;
  font-size: 16px;
  font-weight: 600;
}

.save-template-form {
  margin-bottom: 20px;
}

/* Action Buttons Section */
.action-buttons-section {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-radius: 8px;
  margin-top: 16px;
}

.action-btn {
  flex: 1;
  padding: 12px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.save-template-btn {
  background: #059669;
  color: #fff;
}

.save-template-btn:hover {
  background: #047857;
}

.create-session-btn {
  background: #2563eb;
  color: #fff;
}

.create-session-btn:hover {
  background: #1d4ed8;
}

/* Setup Tab Progressive Workflow Styles */
.setup-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.subtab-navigation {
  background: #f8fafc;
  padding: 8px;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f1f5f9;
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
  gap: 8px;
  min-width: max-content;
  width: max-content;
  max-width: calc(3 * (200px + 8px)); /* Limit to 3 subtabs, each 200px wide + 8px gap */
}

.subtab-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  min-width: 200px; /* Fixed width to make subtabs wider */
  flex-shrink: 0; /* Prevent shrinking */
}

.subtab-item:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.subtab-item.active {
  background: #2563eb;
  color: #ffffff;
  border-color: #2563eb;
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
}

.setup-tabs-container {
  display: flex;
  height: 100%;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f1f5f9;
  gap: 12px;
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
  overflow-y: auto;
  padding: 0 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
}

/* Parameters tab - twice the width */
.setup-tab-panel.experiment-selection-tab {
  flex: 0 0 66%;
  min-width: 66%;
  max-width: 66%;
}

/* Experiment Selection Layout */
.experiment-selection-layout {
  display: flex;
  gap: 20px;
  height: calc(100% - 60px); /* Account for title */
}

.experiment-selection-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.option-label {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #e5e7eb;
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

.illustration-header {
  margin-bottom: 16px;
}

.illustration-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #374151;
}

.illustration-subtitle {
  margin: 4px 0 0 0;
  font-size: 14px;
  color: #6b7280;
  font-weight: 500;
}

.illustration-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff;
  border: 2px dashed #d1d5db;
  border-radius: 8px;
  /* min-height: 200px; */
}

.placeholder-content {
  text-align: center;
  color: #6b7280;
}

.placeholder-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.placeholder-content p {
  margin: 4px 0;
  font-size: 14px;
}

.placeholder-subtitle {
  font-size: 12px !important;
  color: #9ca3af !important;
}

.experiment-illustration {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  min-height: 200px;
  padding: 16px;
}

.illustration-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
}

.setup-tab-panel.parameters-tab {
  flex: 0 0 33.33%;
  min-width: 33.33%;
  max-width: 33.33%;
}

/* Interaction Variables tab - two-thirds width */
.setup-tab-panel.interaction-variables-tab {
  flex: 0 0 66.67%;
  min-width: 66.67%;
  max-width: 66.67%;
}

/* Interaction Variables Layout */
.interaction-variables-layout {
  display: flex;
  gap: 20px;
  height: calc(100% - 60px); /* Account for title and actions */
}

/* Variables Grid Layout */
.variables-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
  margin-top: 12px;
}

/* Toggle Switch Styles */
.toggle-switch {
  margin-top: 8px;
  display: flex;
  align-items: center;
}

.toggle-input {
  display: none;
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

.toggle-text {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  transition: color 0.3s ease;
  z-index: 2;
}

.toggle-text.off-text {
  left: 8px;
  color: #6b7280;
}

.toggle-text.on-text {
  right: 8px;
  color: #6b7280;
}

.toggle-input:checked + .toggle-label {
  border-color: #7ca9f2;
}

.toggle-input:checked + .toggle-label .toggle-slider {
  background-color: #7ca9f2;
}

.toggle-input:checked + .toggle-label .toggle-indicator {
  transform: translateX(calc(100% + 2px));
}

.toggle-input:checked + .toggle-label .toggle-text.off-text {
  color: #6b7280;
}

.toggle-input:checked + .toggle-label .toggle-text.on-text {
  color: #ffffff;
}

.toggle-input + .toggle-label .toggle-text.off-text {
  color: #ffffff;
}

.toggle-input:focus + .toggle-label {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.variables-column {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

/* Clickable entry styles */
.variable-group.clickable-entry {
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  background-color: #ffffff;
}

.variable-group.clickable-entry:hover {
  border-color: #d1d5db;
  background-color: #f9fafb;
}

.variable-group.clickable-entry.selected {
  border-color: #3b82f6;
  background-color: #eff6ff;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.preview-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  height: 100%;
  overflow-y: auto;
}

/* Preview component styles */
.conditional-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-top: 12px;
}

.preview-component {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.no-preview {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-style: italic;
}

/* Chat mode styles */
.chat-mode {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 8px;
}

/* Broadcast mode styles */
.broadcast-mode {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 8px;
}

.broadcast-info {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 12px;
}

.broadcast-info h4 {
  margin: 0 0 4px 0;
  font-size: 14px;
  font-weight: 600;
}

.broadcast-info p {
  margin: 0;
  font-size: 12px;
  opacity: 0.9;
}

/* Message thread and history */
.message-thread {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.message-history {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Base message item styles */
.message-item {
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 8px;
  max-width: 80%;
  word-wrap: break-word;
}

.message-sender {
  font-weight: 600;
  font-size: 12px;
  margin-bottom: 4px;
}

.message-content {
  font-size: 14px;
  line-height: 1.4;
  margin-bottom: 4px;
}

.message-time {
  font-size: 11px;
  opacity: 0.7;
}

/* Chat mode message styles */
.message-item.my-message {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  align-self: flex-end;
  margin-left: 20px;
  margin-right: 0;
  box-shadow: 0 2px 6px rgba(102, 126, 234, 0.3);
}

.message-item.my-message .message-sender {
  color: rgba(255, 255, 255, 0.9);
}

.message-item.my-message .message-content {
  color: white;
}

.message-item.my-message .message-time {
  color: rgba(255, 255, 255, 0.7);
}

.message-item.other-message {
  background: #f8f9fa;
  color: #333;
  align-self: flex-start;
  margin-right: 20px;
  margin-left: 0;
  border-left: 4px solid #667eea;
}

.message-item.other-message .message-sender {
  color: #667eea;
}

.message-item.other-message .message-content {
  color: #333;
}

.message-item.other-message .message-time {
  color: #666;
}

/* Broadcast message styles */
.broadcast-message {
  background: #f8f9fa;
  border-left: 4px solid #667eea;
  border-radius: 0 6px 6px 0;
}

.broadcast-message.other-message {
  background: #f8f9fa;
  color: #333;
  border-left: 4px solid #667eea;
  margin-right: 20px;
  margin-left: 0;
  align-self: flex-start;
}

.broadcast-message.other-message .message-sender {
  font-weight: 600;
  color: #667eea;
  font-size: 12px;
  margin-bottom: 4px;
}

.broadcast-message.other-message .message-content {
  color: #333;
  font-size: 14px;
  line-height: 1.4;
}

.broadcast-message.other-message .message-time {
  color: #666;
  font-size: 11px;
  margin-top: 4px;
}
/* Message input area */
.message-input-area {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e1e5e9;
}

.message-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
}

.message-input:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
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

.send-btn:hover {
  background: #5a6fd8;
}

/* Panel styles to match ParticipantInterface */
.panel {
  background: white;
  border: 1px solid #e1e5e9;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  height: 100%;
}

.panel-header {
  background: #f8fafc;
  padding: 12px 16px;
  border-bottom: 1px solid #e1e5e9;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.panel-body {
  flex: 1;
  padding: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Component text styles to match ParticipantInterface */
.component-text {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.component-num {
  font-size: 12px;
  color: #333;
  font-weight: 600;
}

.component-module {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* Awareness dashboard specific styles */
.awareness-panel .panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.participants-status-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  padding-right: 4px;
  min-height: 0;
}

.participant-status-card {
  background: white;
  border: 1px solid #e1e5e9;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  transition: box-shadow 0.3s ease;
}

.participant-status-card:hover {
  box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

/* Awareness options UI */
.awareness-options {
  margin-top: 10px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.awareness-options .options-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.awareness-options .option-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #374151;
}

.participant-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #f0f0f0;
  gap: 12px;
}

.participant-specialty {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #666;
}

.participant-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stats-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.stats-row .component-module {
  flex: 1;
  min-width: 0;
}

.progress-label {
  margin-bottom: 4px;
}

/* Shape icon styles */
.shape-icon {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}

.shape-icon.circle {
  background-color: #3b82f6;
}

.shape-icon.square {
  background-color: #10b981;
  border-radius: 2px;
}

.shape-icon.triangle {
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-bottom: 10px solid #f59e0b;
  background: none;
}

/* Preview Styles */
.preview-header {
  margin-bottom: 16px;
}

.preview-header h4 {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 4px 0;
}

.preview-description {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.participant-preview {
  flex: 1;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
  margin-top: 8px;
}

.preview-interface {
  height: 400px;
  display: flex;
  flex-direction: column;
  background: white;
  font-size: 10px;
}

/* Header Bar */
.preview-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
  font-size: 12px;
}

.preview-header-left,
.preview-header-center,
.preview-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preview-session-id {
  font-weight: 500;
  color: #374151;
}

.preview-rules-btn,
.preview-logout-btn {
  padding: 4px 8px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}

.preview-timer {
  font-weight: 600;
  color: #1f2937;
  font-size: 14px;
}

.preview-session-status-indicator {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}

.preview-session-status-indicator.ready {
  background: #dcfce7;
  color: #166534;
}

.preview-status-text {
  color: inherit;
}

/* Main Content */
.preview-main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.preview-column-left {
  width: 25%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e5e7eb;
  background: #f8fafc;
}

.preview-column-right {
  width: 75%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e5e7eb;
  background: #f8fafc;
}

.preview-column-awareness {
  width: 25%;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
}

/* Panels */
.preview-panel {
  border-bottom: 1px solid #e5e7eb;
  background: white;
}

.preview-panel:last-child {
  border-bottom: none;
}

.preview-tall-panel {
  flex: 1;
}

.preview-interaction-panel {
  flex: 1;
}

.preview-panel-header {
  padding: 4px 6px ;
  margin: 0;
  font-size: 10px;
  font-weight: 600;
  color: #1f2937;
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
}

.preview-panel-body {
  padding: 8px;
}

/* Component Styles - Matching actual participant interface */
.preview-component-module {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding: 6px 8px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
}

.preview-component-text {
  font-size: 10px;
  color: #374151;
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}

.preview-component-num {
  font-weight: 600;
  color: #1f2937;
  font-size: 10px;
}

.preview-component-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.preview-component-list-item {
  padding: 4px 6px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  font-size: 10px;
}

.preview-component-list-item.preview-selected {
  background: #dbeafe;
  border-color: #3b82f6;
}

.preview-inventory-title {
  font-size: 10px;
  color: #374151;
  margin: 0 0 6px 0;
  font-weight: 500;
}

.preview-empty {
  color: #9ca3af;
  font-style: italic;
  font-size: 10px;
  text-align: center;
  padding: 8px;
}

/* Shape Icons */
.preview-shape-icon {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  display: inline-block;
}

.preview-shape-icon.circle {
  border-radius: 50%;
  background: #ef4444;
}

.preview-shape-icon.square {
  background: #10b981;
}

.preview-shape-icon.triangle {
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-bottom: 10px solid #f59e0b;
  background: transparent;
}

/* Factory Panel - Matching actual participant interface */
.preview-factory-info {
  margin-bottom: 12px;
}

.preview-production-controls {
  margin-bottom: 12px;
  padding: 8px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
}

.preview-production-controls label {
  font-size: 9px;
  color: #374151;
  display: block;
  margin-bottom: 4px;
  font-weight: 500;
}

.preview-controls-row {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}

.preview-production-dropdown {
  flex: 1;
  padding: 3px 5px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 9px;
  background: white;
}

.preview-order-btn {
  padding: 3px 6px;
  background: #10b981;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 9px;
  cursor: pointer;
  font-weight: 500;
}

.preview-production-count-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 9px;
  color: #6b7280;
  margin-top: 3px;
}

.preview-production-count {
  font-weight: 600;
  color: #1f2937;
}

.preview-production-status {
  margin-top: 8px;
  padding: 4px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
}

.preview-production-label {
  font-size: 9px;
  color: #374151;
  margin-bottom: 4px;
  font-weight: 500;
}

.preview-production-queue {
  min-height: 12px;
}

/* Task Panel */
.preview-orders-grid {
  height: 100%;
}

.preview-orders-grid .preview-component-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
}

.preview-order-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-radius: 4px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}

.preview-order-checkbox {
  width: 12px;
  height: 12px;
}

/* Social Panel */
.preview-social-panel {
  flex: 1;
  min-height: 200px;
}

.preview-social-content {
  display: flex;
  height: 100%;
  gap: 8px;
}

.preview-participants-column {
  width: 30%;
  border-right: 1px solid #e5e7eb;
  padding-right: 8px;
}

.preview-interaction-column {
  width: 70%;
  display: flex;
  flex-direction: column;
}

.preview-tab-content-area {
  flex: 1;
  overflow-y: auto;
  min-height: 120px;
}

.preview-player-info {
  width: 100%;
}

/* Interaction Panel */
.preview-interaction-header {
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
  padding: 8px 12px;
}

.preview-interaction-header h3 {
  margin: 0 0 8px 0;
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}

.preview-interaction-tabs {
  display: flex;
}

.preview-tab-btn {
  padding: 4px 8px;
  border: none;
  background: transparent;
  font-size: 9px;
  color: #6b7280;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}

.preview-tab-btn.preview-active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
  background: white;
}

.preview-trade-content {
  padding: 8px 0;
}

.preview-trade-section {
  margin-bottom: 12px;
}

.preview-trade-section h4 {
  margin: 0 0 8px 0;
  font-size: 12px;
  font-weight: 600;
  color: #374151;
}

.preview-offers-list {
  margin-bottom: 12px;
}

.preview-offer-item {
  padding: 8px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  margin-bottom: 6px;
}

.preview-offer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.preview-offer-type {
  font-size: 9px;
  font-weight: 600;
  padding: 2px 4px;
  border-radius: 2px;
  background: #dbeafe;
  color: #1e40af;
}

.preview-offer-from {
  font-size: 9px;
  color: #6b7280;
}

.preview-offer-details {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
  font-size: 10px;
  color: #374151;
}

.preview-offer-price {
  font-weight: 600;
  color: #059669;
}

.preview-offer-actions {
  display: flex;
  gap: 4px;
}

.preview-accept-btn,
.preview-decline-btn {
  padding: 2px 6px;
  border: none;
  border-radius: 2px;
  font-size: 9px;
  cursor: pointer;
}

.preview-accept-btn {
  background: #10b981;
  color: white;
}

.preview-decline-btn {
  background: #ef4444;
  color: white;
}

.preview-propose-trade {
  margin-bottom: 8px;
}

.preview-trade-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-trade-sentence {
  font-size: 10px;
  color: #374151;
  line-height: 1.4;
}

.preview-sentence-builder {
  margin: 0;
}

.preview-trade-select {
  padding: 1px 3px;
  border: 1px solid #d1d5db;
  border-radius: 2px;
  font-size: 10px;
  background: white;
}

/* Tab Content */
.preview-tab-content {
  padding: 8px 0;
  height: 100%;
  overflow-y: auto;
}

/* Message Content */
.preview-message-content,
.preview-broadcast-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.preview-message-thread {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 8px;
  min-height: 80px;
  max-height: 120px;
}

.preview-message-item {
  margin-bottom: 6px;
  padding: 4px 6px;
  border-radius: 4px;
  font-size: 8px;
}

.preview-message-received {
  background: #f3f4f6;
  margin-right: 20px;
}

.preview-message-sent {
  background: #dbeafe;
  margin-left: 20px;
}

.preview-message-broadcast {
  background: #fef3c7;
  border-left: 3px solid #f59e0b;
}

.preview-message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 2px;
  font-size: 9px;
  color: #6b7280;
}

.preview-message-sender {
  font-weight: 600;
}

.preview-message-time {
  color: #9ca3af;
}

.preview-message-text {
  color: #374151;
  line-height: 1.3;
}

.preview-message-input {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}

.preview-message-input-field {
  flex: 1;
  padding: 4px 6px;
  border: 1px solid #d1d5db;
  border-radius: 3px;
  font-size: 10px;
}
.preview-send-btn {
  padding: 4px 8px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 3px;
  font-size: 10px;
  cursor: pointer;
}

.preview-broadcast-info {
  margin-bottom: 8px;
  padding: 6px 8px;
  background: #fef3c7;
  border-radius: 4px;
  border-left: 3px solid #f59e0b;
}

.preview-broadcast-info h4 {
  margin: 0 0 4px 0;
  font-size: 11px;
  font-weight: 600;
  color: #92400e;
}

.preview-broadcast-info p {
  margin: 0;
  font-size: 9px;
  color: #92400e;
  line-height: 1.3;
}

/* Awareness Dashboard */
.preview-participants-status-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-participant-status-card {
  padding: 6px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
}

.preview-participant-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.preview-participant-stats {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.preview-stats-row {
  display: flex;
  gap: 8px;
}

.preview-stats-row .preview-component-module {
  flex: 1;
  margin-bottom: 0;
}

.preview-progress-container {
  width: 100%;
}

.preview-progress-label {
  font-size: 9px;
  color: #6b7280;
  margin-bottom: 2px;
}

.preview-progress-bar {
  height: 4px;
  background: #e5e7eb;
  border-radius: 2px;
  overflow: hidden;
}

.preview-progress-fill {
  height: 100%;
  background: #3b82f6;
  transition: width 0.3s ease;
}


.setup-tab-panel.active {
  border-color: #2563eb;
}

.initial-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 400px;
}

.initial-message {
  text-align: center;
  max-width: 400px;
}

.initial-message h2 {
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 32px;
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

.workflow-step {
  margin: 0 auto;
}

.step-content {
  background: #ffffff;
  padding: 24px;
}

.step-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 2px solid #e5e7eb;
}

.step-title-row .step-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
  padding: 0;
  border: none;
}

.step-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 2px solid #e5e7eb;
}

.step-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
}

.step-btn {
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.step-btn.primary {
  background: #2563eb;
  color: #ffffff;
}

.step-btn.primary:hover:not(:disabled) {
  background: #1d4ed8;
  transform: translateY(-1px);
}

.step-btn.secondary {
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}

.step-btn.secondary:hover:not(:disabled) {
  background: #e5e7eb;
  border-color: #9ca3af;
}

.step-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.tab-content-grid.session-mode {
  grid-template-columns: 1fr 1fr;
}

.tab-col {
  display: flex;
  flex-direction: column;
  min-height: 0; /* so col-body can flex */
  overflow: hidden; /* Prevent column from scrolling */
}

.block-title {
  font-weight: 700;
  color: #111827;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.online-indicator {
  font-size: 12px;
  font-weight: 500;
  color: #059669;
  background: #d1fae5;
  padding: 2px 8px;
  border-radius: 12px;
  border: 1px solid #a7f3d0;
}

.indicators {
  display: flex;
  gap: 6px;
  align-items: center;
}

.online-indicator.pending {
  color: #d97706;
  background: #fef3c7;
  border-color: #fbbf24;
}

/* Column bodies should scroll internally and show borders */
.col-body {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px; /* Reduced from 20px */
  flex: 1;
  overflow-y: auto; /* enable vertical scrolling */
  overflow-x: hidden; /* prevent horizontal scrolling */
  min-height: 0;
  display: flex; /* Added to make content fill height */
  flex-direction: column; /* Added to stack content vertically */
  scrollbar-width: thin; /* Firefox */
  scrollbar-color: #cbd5e1 #f1f5f9; /* Firefox */
}

/* Custom scrollbar for WebKit browsers */
.col-body::-webkit-scrollbar {
  width: 6px;
}

.col-body::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.col-body::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.col-body::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.placeholder {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  border: 2px dashed #e5e7eb;
  border-radius: 8px;
}

/* Metrics */
.metrics {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.metric {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px 10px;
}

.metric .label {
  color: #6b7280;
}

.metric .value {
  font-weight: 700;
  color: #111827;
}

/* Config section (reusing styles with tweaks) */
.config-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px; /* Space for scrollbar */
}

.config-section h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #374151;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.config-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.config-group label {
  font-size: 10px;
  color: #6b7280;
  display: flex;
  align-items: center;
  gap: 4px;
}

.tooltip-icon {
  color: #6b7280;
  font-size: 12px;
  cursor: help;
  opacity: 0.7;
  transition: opacity 0.15s ease;
}

.tooltip-icon:hover {
  opacity: 1;
}

.config-group input, .config-group .config-select {
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  width: 100%;
  font-size: 14px;
}

.config-group .config-select {
  background: #ffffff;
  cursor: pointer;
}

.config-group .config-select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

/* Config clusters */
.config-cluster { margin-bottom: 20px; }
.cluster-title { font-weight: 700; margin-bottom: 12px; color: #111827; padding-bottom: 8px; border-bottom: 1px solid #e5e7eb; }

/* Collapsible cluster titles */
.cluster-title.collapsible {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s ease;
  padding: 8px 12px;
  margin: -8px -12px 12px -12px;
  border-radius: 6px;
}

.cluster-title.collapsible:hover {
  background-color: #f3f4f6;
}

.collapse-icon {
  font-size: 12px;
  transition: transform 0.2s ease;
  color: #6b7280;
}

.collapse-icon.expanded {
  transform: rotate(180deg);
}

/* Export */
.export-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 20px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.export-btn {
  padding: 12px 20px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}

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

.form-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px; /* Further reduced from 8px */
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
  width: 100%;
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

.btn {
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
  overflow: hidden; /* Prevent table from scrolling */
}

.table-body {
  flex: 1; /* Added to make table body fill remaining space */
  overflow-y: auto; /* Added scroll if needed */
  overflow-x: hidden; /* Prevent horizontal scrolling */
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
  grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
  gap: 6px; /* Further reduced from 8px */
  align-items: center;
}

.table-head {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
  gap: 6px;
  align-items: center;
  background: #f8fafc;
  padding: 8px 10px;
  font-weight: 600;
  font-size: 11px;
  color: #374151;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.th {
  font-weight: 600;
  font-size: 11px;
  color: #374151;
}

.table-body .tr {
  padding: 6px 10px; /* Further reduced from 8px 12px */
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
}

.td.type {
  font-size: 10px; /* Reduced from 11px */
  justify-content: flex-start;
}

.td.specialty {
  font-size: 10px; /* Reduced from 11px */
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
  display: flex;
  flex-direction: row;
}

/* Icon button styling */
.btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px; /* Further reduced from 28px */
  height: 24px; /* Further reduced from 28px */
  border: none;
  border-radius: 4px; /* Reduced from 5px */
  cursor: pointer;
  transition: all 0.15s ease;
  background: transparent;
  color: #6b7280;
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
.manage-table .select {
  padding: 4px 5px; /* Further reduced from 5px 6px */
  font-size: 10px; /* Reduced from 11px */
  border: 1px solid #d1d5db;
  border-radius: 3px; /* Reduced from 4px */
  background: #ffffff;
  min-width: 0;
  width: 100%;
}

.manage-table .select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

/* Information Flow Section */
.information-flow-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

/* Action Structures Section */
.action-structures-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

/* Agent Behaviors Section */
.agent-behaviors-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.card-title {
  color: #1f2937c4;
  font-size: 12px;
  margin-bottom: 6px;
  font-weight: 600;
}

/* Section Titles */
.section-title {
  font-weight: 800;
  color: #1f2937a6;
  font-size: 14px;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
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
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
}

.section-container {
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid #e5e7eb;
}

.section-container:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.section-container .section-title {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: #374151;
  padding-bottom: 8px;
}

.input-group {
  display: flex;
  gap: 8px;
}

.input-group .form-input {
  flex: 1;
}

.empty-group {
  color: #6b7280;
  font-style: italic;
  padding: 8px 0;
  text-align: center;
}

.groups-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.group-item {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  background: #f9fafb;
}

.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.group-name {
  font-weight: 600;
  color: #374151;
}

.group-participants {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.participant-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #3b82f6;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.remove-btn {
  background: none;
  border: none;
  color: white;
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 2px;
}

.remove-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.form-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.participants-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  padding: 8px;
  background: #f9fafb;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.checkbox-label:hover {
  background: #e5e7eb;
}

.checkbox-label input[type="checkbox"] {
  margin: 0;
}

/* Interaction Variables */
.interaction-variables {
  display: flex;
  flex-direction: column;
  gap: 12px; /* Reduced from 16px */
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px; /* Space for scrollbar */
}

.communication-mode-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px; /* Reduced from 12px */
  padding: 6px 10px; /* Reduced from 8px 12px */
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.mode-badge {
  padding: 3px 6px; /* Reduced from 4px 8px */
  border-radius: 10px; /* Reduced from 12px */
  font-size: 11px; /* Reduced from 12px */
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.mode-badge.chat {
  background: #dbeafe;
  color: #1e40af;
}

.mode-badge.broadcast {
  background: #fef3c7;
  color: #d97706;
}

.mode-badge.no_chat {
  background: #f3f4f6;
  color: #374151;
}

.mode-description {
  font-size: 11px; /* Reduced from 12px */
  color: #6b7280;
  flex-grow: 1;
  text-align: right;
}

.variable-group {
  display: flex;
  flex-direction: column;
  gap: 4px; /* Reduced from 6px */
}

.variable-group label {
  font-size: 13px; /* Reduced from 14px */
  font-weight: 600;
  color: #374151;
}

.variable-group .select {
  padding: 8px 10px; /* Reduced from 10px 12px */
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #ffffff;
  font-size: 13px; /* Reduced from 14px */
}

.variable-group .select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

/* Responsive */
@media (max-width: 1200px) {
  .tab-content-grid, .tab-header-row {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 640px) {
  .tab-content-grid, .tab-header-row {
    grid-template-columns: 1fr;
  }
  
  /* Ensure proper scrolling on mobile */
  .researcher-container {
    padding: 10px;
  }
  
  .col-body {
    padding: 12px;
  }
}

@media (max-width: 900px) {
  .manage-forms { grid-template-columns: 1fr; }
  .table-head, .tr { grid-template-columns: 1fr 1fr 1fr 1fr; }
  .th.assign, .td.assign, .th.type, .td.type { display: none; }
}

/* Ensure minimum height for better scrolling experience */
@media (max-height: 600px) {
  .researcher-container {
    padding: 10px;
  }
  
  .top-controls {
    margin-bottom: 10px;
    padding: 8px 15px;
  }
  
  .tab-header-row {
    margin-bottom: 0;
  }
  
  .tab-group-card {
    padding: 12px;
  }
  
  .col-body {
    padding: 12px;
  }
}

.table-section {
  margin-top: 8px; /* Further reduced from 12px */
  flex: 1; /* Added to make table section expand and fill remaining space */
  min-height: 0; /* Added to allow proper flex behavior */
  display: flex; /* Added to make table fill available space */
  flex-direction: column; /* Added to stack table elements vertically */
  overflow: hidden; /* Prevent section from scrolling */
}

.table-title {
  font-weight: 700;
  color: #111827;
  margin-bottom: 6px; /* Further reduced from 8px */
  font-size: 14px; /* Reduced from 15px */
  flex-shrink: 0; /* Prevent title from shrinking */
}

/* Session Registration Styles */
.register-button-container {
  display: flex;
  flex-direction: column;
  gap: 4px; /* Further reduced from 6px */
  margin-top: 6px; /* Further reduced from 8px */
}

.register-session-btn {
  padding: 6px 12px; /* Further reduced from 8px 14px */
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 4px; /* Reduced from 6px */
  cursor: pointer;
  font-size: 12px; /* Reduced from 13px */
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px; /* Further reduced from 6px */
  margin-left: auto;
  width: 100%;
}

.register-session-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.register-session-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.registration-message {
  padding: 6px 8px; /* Further reduced from 8px 10px */
  border-radius: 4px; /* Reduced from 6px */
  font-size: 11px; /* Reduced from 12px */
  font-weight: 600;
  text-align: center;
}

.registration-message.success {
  background-color: #d1fae5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}

.registration-message.error {
  background-color: #fef3c7;
  color: #d97706;
  border: 1px solid #fbbf24;
}

.session-settings-section {
  display: flex;
  flex-direction: column;
  gap: 8px; /* Further reduced from 12px */
  flex-shrink: 0; /* Prevent session settings from shrinking */
}

.session-status-message {
  padding: 6px 8px; /* Further reduced from 8px 10px */
  border-radius: 4px; /* Reduced from 6px */
  font-size: 11px; /* Reduced from 12px */
  font-weight: 600;
  text-align: center;
}

.session-status-message.success {
  background-color: #d1fae5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}

.session-status-message.error {
  background-color: #fef3c7;
  color: #d97706;
  border: 1px solid #fbbf24;
}

.session-status-message.info {
  background-color: #dbeafe;
  color: #1e40af;
  border: 1px solid #93c5fd;
}

.form-helper {
  font-size: 10px; /* Reduced from 11px */
  color: #d97706;
  text-align: center;
}

/* Session Management Styles */
.session-buttons {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.session-buttons .btn {
  flex: 1;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
}

.current-session-info {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  margin-top: 12px;
}

.session-info-header {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.session-info-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-id {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
}

.session-status {
  font-size: 12px;
  color: #6b7280;
}

/* Modal Form Styles */
.create-session-form,
.load-session-form,
.load-template-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.session-type-selector {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 8px 0px;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.radio-label:hover {
  background-color: #f9fafb;
  border-color: #9ca3af;
}

.radio-label:has(.radio-input:checked) {
  background-color: #eff6ff;
  border-color: #2563eb;
}

.radio-input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.radio-text {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
}

.checkbox-input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.session-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px; /* Further reduced from 3px */
}

.session-info.no-session {
  opacity: 0.7;
}

.session-label {
  font-size: 12px; /* Reduced from 11px */
  font-weight: 600;
  color: #6b7280;
}

.session-code {
  font-size: 14px; /* Reduced from 13px */
  font-weight: 700;
  color: #111827;
}

/* Custom Select Styles */
.custom-select-wrapper {
  position: relative;
  display: inline-block;
  width: 100%;
}

.custom-select-trigger {
  background: #ffffff;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 4px 4px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.custom-select-trigger:hover {
  border-color: #9ca3af;
}

.custom-select-trigger:focus-within {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.selected-option {
  font-weight: 600;
  flex: 1;
  display: flex;
  align-items: center;
}

.selected-content {
  display: flex;
  flex-direction: row;
  align-items: center;
  flex: 1;
  gap: 8px;
}

.communication-description {
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.4;
}

.option-content {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

.option-description {
  font-size: 10px;
  color: #6b7280;
  font-weight: normal;
  text-transform: none;
  letter-spacing: normal;
}

.dropdown-arrow {
  font-size: 10px;
  color: #6b7280;
  transition: transform 0.15s ease;
  margin-left: 8px;
  flex-shrink: 0;
}

.custom-select-wrapper:has(.custom-dropdown-menu) .dropdown-arrow {
  transform: rotate(180deg);
}

.custom-dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: #ffffff;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  z-index: 10;
  margin-top: 2px;
}

.dropdown-item {
  padding: 8px 12px;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.dropdown-item:hover {
  background-color: #f9fafb;
}

/* Tag styles for communication options */
.selected-option.chat,
.option-tag.chat {
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

.selected-option.broadcast,
.option-tag.broadcast {
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

/* Edit Participant Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
  width: 400px;
  max-width: 90vw;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
}
.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.modal-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #6b7280;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.15s ease;
}

.modal-close:hover {
  background-color: #f3f4f6;
  color: #374151;
}

.modal-body {
  padding: 24px;
}

.edit-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
  width: 100%;
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

.form-help {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid #e5e7eb;
  background-color: #f9fafb;
  border-bottom-left-radius: 12px;
  border-bottom-right-radius: 12px;
}

.btn {
  padding: 10px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn.secondary {
  background-color: #f3f4f6;
  color: #374151;
}

.btn.secondary:hover {
  background-color: #e5e7eb;
}

.btn.primary {
  background-color: #2563eb;
  color: #fff;
}

.btn.primary:hover:not(:disabled) {
  background-color: #1d4ed8;
}

.btn.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.tooltip-icon:hover {
  opacity: 1;
}

.custom-tooltip {
  position: fixed;
  background: #1f2937;
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  max-width: 250px;
  z-index: 1000;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  white-space: normal;
  line-height: 1.4;
  pointer-events: none;
}

.config-group {
  position: relative;
}

/* Template Selection Styles */
.template-selection-container {
  display: flex;
  align-items: center;
  gap: 8px;
}

.template-selection-container .form-select {
  flex: 1;
}

.delete-template-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  color: #ef4444;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
}

.delete-template-btn:hover {
  background: #fef2f2;
  border-color: #ef4444;
  color: #dc2626;
  transform: scale(1.05);
}

.delete-template-btn:active {
  transform: scale(0.95);
}

/* Export Form Styles */
.export-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.export-form .form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.export-form .form-group label {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.export-form .form-group .select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #ffffff;
  font-size: 14px;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.export-form .form-group .select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.export-form .form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.export-form .form-actions .btn {
  padding: 12px 24px;
  font-size: 14px;
  font-weight: 600;
}

.export-form .form-helper {
  font-size: 12px;
  color: #d97706;
  text-align: center;
  padding: 8px;
  background: #fef3c7;
  border: 1px solid #fbbf24;
  border-radius: 6px;
}

/* Behavioral Logs Styles */
.behavioral-logs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  height: 100%;
  overflow: hidden;
}

.left-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f1f5f9;
}

.left-column::-webkit-scrollbar {
  width: 6px;
}

.left-column::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.left-column::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.left-column::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.right-column {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.controls-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.control-group label {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.checkbox-group {
  display: flex;
  gap: 16px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox-input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.checkbox-text {
  font-size: 14px;
  color: #374151;
}

.participant-checkbox {
  width: 14px;
  height: 14px;
  margin-right: 8px;
}

.participant-name {
  font-size: 13px;
  color: #374151;
}

.statistics-section {
  padding: 16px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f1f5f9;
}

.statistics-section .section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.refresh-btn {
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 14px;
  transition: all 0.15s ease;
}

.refresh-btn:hover:not(:disabled) {
  background: #f3f4f6;
  color: #374151;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-message {
  text-align: center;
  color: #6b7280;
  font-style: italic;
  padding: 20px;
}

.no-data-message {
  text-align: center;
  color: #9ca3af;
  font-style: italic;
  padding: 20px;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px dashed #d1d5db;
}

.statistics-section::-webkit-scrollbar {
  width: 6px;
}

.statistics-section::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.statistics-section::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.statistics-section::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.stats-container {
  margin-top: 12px;
  padding-bottom: 8px;
}

.stats-category {
  margin-bottom: 12px;
}

.category-header {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  background: #f0f5fe;
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 8px;
  border-left: 3px solid #3b82f6;
}

.stats-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 6px 12px;
  background: #f9fafb;
  border-radius: 4px;
  border: 1px solid #e5e7eb;
  min-height: 60px;
  justify-content: space-between;
}

.stat-label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
  margin-bottom: 4px;
  line-height: 1.2;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  line-height: 1.2;
}

.charts-section {
  padding: 16px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.charts-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-top: 12px;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f1f5f9;
  /* Ensure the grid takes up the available space */
  height: calc(100vh - 400px);
  min-height: 400px;
}

.charts-grid::-webkit-scrollbar {
  width: 6px;
}

.charts-grid::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.charts-grid::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.charts-grid::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.chart-container {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px 16px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  /* Flexible height that adapts to content */
  min-height: 250px;
  flex: 1;
  flex-shrink: 0;
  /* Add smooth transitions for responsive changes */
  transition: all 0.3s ease;
}

.chart-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: 700;
  color: #111827;
  margin-bottom: 12px;
  border-bottom: 2px solid #f3f4f6;
  padding-bottom: 8px;
}

.chart-title-text {
  flex: 1;
}

.chart-legend {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #6b7280;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 6px;
}

.legend-color.completed {
  background: linear-gradient(90deg, #3b82f6, #1d4ed8);
}

.legend-color.pending {
  background: linear-gradient(90deg, #f59e0b, #d97706);
}

.chart-placeholder {
  flex: 1;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  position: relative;
  overflow: visible;
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.google-chart-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 220px;
  padding: 8px;
  box-sizing: border-box;
}

.google-chart {
  width: 100%;
  height: 200px;
  overflow: hidden;
}

.chart-no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

/* Custom timeline chart styles */
.timeline-container {
  width: 100%;
  height: 100%;
  padding: 4px 16px 4px 40px; /* Added left padding for y-axis label */
  display: flex;
  flex-direction: column;
  position: relative;
}

/* Y-axis label */
.y-axis-label {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  text-align: center;
  margin-bottom: 8px;
  transform: rotate(-90deg);
  width: 20px;
  margin-left: 15px;
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%) rotate(-90deg);
}

.timeline-rows {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px; /* Minimal gap between rows */
}

.timeline-row {
  display: flex;
  align-items: center;
  height: 20px; /* Reduced row height */
}

.participant-label {
  width: 60px; /* Increased width for better spacing */
  font-weight: 500;
  color: #374151;
  text-align: right;
  padding-right: 12px;
  flex-shrink: 0;
  font-size: 11px; /* Smaller font */
}

.timeline-bars {
  flex: 1;
  height: 16px; /* Reduced height */
  position: relative;
  border-left: 2px solid #e5e7eb; /* Left line for row bars */
  padding-left: 8px;
}

.timeline-bar {
  position: absolute;
  height: 14px; /* Adjusted bar height */
  top: 1px; /* Center the bar */
  background: linear-gradient(90deg, #3b82f6, #1d4ed8);
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 30px;
}

.timeline-bar:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.timeline-bar.completed {
  background: linear-gradient(90deg, #3b82f6, #1d4ed8);
  height: 14px; /* Full height for completed trades */
}

.timeline-bar.pending {
  background: linear-gradient(90deg, #f59e0b, #d97706);
  border: 2px solid #d97706;
  box-shadow: 0 0 4px rgba(217, 119, 6, 0.6);
  animation: pulse 2s infinite;
  height: 14px; /* Same height as completed trades for consistency */
  border-radius: 2px; /* Rounded corners for pending trades */
}

@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
  100% {
    opacity: 1;
  }
}

/* X-axis at the bottom */
.timeline-x-axis {
  width: 100%;
  padding-left: 50px; /* Align with participant labels */
  padding-right: 16px;
  margin-top: 4px;
}

.x-axis-label {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  text-align: center;
  margin-top: 3px;
}

.x-axis-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px; /* Smaller font */
  color: #6b7280;
  font-weight: 500;
}

.x-label {
  position: relative;
}

/* Timeline tooltip styles */
.timeline-tooltip {
  position: fixed;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.9);
  color: white;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  max-width: 250px;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.tooltip-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: #fbbf24;
}

.tooltip-content {
  line-height: 1.4;
  color: #e5e7eb;
}

/* No data selected message */
.no-data-selected {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-top: 20px;
}

.no-data-selected .no-data-message {
  text-align: center;
  color: #6b7280;
}

.no-data-selected .no-data-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.no-data-selected .no-data-text {
  font-size: 16px;
  font-weight: 500;
}

/* Essay Upload Styles */
.essay-upload-section {
  margin-top: 20px;
  padding: 20px;
  border: 2px dashed #d1d5db;
  border-radius: 8px;
  background-color: #f9fafb;
}

.essay-upload-section.full-width {
  width: 100%;
  grid-column: 1 / -1; /* Span all columns in the grid */
}

.essay-upload-container {
  margin-bottom: 20px;
}

.upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.upload-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #2563eb, #1e40af);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.upload-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.uploaded-essays-list {
  margin-top: 20px;
}

.uploaded-essays-list h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #374151;
}

.essay-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  margin-bottom: 8px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.essay-item:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.1);
}

.essay-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.essay-info i {
  color: #dc2626;
  font-size: 18px;
}

.essay-title {
  font-weight: 500;
  color: #374151;
}

.essay-filename {
  color: #6b7280;
  font-size: 14px;
}

.remove-essay-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  min-width: 28px;
  min-height: 28px;
  background: #fee2e2;
  color: #dc2626;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
  font-size: 12px;
}

.remove-essay-btn:hover {
  background: #fecaca;
  transform: scale(1.1);
}

.remove-essay-btn i {
  font-size: 12px;
  line-height: 1;
}
</style> 