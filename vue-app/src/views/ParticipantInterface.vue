<template>
  <div class="participant-container">
    <!-- ECL Interface (if experiment is ECL-based) -->
    <div v-if="isECLExperiment" class="ecl-interface-wrapper">
      <!-- ECL Header -->
      <header class="header-row">
        <div class="header-left">
          <span class="session-label">Session ID: <span>{{ sessionId }}</span></span>
          <button @click="showRulesPopup" class="rules-btn">Rules</button>
        </div>
        <div class="header-center">
          <span class="timer-display">{{ timerDisplay }}</span>
          <div class="session-status-indicator" :class="sessionStatus">
            <span class="status-text">{{ sessionStatusMessage }}</span>
          </div>
        </div>
        <div class="header-right">
          <button @click="logout" class="login-toggle-btn">Logout</button>
        </div>
      </header>

      <!-- ECL Rules Popup -->
      <div v-show="showRules" class="rules-popup" @click="hideRulesIfClickedOutside">
        <div class="rules-popup-content">
          <div class="rules-popup-header">
            <h3>{{ eclConfig.experiment?.title || 'Experiment Rules' }}</h3>
            <button @click="hideRulesPopup" class="close-rules-btn">×</button>
          </div>
          <div class="rules-popup-body">
            <p><strong>Description:</strong> {{ eclConfig.experiment?.description || 'No description available.' }}</p>
            <div v-if="eclConfig.experiment?.timing">
              <p><strong>Duration:</strong> {{ eclConfig.experiment.timing.session_duration_minutes }} minutes</p>
            </div>
            <div v-if="eclConfig.actions">
              <p><strong>Available Actions:</strong></p>
              <ul>
                <li v-for="(action, name) in eclConfig.actions" :key="name">
                  <strong>{{ name }}:</strong> {{ action.description || 'No description available' }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- ECL Session Status Overlay -->
      <Transition name="session-overlay" mode="out-in">
        <div v-if="!isSessionActive" class="session-overlay" key="session-overlay">
          <div class="session-overlay-content">
            <div class="session-overlay-icon">⏸️</div>
            <h3>{{ sessionStatusMessage }}</h3>
            <p v-if="stableSessionStatus === 'completed' || stableSessionStatus === 'stopped' || stableSessionStatus === 'ended'">
              The session has ended. Thank you for participating!
            </p>
            <p v-else>
              Please wait for the researcher to start the session.
            </p>
            
            <div v-if="stableSessionStatus === 'completed' || stableSessionStatus === 'ended'" class="session-overlay-actions">
              <button @click="returnToLogin" class="return-to-login-btn">
                Return to Login
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- ECL Main Content with Same Layout as Participant Interface -->
      <Transition name="content-disabled" mode="out-in">
        <div class="main-content" :class="{ 'disabled-content': !isSessionActive }" key="main-content">
          <!-- LEFT COLUMN: ECL STATUS + ACTION -->
          <div class="column column-left">
            <div class="left-sub-column">
              <!-- ECL My Status Panel -->
              <div class="panel player-status-panel">
                <h3 class="panel-header">My Status</h3>
                <div class="panel-body">
                  <div v-for="component in eclMyStatusComponents" :key="component.label" class="wealth-display">
                    <div class="component-module">
                      <span class="component-text">{{ component.label }}:</span>
                      <span class="component-num">{{ getECLValue(component.path) }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- ECL My Action Panel -->
              <div class="panel factory-panel">
                <h3 class="panel-header">My Action</h3>
                <div class="panel-body">
                  <div v-for="component in eclMyActionComponents" :key="component.label || component.bind_to">
                    <!-- Select Input Component -->
                    <div v-if="component.control === 'select'" class="factory-info">
                      <label class="component-text">{{ component.label }}</label>
                      <select 
                        v-model="eclLocalState[component.bind_to.replace('$local.', '')]" 
                        class="production-dropdown"
                        :disabled="!isSessionActive"
                      >
                        <option v-for="option in component.options" :key="option" :value="option">
                          {{ option }}
                        </option>
                      </select>
                    </div>

                    <!-- Segmented Control Component -->
                    <div v-else-if="component.control === 'segmented'" class="factory-info">
                      <label class="component-text">{{ component.label }}</label>
                      <div class="segmented-control">
                        <button 
                          v-for="option in component.options" 
                          :key="option"
                          type="button" 
                          :class="{ active: eclLocalState[component.bind_to.replace('$local.', '')] === option }" 
                          @click="eclLocalState[component.bind_to.replace('$local.', '')] = option"
                          :disabled="!isSessionActive"
                          class="btn secondary"
                        >
                          {{ option }}
                        </button>
                      </div>
                    </div>

                    <!-- Number Input Component -->
                    <div v-else-if="component.control === 'number'" class="factory-info">
                      <label class="component-text">{{ component.label }}</label>
                      <input 
                        v-model.number="eclLocalState[component.bind_to.replace('$local.', '')]"
                        type="number"
                        :min="component.min || 0"
                        :max="component.max || 100"
                        :step="component.step || 1"
                        class="production-dropdown"
                        :disabled="!isSessionActive"
                      />
                    </div>

                    <!-- Action Button Component -->
                    <div v-else-if="component.action" class="factory-info">
                      <button 
                        type="button" 
                        @click="executeECLAction(component.action, component.inputs)"
                        class="btn primary"
                        :disabled="!isSessionActive"
                      >
                        {{ component.label }}
                      </button>
                    </div>

                    <!-- Display Component -->
                    <div v-else-if="component.path" class="wealth-display">
                      <div class="component-module">
                        <span class="component-text">{{ component.label }}:</span>
                        <span class="component-num">{{ getECLValue(component.path) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- RIGHT COLUMN: ECL SOCIAL PANEL (reuse existing structure) -->
          <div class="column column-right">
            <!-- Social Navigation Panel -->
            <div class="panel social-panel">
              <h3 class="panel-header">Social</h3>
              <div class="panel-body">
                <div class="component-list">
                  <div 
                    v-for="participant in otherParticipants" 
                    :key="participant.participant_id"
                    class="component-list-item"
                    :class="{ selected: selectedPlayer?.participant_id === participant.participant_id }"
                    @click="selectPlayer(participant)"
                  >
                    <div class="player-info">
                      <div class="component-text">
                        <span v-if="hasUnreadMessagesFromParticipant(participant.participant_id)" class="unread-dot message-dot"></span>
                        <span v-if="hasUnreadTradesFromParticipant(participant.participant_id)" class="unread-dot trade-dot"></span>
                        {{ participant.participant_id }}
                      </div>
                    </div>
                  </div>
                  <div v-if="!otherParticipants.length" class="empty">
                    No other players
                  </div>
                </div>
              </div>
            </div>

            <!-- Unified Interaction Panel (reuse existing structure) -->
            <div class="panel interaction-panel">
              <!-- Broadcast mode: show broadcast UI with messaging capability -->
              <template v-if="isBroadcastMode">
                <div class="broadcast-mode">
                  <!-- Broadcast Mode Header with Tabs -->
                  <div class="interaction-header">
                    <h3>Broadcast Mode</h3>
                    <div class="interaction-tabs">
                      <button 
                        v-if="eclMessageTabEnabled"
                        @click="currentTab = 'message'; markMessagesAsRead()" 
                        class="tab-btn" 
                        :class="{ active: currentTab === 'message', 'has-message-notifications': unreadBroadcastCount > 0 }"
                      >
                        Broadcast
                        <span v-if="unreadBroadcastCount > 0" class="unread-badge">{{ unreadBroadcastCount }}</span>
                      </button>
                    </div>
                  </div>

                  <!-- Message Interface Tab (reuse existing structure) -->
                  <div v-show="currentTab === 'message' && eclMessageTabEnabled" class="tab-content" data-tab="message">
                    <div class="message-history">
                      <div 
                        v-for="message in broadcastMessages" 
                        :key="message.id" 
                        class="message-item"
                      >
                        <div class="message-sender">{{ message.sender }}</div>
                        <div class="message-content">{{ message.content }}</div>
                        <div class="message-time">{{ formatMessageTime(message.timestamp) }}</div>
                      </div>
                      <div v-if="!broadcastMessages.length" class="empty">
                        No messages yet
                      </div>
                    </div>
                    
                    <div class="message-input-area">
                      <input 
                        v-model="newMessage" 
                        @keyup.enter="sendBroadcastMessage"
                        placeholder="Type your message..."
                        class="message-input"
                        :disabled="!isSessionActive"
                      />
                      <button @click="sendBroadcastMessage" class="send-btn" :disabled="!isSessionActive">Broadcast</button>
                    </div>
                  </div>
                </div>
              </template>
              
              <!-- Chat mode: require participant selection -->
              <div v-else-if="!selectedPlayer" class="no-selection">
                <h3>No Player Selected</h3>
                <p>Click on a player above to start messaging with them.</p>
              </div>
              
              <!-- Individual chat interface (reuse existing structure) -->
              <div v-else class="chat-mode">
                <div class="interaction-header">
                  <h3>{{ selectedPlayer.participant_id }}</h3>
                  <div class="interaction-tabs">
                    <button 
                      v-if="eclMessageTabEnabled"
                      @click="currentTab = 'message'; markMessagesAsRead()" 
                      class="tab-btn" 
                      :class="{ active: currentTab === 'message', 'has-message-notifications': hasUnreadMessagesFromParticipant(selectedPlayer.participant_id) }"
                    >
                      Message
                      <span v-if="hasUnreadMessagesFromParticipant(selectedPlayer.participant_id)" class="unread-badge">!</span>
                    </button>
                  </div>
                </div>

                <!-- Message Interface Tab -->
                <div v-show="currentTab === 'message' && eclMessageTabEnabled" class="tab-content" data-tab="message">
                  <div class="message-history">
                    <div 
                      v-for="message in messages" 
                      :key="message.id" 
                      class="message-item"
                      :class="{ 'my-message': message.sender === participantId, 'other-message': message.sender !== participantId }"
                    >
                      <div class="message-sender">{{ message.sender }}</div>
                      <div class="message-content">{{ message.content }}</div>
                      <div class="message-time">{{ formatMessageTime(message.timestamp) }}</div>
                    </div>
                    <div v-if="!messages.length" class="empty">
                      No messages yet
                    </div>
                  </div>
                  
                  <div class="message-input-area">
                    <input 
                      v-model="newMessage" 
                      @keyup.enter="sendMessage"
                      placeholder="Type your message..."
                      class="message-input"
                      :disabled="!isSessionActive"
                    />
                    <button @click="sendMessage" class="send-btn" :disabled="!isSessionActive">Send</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- AWARENESS DASHBOARD COLUMN (for ECL Information Dashboard) -->
          <div v-if="eclInfoDashboardEnabled" class="column column-awareness">
            <div class="panel awareness-panel">
              <h3 class="panel-header">Information Dashboard</h3>
              <div class="panel-body">
                <div v-for="component in eclInfoDashboardComponents" :key="component.label" class="wealth-display">
                  <div class="component-module">
                    <span class="component-text">{{ component.label }}:</span>
                    <span class="component-num">{{ getECLValue(component.path) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </div>
    
    <!-- Standard Shape Factory Interface (if not ECL or WordGuessing) -->
    <div v-else>

    <!-- HEADER ROW -->
    <header class="header-row">
      <div class="header-left">
        <span class="session-label">Session ID: <span>{{ sessionId }}</span></span>
        <button @click="showRulesPopup" class="rules-btn">Rules</button>
      </div>
      <div class="header-center">
        <span class="timer-display">{{ timerDisplay }}</span>
        <div class="session-status-indicator" :class="sessionStatus">
          <span class="status-text">{{ sessionStatusMessage }}</span>
        </div>
      </div>
      <div class="header-right">

        <button @click="logout" class="login-toggle-btn">Logout</button>
      </div>
    </header>

    <!-- RULES POPUP -->
    <div v-show="showRules" class="rules-popup" @click="hideRulesIfClickedOutside">
      <div class="rules-popup-content">
        <div class="rules-popup-header">
          <h3>Experiment Rules</h3>
          <button @click="hideRulesPopup" class="close-rules-btn">×</button>
        </div>
        <div class="rules-popup-body">
          <p><strong>Objective:</strong> Maximize your individual earnings by:<br>
&nbsp;&nbsp;&nbsp;&nbsp;<strong>Selling</strong> your specialty shape to others who need it.<br>
&nbsp;&nbsp;&nbsp;&nbsp;<strong>Buying</strong> other shapes to complete your assigned orders.
</p>
          <p><strong>Production:</strong> You can produce up to {{ gameState.experiment_config?.maxProductionNum || 6 }} shapes per round. Your specialty shape costs less to produce {{ productionCostComparison }}.</p>
          <p><strong>Trading:</strong> Negotiate with other players to exchange shapes you need. Prices range from ${{ gameState.experiment_config?.minTradePrice || 15 }}-${{ gameState.experiment_config?.maxTradePrice || 30 }}.</p>
          <p><strong>Orders:</strong> Check off completed orders and click "Fulfill" to earn money. Fulfilling one order earns you ${{ gameState.experiment_config?.orderReward || 25 }}.</p>
          <p><strong>Communication:</strong> Select a player from the Social panel to send messages or trade offers.</p>
        </div>
      </div>
    </div>

    <!-- ESSAY VIEWER MODAL -->
    <div v-show="showEssayViewer" class="essay-viewer-modal" @click="hideEssayViewerIfClickedOutside">
      <div class="essay-viewer-content">
        <div class="essay-viewer-header">
          <h3>{{ currentEssay?.title || 'Essay Viewer' }}</h3>
          <button @click="hideEssayViewer" class="close-essay-btn">×</button>
        </div>
        <div class="essay-viewer-body">
          <div v-if="currentEssay" class="essay-content">
            <div class="essay-info">
              <p><strong>Essay ID:</strong> {{ currentEssay.essay_id }}</p>
              <p><strong>Title:</strong> {{ currentEssay.title }}</p>
            </div>
            <div class="essay-actions">
              <button @click="downloadEssay" class="download-essay-btn">
                <i class="fa-solid fa-download"></i>
                Download Essay
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- SESSION STATUS OVERLAY -->
    <Transition name="session-overlay" mode="out-in">
      <div v-if="!isSessionActive" class="session-overlay" key="session-overlay">
        <div class="session-overlay-content">
          <div class="session-overlay-icon">⏸️</div>
          <h3>{{ sessionStatusMessage }}</h3>
          <p v-if="stableSessionStatus === 'completed' || stableSessionStatus === 'stopped' || stableSessionStatus === 'ended'">
            The session has ended. Thank you for participating!
          </p>
          <p v-else>
            Please wait for the researcher to start the session.
          </p>
          
          <!-- Return to Login Button (only show when session has ended) -->
          <div v-if="stableSessionStatus === 'completed' || stableSessionStatus === 'ended'" class="session-overlay-actions">
            <button @click="returnToLogin" class="return-to-login-btn">
              Return to Login
            </button>
          </div>
        </div>
      </div>
    </Transition>


    <!-- TWO COLUMN LAYOUT -->
    <Transition name="content-disabled" mode="out-in">
      <div class="main-content" :class="{ 'disabled-content': !isSessionActive }" key="main-content">
      <!-- LEFT COLUMN: STATUS + FACTORY + ORDERS (2-SUB-COLUMN LAYOUT) -->
      <div class="column column-left">
        <!-- LEFT SUB-COLUMN: Status + Factory -->
        <div class="left-sub-column">
          <!-- Player Status Panel -->
          <div class="panel player-status-panel">
            <h3 class="panel-header">My Status</h3>
            <div class="panel-body">
              <!-- Money Display (conditional) -->
              <div v-if="interfaceConfig.myStatus.showMoney" class="wealth-display">
                <div class="component-module">
                  <span class="component-text">My Wealth:</span>
                  <span class="component-num">${{ participantMoney }}</span>
                </div>
              </div>
              
              <!-- Inventory Section (conditional) -->
              <div v-if="interfaceConfig.myStatus.showInventory || interfaceConfig.myAction.type === 'essayranking' || (isWordGuessingExperiment && isHinter)" class="inventory-section">
                <h4 class="component-text">
                  {{ interfaceConfig.myAction.type === 'essayranking' ? 'Available Essays:' : (isWordGuessingExperiment ? 'My Words:' : 'My Inventory:') }}
                </h4>
                
                <!-- Essay Inventory (for essay ranking experiments) -->
                <div v-if="interfaceConfig.myAction.type === 'essayranking'" class="component-list">
                  <div 
                    v-for="essay in assignedEssays" 
                    :key="essay.essay_id"
                    class="component-list-item"
                    @click="viewEssay(essay)"
                    :class="{ 'selected': selectedEssay === essay.essay_id }"
                  >
                    <div class="component-text">
                      <i class="fa-solid fa-file-pdf" style="color: #dc2626; margin-right: 8px;"></i>
                      <span>{{ essay.title }}</span>
                    </div>
                  </div>
                  <div v-if="assignedEssays.length === 0" class="empty">
                    No essays assigned yet
                  </div>
                </div>
                
                <!-- WordGuessing Words (for wordguessing experiments) -->
                <div v-else-if="isWordGuessingExperiment" class="component-list">
                  <div 
                    v-for="(word, index) in assignedWords" 
                    :key="index" 
                    class="component-list-item"
                  >
                    <div class="component-text">
                      <span style="color: #059669; font-weight: bold;">{{ word }}</span>
                    </div>
                  </div>
                  <div v-if="assignedWords.length === 0" class="empty">
                    No words assigned yet
                  </div>
                </div>
                
                <!-- Shape Inventory (for other experiments) -->
                <div v-else class="component-list">
                  <div 
                    v-for="shape in gameState.participant?.shapes_acquired || []" 
                    :key="shape" 
                    class="component-list-item"
                  >
                    <div class="component-text">
                      <span :class="getShapeIcon(shape)" :style="shape === 'triangle' ? { borderBottomColor: getShapeColor(shape) } : { backgroundColor: getShapeColor(shape) }"></span>
                      <span>{{ getShapeDisplayName(shape) }}</span>
                    </div>
                  </div>
                  <div v-if="!gameState.participant?.shapes_acquired?.length" class="empty">
                    No shapes in inventory
                  </div>
                </div>
              </div>
              
            </div>
          </div>

          <!-- My Action Panel -->
          <div v-if="interfaceConfig.myAction.type !== 'disabled'" class="panel factory-panel">
            <h3 class="panel-header">My Action</h3>
            <div class="panel-body">
              <!-- DayTrader Action Form -->
              <div v-if="interfaceConfig.myAction.type === 'daytrader'" class="daytrader-action">
                <div class="trade-form">
                  <div class="trade-sentence">
                    <p class="sentence-builder">
                      I want to invest at 
                      $<input 
                        type="number" 
                        v-model="tradePrice" 
                        class="inline-input" 
                        :placeholder="String(gameState.experiment_config?.minTradePrice || 22)" 
                        :min="String(gameState.experiment_config?.minTradePrice || 15)" 
                        :max="String(gameState.experiment_config?.maxTradePrice || 30)"
                        :disabled="!isSessionActive"
                      > 
                      as a 
                      <select v-model="decisionType" class="inline-select" :disabled="!isSessionActive">
                        <option value="individual">individual</option>
                        <option value="group">group</option>
                      </select>
                      decision.
                    </p>
                  </div>
                  <button @click="proposeTradeOffer" class="propose-btn" :disabled="!isSessionActive">Send Trade Offer</button>
                </div>
                
                <!-- Investment History -->
                <div class="investment-history" style="margin-top: 20px;">
                  <h4 style="margin-bottom: 10px; color: #333;">Investment History</h4>
                  <div class="history-list" style="max-height: 200px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px; padding: 10px;">
                    <div v-if="investmentHistory.length === 0" style="color: #666; font-style: italic;">
                      No investments made yet
                    </div>
                    <div v-for="(investment, index) in investmentHistory" :key="index" 
                         style="padding: 8px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
                      <div>
                        <span style="font-weight: bold;">${{ investment.price }}</span>
                        <span style="color: #666; margin-left: 10px;">({{ investment.decision_type }})</span>
                      </div>
                      <div style="color: #666; font-size: 12px;">
                        {{ formatTimestamp(investment.timestamp) }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Essay Ranking Action Forms -->
              <div v-else-if="interfaceConfig.myAction.type === 'essayranking'" class="essay-ranking-action">
                <div class="factory-info">
                  <span class="component-text">Select Essay to Rank</span>
                </div>
                <div class="production-controls">
                  <label for="essay-dropdown">Select essay:</label>
                  <div class="controls-row">
                    <select v-model="selectedEssay" class="production-dropdown">
                      <option value="">Choose an essay...</option>
                      <option v-for="essay in assignedEssays" :key="essay.essay_id" :value="essay.essay_id">
                        {{ essay.title }}
                      </option>
                    </select>
                  </div>
                  <div class="ranking-input-row">
                    <label for="ranking-input">Enter ranking:</label>
                    <div class="ranking-controls">
                      <input v-model="rankingInput" type="text" class="inline-input" placeholder="Enter ranking">
                      <button @click="confirmRanking" class="btn primary">Confirm</button>
                    </div>
                  </div>
                </div>
                
                <!-- Current Rankings Display -->
                <div class="current-rankings-section">
                  <h4 class="component-text">My Current Rankingsst </h4>
                  <div class="component-list">
                    <div 
                      v-for="ranking in sortedCurrentRankings" 
                      :key="ranking.essay_id"
                      class="component-list-item"
                    >
                      <div class="component-text">
                        <span class="essay-title">{{ getEssayTitle(ranking.essay_id) }}</span>
                      </div>
                    </div>
                    <div v-if="!gameState.participant?.current_rankings?.length" class="component-list-item">
                      <div class="component-text">
                        <span style="color: #9ca3af;">No rankings</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Shape Factory Action Forms -->
              <div v-else-if="interfaceConfig.myAction.type === 'shapefactory'">
                <!-- Factory Info (only for Shape Factory) -->
                <div class="factory-info">
                  <div class="component-module">
                    <span class="component-text">My Specialty:</span>
                    <div class="component-text">
                      <span :class="getShapeIcon(gameState.participant?.shape || '')" :style="(gameState.participant?.shape || '') === 'triangle' ? { borderBottomColor: getShapeColor(gameState.participant?.shape || '') } : { backgroundColor: getShapeColor(gameState.participant?.shape || '') }"></span>
                      <span>{{ getShapeDisplayName(gameState.participant?.shape || '') }}</span>
                    </div>
                  </div>
                </div>

                <!-- Production Controls (only for Shape Factory) -->
                <div v-if="interfaceConfig.myAction.showProductionForm" class="production-controls">
                  <label for="production-dropdown">Select shape to produce:</label>
                  <div class="controls-row">
                    <select v-model="selectedShape" class="production-dropdown" :disabled="!isSessionActive || productionCount >= (gameState.experiment_config?.maxProductionNum || 6)">
                      <option value="">Choose a shape...</option>
                      <option v-for="shape in availableShapes" :key="shape" :value="shape">
                        {{ getShapeDisplayName(shape) }} ({{ getProductionCost(shape) }})
                      </option>
                    </select>
                    <button @click="startProduction" class="order-btn" :disabled="!isSessionActive || productionCount >= (gameState.experiment_config?.maxProductionNum || 6)">Start Production</button>
                  </div>
                  <div class="production-count-row">
                    <label>Production Count:</label>
                    <span class="production-count">{{ productionCount }}/{{ gameState.experiment_config?.maxProductionNum || 6 }}</span>
                  </div>
                </div>

                <!-- Production Status (only for Shape Factory) -->
                <div v-if="interfaceConfig.myAction.showProductionForm" class="production-status">
                  <div class="production-label">In Production:</div>
                  <div class="production-queue">
                    <div 
                      v-if="currentProductionItem" 
                      class="component-list-item"
                    >
                      <div class="component-text">
                        <span :class="getShapeIcon(currentProductionItem.shape)" :style="currentProductionItem.shape === 'triangle' ? { borderBottomColor: getShapeColor(currentProductionItem.shape) } : { backgroundColor: getShapeColor(currentProductionItem.shape) }"></span>
                        <span>{{ getShapeDisplayName(currentProductionItem.shape) }} - {{ formatProductionTime(currentProductionItem.time_remaining) }}</span>
                      </div>
                    </div>
                    <div v-else class="empty">
                      No production in progress
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <!-- My Task Panel (conditional) -->
          <div v-if="interfaceConfig.myTask.enabled" class="panel order-panel tall-panel">
            <h3 class="panel-header">My Task</h3>
            <div class="panel-body">
              <!-- Simple Task with Instructions -->
              <div v-if="interfaceConfig.myTask.type === 'simple' && interfaceConfig.myTask.instruction" class="task-instructions">
                <div class="instruction-content">
                  <h4>Instructions:</h4>
                  <p>{{ interfaceConfig.myTask.instruction }}</p>
                </div>
              </div>
              
              <!-- Shape Factory Task (Order Fulfillment) -->
              <div v-else-if="interfaceConfig.myTask.type === 'shapefactory'" class="orders-grid">
                <div class="component-list order-list">
                  <div 
                    v-for="(order, index) in gameState.participant?.orders || []" 
                    :key="index" 
                    class="component-list-item order-item"
                  >
                    <input 
                      type="checkbox" 
                      :id="`order-${index}`" 
                      class="order-checkbox"
                      v-model="selectedOrders"
                      :value="index"
                      :disabled="!isSessionActive"
                    >
                    <label :for="`order-${index}`">
                      <div class="component-text">
                        <span :class="getShapeIcon(order)" :style="order === 'triangle' ? { borderBottomColor: getShapeColor(order) } : { backgroundColor: getShapeColor(order) }"></span>
                        <span>{{ getShapeDisplayName(order) }}</span>
                      </div>
                    </label>
                  </div>
                  <div v-if="!gameState.participant?.orders?.length" class="empty">
                    No pending orders
                  </div>
                </div>
              </div>
              
              <!-- Default Task (when no specific type is set) -->
              <div v-else class="default-task">
                <div class="task-content">
                  <p>Complete your assigned tasks as instructed.</p>
                </div>
              </div>
            </div>
          </div>
        </div>    
      </div>

      <!-- RIGHT COLUMN: UNIFIED SOCIAL INTERFACE -->
      <div class="column column-right">
        <!-- Social Navigation Panel -->
        <div class="panel social-panel">
          <h3 class="panel-header">Social</h3>
                      <div class="panel-body">
              <div class="component-list">
                <div 
                  v-for="participant in otherParticipants" 
                  :key="participant.participant_id"
                  class="component-list-item"
                  :class="{ selected: selectedPlayer?.participant_id === participant.participant_id }"
                  @click="selectPlayer(participant)"
                >
                  <div class="player-info">
                    <div class="component-text">
                      <span v-if="hasUnreadMessagesFromParticipant(participant.participant_id)" class="unread-dot message-dot"></span>
                      <span v-if="hasUnreadTradesFromParticipant(participant.participant_id)" class="unread-dot trade-dot"></span>
                      {{ participant.participant_id }}
                    </div>
                  </div>
                </div>
                <div v-if="!otherParticipants.length" class="empty">
                  No other players
                </div>
              </div>
            </div>
        </div>

        <!-- Unified Interaction Panel -->
        <div class="panel interaction-panel">
          <!-- Broadcast mode: show broadcast UI with trading capability -->
          <template v-if="isBroadcastMode">
            <div class="broadcast-mode">
              <!-- Broadcast Mode Header with Tabs -->
              <div class="interaction-header">
                <h3>Broadcast Mode</h3>
                <div class="interaction-tabs">
                  <button 
                    v-if="interfaceConfig.socialPanel.showTradeTab"
                    @click="currentTab = 'trade'; clearTradeNotifications()" 
                    class="tab-btn" 
                    :class="{ active: currentTab === 'trade', 'has-trade-notifications': hasAnyUnreadTrades() }"
                  >
                    Trade
                  </button>
                  <button 
                    v-if="interfaceConfig.socialPanel.showChatTab"
                    @click="currentTab = 'message'; markMessagesAsRead()" 
                    class="tab-btn" 
                    :class="{ active: currentTab === 'message', 'has-message-notifications': unreadBroadcastCount > 0 }"
                  >
                    Broadcast
                    <span v-if="unreadBroadcastCount > 0" class="unread-badge">{{ unreadBroadcastCount }}</span>
                  </button>
                </div>
              </div>

              <!-- Trade Interface Tab -->
              <div v-show="currentTab === 'trade' && interfaceConfig.socialPanel.showTradeTab" class="tab-content trade-tab-content" data-tab="trade">
                <!-- Pending Offers - Always show all trade offers -->
                <div class="trade-section">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <h4>Pending Offers</h4>
                  </div>
                  <div class="offers-list">
                                      <div 
                    v-for="offer in filteredPendingOffers" 
                    :key="offer.id" 
                    class="offer-item"
                  >
                      <div class="offer-header" :style="{ backgroundColor: offer.offer_type === 'buy' ? '#e3f2fd' : 'rgb(255, 240, 240)' }">
                        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                          <strong>{{ offer.offer_type.toUpperCase() }}</strong>
                          <!-- Show context about who initiated -->
                          <span v-if="isOutgoingOffer(offer)" style="font-size: 12px; color: #666;">
                            (waiting for {{ getRecipientDisplay(offer) }} response)
                          </span>
                          <span v-else style="font-size: 12px; color: #666;">
                            (from {{ getOfferSender(offer) }})
                          </span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 6px;">
                          <span>{{ offer.quantity }}x</span>
                          <div style="display: flex; align-items: center; white-space: nowrap;">
                            <span :class="getShapeIcon(offer.shape)" :style="offer.shape === 'triangle' ? { borderBottomColor: getShapeColor(offer.shape) } : { backgroundColor: getShapeColor(offer.shape) }"></span>
                            <span>{{ getShapeDisplayName(offer.shape) }}</span>
                          </div>
                          <span class="component-num">{{ getOfferPriceDisplay(offer) }}</span>
                        </div>
                      </div>
                      <div class="offer-actions">
                        <!-- Show different actions based on whether it's outgoing or incoming -->
                        <div v-if="isOutgoingOffer(offer)" class="outgoing-offer-actions">
                          <!-- If I sent the original offer, I can cancel -->
                          <div class="original-offer-actions">
                            <button @click="cancelTradeOffer(offer.id)" class="cancel-btn" :disabled="!isSessionActive">Cancel</button>
                          </div>
                        </div>
                        <div v-else class="incoming-offer-actions">
                          <!-- If I received the offer, I can accept/decline -->
                          <div class="original-offer-actions">
                            <button @click="respondToOffer(offer.id, 'accept')" class="accept-btn" :disabled="!isSessionActive">Accept</button>
                            <button @click="respondToOffer(offer.id, 'reject')" class="decline-btn" :disabled="!isSessionActive">Decline</button>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div v-if="!filteredPendingOffers.length" class="empty">No pending offers</div>
                  </div>
                </div>

                <!-- Trade History - Always show all trade history -->
                <div class="trade-section trade-history-section">
                  <h4>Trade History</h4>
                  <div class="trade-history-list">
                                      <div 
                    v-for="trade in filteredTradeHistory" 
                    :key="trade.id" 
                    class="history-item"
                    :class="{ 'declined-trade': trade.type === 'declined' || trade.type === 'cancelled' }"
                  >
                      <span v-if="trade.type === 'declined'" class="trade-status declined">DECLINED:</span>
                      <span v-else-if="trade.type === 'cancelled'" class="trade-status cancelled">CANCELLED:</span>
                      <span v-else class="trade-status">{{ trade.type }}:</span>
                      <span>{{ trade.quantity }}x</span>
                      <div style="display: flex; align-items: center; white-space: nowrap;">
                        <span :class="getShapeIcon(trade.shape)" :style="trade.shape === 'triangle' ? { borderBottomColor: getShapeColor(trade.shape) } : { backgroundColor: getShapeColor(trade.shape) }"></span>
                        <span>{{ getShapeDisplayName(trade.shape) }}</span>
                      </div>
                      <span class="component-num">${{ trade.price }}</span>
                    </div>
                    <div v-if="!filteredTradeHistory.length" class="empty">No trade history</div>
                  </div>
                </div>

                <!-- Player Selection for Trading in Broadcast Mode -->
                <div v-if="!selectedPlayer" class="no-selection">
                  <h4>Select a Player to Trade With</h4>
                  <p>Choose a player from the list above to start trading. In broadcast mode, you can still trade directly with other participants.</p>
                </div>
                
                <div v-else class="player-interaction">
                  <!-- Propose Trade Form -->
                  <div class="propose-trade">
                    <div class="trade-form">
                      <div class="trade-sentence">
                        <p class="sentence-builder">
                          I want to 
                          <select v-model="tradeType" class="inline-select" :disabled="!isSessionActive">
                            <option value="sell">sell</option>
                            <option value="buy">buy</option>
                          </select>
                          one 
                          <select v-model="tradeShape" class="inline-select" :disabled="!isSessionActive">
                            <option value="">shape</option>
                            <option v-for="shape in availableShapes" :key="shape" :value="shape">
                              {{ getShapeDisplayName(shape) }}
                            </option>
                          </select>
                          <span v-if="tradeType === 'sell'">to</span>
                          <span v-else>from</span>
                          <strong>{{ selectedPlayer?.participant_id || 'player' }}</strong>
                          at 
                          $<input 
                            type="number" 
                            v-model="tradePrice" 
                            class="inline-input" 
                            :placeholder="gameState.experiment_config?.minTradePrice || 22" 
                            :min="gameState.experiment_config?.minTradePrice || 15" 
                            :max="gameState.experiment_config?.maxTradePrice || 30"
                            :disabled="!isSessionActive"
                          >.
                        </p>
                      </div>
                      <button @click="proposeTradeOffer" class="propose-btn" :disabled="!isSessionActive">Send Trade Offer</button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Broadcast Message Interface Tab -->
              <div v-show="currentTab === 'message' && interfaceConfig.socialPanel.showChatTab" class="tab-content trade-tab-content" data-tab="message" :key="'broadcast-messages'">
                <div class="message-thread">
                  <div class="message-history" ref="messageHistory">
                    <div 
                      v-for="message in broadcastMessages" 
                      :key="message.id" 
                      class="message-item broadcast-message"
                      :class="{ 'my-message': message.sender === participantId, 'other-message': message.sender !== participantId }"
                    >
                      <div class="message-sender">{{ message.sender }}</div>
                      <div class="message-content">{{ message.content }}</div>
                      <div class="message-time">{{ formatTime(message.timestamp) }}</div>
                    </div>
                    <div v-if="!broadcastMessages.length" class="empty">No broadcast messages yet</div>
                  </div>
                </div>
                <div class="message-input-area">
                  <input 
                    type="text" 
                    v-model="newMessage" 
                    @keypress.enter="sendBroadcastMessage"
                    class="message-input" 
                    placeholder="Type your broadcast message..." 
                    maxlength="200"
                    :disabled="!isSessionActive"
                  >
                  <button @click="sendBroadcastMessage" class="send-btn" :disabled="!isSessionActive">Broadcast</button>
                </div>
              </div>
            </div>
          </template>
          
          <!-- Chat mode: require participant selection -->
          <div v-else-if="!selectedPlayer" class="no-selection">
            <h3>No Player Selected</h3>
            <p>Click on a player above to start trading or messaging with them.</p>
          </div>
          
          <div v-else class="player-interaction">
            <!-- Player Header -->
            <div class="interaction-header">
              <div class="interaction-tabs">
                <button 
                  v-if="interfaceConfig.socialPanel.showTradeTab"
                  @click="currentTab = 'trade'; clearTradeNotifications()" 
                  class="tab-btn" 
                  :class="{ active: currentTab === 'trade', 'has-trade-notifications': hasUnreadTradesFromParticipant(selectedPlayer?.participant_id) }"
                >
                  Trade
                </button>
                <button 
                  v-if="showMessagesTab && interfaceConfig.socialPanel.showChatTab"
                  @click="currentTab = 'message'; markMessagesAsRead()" 
                  class="tab-btn" 
                  :class="{ active: currentTab === 'message', 'has-message-notifications': hasUnreadMessagesFromParticipant(selectedPlayer?.participant_id) }"
                >
                  Messages
                  <span v-if="unreadChatCount > 0" class="unread-badge">{{ unreadChatCount }}</span>
                </button>
              </div>
            </div>

            <!-- Trade Interface Tab -->
            <div v-show="currentTab === 'trade' && interfaceConfig.socialPanel.showTradeTab" class="tab-content trade-tab-content" data-tab="trade">
              <!-- Propose Trade Form -->
              <div class="propose-trade">
                <div class="trade-form">
                  <div class="trade-sentence">
                    <p class="sentence-builder">
                      I want to 
                      <select v-model="tradeType" class="inline-select">
                        <option value="sell">sell</option>
                        <option value="buy">buy</option>
                      </select>
                      one 
                      <select v-model="tradeShape" class="inline-select">
                        <option value="">shape</option>
                        <option v-for="shape in availableShapes" :key="shape" :value="shape">
                          {{ getShapeDisplayName(shape) }}
                        </option>
                      </select>
                      <span v-if="tradeType === 'sell'">to</span>
                      <span v-else>from</span>
                      <strong>{{ selectedPlayer?.participant_id || 'player' }}</strong>
                      at 
                      $<input 
                        type="number" 
                        v-model="tradePrice" 
                        class="inline-input" 
                        :placeholder="gameState.experiment_config?.minTradePrice || 22" 
                        :min="gameState.experiment_config?.minTradePrice || 15" 
                        :max="gameState.experiment_config?.maxTradePrice || 30"
                      >.
                    </p>
                  </div>
                  <button @click="proposeTradeOffer" class="propose-btn">Send Trade Offer</button>
                </div>
              </div>

              <!-- Pending Offers -->
              <div class="trade-section">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                  <h4>Pending Trade Offers</h4>
                </div>
                <div class="offers-list">
                  <div 
                    v-for="offer in filteredPendingOffers" 
                    :key="offer.id" 
                    class="offer-item"
                  >
                                            <div class="offer-header" :style="{ backgroundColor: offer.offer_type === 'buy' ? '#e3f2fd' : '#f3e5f5' }">
                          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                            <strong>{{ offer.offer_type.toUpperCase() }}</strong>
                            <!-- Show context about who initiated -->
                            <span v-if="isOutgoingOffer(offer)" style="font-size: 12px; color: #666;">
                              (waiting for {{ getRecipientDisplay(offer) }} response)
                            </span>
                            <span v-else style="font-size: 12px; color: #666;">
                              (from {{ getOfferSender(offer) }})
                            </span>
                          </div>
                      <div style="display: flex; align-items: center; gap: 6px;">
                        <span>{{ offer.quantity }}x</span>
                        <span>{{ getShapeDisplayName(offer.shape) }}</span>
                        <span class="component-num">{{ getOfferPriceDisplay(offer) }}</span>
                      </div>
                    </div>
                    <div class="offer-actions">
                      <!-- Show different actions based on whether it's outgoing or incoming -->
                      <div v-if="isOutgoingOffer(offer)" class="outgoing-offer-actions">
                        <!-- If I sent the original offer, I can cancel -->
                        <div class="original-offer-actions">
                          <button @click="cancelTradeOffer(offer.id)" class="cancel-btn" :disabled="!isSessionActive">Cancel</button>
                        </div>
                      </div>
                      <div v-else class="incoming-offer-actions">
                        <!-- If I received the offer, I can accept/decline -->
                        <div class="original-offer-actions">
                          <button @click="respondToOffer(offer.id, 'accept')" class="accept-btn" :disabled="!isSessionActive">Accept</button>
                          <button @click="respondToOffer(offer.id, 'reject')" class="decline-btn" :disabled="!isSessionActive">Decline</button>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-if="!filteredPendingOffers.length" class="empty">No pending offers</div>
                </div>
              </div>

              <!-- Trade History -->
              <div class="trade-section trade-history-section">
                <h4>Trade History</h4>
                <div class="trade-history-list">
                  <div 
                    v-for="trade in filteredTradeHistory" 
                    :key="trade.id" 
                    class="history-item"
                    :class="{ 'declined-trade': trade.type === 'declined' || trade.type === 'cancelled' }"
                  >
                    <span v-if="trade.type === 'declined'" class="trade-status declined">DECLINED:</span>
                    <span v-else-if="trade.type === 'cancelled'" class="trade-status cancelled">CANCELLED:</span>
                    <span v-else class="trade-status">{{ trade.type }}:</span>
                    <span>{{ trade.quantity }}x</span>
                    <div style="display: flex; align-items: center; white-space: nowrap;">
                      <span :class="getShapeIcon(trade.shape)" :style="trade.shape === 'triangle' ? { borderBottomColor: getShapeColor(trade.shape) } : { backgroundColor: getShapeColor(trade.shape) }"></span>
                      <span>{{ getShapeDisplayName(trade.shape) }}</span>
                    </div>
                    <span class="component-num">${{ trade.price }}</span>
                  </div>
                  <div v-if="!filteredTradeHistory.length" class="empty">No trade history</div>
                </div>
              </div>
            </div>

            <!-- Message Interface Tab -->
            <div v-show="currentTab === 'message' && interfaceConfig.socialPanel.showChatTab" class="tab-content" :key="`chat-messages-${selectedPlayer?.participant_id || 'none'}`">
              <!-- Chat Mode -->
              <div class="chat-mode">
                <!-- Message Thread -->
                <div class="message-thread">
                  <div class="message-history" ref="messageHistory">
                    <div 
                      v-for="message in conversationMessages" 
                      :key="message.id" 
                      class="message-item"
                      :class="{ 'my-message': message.sender === participantId, 'other-message': message.sender !== participantId }"
                    >
                      <div class="message-sender">{{ message.sender }}</div>
                      <div class="message-content">{{ message.content }}</div>
                      <div class="message-time">{{ formatTime(message.timestamp) }}</div>
                    </div>
                    <div v-if="!conversationMessages.length" class="empty">No messages yet</div>
                  </div>
                </div>

                <!-- Message Input -->
                <div class="message-input-area">
                  <input 
                    type="text" 
                    v-model="newMessage" 
                    @keypress.enter="sendMessage"
                    class="message-input" 
                    placeholder="Type your message..." 
                    maxlength="200"
                    :disabled="!isSessionActive"
                  >
                  <button @click="sendMessage" class="send-btn" :disabled="!isSessionActive">Send</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- AWARENESS DASHBOARD COLUMN (ONLY WHEN ENABLED) -->
      <div v-if="awarenessDashboardEnabled" class="column column-awareness">
        <div class="panel awareness-panel">
          <h3 class="panel-header">All Participant Status</h3>
          <div class="panel-body">
            <!-- <div class="awareness-info">
              <p>Real-time status of all participants' progress and finances</p>
            </div> -->
            
            <div class="participants-status-grid">
              <div 
                v-for="participant in otherParticipantsWithAwareness" 
                :key="participant.participant_id"
                class="participant-status-card"
              >
                <div class="participant-header">
                  <div class="component-text">{{ participant.participant_id }}</div>
                  <!-- Only show shape for Shape Factory experiments -->
                  <div v-if="interfaceConfig.myAction.type === 'shapefactory'" class="component-text">
                    <span :class="getShapeIcon(participant.shape)" :style="participant.shape === 'triangle' ? { borderBottomColor: getShapeColor(participant.shape) } : { backgroundColor: getShapeColor(participant.shape) }"></span>
                    <span>{{ getShapeDisplayName(participant.shape) }}</span>
                  </div>
                </div>
                
                <div class="participant-stats">
                  <!-- Show content based on awareness dashboard configuration from researcher -->
                  <!-- First row: Money and Production -->
                  <div class="stats-row">
                    <!-- Money - only show if enabled by researcher -->
                    <div v-if="gameState.awareness_dashboard_config?.showMoney" class="component-module">
                      <span class="component-text">Money:</span>
                      <span class="component-num">${{ participant.money || 300 }}</span>
                    </div>
                    <!-- Production - only show if enabled by researcher -->
                    <div v-if="gameState.awareness_dashboard_config?.showProductionCount" class="component-module">
                      <span class="component-text">Production:</span>
                      <span class="component-num">
                        {{ participant.specialty_production_used || 0 }}/{{ gameState.experiment_config?.maxProductionNum || 6 }}
                      </span>
                    </div>
                  </div>
                  
                  <!-- Second row: Order completion progress - only show if enabled by researcher -->
                  <div v-if="gameState.awareness_dashboard_config?.showOrderProgress" class="stats-row">
                    <div class="progress-container">
                      <div class="progress-label">
                        <span class="component-text">Orders: {{ getOrdersCompletedForParticipant(participant.participant_id) }}/{{ gameState.experiment_config?.shapesPerOrder || 3 }}</span>
                      </div>
                      <div class="progress-bar">
                        <div 
                          class="progress-fill" 
                          :style="{ width: `${getOrderCompletionPercentageForParticipant(participant.participant_id)}%` }"
                        ></div>
                      </div>
                      <span class="completion-percentage">{{ getOrderCompletionPercentageForParticipant(participant.participant_id) }}%</span>
                    </div>
                  </div>
                </div>
              </div>
              
              <div v-if="!otherParticipantsWithAwareness.length" class="empty">
                No other participants available
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
  </div>



  <!-- Order Fulfillment Popup Modal -->
  <div v-if="showOrderFulfillmentPopup" class="modal-overlay" @click="closeOrderFulfillmentPopup">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>Fulfill Order</h3>
        <button class="modal-close" @click="closeOrderFulfillmentPopup">×</button>
      </div>
      <div class="modal-body">
        <div class="order-fulfillment-form">
          <p>Do you want to fulfill this order?</p>
          <div class="order-details">
            <div class="shape-display">
              <span :class="getShapeIcon(selectedOrderShape)" :style="selectedOrderShape === 'triangle' ? { borderBottomColor: getShapeColor(selectedOrderShape) } : { backgroundColor: getShapeColor(selectedOrderShape) }"></span>
              <span>{{ getShapeDisplayName(selectedOrderShape) }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn secondary" @click="closeOrderFulfillmentPopup">Cancel</button>
        <button class="btn primary" @click="confirmFulfillOrder" :disabled="!isSessionActive">Yes, Fulfill Order</button>
      </div>
    </div>
  </div>

  <!-- Automated Session Start Popup Modal -->
  <div v-if="showAutoStartPopup" class="modal-overlay auto-start-overlay" @click="closeAutoStartPopup">
    <div class="modal-content auto-start-modal" @click.stop>
      <div class="modal-header">
        <h3>Session Starting</h3>
      </div>
      <div class="modal-body">
        <div class="auto-start-content">
          <div class="countdown-display">
            <div class="countdown-number">{{ autoStartCountdown }}</div>
            <div class="countdown-label">seconds</div>
          </div>
          <p class="auto-start-message">{{ autoStartMessage }}</p>
          <div class="auto-start-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${autoStartProgress}%` }"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
    </div> <!-- Close the v-else div for standard interface -->
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { BACKEND_URL } from '@/config.js'
import ECLInterface from '@/components/ECLInterface.vue'
// @ts-ignore
import io from 'socket.io-client'

// Types
interface ECLConfig {
  experiment?: {
    title?: string
    description?: string
    timing?: {
      session_duration_minutes?: number
    }
  }
  actions?: Record<string, any>
  views?: {
    my_status?: Array<{ bindings: Array<{ label: string; path: string }> }>
    my_action?: Array<{ bindings: Array<any> }>
    info_dashboard?: Array<{ bindings: Array<{ label: string; path: string }>; visible_if: string }>
    message_tab?: Array<{ visible_if: string; communication_level?: string }>
  }
  types?: Record<string, any>
  objects?: Record<string, any>
  variables?: Record<string, any>
  constraints?: Array<any>
  policies?: Array<any>
}

interface Participant {
  participant_id: string
  shape: string
  money?: number
  shapes_acquired?: string[]
  orders?: string[]
  production_queue?: ProductionItem[]
  specialty_cost?: number // Added for production cost
  regular_cost?: number // Added for regular production cost
  orders_completed?: number // Added for awareness dashboard
  total_orders?: number // Added for awareness dashboard
  completion_percentage?: number // Added for awareness dashboard
  specialty_production_used?: number // Added for awareness dashboard production count
  current_rankings?: Array<{essay_id: string, rank: number}> // Added for essay ranking
  submitted_rankings_count?: number // Added for essay ranking
  role?: string // Added for wordguessing experiments
  current_round?: number // Added for wordguessing experiments
  score?: number // Added for wordguessing experiments
  assigned_words?: string[] // Added for wordguessing experiments
}

interface ProductionItem {
  id: string
  shape: string
  time_remaining: number
  status?: string // Added for status
  isTestItem?: boolean // Added for test items
}

interface GameState {
  participant?: Participant
  participants?: Participant[]
  session_status?: {
    time_remaining: number
  }
  communication_level?: string // Add communication level to game state
  awareness_dashboard_enabled?: boolean // Added for awareness dashboard
  awareness_dashboard_config?: { // Added for awareness dashboard configuration
    showMoney: boolean
    showProductionCount: boolean
    showOrderProgress: boolean
  }
  experiment_interface_config?: any // Added for experiment interface configuration
  experiment_config?: any // Added for experiment configuration parameters
  experiment_type?: string // Added for experiment type
}

interface TradeOffer {
  id: string
  offer_type: 'buy' | 'sell'  // The type of offer (what the proposer wants to do)
  shape: string
  quantity: number  // Add quantity field
  price: number
  proposer_code: string  // Who initiated the offer
  recipient_code: string  // Who receives the offer
  is_outgoing: boolean  // Whether this participant initiated the offer
}

interface TradeHistory {
  id: string
  type: 'bought' | 'sold' | 'declined' | 'cancelled'
  shape: string
  quantity: number  // Add quantity field
  price: number
  proposer_code?: string  // Add participant information for filtering
  recipient_code?: string // Add participant information for filtering
}

interface Message {
  id: string
  sender: string
  content: string
  timestamp: Date
  recipient?: string // Added recipient for message filtering
}

// Router
const router = useRouter()

// Interface configuration for dynamic adaptation
const interfaceConfig = ref({
  myStatus: {
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
    type: 'shapefactory' // Default to shapefactory for basic experiment
  },
  trade: {
    enabled: true,
    showTradeHistory: true
  },
  socialPanel: {
    showTradeTab: true,
    showChatTab: true
  }
})

// ECL-specific reactive data
const eclConfig = ref<ECLConfig>({})
const eclState = ref<any>({})
const eclLocalState = ref<Record<string, any>>({})

// ECL computed properties
const eclMyStatusComponents = computed(() => {
  if (!eclConfig.value.views?.my_status?.[0]?.bindings) return []
  return eclConfig.value.views.my_status[0].bindings.filter(b => b.path)
})

const eclMyActionComponents = computed(() => {
  if (!eclConfig.value.views?.my_action?.[0]?.bindings) return []
  return eclConfig.value.views.my_action[0].bindings
})

const eclInfoDashboardComponents = computed(() => {
  if (!eclConfig.value.views?.info_dashboard?.[0]?.bindings) return []
  return eclConfig.value.views.info_dashboard[0].bindings
})

const eclInfoDashboardEnabled = computed(() => {
  return eclConfig.value.views?.info_dashboard?.[0]?.visible_if === 'true'
})

const eclMessageTabEnabled = computed(() => {
  return eclConfig.value.views?.message_tab?.[0]?.visible_if === 'true'
})


// Experiment configurations
const experimentConfigs = {
  'shapefactory': {
    myStatus: {
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
    },
    socialPanel: {
      showTradeTab: true,
      showChatTab: true
    }
  },
  'daytrader': {
    myStatus: {
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
      enabled: true,
      type: 'simple',
      instruction: 'Make trading decisions based on market conditions and your investment strategy.'
    },
    trade: {
      enabled: true,
      showTradeHistory: true
    },
    socialPanel: {
      showTradeTab: false,
      showChatTab: true
    }
  },
  'essayranking': {
    myStatus: {
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
      type: 'simple',
      instruction: 'Read the essays and participate in the ranking discussion to reach consensus.'
    },
    trade: {
      enabled: false,
      showTradeHistory: false
    },
    socialPanel: {
      showTradeTab: false,
      showChatTab: true
    }
  },
  'wordguessing': {
    myStatus: {
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
      type: 'simple',
      instruction: 'Participate in the word guessing game and collaborate with other participants.'
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

// DayTrader specific state
const decisionType = ref('individual')
const investmentHistory = ref([])

// Load investment history for DayTrader
const loadInvestmentHistory = async () => {
  
  if (interfaceConfig.value.myAction.type !== 'daytrader') {
    return
  }
  
  try {
    const authToken = sessionStorage.getItem('auth_token')
    if (!authToken) {
      return
    }

    const response = await fetch(`/api/daytrader/investment-history?session_code=${sessionId.value}`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    })

    if (response.ok) {
      const data = await response.json()
      console.log('  Investment history data:', data)
      investmentHistory.value = data.investments || []
      console.log('  Updated investment history:', investmentHistory.value)
    } else {
      console.log('  Investment history response error:', response.status, response.statusText)
      const errorText = await response.text()
      console.log('  Error details:', errorText)
    }
  } catch (error) {
    console.error('Error loading investment history:', error)
  }
}

// Format timestamp for display
const formatTimestamp = (timestamp) => {
  if (!timestamp) return 'Unknown time'
  const date = new Date(timestamp)
  return date.toLocaleTimeString()
}

// Clear investment history (for DayTrader experiments)
const clearInvestmentHistory = () => {
  if (interfaceConfig.value.myAction.type === 'daytrader') {
    investmentHistory.value = []
  }
}

// Configure interface based on experiment type from session data
const configureInterface = async () => {
  try {
    // Try to get experiment type from session data
    const authToken = sessionStorage.getItem('auth_token')
    if (!authToken) {
      return false
    }

    const response = await fetch('/api/session/current', {
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    })
    
    if (response.ok) {
      const sessionData = await response.json()
      let experimentType = sessionData.experiment_type || 'shapefactory'
      
      // Handle ECL experiments - configure social panel based on ECL message tab
      if (experimentType === 'custom_ecl') {
        
        // Get communication level from ECL message tab configuration
        const messageTabConfig = eclConfig.value.views?.message_tab?.[0]
        const communicationLevel = messageTabConfig?.communication_level || 'group_chat'
        
        // Configure interface for ECL experiments
        interfaceConfig.value = {
          myStatus: {
            showMoney: true,
            showInventory: false // ECL handles its own status display
          },
          myAction: {
            type: 'disabled', // ECL handles its own action display
            showTradeForm: false,
            showProductionForm: false,
            showOrderForm: false
          },
          myTask: {
            enabled: false, // ECL handles its own task display
            type: 'disabled'
          },
          trade: {
            enabled: false, // ECL doesn't use trading
            showTradeHistory: false
          },
          socialPanel: {
            showTradeTab: false, // ECL doesn't use trading
            showChatTab: eclMessageTabEnabled.value // Enable chat based on ECL message tab
          }
        }
        
        // Set communication level for the session
        if (communicationLevel) {
          // Update the game state communication level
          if (gameState.value.experiment_config) {
            gameState.value.experiment_config.communicationLevel = communicationLevel
          }
        }
        
        return true
      }
      
      const config = experimentConfigs[experimentType]
      
      if (config) {
        
        // Replace the entire configuration to ensure Vue reactivity
        interfaceConfig.value = {
          myStatus: config.myStatus,
          myAction: config.myAction,
          myTask: config.myTask,
          trade: config.trade,
          socialPanel: config.socialPanel
        }
        
        
        // Force a re-render by triggering a small delay
        await nextTick()
        return true // Return success
      } else {
        return false
      }
    } else {
      return false
    }
  } catch (error) {
    return false
  }
}

// Auto-configure interface with retry logic
const autoConfigureInterface = async () => {
  // Try multiple times with increasing delays
  const delays = [0, 500, 1000, 2000, 3000, 5000]
  
  for (let i = 0; i < delays.length; i++) {
    const delay = delays[i]
    
    if (delay > 0) {
      await new Promise(resolve => setTimeout(resolve, delay))
    }
    
    try {
      const success = await configureInterface()
      
      if (success) {
        // For ECL experiments, success means we can proceed
        if (isECLExperiment.value) {
          return true
        }
        
        // For other experiments, check if it's the right type
        const currentType = interfaceConfig.value.myAction.type
        
        // Verify the configuration was actually applied
        if (currentType === 'daytrader' || currentType === 'shapefactory' || currentType === 'essayranking' || currentType === 'disabled') {
          
          // Load investment history for DayTrader
          if (currentType === 'daytrader') {
            await loadInvestmentHistory()
          }
          
          return true
        }
      } 
    } catch (error) {
    }
  }
  
  return false
}



// Reactive state
const sessionId = ref('')  // Will be set from sessionStorage
const participantId = ref('')
const gameState = ref<GameState>({})
const showRules = ref(false)
const selectedPlayer = ref<Participant | null>(null)
const currentTab = ref<'trade' | 'message'>('trade')

// Watch for session changes and auto-configure
watch(sessionId, async (newSessionId, oldSessionId) => {
  if (newSessionId && newSessionId !== oldSessionId) {
    console.log('Session ID changed, interface will be configured in onMounted')
  }
}, { immediate: false })

// Add timer state tracking
const lastWebSocketTimerUpdate = ref<number>(0)
const timerUpdateThreshold = 500 // 0.5 seconds - if we got a WebSocket update within this time, don't let local timer overwrite it

// WebSocket connection status
const isConnected = ref(false)

// Local countdown timer for smooth real-time updates
const localTimerInterval = ref<number | null>(null)

// Track last update timestamps for each field to ensure idempotency
const lastUpdateTimestamps = ref<Map<string, number>>(new Map())

// Track processed event IDs to prevent duplicate processing
const processedEventIds = ref<Set<string>>(new Set())

// Track recently added shapes to prevent backend overwrites
const recentlyAddedShapes = ref<Set<string>>(new Set())

// Track recently fulfilled orders to prevent backend overwrites
const recentlyFulfilledOrders = ref<Set<string>>(new Set())

// Timer state - use timestamp-based approach for background accuracy
const timeRemaining = ref<number>(0)
const timerStartTime = ref<number>(0) // When the timer started
const timerInitialDuration = ref<number>(0) // Initial duration when timer started
const isTimerRunning = ref<boolean>(false) // Whether timer is actively running

// Template refs
const messageHistory = ref<HTMLElement | null>(null)

// Production
const selectedShape = ref('')
const availableShapes = ['circle', 'square', 'triangle', 'diamond', 'pentagon']

// Track completed production items to prevent duplicate messages
const completedProductionItems = ref<Set<string>>(new Set())

// Current production item (single item, no queue)
const currentProduction = ref<ProductionItem | null>(null)

// Production state tracking
const isProductionInProgress = ref(false)

// Flag to track if we explicitly started a production (not from backend queue)
const explicitlyStartedProduction = ref(false)

// Orders
const selectedOrders = ref<number[]>([])

// Trading
const tradeType = ref('sell')
const tradeShape = ref('')
const tradePrice = ref(22)
const pendingOffers = ref<TradeOffer[]>([])
const tradeHistory = ref<TradeHistory[]>([])

// Essay Ranking
const selectedEssay = ref('')
const rankingInput = ref('')

// Essay viewing and API integration
const assignedEssays = ref<Array<{
  essay_id: string
  title: string
}>>([])
const showEssayViewer = ref(false)
const currentEssay = ref<{
  essay_id: string
  title: string
} | null>(null)

const confirmRanking = async () => {
  if (!isSessionActive.value) {
    alert('Session is not active. Please wait for the researcher to start the session.')
    return
  }

  if (!selectedEssay.value || !rankingInput.value) {
    alert('Please select an essay and enter a ranking.')
    return
  }

  try {
    const authToken = sessionStorage.getItem('auth_token')
    const participantCode = sessionStorage.getItem('participant_code')
    const sessionCode = sessionStorage.getItem('session_code')
    
    // Convert ranking input to number for validation
    const ranking = parseInt(rankingInput.value)
    if (isNaN(ranking)) {
      alert('Please enter a valid number for ranking.')
      return
    }
    
    const response = await fetch('/api/essayranking/submit-ranking', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        participant_code: participantCode,
        session_code: sessionCode,
        rankings: [{
          essay_id: selectedEssay.value,
          rank: ranking
        }]
      })
    })

            if (response.ok) {
              const result = await response.json()
              alert(`Ranking submitted successfully! Essay ranked as ${ranking}`)
              selectedEssay.value = ''
              rankingInput.value = ''
              // Refresh game state to update the rankings display
              await loadGameStateIncremental()
            } else {
              const error = await response.json()
              alert(`Failed to submit ranking: ${error.error || 'Unknown error'}`)
            }
  } catch (error) {
    console.error('Error submitting ranking:', error)
    alert('Error submitting ranking. Please try again.')
  }
}

// Essay viewing functions
const viewEssay = (essay: { essay_id: string; title: string }) => {
  currentEssay.value = essay
  showEssayViewer.value = true
}

const hideEssayViewer = () => {
  showEssayViewer.value = false
  currentEssay.value = null
}

const hideEssayViewerIfClickedOutside = (event: Event) => {
  const target = event.target as HTMLElement
  if (target.classList.contains('essay-viewer-modal')) {
    hideEssayViewer()
  }
}

const downloadEssay = () => {
  if (!currentEssay.value) return
  
  // For now, show a message since we don't have actual PDF files stored
  // In a full implementation, this would download the actual PDF file
  alert(`Download functionality for "${currentEssay.value.title}" would be implemented here.\n\nIn a full system, this would download the PDF file from the server.`)
  
  // TODO: Implement actual PDF download when file storage is available
  // Example implementation:
  // const link = document.createElement('a')
  // link.href = `/api/essayranking/download-essay/${currentEssay.value.essay_id}`
  // link.download = `${currentEssay.value.title}.pdf`
  // link.click()
}

// Essay ranking computed properties and methods
const sortedCurrentRankings = computed(() => {
  const rankings = gameState.value.participant?.current_rankings || []
  return [...rankings].sort((a, b) => a.rank - b.rank)
})

const getEssayTitle = (essayId: string) => {
  const essay = assignedEssays.value.find(e => e.essay_id === essayId)
  return essay ? essay.title : `Essay ${essayId}`
}


// Load assigned essays from backend
const loadAssignedEssays = async () => {
  try {
    const sessionCode = sessionStorage.getItem('session_code')
    if (!sessionCode) {
      console.warn('No session code available to load essays')
      return
    }
  
    
    const response = await fetch(`/api/essayranking/get-essays?session_code=${sessionCode}`)
    
    if (response.ok) {
      const result = await response.json()
      assignedEssays.value = result.essays || []
    } else {
      console.error('❌ Failed to load essays:', response.statusText)
      const errorText = await response.text()
      console.error('❌ Error details:', errorText)
    }
  } catch (error) {
    console.error('❌ Error loading essays:', error)
  }
}

// Watch for interface config changes and reload essays
watch(() => interfaceConfig.value.myAction?.type, (newType, oldType) => {
  if (newType === 'essayranking' && newType !== oldType) {
    loadAssignedEssays()
  }
}, { immediate: false })




// Order fulfillment popup
const showOrderFulfillmentPopup = ref(false)
const selectedOrderShape = ref('')
const selectedOrderIndex = ref(-1)

// Automated session start popup
const showAutoStartPopup = ref(false)
const autoStartCountdown = ref(5)
const autoStartMessage = ref('Session starts in 5 seconds.')
const autoStartProgress = ref(0)
const autoStartInterval = ref<number | null>(null)
const hasCheckedAutoStart = ref(false)

// Messages
const newMessage = ref('')
const messages = ref<Message[]>([])

// Unread message tracking
const lastReadTimestamp = ref<number>(0) // Start at 0 so all existing messages are unread initially
const unreadMessages = ref<Set<string>>(new Set())

// Track unread messages per participant
const unreadMessagesByParticipant = ref<Map<string, number>>(new Map())
const lastReadTimestampByParticipant = ref<Map<string, number>>(new Map())

// Track unread trade offers per participant (separate from pendingOffers to avoid race conditions)
const unreadTradeOffersByParticipant = ref<Map<string, number>>(new Map())

// WebSocket
let socket: any = null

// Watch for session changes and reconfigure interface
watch(sessionId, async (newSessionId) => {
  if (newSessionId) {
    console.log('Session ID changed, interface will be configured in onMounted')
  }
}, { immediate: false })

// Shape configuration
const shapeConfig = {
  'circle': { color: '#dc3545', name: 'Circle', icon: 'shape-circle' },
  'square': { color: '#007bff', name: 'Square', icon: 'shape-square' },
  'triangle': { color: '#28a745', name: 'Triangle', icon: 'shape-triangle' },
  'diamond': { color: '#6f42c1', name: 'Diamond', icon: 'shape-diamond' },
  'pentagon': { color: '#fd7e14', name: 'Pentagon', icon: 'shape-pentagon' }
}

// Computed properties
const timerDisplay = computed(() => {
  if (timeRemaining.value <= 0) return 'Time: --:--'
  
  const minutes = Math.floor(timeRemaining.value / 60)
  const seconds = timeRemaining.value % 60
  return `Time: ${minutes}:${seconds.toString().padStart(2, '0')}`
})

// Local countdown timer functions
const startLocalTimer = () => {
  if (localTimerInterval.value) {
    clearInterval(localTimerInterval.value)
  }
  
  // Store the start time and initial duration for background calculation
  timerStartTime.value = Date.now()
  timerInitialDuration.value = timeRemaining.value
  isTimerRunning.value = true
  
  localTimerInterval.value = setInterval(() => {
    // Only update if experiment is running and we have time remaining
    if (gameState.value.experiment_config?.experiment_status === 'running' && isTimerRunning.value) {
      // Check if we've received a recent WebSocket update
      const timeSinceLastWebSocketUpdate = Date.now() - lastWebSocketTimerUpdate.value
      const hasRecentWebSocketUpdate = timeSinceLastWebSocketUpdate < timerUpdateThreshold
      
      if (!hasRecentWebSocketUpdate) {
        // Calculate time remaining based on elapsed time since start
        const elapsedSeconds = Math.floor((Date.now() - timerStartTime.value) / 1000)
        const calculatedTimeRemaining = Math.max(0, timerInitialDuration.value - elapsedSeconds)
        
        // Update the timer value
        timeRemaining.value = calculatedTimeRemaining
        
        // If timer reaches 0, update status
        if (timeRemaining.value === 0) {
          isTimerRunning.value = false
          if (gameState.value.experiment_config) {
            gameState.value.experiment_config.experiment_status = 'completed'
          }
        }
      } else {
        // If we have recent WebSocket updates, use them to keep the timer synchronized
        // This prevents the local timer from drifting away from the server
      }
    }
  }, 1000) // Update every second
  
}

const stopLocalTimer = () => {
  if (localTimerInterval.value) {
    clearInterval(localTimerInterval.value)
    localTimerInterval.value = null
  }
  isTimerRunning.value = false
}

// Add session status computed property with debouncing to prevent flickering
const sessionStatus = computed(() => {
  const status = gameState.value.experiment_config?.experiment_status || 'idle'
  return status
})

// Add a stable session status that prevents flickering once session ends
const stableSessionStatus = ref(sessionStatus.value)
let sessionStatusDebounceTimeout: NodeJS.Timeout | null = null

// Track if session has ended to prevent flickering
const sessionHasEnded = ref(false)

const isSessionActive = computed(() => {
  // If session has ended, always show the overlay
  if (sessionHasEnded.value) {
    console.log('🔍 Session has ended, showing overlay')
    return false
  }
  
  const status = stableSessionStatus.value
  const isActive = status !== 'completed' && status !== 'stopped' && status !== 'ended'
  
  console.log('🔍 Session Active Check:', {
    status: status,
    isActive: isActive,
    sessionHasEnded: sessionHasEnded.value
  })
  
  return isActive
})

// Watch for session status changes with stable handling
watch(sessionStatus, (newStatus, oldStatus) => {
  if (newStatus !== oldStatus) {
    console.log('=== SESSION STATUS CHANGE ===')
    console.log('Session status changed from', oldStatus, 'to', newStatus)
    console.log('Current stable status:', stableSessionStatus.value)
    console.log('Session has ended flag:', sessionHasEnded.value)
    console.log('Is session active before change:', isSessionActive.value)
    console.log('Game state experiment config:', gameState.value.experiment_config)
    console.log('Timestamp:', new Date().toISOString())
    
    // If session has already ended, don't change the status anymore
    if (sessionHasEnded.value) {
      console.log('Session has already ended, ignoring status change to prevent flickering')
      return
    }
    
    // Check if this is an end status
    const isEndStatus = newStatus === 'completed' || newStatus === 'stopped' || newStatus === 'ended'
    
    // Check if this is a start status
    const isStartStatus = newStatus === 'running'
    
    // If transitioning to an end status, mark session as ended immediately
    if (isEndStatus) {
      console.log('Session ending detected, marking as ended immediately')
      sessionHasEnded.value = true
      stableSessionStatus.value = newStatus
      return
    }
    
    // If transitioning to running status, reset the session ended flag
    if (isStartStatus && sessionHasEnded.value) {
      console.log('Session starting detected, resetting session ended flag')
      sessionHasEnded.value = false
    }
    
    // Clear existing timeout
    if (sessionStatusDebounceTimeout) {
      clearTimeout(sessionStatusDebounceTimeout)
    }
    
    // Debounce the status change to prevent flickering (only for non-end statuses)
    sessionStatusDebounceTimeout = setTimeout(() => {
      stableSessionStatus.value = newStatus
      console.log('Stable session status updated to:', newStatus)
      console.log('Is session active after update:', isSessionActive.value)
      console.log('Interface will be:', isSessionActive.value ? 'ENABLED' : 'DISABLED')
    }, 200) // Reduced to 0.2 second debounce for better responsiveness
  }
}, { immediate: true })

const sessionStatusMessage = computed(() => {
  switch (stableSessionStatus.value) {
    case 'idle':
      return 'Session not started'
    case 'running':
      return 'Session active'
    case 'paused':
      return 'Session paused'
    case 'completed':
      return 'Session ended'
    case 'stopped':
      return 'Session stopped'
    case 'ended':
      return 'Session ended'
    default:
      return 'Unknown status'
  }
})

// Debug computed property to help understand session state
const sessionDebugInfo = computed(() => {
  return {
    rawStatus: sessionStatus.value,
    stableStatus: stableSessionStatus.value,
    sessionHasEnded: sessionHasEnded.value,
    isActive: isSessionActive.value,
    timestamp: new Date().toISOString()
  }
})

const participantMoney = computed(() => {
  // First try to get money from participant state
  if (gameState.value.participant?.money !== undefined && gameState.value.participant?.money !== null) {
    return gameState.value.participant.money
  }
  // Fallback to experiment config starting money
  return gameState.value.experiment_config?.startingMoney || 300
})

const productionCount = computed(() => {
  // Use the same backend source as awareness dashboard for consistency
  if (awarenessDashboardData.value.length > 0) {
    // Find current participant in awareness dashboard data
    const currentParticipant = awarenessDashboardData.value.find((p: any) => p.participant_id === participantId.value)
    if (currentParticipant) {
      const count = currentParticipant.specialty_production_used || 0
      console.log('Production count from awareness dashboard data:', count)
      return count
    }
  }
  
  // Fallback to game state if awareness dashboard data is not available
  const count = gameState.value.participant?.specialty_production_used || 0
  console.log('Production count from game state (fallback):', count)
  return count
})

// Function to get orders completed count for a specific participant
const getOrdersCompletedForParticipant = (participantId: string) => {
  if (awarenessDashboardData.value.length > 0) {
    const participant = awarenessDashboardData.value.find((p: any) => p.participant_id === participantId)
    if (participant) {
      const count = participant.orders_completed || 0
      return count
    }
  }
  
  // Fallback to game state if awareness dashboard data is not available
  if (participantId === participantId.value) {
    const count = gameState.value.participant?.orders_completed || 0
    console.log(`Orders completed for ${participantId} (fallback): ${count}`)
    return count
  }
  
  console.log(`Orders completed for ${participantId}: 0 (not found)`)
  return 0
}

// Function to get order completion percentage for a specific participant
const getOrderCompletionPercentageForParticipant = (participantId: string) => {
  const ordersCompleted = getOrdersCompletedForParticipant(participantId)
  const totalOrders = gameState.value.experiment_config?.shapesPerOrder || 3
  
  if (totalOrders === 0) return 0
  return Math.min(Math.round((ordersCompleted / totalOrders) * 100), 100)
}

// Computed property for orders completed count (for current participant only)
const ordersCompletedCount = computed(() => {
  return getOrdersCompletedForParticipant(participantId.value)
})

// Computed property for order completion percentage (for current participant only)
const orderCompletionPercentage = computed(() => {
  return getOrderCompletionPercentageForParticipant(participantId.value)
})

// Computed property for current production with real-time timer
const currentProductionItem = computed(() => {
  // Get backend data
  const backendQueue = gameState.value.participant?.production_queue || []
  
  // Filter out completed items from backend queue
  const activeBackendItems = backendQueue.filter((item: ProductionItem) => 
    item.status !== 'completed'
  )
  
  // If we have a local production item with time remaining, use it (preserve timer)
  if (currentProduction.value && currentProduction.value.time_remaining > 0) {
    console.log('Using existing local production item with timer:', currentProduction.value.time_remaining)
    isProductionInProgress.value = true
    return currentProduction.value
  }
  
  // IMPORTANT: Do NOT automatically pick up backend productions
  // Only use backend data if we explicitly started a production
  // This prevents the queue system from automatically starting productions
  
  // No active production
  console.log('No active production found')
  currentProduction.value = null
  isProductionInProgress.value = false
  
  return null
})

const conversationMessages = computed(() => {
  if (!selectedPlayer.value) return []
  
  const currentDisplayName = extractDisplayName(participantId.value)
  const selectedDisplayName = extractDisplayName(selectedPlayer.value.participant_id)
  
  return messages.value
    .filter((msg: Message) => 
      (msg.sender === currentDisplayName && msg.recipient === selectedDisplayName) ||
      (msg.sender === selectedDisplayName && msg.recipient === currentDisplayName)
    )
    .sort((a: Message, b: Message) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
})

// Add computed property to filter out current participant
const otherParticipants = computed(() => {
  if (!gameState.value.participants) {
    console.log('No participants in gameState')
    return []
  }
  
  const filtered = gameState.value.participants.filter((participant: Participant) => 
    participant.participant_id !== participantId.value
  )
  
  // Use stable order if available, otherwise sort by participant_id
  let sorted: Participant[]
  if (stableParticipantOrder.value.length > 0) {
    // Sort using the stable order
    sorted = filtered.sort((a: Participant, b: Participant) => {
      const aIndex = stableParticipantOrder.value.indexOf(a.participant_id)
      const bIndex = stableParticipantOrder.value.indexOf(b.participant_id)
      
      // If both are in stable order, use that order
      if (aIndex !== -1 && bIndex !== -1) {
        return aIndex - bIndex
      }
      // If only one is in stable order, prioritize the stable one
      if (aIndex !== -1) return -1
      if (bIndex !== -1) return 1
      // If neither is in stable order, sort alphabetically
      return a.participant_id.localeCompare(b.participant_id)
    })
  } else {
    // Fallback to alphabetical sorting
    sorted = filtered.sort((a: Participant, b: Participant) => {
      return a.participant_id.localeCompare(b.participant_id)
    })
  }
  
  console.log('Other participants (stable sorted):', sorted)
  
  // Fallback to awareness dashboard participants if regular list is empty
  if (sorted.length === 0 && awarenessDashboardEnabled.value) {
    console.log('Using awareness dashboard participants as fallback')
    return otherParticipantsWithAwareness.value
  }
  
  return sorted
})

// Add computed property for awareness dashboard participants
const otherParticipantsWithAwareness = computed(() => {
  if (!awarenessDashboardEnabled.value) return []
  
  // Use the awareness dashboard data but filter out the current participant
  // Sort by participant_id to ensure consistent order
  return awarenessDashboardData.value
    .filter((participant: Participant) => participant.participant_id !== participantId.value)
    .sort((a: Participant, b: Participant) => {
      return a.participant_id.localeCompare(b.participant_id)
    })
})

// Add new reactive state for awareness dashboard data
const awarenessDashboardData = ref<Participant[]>([])

// Add stable participant order tracking
const stableParticipantOrder = ref<string[]>([])

// Add function to load awareness dashboard data
const loadAwarenessDashboardData = async () => {
  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    return
  }
  
  // Always load the data even if awareness dashboard is not enabled
  // This ensures the factory panel can use it as a data source

  try {
    const response = await fetch(`/api/participants/status?session_code=${encodeURIComponent(sessionId.value)}`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      }
    })

    if (response.ok) {
      const data = await response.json()
      console.log('Awareness dashboard data received:', data)
      
      // Map the data to the expected format
      const mappedData = data.map((p: any) => ({
        participant_id: p.participant_code,
        shape: p.specialty_shape,
        money: p.money || 300,
        orders_completed: p.orders_completed || 0,
        total_orders: p.total_orders || 8,
        completion_percentage: p.completion_percentage || 0,
        specialty_production_used: p.specialty_production_used || 0,
        login_status: p.login_status || 'inactive'
      }))
      
      // Maintain stable order for awareness dashboard data
      if (stableParticipantOrder.value.length === 0 && mappedData.length > 0) {
        stableParticipantOrder.value = mappedData.map(p => p.participant_id)
        console.log('Established stable participant order from awareness dashboard:', stableParticipantOrder.value)
      }
      
      awarenessDashboardData.value = mappedData;

    } else if (response.status === 401) {
      sessionStorage.clear()
      router.push('/login')
    } else {
      console.error('Failed to load awareness dashboard data:', response.status)
    }
  } catch (error) {
    console.error('Error loading awareness dashboard data:', error)
  }
}

// Communication mode computed properties
const communicationLevel = computed(() => {
  const level = gameState.value.communication_level || 'chat'
  return level
})

const showMessagesTab = computed(() => {
  const show = communicationLevel.value !== 'no_chat'
  return show
})

const isBroadcastMode = computed(() => {
  return communicationLevel.value === 'broadcast'
})

const isChatMode = computed(() => {
  return communicationLevel.value === 'chat'
})

const isNoChatMode = computed(() => {
  return communicationLevel.value === 'no_chat'
})

const awarenessDashboardEnabled = computed(() => {
  // Check if the researcher has enabled the awareness dashboard toggle
  const researcherEnabled = gameState.value.awareness_dashboard_enabled || false
  
  // Check if the experiment's interface configuration allows the awareness dashboard
  const experimentAllows = gameState.value.experiment_interface_config?.awarenessDashboard?.enabled !== false
  
  // Fallback: Check experiment type directly if interface config is not available
  let experimentTypeAllows = true
  if (!gameState.value.experiment_interface_config || Object.keys(gameState.value.experiment_interface_config).length === 0) {
    // If no interface config, check experiment type directly
    const experimentType = gameState.value.experiment_config?.experiment_type || 'shapefactory'
    
    // Essay Ranking should not show awareness dashboard
    if (experimentType === 'essayranking') {
      experimentTypeAllows = false
    }
  } else {
    experimentTypeAllows = experimentAllows
  }
  
  // Both conditions must be true for the awareness dashboard to be shown
  const enabled = researcherEnabled && experimentTypeAllows
  
  
  return enabled
})

// Watch for changes in communication level to reload messages
watch(communicationLevel, (newLevel, oldLevel) => {
  if (newLevel !== oldLevel) {
    console.log('Communication level changed from', oldLevel, 'to', newLevel)
    
    // Only clear messages when switching to no_chat mode or when switching between broadcast and chat
    // This prevents unnecessary clearing when the mode hasn't actually changed
    if (newLevel === 'no_chat') {
      console.log('Switching to no chat mode - clearing messages')
      messages.value = []
    } else if (oldLevel === 'broadcast' && newLevel === 'chat') {
      console.log('Switching from broadcast to chat mode - clearing broadcast messages')
      messages.value = []
    } else if (oldLevel === 'chat' && newLevel === 'broadcast') {
      console.log('Switching from chat to broadcast mode - clearing chat messages')
      messages.value = []
    }
    
    // Reload messages based on new communication mode
    if (newLevel === 'broadcast') {
      console.log('Switching to broadcast mode - loading broadcast messages')
      loadMessages()
      // Clear participant notification dots when switching to broadcast mode since message tab is immediately available
      // But keep tab badge until user actually opens the message tab
      console.log('Broadcast mode active, clearing participant notification dots')
      clearParticipantNotificationDot()
    } else if (newLevel === 'chat') {
      console.log('Switching to chat mode - messages will load when player is selected')
      // In chat mode, messages are loaded when a player is selected
    }
  }
})

// Watch for changes in awareness dashboard enabled to load data
watch(awarenessDashboardEnabled, (newEnabled, oldEnabled) => {
  if (newEnabled !== oldEnabled) {
    console.log('Awareness dashboard enabled changed from', oldEnabled, 'to', newEnabled)
    
    if (newEnabled) {
      console.log('Loading awareness dashboard data...')
      loadAwarenessDashboardData()
    } else {
      console.log('Clearing awareness dashboard data...')
      awarenessDashboardData.value = []
    }
  }
})

// Watch for changes in otherParticipants to automatically select the first one
watch(otherParticipants, (newParticipants, oldParticipants) => {
  // Only auto-select if we don't have a selected player and there are participants available
  if (!selectedPlayer.value && newParticipants.length > 0) {
    // Additional validation: ensure the participant has a valid ID
    const firstParticipant = newParticipants[0]
    if (firstParticipant && firstParticipant.participant_id && firstParticipant.participant_id.trim() !== '') {
      console.log('Auto-selecting first participant:', firstParticipant.participant_id)
      selectPlayer(firstParticipant)
    } else {
      console.warn('Skipping auto-selection of invalid participant:', firstParticipant)
    }
  }
}, { immediate: false }) // Don't run immediately, wait for the first change

const broadcastMessages = computed(() => {
  if (!isBroadcastMode.value) return []
  
  return messages.value
    .filter((msg: Message) => msg.recipient === 'all' || msg.recipient === null)
    .sort((a: Message, b: Message) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
})

// Unread message count for broadcast messages
const unreadBroadcastCount = computed(() => {
  if (!isBroadcastMode.value) return 0
  
  const currentDisplayName = extractDisplayName(participantId.value)
  
  return broadcastMessages.value.filter((msg: Message) => {
    const messageTime = new Date(msg.timestamp).getTime()
    return messageTime > lastReadTimestamp.value && msg.sender !== currentDisplayName
  }).length
})

// Unread message count for chat messages with selected player
const unreadChatCount = computed(() => {
  if (!selectedPlayer.value || !isChatMode.value) return 0
  
  const currentDisplayName = extractDisplayName(participantId.value)
  
  return conversationMessages.value.filter((msg: Message) => {
    const messageTime = new Date(msg.timestamp).getTime()
    return messageTime > lastReadTimestamp.value && msg.sender !== currentDisplayName
  }).length
})

// Total unread messages count
const totalUnreadCount = computed(() => {
  if (isBroadcastMode.value) {
    return unreadBroadcastCount.value
  } else if (isChatMode.value && selectedPlayer.value) {
    return unreadChatCount.value
  }
  return 0
})

const productionCostComparison = computed(() => {
  const specialtyCost = gameState.value.experiment_config?.specialtyCost || 8
  const regularCost = gameState.value.experiment_config?.regularCost || 25
  return `($${specialtyCost} vs $${regularCost})`
})

// ECL experiment detection
const isECLExperiment = computed(() => {
  const experimentType = gameState.value.experiment_config?.experiment_type
  console.log('🔍 ECL Detection Debug:')
  console.log('  - Experiment Type:', experimentType)
  console.log('  - Full Experiment Config:', gameState.value.experiment_config)
  console.log('  - Is ECL Experiment:', experimentType === 'custom_ecl')
  return experimentType === 'custom_ecl'
})

// WordGuessing experiment detection
const isWordGuessingExperiment = computed(() => {
  const experimentType = gameState.value.experiment_config?.experiment_type
  return experimentType === 'wordguessing'
})

// WordGuessing specific reactive data for assigned words
const assignedWords = computed(() => {
  if (gameState.value.experiment_config?.experiment_type === 'wordguessing') {
    const participant = gameState.value.participant as any
    const words = participant?.assigned_words || []
    console.log('🔍 WordGuessing assigned words:', { 
      words, 
      participant, 
      experiment_type: gameState.value.experiment_config?.experiment_type,
      participant_role: participant?.role,
      is_hinter: participant?.role === 'hinter'
    })
    return Array.isArray(words) ? words : []
  }
  return []
})

// Check if current participant is a hinter in wordguessing experiment
const isHinter = computed(() => {
  if (gameState.value.experiment_config?.experiment_type === 'wordguessing') {
    const participant = gameState.value.participant as any
    const role = participant?.role
    const isHinterResult = role === 'hinter'
    console.log('🔍 WordGuessing isHinter check:', { 
      role, 
      participant, 
      isHinterResult,
      experiment_type: gameState.value.experiment_config?.experiment_type
    })
    return isHinterResult
  }
  return false
})

// Watch for experiment type changes and reconfigure interface
watch(() => gameState.value.experiment_config?.experiment_type, async (newType, oldType) => {
  if (newType && newType !== oldType) {
    console.log('🔧 Experiment type changed from', oldType, 'to', newType, '- reconfiguring interface')
    await autoConfigureInterface()
  }
}, { immediate: false })

// Computed properties for filtered trade data based on selected participant
const filteredPendingOffers = computed(() => {
  // In broadcast mode, show all pending offers since no specific participant is selected
  if (isBroadcastMode.value) {
    console.log('Broadcast mode: showing all pending offers:', pendingOffers.value.length)
    return pendingOffers.value
  }
  
  // In chat mode, filter by selected participant
  if (!selectedPlayer.value) {
    console.log('No selected player: showing no pending offers')
    return []
  }
  
  const filtered = pendingOffers.value.filter((offer: TradeOffer) => {
    // Extract display names for comparison
    const currentDisplayName = extractDisplayName(participantId.value)
    const selectedDisplayName = selectedPlayer.value?.participant_id ? extractDisplayName(selectedPlayer.value.participant_id) : null
    
    // Show offers that involve the selected participant
    const involvesSelectedPlayer = offer.proposer_code === selectedDisplayName || 
                                  offer.recipient_code === selectedDisplayName
    
    // Also show offers that involve the current participant
    const involvesCurrentParticipant = offer.proposer_code === currentDisplayName || 
                                      offer.recipient_code === currentDisplayName
    
    // Return true if both conditions are met (this ensures we show all relevant offers)
    return involvesSelectedPlayer && involvesCurrentParticipant
  })
  
  console.log(`Filtered pending offers for ${selectedPlayer.value.participant_id}: ${filtered.length} out of ${pendingOffers.value.length} total`)
  return filtered
})

const filteredTradeHistory = computed(() => {
  // In broadcast mode, show all trade history since no specific participant is selected
  if (isBroadcastMode.value) {
    return tradeHistory.value
  }
  
  // In chat mode, show trade history when a participant is selected
  if (!selectedPlayer.value) return []
  
  return tradeHistory.value.filter((trade: TradeHistory) => {
    // Extract display names for comparison
    const currentDisplayName = extractDisplayName(participantId.value)
    const selectedDisplayName = selectedPlayer.value?.participant_id ? extractDisplayName(selectedPlayer.value.participant_id) : null
    
    // Filter trade history to show only trades involving the selected participant
    const involvesSelectedPlayer = trade.proposer_code === selectedDisplayName || 
                                  trade.recipient_code === selectedDisplayName
    
    // Also ensure the current participant was involved in the trade
    const involvesCurrentParticipant = trade.proposer_code === currentDisplayName || 
                                      trade.recipient_code === currentDisplayName
    
    return involvesSelectedPlayer && involvesCurrentParticipant
  })
})

// Helper function to extract display name from participant code (for session-aware naming)
const extractDisplayName = (participantCode: string) => {
  if (participantCode && participantCode.includes('_')) {
    return participantCode.split('_')[0]
  }
  return participantCode
}

// Methods
const getShapeDisplayName = (shape: string) => {
  return shapeConfig[shape as keyof typeof shapeConfig]?.name || shape
}

const getShapeIcon = (shape: string) => {
  return shapeConfig[shape as keyof typeof shapeConfig]?.icon || 'fa-question'
}

const getShapeColor = (shape: string) => {
  return shapeConfig[shape as keyof typeof shapeConfig]?.color || '#6c757d'
}

const getProductionCost = (shape: string) => {
  const isSpecialty = shape === gameState.value.participant?.shape
  const specialtyCost = gameState.value.experiment_config?.specialtyCost || 8
  const regularCost = gameState.value.experiment_config?.regularCost || 25
  return isSpecialty ? `$${specialtyCost}` : `$${regularCost}`
}

// Check if there are unread messages or trades from a specific participant
const hasUnreadFromParticipant = (participantId: string) => {
  // Check for unread messages from this participant
  const unreadCount = unreadMessagesByParticipant.value.get(participantId) || 0
  const hasUnreadMessages = unreadCount > 0
  
  // Check for pending trade offers from this participant
  const hasPendingTrades = pendingOffers.value.some((offer: TradeOffer) => {
    const currentDisplayName = extractDisplayName(participantId.value)
    const participantDisplayName = extractDisplayName(participantId)
    const isFromParticipant = offer.proposer_code === participantDisplayName
    const isToMe = offer.recipient_code === currentDisplayName
    const isIncoming = !offer.is_outgoing
    
    return isFromParticipant && isToMe && isIncoming
  })
  
  const hasUnread = hasUnreadMessages || hasPendingTrades
  
  // Debug logging for notification dots
  if (hasUnread) {
    console.log(`Notification dot for ${participantId}: messages=${hasUnreadMessages} (${unreadCount}), trades=${hasPendingTrades}`)
  }
  
  return hasUnread
}

// Check if there are unread messages from a specific participant
const hasUnreadMessagesFromParticipant = (participantId: string) => {
  const unreadCount = unreadMessagesByParticipant.value.get(participantId) || 0
  return unreadCount > 0
}

// Check if there are unread trades from a specific participant
const hasUnreadTradesFromParticipant = (participantId: string) => {
  const unreadCount = unreadTradeOffersByParticipant.value.get(participantId) || 0
  return unreadCount > 0
}

// Check if there are any unread trades from any participant
const hasAnyUnreadTrades = () => {
  for (const [participantId, unreadCount] of unreadTradeOffersByParticipant.value) {
    if (unreadCount > 0) {
      return true
    }
  }
  return false
}

const formatTime = (timestamp: Date) => {
  return new Date(timestamp).toLocaleTimeString()
}

const formatProductionTime = (seconds: number) => {
  if (seconds < 60) {
    return `${seconds}s`
  } else {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}s`
  }
}

// Update production timer countdown
const updateProductionTimer = () => {
  if (!currentProduction.value || currentProduction.value.time_remaining <= 0) {
    return // No production to update
  }
  
  console.log('=== PRODUCTION TIMER UPDATE ===')
  console.log('Current production:', currentProduction.value)
  
  // Update timer
  currentProduction.value.time_remaining = Math.max(0, currentProduction.value.time_remaining - 1)
  console.log(`Updated timer for ${currentProduction.value.shape}: ${currentProduction.value.time_remaining}s remaining`)
  
  // If timer reaches 0, complete production
  if (currentProduction.value.time_remaining === 0) {
    console.log(`Production completed: ${currentProduction.value.shape}`)
    
    // Check if we've already processed this completion to prevent duplicates
    if (completedProductionItems.value.has(currentProduction.value.id)) {
      return
    }
    
    // Mark as processed
    completedProductionItems.value.add(currentProduction.value.id)
    
    // Store values before clearing production state
    const completedShape = currentProduction.value.shape
    const completedProductionId = currentProduction.value.id
    
    // Add to inventory immediately for instant feedback
    addShapeToInventory(completedShape)
    
    // Clear production state immediately and prevent new productions
    currentProduction.value = null
    isProductionInProgress.value = false
    explicitlyStartedProduction.value = false
    console.log('Production state cleared')
    console.log('Current production after clearing:', currentProduction.value)
    console.log('Production in progress after clearing:', isProductionInProgress.value)
    
    // Force reactive update
    nextTick(() => {
      console.log('Production completion reactive update completed')
    })
    
    // Trigger backend processing immediately to ensure inventory is updated on server
    processCompletedProductions()
    
    // Add extra protection to prevent inventory overrides for a longer time during production
    const productionProtectionKey = `production_${completedShape}_${Date.now()}`
    recentlyAddedShapes.value.add(productionProtectionKey)
    
    // Remove production protection after backend has time to process
    setTimeout(() => {
      recentlyAddedShapes.value.delete(productionProtectionKey)
      console.log(`🔓 Removed production protection: ${productionProtectionKey}`)
    }, 5000) // Extended protection for production completion
    
    // Prevent any new productions from starting for a short time
    setTimeout(() => {
      completedProductionItems.value.delete(completedProductionId)
      console.log(`Removed ${completedProductionId} from completed items tracking`)
    }, 2000) // Keep in tracking for 2 seconds to prevent immediate duplicates
  }
}

// Trade offer helper methods
const isOutgoingOffer = (offer: TradeOffer) => {
  // Use the is_outgoing field from the API which tells us who initiated the trade
  return offer.is_outgoing
}

const getOfferSender = (offer: TradeOffer) => {
  // Return who sent this offer (who initiated it) - always the proposer
  return offer.proposer_code
}

const getOfferRecipient = (offer: TradeOffer) => {
  // Return who should respond to this offer (the other party) - always the recipient
  return offer.recipient_code
}

const getRecipientDisplay = (offer: TradeOffer) => {
  const recipient = getOfferRecipient(offer)
  console.log('Debug - recipient:', recipient, 'participantId:', participantId.value)
  return recipient === participantId.value ? 'your' : recipient + "'s"
}

const getOfferPriceDisplay = (offer: TradeOffer) => {
  return `$${offer.price}`
}

// UI Methods
const showRulesPopup = () => {
  showRules.value = true
}

const hideRulesPopup = () => {
  showRules.value = false
}

const hideRulesIfClickedOutside = (event: Event) => {
  if (event.target === event.currentTarget) {
    hideRulesPopup()
  }
}

const selectPlayer = (participant: Participant) => {
  console.log('Selecting player:', participant.participant_id)
  
  // Validate that the participant exists in the current session
  const validParticipants = gameState.value.participants || []
  const participantExists = validParticipants.some(p => p.participant_id === participant.participant_id)
  
  if (!participantExists) {
    console.warn('Attempted to select participant that does not exist in current session:', participant.participant_id)
    return
  }
  
  selectedPlayer.value = participant
  
  // Load all trade data
  loadAllTradeData()
  
  // Load all messages to update notification dots for all participants
  loadMessages()
  
  // Handle message loading based on communication mode
  if (isBroadcastMode.value) {
    console.log('Loading broadcast messages for all participants')
    // In broadcast mode, loadMessages() will handle all messages including broadcast
    loadMessages()
  } else if (isChatMode.value) {
    console.log('Loading chat messages for participant:', participant.participant_id)
    // In chat mode, loadMessages() will handle all messages including conversation
    loadMessages()
  } else {
    console.log('No chat mode - not loading messages')
  }
  
  // Clear participant notification dot when selecting a participant if message tab is available
  // This removes the notification dot as soon as the message tab is displayed, but keeps tab badge
  if (showMessagesTab.value) {
    console.log('Message tab is available, clearing participant notification dot for:', participant.participant_id)
    clearParticipantNotificationDot()
  }
  
  unreadTradeOffersByParticipant.value.delete(participant.participant_id)
  
  // Force Vue reactivity update for notification dots
  nextTick(() => {
    unreadTradeOffersByParticipant.value = new Map(unreadTradeOffersByParticipant.value)
  })
}

// Function to mark messages as read (for tab badges - only when message tab is active)
const markMessagesAsRead = () => {
  console.log('Marking messages as read, setting timestamp to:', Date.now())
  lastReadTimestamp.value = Date.now()
  unreadMessages.value.clear()
  
  // Clear unread messages for the selected participant
  if (selectedPlayer.value) {
    console.log('Clearing unread messages for participant:', selectedPlayer.value.participant_id)
    unreadMessagesByParticipant.value.set(selectedPlayer.value.participant_id, 0)
    lastReadTimestampByParticipant.value.set(selectedPlayer.value.participant_id, Date.now())
  }
  
  // Force Vue reactivity update for notification dots
  nextTick(() => {
    unreadMessagesByParticipant.value = new Map(unreadMessagesByParticipant.value)
  })
  
  // Refresh all messages to update notification dots for all participants
  loadMessages()
}

// Function to clear participant notification dots (when message tab becomes available)
const clearParticipantNotificationDot = () => {
  if (selectedPlayer.value) {
    console.log('Clearing participant notification dot for:', selectedPlayer.value.participant_id)
    // Only clear the participant-specific unread count, not the tab badge timestamp
    unreadMessagesByParticipant.value.set(selectedPlayer.value.participant_id, 0)
    lastReadTimestampByParticipant.value.set(selectedPlayer.value.participant_id, Date.now())
  } else if (isBroadcastMode.value) {
    console.log('Clearing participant notification dots for all participants in broadcast mode')
    // In broadcast mode, clear notification dots for all participants since they can all see messages
    for (const participant of otherParticipants.value) {
      unreadMessagesByParticipant.value.set(participant.participant_id, 0)
      lastReadTimestampByParticipant.value.set(participant.participant_id, Date.now())
    }
  }
  
  // Force Vue reactivity update for notification dots
  nextTick(() => {
    unreadMessagesByParticipant.value = new Map(unreadMessagesByParticipant.value)
  })
  
  // Refresh all messages to update notification dots for all participants
  loadMessages()
  
  // Also refresh all trade data to update trade notification dots for all participants
  loadAllTradeData()
}

// Function to clear trade notifications when switching to trade tab
const clearTradeNotifications = () => {
  console.log('Clearing trade notifications')
  
  // Clear unread trade tracking for the selected participant
  if (selectedPlayer.value) {
    unreadTradeOffersByParticipant.value.delete(selectedPlayer.value.participant_id)
    console.log('Cleared trade notifications for participant:', selectedPlayer.value.participant_id)
  } else if (isBroadcastMode.value) {
    // In broadcast mode, clear all unread trade tracking
    unreadTradeOffersByParticipant.value.clear()
    console.log('Cleared all trade notifications (broadcast mode)')
  }
  
  // Force Vue reactivity update for notification dots
  nextTick(() => {
    unreadTradeOffersByParticipant.value = new Map(unreadTradeOffersByParticipant.value)
  })
}

// Watch for when user switches to message tab to mark messages as read
watch(currentTab, (newTab) => {
  if (newTab === 'message') {
    console.log('User switched to message tab, marking messages as read')
    markMessagesAsRead()
  } else if (newTab === 'trade') {
    console.log('User switched to trade tab, clearing trade notifications')
    clearTradeNotifications()
  }
})

// Watch for interface configuration changes to handle tab switching
watch(() => interfaceConfig.value.socialPanel, (newConfig) => {
  // If trade tab is disabled and we're currently on trade tab, switch to message tab
  if (!newConfig.showTradeTab && currentTab.value === 'trade') {
    if (newConfig.showChatTab) {
      currentTab.value = 'message'
    }
  }
  // If chat tab is disabled and we're currently on message tab, switch to trade tab
  else if (!newConfig.showChatTab && currentTab.value === 'message') {
    if (newConfig.showTradeTab) {
      currentTab.value = 'trade'
    }
  }
}, { deep: true })

// Watch for interface configuration changes to debug UI updates
watch(() => interfaceConfig.value, (newConfig) => {
  console.log('🔧 Interface configuration changed:', newConfig)
  console.log('🔧 Current myAction type:', newConfig.myAction?.type)
  console.log('🔧 Current myStatus:', newConfig.myStatus)
  console.log('🔧 Current socialPanel:', newConfig.socialPanel)
}, { deep: true, immediate: true })

// Watch for changes in participants list to update unread counts
watch(otherParticipants, async (newParticipants) => {
  if (newParticipants.length > 0) {
    console.log('Participants list changed, updating unread counts...')
    await initializeUnreadCounts()
  }
}, { deep: true })


// Make debug function available globally
if (typeof window !== 'undefined') {
  // (window as any).debugUnreadStatus = debugUnreadStatus
  
  // Add production debug function
  ;(window as any).debugProduction = () => {
    console.log('=== PRODUCTION DEBUG ===')
    console.log('Current production:', currentProduction.value)
    console.log('Backend production queue:', gameState.value.participant?.production_queue)
    console.log('Completed items tracking:', Array.from(completedProductionItems.value))
    console.log('Production in progress flag:', isProductionInProgress.value)
    console.log('Explicitly started production flag:', explicitlyStartedProduction.value)
    console.log('Current production item computed:', currentProductionItem.value)
  }
  
  // Add inventory debug function
  ;(window as any).debugInventory = () => {
    console.log('=== INVENTORY DEBUG ===')
    console.log('Frontend inventory (shapes_acquired):', gameState.value.participant?.shapes_acquired)
    console.log('Inventory count by shape:')
    const inventory = gameState.value.participant?.shapes_acquired || []
    const counts: { [key: string]: number } = {}
    inventory.forEach(shape => {
      counts[shape] = (counts[shape] || 0) + 1
    })
    console.log('Shape counts:', counts)
    console.log('Total inventory items:', inventory.length)
  }
  
  // Add session status debug function
  ;(window as any).debugSessionStatus = () => {
    console.log('=== SESSION STATUS DEBUG ===')
    console.log('Raw session status:', sessionStatus.value)
    console.log('Stable session status:', stableSessionStatus.value)
    console.log('Session has ended flag:', sessionHasEnded.value)
    console.log('Is session active:', isSessionActive.value)
    console.log('Timer running:', isTimerRunning.value)
    console.log('Time remaining:', timeRemaining.value)
    console.log('Experiment config:', gameState.value.experiment_config)
  }
  
  // Add function to force clear production state
  ;(window as any).clearProductionState = () => {
    console.log('=== FORCE CLEARING PRODUCTION STATE ===')
    currentProduction.value = null
    isProductionInProgress.value = false
    explicitlyStartedProduction.value = false
    completedProductionItems.value.clear()
    console.log('Production state and completed items cleared')
  }
  
  // Add function to check production state
  ;(window as any).checkProductionState = () => {
    console.log('=== PRODUCTION STATE CHECK ===')
    console.log('Current production:', currentProduction.value)
    console.log('Production in progress:', isProductionInProgress.value)
    console.log('Explicitly started production:', explicitlyStartedProduction.value)
    console.log('Completed items:', Array.from(completedProductionItems.value))
    console.log('Backend queue:', gameState.value.participant?.production_queue)
  }
  
  // Add function to force refresh game state
  ;(window as any).forceRefreshGameState = async () => {
    console.log('=== FORCE REFRESHING GAME STATE ===')
    if (isAuthenticated()) {
      await loadGameStateIncremental()
      console.log('Game state refreshed')
      ;(window as any).debugInventory()
    } else {
      console.log('Not authenticated, cannot refresh game state')
    }
  }
  
  // Add function to debug rankings
  ;(window as any).debugRankings = () => {
    console.log('=== RANKINGS DEBUG ===')
    console.log('Game state participant:', gameState.value.participant)
    console.log('Current rankings:', gameState.value.participant?.current_rankings)
    console.log('Submitted rankings count:', gameState.value.participant?.submitted_rankings_count)
    console.log('Sorted rankings:', sortedCurrentRankings.value)
    console.log('Assigned essays:', assignedEssays.value)
  }
  
  // Add function to check notification state
  ;(window as any).checkNotificationState = () => {
    console.log('=== NOTIFICATION STATE CHECK ===')
    console.log('Unread messages by participant:', Object.fromEntries(unreadMessagesByParticipant.value))
    console.log('Unread trade offers by participant:', Object.fromEntries(unreadTradeOffersByParticipant.value))
    console.log('Pending offers:', pendingOffers.value)
    console.log('Selected player:', selectedPlayer.value?.participant_id)
    console.log('Current tab:', currentTab.value)
    
    // Check specific participant notifications
    if (selectedPlayer.value) {
      const participantId = selectedPlayer.value.participant_id
      console.log(`Notifications for ${participantId}:`)
      console.log(`- Messages: ${hasUnreadMessagesFromParticipant(participantId)}`)
      console.log(`- Trades: ${hasUnreadTradesFromParticipant(participantId)}`)
    }
  }
  
  // Add function to check trade filtering
  ;(window as any).checkTradeFiltering = () => {
    console.log('=== TRADE FILTERING CHECK ===')
    console.log('Total pending offers:', pendingOffers.value.length)
    console.log('Filtered pending offers:', filteredPendingOffers.value.length)
    console.log('Selected player:', selectedPlayer.value?.participant_id)
    console.log('Broadcast mode:', isBroadcastMode.value)
    console.log('Chat mode:', isChatMode.value)
    
    if (selectedPlayer.value) {
      console.log('Pending offers involving selected player:')
      filteredPendingOffers.value.forEach((offer, index) => {
        console.log(`  ${index + 1}. ${offer.offer_type} ${offer.quantity}x ${offer.shape} for $${offer.price}`)
        console.log(`     Proposer: ${offer.proposer_code}, Recipient: ${offer.recipient_code}`)
      })
    }
  }
  
  // Add function to manually reset session ended flag for debugging
  ;(window as any).resetSessionEndedFlag = () => {
    console.log('=== MANUALLY RESETTING SESSION ENDED FLAG ===')
    sessionHasEnded.value = false
    console.log('Session ended flag reset to false')
    console.log('Current session status:', stableSessionStatus.value)
    console.log('Is session active:', isSessionActive.value)
  }
  
  // Add function to check session completion status
  ;(window as any).checkSessionCompletionStatus = () => {
    console.log('=== SESSION COMPLETION STATUS CHECK ===')
    console.log('Experiment config status:', gameState.value.experiment_config?.experiment_status)
    console.log('Session has ended flag:', sessionHasEnded.value)
    console.log('Stable session status:', stableSessionStatus.value)
    console.log('Is session active:', isSessionActive.value)
    console.log('Has checked auto-start:', hasCheckedAutoStart.value)
    console.log('Session ID:', sessionId.value)
    console.log('Participant ID:', participantId.value)
  }
}

// Function to initialize unread counts for all participants
const initializeUnreadCounts = async () => {
  console.log('Initializing unread counts for all participants...')
  
  // Note: Removed redundant message loading that was causing messages to be cleared
  // Unread counts will be updated via WebSocket events instead
  console.log('Unread counts will be updated via WebSocket events')
}

// Game Actions
const startProduction = async () => {
  if (!isSessionActive.value) {
    alert('Session is not active. Please wait for the researcher to start the session.')
    return
  }

  if (!selectedShape.value) {
    alert('Please select a shape to produce')
    return
  }

  // Check production limit
  const maxProductionNum = gameState.value.experiment_config?.maxProductionNum || 6
  const currentProductionUsed = gameState.value.participant?.specialty_production_used || 0
  
  if (currentProductionUsed >= maxProductionNum) {
    alert(`You have reached the maximum production limit of ${maxProductionNum} shapes. You cannot produce any more shapes.`)
    return
  }

  // Check if there's already a production in progress
  if (isProductionInProgress.value || currentProduction.value) {
    console.log('Production already in progress, blocking new production')
    console.log('isProductionInProgress:', isProductionInProgress.value)
    console.log('currentProduction:', currentProduction.value)
    alert('You can only produce one shape at a time. Please wait for the current production to complete.')
    return
  }
  
  // Note: Removed check for recently completed productions since we're not using backend queue

  // Prevent duplicate production calls
  if (isProductionInProgress.value) {
    console.log('Production already in progress, ignoring duplicate call')
    return
  }

  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    router.push('/login')
    return
  }

  try {
    // Set production in progress flag
    isProductionInProgress.value = true
    
    console.log('=== STARTING PRODUCTION ===')
    console.log('Selected shape:', selectedShape.value)
    console.log('Current production state:', isProductionInProgress.value)
    
    const response = await fetch('/api/produce-shape', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        shape: selectedShape.value,
        quantity: 1
      })
    })

    if (response.ok) {
      const result = await response.json()
      
      // Check if the API returned an error despite 200 status
      if (result.error) {
        alert(`Production Error: ${result.error}`)
        isProductionInProgress.value = false // Reset flag on error
        return
      }
      
      const shapeName = getShapeDisplayName(selectedShape.value)
      const originalSelectedShape = selectedShape.value // Store the shape before clearing
      console.log('Production started successfully:', result)
      console.log('Selected shape:', selectedShape.value)
      console.log('Shape name:', shapeName)
      selectedShape.value = ''
      
      if (isAuthenticated()) {
            // Refresh awareness dashboard data to update production counts for all participants
    // This will update both the awareness dashboard and the factory panel since they use the same data source
    loadAwarenessDashboardData()
        
        console.log('Loading game state after production start...')
        await loadGameStateIncremental()
        console.log('Game state loaded. Production queue:', gameState.value.participant?.production_queue)
        
        // Set current production from backend response
        if (result.production_id) {
          console.log('=== PRODUCTION START DEBUG ===')
          console.log('Original selected shape:', originalSelectedShape)
          console.log('Current selected shape (after clearing):', selectedShape.value)
          console.log('Result production time:', result.production_time)
          console.log('Result production duration seconds:', result.production_duration_seconds)
          console.log('Config production time:', gameState.value.experiment_config?.productionTime)
          console.log('Full result:', result)
          
          // Get the shape from the result message or use the original selected shape
          const shapeFromMessage = result.message?.match(/Started production of \d+x (\w+)/)?.[1]
          const productionShape = shapeFromMessage || originalSelectedShape
          
          console.log('Shape from message:', shapeFromMessage)
          console.log('Final production shape:', productionShape)
          
          currentProduction.value = {
            id: result.production_id,
            shape: productionShape,
            time_remaining: result.production_duration_seconds || result.production_time || gameState.value.experiment_config?.productionTime || 30,
            status: 'in_progress'
          }
          isProductionInProgress.value = true
          explicitlyStartedProduction.value = true
          console.log('Set current production:', currentProduction.value)
          
          // Force reactive update
          nextTick(() => {
            console.log('Production start reactive update completed')
          })
        }
      }
    } else if (response.status === 401) {
      // Token expired
      sessionStorage.clear()
      router.push('/login')
    } else {
      const errorData = await response.json()
      const errorMessage = errorData.error || errorData.message || 'Unknown error occurred'
      alert(`Error: ${errorMessage}`)
      isProductionInProgress.value = false // Reset flag on error
    }
  } catch (error) {
    console.error('Error starting production:', error)
    alert('Network error. Please try again.')
    isProductionInProgress.value = false // Reset flag on error
  }
}

const fulfillOrders = async () => {
  if (!isSessionActive.value) {
    alert('Session is not active. Please wait for the researcher to start the session.')
    return
  }

  if (selectedOrders.value.length === 0) {
    alert('Please select orders to fulfill')
    return
  }

  // Don't refresh game state before fulfillment to prevent double refresh
  // The order fulfillment will be handled by the API response and WebSocket events

  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    router.push('/login')
    return
  }

  try {
    const response = await fetch('/api/fulfill-orders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        order_indices: selectedOrders.value
      })
    })

    if (response.ok) {
      const result = await response.json()
      
      // Provide immediate UI feedback by updating orders locally
      if (result.success && gameState.value.participant?.orders && selectedOrders.value.length > 0) {
        console.log('Order fulfillment successful, updating UI immediately')
        
        // Create a copy of current orders and remove fulfilled orders (sort indices in reverse order)
        const updatedOrders = [...gameState.value.participant.orders]
        const sortedIndices = [...selectedOrders.value].sort((a, b) => b - a) // Sort in descending order
        
        // Remove orders from highest index to lowest to maintain correct indices
        sortedIndices.forEach(index => {
          updatedOrders.splice(index, 1)
        })
        
        // Update orders immediately for smooth UX
        gameState.value.participant.orders = updatedOrders
        
        // Protect from backend overwrites for a short time
        const protectionKey = `fulfilled_${Date.now()}`
        recentlyFulfilledOrders.value.add(protectionKey)
        
        // Remove protection after backend processing is complete
        setTimeout(() => {
          recentlyFulfilledOrders.value.delete(protectionKey)
          console.log(`🔓 Removed order fulfillment protection: ${protectionKey}`)
        }, 5000) // Protect for 5 seconds
        
        // Update money immediately if provided
        if (result.new_money !== undefined) {
          gameState.value.participant.money = result.new_money
        }
        
        // Update inventory immediately if provided
        if (result.new_inventory !== undefined) {
          gameState.value.participant.shapes_acquired = result.new_inventory
          console.log('Updated inventory via API response:', result.new_inventory)
          
          // Clear any shape addition protection to allow inventory reductions
          if (recentlyAddedShapes.value.size > 0) {
            recentlyAddedShapes.value.clear()
            console.log('Cleared recently added shapes protection for order fulfillment')
          }
        }
        
        console.log('Immediate UI update completed')
      }
      
      const message = result.message || result.error || 'Order fulfillment completed'
      alert(message + (result.score_gained ? ` (+${result.score_gained} points)` : ''))
      
      // Clear selections - no need for immediate game state refresh as we updated locally
      selectedOrders.value = []
    } else if (response.status === 401) {
      sessionStorage.clear()
      router.push('/login')
    } else {
      const errorData = await response.json()
      const errorMessage = errorData.error || errorData.message || 'Unknown error occurred'
      alert(`Error: ${errorMessage}`)
    }
  } catch (error) {
    console.error('Error fulfilling orders:', error)
    alert('Network error. Please try again.')
  }
}

const confirmFulfillOrder = async () => {
  if (!isSessionActive.value) {
    alert('Session is not active. Please wait for the researcher to start the session.')
    return
  }

  if (selectedOrderIndex.value === -1) {
    alert('No order selected')
    return
  }

  // Don't refresh game state before fulfillment to prevent double refresh
  // The order fulfillment will be handled by the API response and WebSocket events

  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    router.push('/login')
    return
  }

  try {
    const response = await fetch('/api/fulfill-orders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        order_indices: [selectedOrderIndex.value]
      })
    })

    if (response.ok) {
      const result = await response.json()
      
      // Provide immediate UI feedback by updating orders locally
      if (result.success && gameState.value.participant?.orders) {
        console.log('Order fulfillment successful, updating UI immediately')
        
        // Create a copy of current orders and remove the fulfilled order
        const updatedOrders = [...gameState.value.participant.orders]
        updatedOrders.splice(selectedOrderIndex.value, 1)
        
        // Update orders immediately for smooth UX
        gameState.value.participant.orders = updatedOrders
        
        // Protect from backend overwrites for a short time
        const protectionKey = `fulfilled_${Date.now()}`
        recentlyFulfilledOrders.value.add(protectionKey)
        
        // Remove protection after backend processing is complete
        setTimeout(() => {
          recentlyFulfilledOrders.value.delete(protectionKey)
          console.log(`🔓 Removed order fulfillment protection: ${protectionKey}`)
        }, 5000) // Protect for 5 seconds
        
        // Update money immediately if provided
        if (result.new_money !== undefined) {
          gameState.value.participant.money = result.new_money
        }
        
        // Update inventory immediately if provided
        if (result.new_inventory !== undefined) {
          gameState.value.participant.shapes_acquired = result.new_inventory
          console.log('Updated inventory via API response:', result.new_inventory)
          
          // Clear any shape addition protection to allow inventory reductions
          if (recentlyAddedShapes.value.size > 0) {
            recentlyAddedShapes.value.clear()
            console.log('Cleared recently added shapes protection for order fulfillment')
          }
        }
        
        console.log('Immediate UI update completed')
      }
      
      const message = result.message || result.error || 'Order fulfillment completed'
      alert(message + (result.score_gained ? ` (+${result.score_gained} points)` : ''))
      
      // Close popup - no need for immediate game state refresh as we updated locally
      closeOrderFulfillmentPopup()
    } else if (response.status === 401) {
      sessionStorage.clear()
      router.push('/login')
    } else {
      const errorData = await response.json()
      const errorMessage = errorData.error || errorData.message || 'Unknown error occurred'
      alert(`Error: ${errorMessage}`)
    }
  } catch (error) {
    console.error('Error fulfilling order:', error)
    alert('Network error. Please try again.')
  }
}

const proposeTradeOffer = async () => {
  if (!isSessionActive.value) {
    alert('Session is not active. Please wait for the researcher to start the session.')
    return
  }

  // Get trade price limits from experiment config
  const minTradePrice = gameState.value.experiment_config?.minTradePrice || 15
  const maxTradePrice = gameState.value.experiment_config?.maxTradePrice || 30

  if (!tradePrice.value || tradePrice.value < minTradePrice || tradePrice.value > maxTradePrice) {
    alert(`Please enter a valid price between $${minTradePrice}-${maxTradePrice}`)
    return
  }

  // DayTrader mode - no need to select player or shape
  if (interfaceConfig.value.myAction.type === 'daytrader') {
    const authToken = sessionStorage.getItem('auth_token')
    if (!authToken) {
      router.push('/login')
      return
    }

    try {
      const response = await fetch('/api/daytrader/make-investment', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          participant_code: participantId.value,
          session_code: sessionId.value,
          invest_price: Number(tradePrice.value),
          invest_decision_type: decisionType.value
        })
      })

      if (response.ok) {
        const result = await response.json()
        console.log('✅ Investment successful:', result)
        alert(`Investment recorded: $${tradePrice.value} (${decisionType.value})`)
        console.log('🔄 Reloading game state...')
        await loadGameStateIncremental()
        console.log('🔄 Loading investment history...')
        await loadInvestmentHistory()
      } else if (response.status === 401) {
        sessionStorage.clear()
        router.push('/login')
      } else {
        const errorData = await response.json()
        const errorMessage = errorData.error || errorData.message || 'Unknown error'
        alert(`Error: ${errorMessage}`)
      }
    } catch (err) {
      console.error('Error making investment:', err)
      alert('Network error. Please try again.')
    }
    return
  }

  // Shape Factory mode - require player and shape selection
  if (!selectedPlayer.value) {
    alert('Please select a player first')
    return
  }

  if (!tradeShape.value) {
    alert('Please select a shape to trade')
    return
  }

  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    router.push('/login')
    return
  }

  const tradedShape = tradeShape.value

  try {
    const response = await fetch('/api/create-trade-offer', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        session_code: sessionId.value,
        recipient: selectedPlayer.value.participant_id,
        offer_type: tradeType.value,
        shape: tradedShape,
        quantity: 1,
        price_per_unit: tradePrice.value
      })
    })

    if (response.ok) {
      const actionText = tradeType.value === 'sell' ? 'sell' : 'buy'
      alert(`Trade offer sent: ${actionText} 1 ${tradedShape} for $${tradePrice.value}`)
      tradePrice.value = 22
      tradeShape.value = ''
      
        // Refresh trade data immediately to show the new offer
        loadAllTradeData()
      
      // Note: WebSocket events will handle inventory updates, no need to refresh game state here
    } else if (response.status === 401) {
      sessionStorage.clear()
      router.push('/login')
    } else {
      const errorData = await response.json()
      const errorMessage = errorData.error || errorData.message || 'Unknown error occurred'
      alert(`Error: ${errorMessage}`)
    }
  } catch (error) {
    console.error('Error proposing trade:', error)
    alert('Network error. Please try again.')
  }
}

const respondToOffer = async (offerId: string, response: string) => {
  console.log('=== RESPONDING TO OFFER ===')
  console.log('Offer ID:', offerId)
  console.log('Response:', response)
  console.log('Selected player:', selectedPlayer.value?.participant_id)
  
  if (!isSessionActive.value) {
    alert('Session is not active. Please wait for the researcher to start the session.')
    return
  }

  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    router.push('/login')
    return
  }

  try {
    // Find the offer to get its details for immediate UI update
    const offer = pendingOffers.value.find((o: TradeOffer) => o.id === offerId)
    if (!offer) {
      console.error('Offer not found for immediate update:', offerId)
    } else {
      console.log('Found offer for immediate update:', offer)
    }

    console.log('Sending API request to respond to offer...')
    const apiResponse = await fetch('/api/respond-trade-offer', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        transaction_id: offerId,
        response: response
      })
    })

    console.log('API response status:', apiResponse.status)
    
    if (apiResponse.ok) {
      const result = await apiResponse.json()
      console.log('API response result:', result)
      
      // Check if the API call was actually successful
      if (result.success === false) {
        console.error('API returned success: false:', result.error)
        alert(`Error: ${result.error}`)
        return
      }
      
      // Remove from pending offers immediately for instant UI feedback
      if (offer) {
        const offerIndex = pendingOffers.value.findIndex((o: TradeOffer) => o.id === offerId)
        if (offerIndex !== -1) {
          console.log('Removing offer from pending offers at index:', offerIndex)
          pendingOffers.value.splice(offerIndex, 1)
        }
        console.log('Updated pending offers count:', pendingOffers.value.length)
        
        // Don't add to trade history immediately - let the backend API response handle it
        // This prevents any potential flicker between immediate UI update and backend response
      }
      
      const responseText = response === 'accept' ? 'accepted' : 'cancelled'
      alert(`Offer ${responseText}!`)
      
      // Refresh trade data and game state immediately
      console.log('Refreshing trade data and game state immediately after response...')
      loadAllTradeData()
      if (isAuthenticated()) {
        loadGameStateIncremental()
      }
      
      // Refresh again after a delay to ensure backend processing is complete
      setTimeout(() => {
        console.log('Refreshing trade data and game state after backend processing...')
        loadAllTradeData()
        if (isAuthenticated()) {
          loadGameStateIncremental()
        }
      }, 2000) // Wait 2 seconds for backend processing
      
    } else if (apiResponse.status === 401) {
      sessionStorage.clear()
      router.push('/login')
    } else {
      // Log the error response
      const errorText = await apiResponse.text()
      console.error('API Error Response:', errorText)
      try {
        const errorData = JSON.parse(errorText)
        const errorMessage = errorData.error || errorData.message || 'Unknown error occurred'
        console.error('Parsed API error:', errorMessage)
        alert(`Error: ${errorMessage}`)
      } catch (e) {
        console.error('Could not parse error response as JSON')
        alert(`Error: ${errorText}`)
      }
    }
  } catch (error) {
    console.error('Error responding to offer:', error)
    alert('Network error. Please try again.')
  }
}



const closeOrderFulfillmentPopup = () => {
  showOrderFulfillmentPopup.value = false
  selectedOrderShape.value = ''
  selectedOrderIndex.value = -1
  // Clear the selected order
  selectedOrders.value = []
}

// Automated session start methods
const checkAndStartSession = async () => {
  if (hasCheckedAutoStart.value) {
    return // Already checked
  }
  
  hasCheckedAutoStart.value = true
  
  // Check if session is already running or paused
  if (gameState.value.experiment_config?.experiment_status === 'running') {
    return
  }
  
  if (gameState.value.experiment_config?.experiment_status === 'paused') {
    return
  }
  
  // Check if session was previously completed
  if (gameState.value.experiment_config?.experiment_status === 'completed' || 
      gameState.value.experiment_config?.experiment_status === 'stopped' || 
      gameState.value.experiment_config?.experiment_status === 'ended') {
    console.log('Session was previously completed, cannot start again')
    return
  }
  
  console.log('Checking if session should start automatically...')
  
  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    console.error('No auth token available for auto-start check')
    return
  }
  
  try {
    const response = await fetch('/api/experiment/check-and-start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        session_code: sessionId.value
      })
    })
    
    if (response.ok) {
      const data = await response.json()
      console.log('Auto-start check response:', data)
      
      if (data.status === 'ready_to_start') {
        console.log('Session ready to start - beginning countdown')
        startAutoStartCountdown()
      } else if (data.status === 'already_running') {
        console.log('Session is already running')
        // Check real-time status to get current timer state
        checkSessionStatusRealTime()
      } else if (data.status === 'paused') {
        console.log('Session is paused - cannot auto-start:', data.message)
        // Check real-time status to get current timer state
        checkSessionStatusRealTime()
      } else if (data.status === 'not_ready') {
        console.log('Session not ready to start:', data.message)
      }
    } else {
      console.error('Failed to check auto-start:', response.status)
    }
  } catch (error) {
    console.error('Error checking auto-start:', error)
  }
}

const startAutoStartCountdown = () => {
  console.log('Starting auto-start countdown...')
  
  // Double-check that session is not completed before starting countdown
  if (gameState.value.experiment_config?.experiment_status === 'completed' || 
      gameState.value.experiment_config?.experiment_status === 'stopped' || 
      gameState.value.experiment_config?.experiment_status === 'ended') {
    console.log('Session was previously completed, cannot start countdown')
    return
  }
  
  // Reset countdown values
  autoStartCountdown.value = 5
  autoStartMessage.value = 'Session starts in 5 seconds.'
  autoStartProgress.value = 0
  
  // Show popup
  showAutoStartPopup.value = true
  
  // Start countdown interval
  autoStartInterval.value = setInterval(() => {
    autoStartCountdown.value--
    autoStartProgress.value = ((5 - autoStartCountdown.value) / 5) * 100
    
    if (autoStartCountdown.value <= 0) {
      // Countdown finished
      clearInterval(autoStartInterval.value!)
      autoStartInterval.value = null
      showAutoStartPopup.value = false
      
      // Update message to indicate session has started
      autoStartMessage.value = 'Session started!'
      
      console.log('Auto-start countdown completed - now starting session')
      
      // Call backend to actually start the session (using a separate async function)
      startSessionAfterCountdown()
    } else {
      // Update message
      autoStartMessage.value = `Session starts in ${autoStartCountdown.value} seconds.`
    }
  }, 1000)
}

const startSessionAfterCountdown = async () => {
  console.log('Starting session after countdown completion...')
  
  // Final check that session is not completed before starting
  if (gameState.value.experiment_config?.experiment_status === 'completed' || 
      gameState.value.experiment_config?.experiment_status === 'stopped' || 
      gameState.value.experiment_config?.experiment_status === 'ended') {
    console.log('Session was previously completed, cannot start session')
    return
  }
  
  // Call backend to actually start the session
  const authToken = sessionStorage.getItem('auth_token')
  if (authToken) {
    try {
      const startResponse = await fetch('/api/experiment/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          session_code: sessionId.value
        })
      })
      
      if (startResponse.ok) {
        const startData = await startResponse.json()
        console.log('✅ Session started successfully via backend:', startData)
        
        // Update local session status to 'running'
        if (!gameState.value.experiment_config) {
          gameState.value.experiment_config = {}
        }
        gameState.value.experiment_config.experiment_status = 'running'
        
        // Get session duration from config or use default
        const sessionDuration = gameState.value.experiment_config?.sessionDuration || 15
        const timeRemainingSeconds = sessionDuration * 60
        
        // Initialize timer immediately
        timeRemaining.value = timeRemainingSeconds
        timerStartTime.value = Date.now()
        timerInitialDuration.value = timeRemainingSeconds
        isTimerRunning.value = true
        
        // Start local timer immediately for smooth countdown
        startLocalTimer()
        
        console.log('✅ Session status updated to running, timer started immediately')
        
        // Immediately check real-time status to ensure synchronization
        checkSessionStatusRealTime()
        
        // Also refresh from backend to ensure synchronization
        setTimeout(() => {
          loadGameStateIncremental()
          // Also check real-time status to ensure timer is properly synchronized
          checkSessionStatusRealTime()
        }, 500)
      } else {
        console.error('Failed to start session after countdown:', startResponse.status)
      }
    } catch (error) {
      console.error('Error starting session after countdown:', error)
    }
  }
}

const closeAutoStartPopup = () => {
  // Don't allow closing the popup during countdown
  if (autoStartCountdown.value > 0) {
    return
  }
  
  showAutoStartPopup.value = false
  
  // Clear interval if still running
  if (autoStartInterval.value) {
    clearInterval(autoStartInterval.value)
    autoStartInterval.value = null
  }
}

// Real-time session status monitoring
const checkSessionStatusRealTime = async () => {
  // Skip if we're in the middle of an auto-start countdown
  if (showAutoStartPopup.value && autoStartCountdown.value > 0) {
    return
  }
  
  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    return
  }
  
  try {
    const response = await fetch(`/api/experiment/timer-state?session_code=${encodeURIComponent(sessionId.value)}`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const data = await response.json()
      
      // Check if session status has changed
      const currentStatus = gameState.value.experiment_config?.experiment_status || 'idle'
      const newStatus = data.experiment_status || 'idle'
      
      if (currentStatus !== newStatus) {
        console.log(`🔄 Real-time status update: ${currentStatus} -> ${newStatus}`)
        
        // Update experiment status
        if (!gameState.value.experiment_config) {
          gameState.value.experiment_config = {}
        }
        gameState.value.experiment_config.experiment_status = newStatus
        
        // Handle status change
        if (newStatus === 'running') {
          // Session just started running
          timeRemaining.value = data.time_remaining || 900 // Default 15 minutes
          timerStartTime.value = Date.now()
          timerInitialDuration.value = data.time_remaining || 900
          isTimerRunning.value = true
          startLocalTimer()
          
          // Close auto-start popup if it's open
          if (showAutoStartPopup.value) {
            closeAutoStartPopup()
          }
          
          console.log('✅ Real-time update: Session started, timer initialized')
        } else if (newStatus === 'paused' || newStatus === 'completed' || newStatus === 'idle') {
          // Session stopped
          stopLocalTimer()
          console.log('⏸️ Real-time update: Session stopped')
        }
      } else if (currentStatus === 'running' && newStatus === 'running') {
        // Session is already running, but check if timer needs sync
        if (Math.abs((data.time_remaining || 0) - timeRemaining.value) > 5) {
          console.log('🔄 Real-time timer sync: updating timer to match backend')
          timeRemaining.value = data.time_remaining || 900
          timerStartTime.value = Date.now()
          timerInitialDuration.value = data.time_remaining || 900
        }
      }
    }
  } catch (error) {
    console.error('Error in real-time session status check:', error)
  }
}





const sendMessage = async () => {
  if (!isSessionActive.value) {
    alert('Session is not active. Please wait for the researcher to start the session.')
    return
  }

  if (!selectedPlayer.value || !newMessage.value.trim()) {
    return
  }

  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    router.push('/login')
    return
  }

  try {
    const response = await fetch('/api/send-message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        recipient: selectedPlayer.value.participant_id,
        content: newMessage.value.trim()
      })
    })

    if (response.ok) {
      const justSent = newMessage.value.trim()
      newMessage.value = ''
      // Mark messages as read when user sends a message
      markMessagesAsRead()
      
      // Scroll to bottom for immediate feedback
      nextTick(() => {
        if (messageHistory.value) {
          messageHistory.value.scrollTop = messageHistory.value.scrollHeight
        }
      })
      // Refresh from server to get the actual message with proper ID
      setTimeout(() => {
        loadMessages()
      }, 500) // Small delay to ensure server has processed the message
    } else if (response.status === 401) {
      sessionStorage.clear()
      router.push('/login')
    } else {
      const error = await response.json()
      alert(`Error: ${error.message}`)
    }
  } catch (error) {
    console.error('Error sending message:', error)
    alert('Network error. Please try again.')
  }
}

const sendBroadcastMessage = async () => {
  if (!isSessionActive.value) {
    alert('Session is not active. Please wait for the researcher to start the session.')
    return
  }

  if (!newMessage.value.trim()) {
    alert('Please enter a message to broadcast.')
    return
  }

  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    router.push('/login')
    return
  }

  try {
    const response = await fetch('/api/send-message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        recipient: 'all', // Broadcast to all participants
        content: newMessage.value.trim()
      })
    })

    if (response.ok) {
      const justSent = newMessage.value.trim()
      newMessage.value = ''
      // Mark messages as read when user sends a broadcast message
      markMessagesAsRead()
      
      // Scroll to bottom for immediate feedback
      nextTick(() => {
        if (messageHistory.value) {
          messageHistory.value.scrollTop = messageHistory.value.scrollHeight
        }
      })
      // Refresh from server to get the actual message with proper ID
      setTimeout(() => {
        loadMessages()
      }, 500) // Small delay to ensure server has processed the message
    } else if (response.status === 401) {
      sessionStorage.clear()
      router.push('/login')
    } else {
      const error = await response.json()
      alert(`Error: ${error.message}`)
    }
  } catch (error) {
    console.error('Error sending broadcast message:', error)
    alert('Network error. Please try again.')
  }
}

// Helper function to check if user is authenticated
const isAuthenticated = () => {
  const authToken = sessionStorage.getItem('auth_token')
  const participantCode = sessionStorage.getItem('participant_code')
  return !!(authToken && participantCode && participantId.value)
}



// Helper function to scroll to bottom of message history
const scrollToBottom = () => {
  nextTick(() => {
    if (messageHistory.value) {
      messageHistory.value.scrollTop = messageHistory.value.scrollHeight
    }
  })
}



// Debounced game state loading to prevent rapid successive calls
let loadGameStateTimeout: NodeJS.Timeout | null = null
const loadGameStateDebounced = async () => {
  if (loadGameStateTimeout) {
    clearTimeout(loadGameStateTimeout)
  }
  loadGameStateTimeout = setTimeout(() => {
    loadGameState()
  }, 500) // Debounce by 500ms
}

// Helper function to check if an update should be applied
const shouldApplyUpdate = (fieldKey: string, newValue: any, eventTimestamp: number = Date.now()): boolean => {
  const lastTimestamp = lastUpdateTimestamps.value.get(fieldKey) || 0
  const currentValue = getNestedValue(gameState.value, fieldKey)
  
  // Special protection for inventory updates to prevent glitches
  if (fieldKey === 'participant.shapes_acquired') {
    
    // If we have recently added shapes, protect the current inventory from backend overwrites
    // BUT always allow inventory reductions (indicating order fulfillment/selling/trading)
    if (recentlyAddedShapes.value.size > 0) {
      // Always allow updates that reduce inventory size (order fulfillment, selling, trading)
      if (Array.isArray(currentValue) && Array.isArray(newValue) && newValue.length < currentValue.length) {
        console.log(`🔓 Allowing inventory reduction despite recent additions: ${currentValue.length} -> ${newValue.length}`)
        // Clear the protection since this is a legitimate backend update
        recentlyAddedShapes.value.clear()
        return true
      }
      console.log(`🛡️ Protecting inventory from backend overwrite due to recent shape additions`)
      return false
    }
    
    // Additional protection: if current inventory has more items than new inventory, 
    // always allow the reduction (order fulfillment, selling, trading)
    if (Array.isArray(currentValue) && Array.isArray(newValue) && currentValue.length > newValue.length) {
      console.log(`🔓 Allowing inventory reduction from order fulfillment/selling/trading: ${currentValue.length} -> ${newValue.length}`)
      return true
    }
  }
  
  // Special protection for orders updates after recent fulfillment
  if (fieldKey === 'participant.orders') {
    // If we have recently fulfilled orders, protect from backend overwrites for a short time
    if (recentlyFulfilledOrders.value.size > 0) {
      console.log(`🛡️ Protecting orders from backend overwrite due to recent fulfillment`)
      return false
    }
    
    // Allow legitimate order updates (new orders, etc.)
    return true
  }
  

  
  // Special debugging for experiment status changes
  if (fieldKey === 'experiment_config.experiment_status') {

    
    // Prevent any experiment status updates if session has already ended
    if (sessionHasEnded.value) {
      console.log(`🛡️ PROTECTING experiment status: session has ended, preventing any status changes`)
      return false
    }
    
    // Special protection for experiment status: don't allow undefined/null to overwrite valid status
    if ((newValue === undefined || newValue === null || newValue === '') && 
        (currentValue === 'running' || currentValue === 'paused')) {
      console.log(`🛡️ PROTECTING experiment status: preventing ${newValue} from overwriting ${currentValue}`)
      return false
    }
    
    // Allow 'idle' status to be set if it's a legitimate status change
    if (newValue === 'idle' && currentValue === 'running' && isTimerRunning.value && timeRemaining.value > 0) {
      console.log(`🛡️ PROTECTING running status: preventing idle from overwriting running during active timer`)
      return false
    }
  }
  
  // Check if this is a newer update
  if (eventTimestamp <= lastTimestamp) {
    return false
  }
  
  // Check if the value is actually different
  if (JSON.stringify(currentValue) === JSON.stringify(newValue)) {
    return false
  }
  
  lastUpdateTimestamps.value.set(fieldKey, eventTimestamp)
  return true
}

// Helper function to get nested object values
const getNestedValue = (obj: any, path: string): any => {
  return path.split('.').reduce((current, key) => current?.[key], obj)
}

// Helper function to set nested object values
const setNestedValue = (obj: any, path: string, value: any): void => {
  const keys = path.split('.')
  const lastKey = keys.pop()!
  const target = keys.reduce((current, key) => {
    if (!current[key]) current[key] = {}
    return current[key]
  }, obj)
  
  // Special handling for experiment status changes
  if (path === 'experiment_config.experiment_status') {
    
    // Prevent any experiment status changes if session has already ended
    if (sessionHasEnded.value) {
      console.log(`🛡️ FINAL PROTECTION: session has ended, preventing experiment status change`)
      return
    }
    
    // Additional protection: don't allow invalid values to overwrite running status when timer is active
    if ((value === undefined || value === null || value === '') && 
        (target[lastKey] === 'running' || target[lastKey] === 'paused') && 
        isTimerRunning.value) {
      console.log(`🛡️ FINAL PROTECTION: preventing ${value} from overwriting ${target[lastKey]} while timer is running`)
      return
    }
  }
  
  target[lastKey] = value
}

// Function to apply incremental update to a specific field
const applyIncrementalUpdate = (fieldKey: string, newValue: any, eventTimestamp: number = Date.now()): boolean => {
  if (shouldApplyUpdate(fieldKey, newValue, eventTimestamp)) {
    setNestedValue(gameState.value, fieldKey, newValue)
    return true
  }
  return false
}

// Function to check if an event has already been processed
const isEventProcessed = (eventId: string): boolean => {
  return processedEventIds.value.has(eventId)
}

// Function to mark an event as processed
const markEventProcessed = (eventId: string): void => {
  processedEventIds.value.add(eventId)
  
  // Clean up old event IDs to prevent memory leaks
  if (processedEventIds.value.size > 1000) {
    const eventIdsArray = Array.from(processedEventIds.value)
    processedEventIds.value.clear()
    // Keep only the most recent 500 events
    eventIdsArray.slice(-500).forEach(id => processedEventIds.value.add(id))
  }
}

// Incremental game state loading that preserves all local state
const loadGameStateIncremental = async () => {
  const authToken = sessionStorage.getItem('auth_token')
  const participantCode = sessionStorage.getItem('participant_code')
  
  if (!authToken || !participantCode) {
    if (participantId.value) {
      console.warn('Authentication data not available, redirecting to login...')
      sessionStorage.clear()
      router.push('/login')
    }
    return
  }

  try {
    const response = await fetch(`/api/game-state?participant=${participantCode}`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const data = await response.json()
      
      if (data.game_state) {
        const apiGameState = data.game_state
        const updateTimestamp = Date.now()
        
        console.log('🔄 Processing incremental game state update')
        
        // Apply updates field by field, preserving local state
        if (apiGameState.private_state) {
          console.log('🔄 Processing private state:', apiGameState.private_state)
          
          // Update participant money only if different
          const newMoney = apiGameState.private_state.money || data.participant?.money || 0
          if (shouldApplyUpdate('participant.money', newMoney, updateTimestamp)) {
            if (!gameState.value.participant) gameState.value.participant = {}
            gameState.value.participant.money = newMoney
          }
          
          // Update inventory only if different
          const newInventory = (() => {
            const inventory = apiGameState.private_state.inventory || []
            let mapped: string[] = []
            if (Array.isArray(inventory)) {
              mapped = inventory.map((item: any) => {
                if (typeof item === 'string') return item
                if (item && typeof item === 'object' && item.shape) return item.shape
                return null
              }).filter((item: string | null) => item !== null) as string[]
            } else if (typeof inventory === 'string') {
              try {
                const parsed = JSON.parse(inventory)
                if (Array.isArray(parsed)) {
                  mapped = parsed.map((item: any) => 
                    typeof item === 'string' ? item : (item?.shape || null)
                  ).filter((item: string | null) => item !== null) as string[]
                }
              } catch (e) {
                console.error('Failed to parse inventory string:', e)
                mapped = []
              }
            }
            return mapped
          })()
          
          if (shouldApplyUpdate('participant.shapes_acquired', newInventory, updateTimestamp)) {
            if (!gameState.value.participant) gameState.value.participant = {}
            gameState.value.participant.shapes_acquired = newInventory
          }
          
          // Update orders only if different
          const newOrders = apiGameState.private_state.orders || []
          if (shouldApplyUpdate('participant.orders', newOrders, updateTimestamp)) {
            if (!gameState.value.participant) gameState.value.participant = {}
            gameState.value.participant.orders = newOrders
          }
          
          // Update production queue only if different
          const newProductionQueue = (() => {
            const queue = apiGameState.private_state.production_queue || []
            return queue.map((item: any) => ({
              id: item.production_id,
              shape: item.shape,
              time_remaining: item.time_remaining || 0,
              status: item.status || 'unknown'
            }))
          })()
          
          if (shouldApplyUpdate('participant.production_queue', newProductionQueue, updateTimestamp)) {
            if (!gameState.value.participant) gameState.value.participant = {}
            gameState.value.participant.production_queue = newProductionQueue
          }
          
          // Update wordguessing-specific fields
          if (apiGameState.private_state.participant && apiGameState.private_state.participant.assigned_words !== undefined) {
            const newAssignedWords = apiGameState.private_state.participant.assigned_words || []
            if (shouldApplyUpdate('participant.assigned_words', newAssignedWords, updateTimestamp)) {
              if (!gameState.value.participant) gameState.value.participant = {}
              gameState.value.participant.assigned_words = newAssignedWords
            }
          }
          
          // Update wordguessing role
          if (apiGameState.private_state.participant && apiGameState.private_state.participant.role !== undefined) {
            const newRole = apiGameState.private_state.participant.role
            if (shouldApplyUpdate('participant.role', newRole, updateTimestamp)) {
              if (!gameState.value.participant) gameState.value.participant = {}
              gameState.value.participant.role = newRole
            }
          }
          
          // Update other participant fields
          const fieldsToUpdate = [
            { key: 'participant.shape', value: apiGameState.private_state.specialty_shape },
            { key: 'participant.orders_completed', value: apiGameState.private_state.orders_completed },
            { key: 'participant.total_orders', value: apiGameState.private_state.total_orders },
            { key: 'participant.completion_percentage', value: apiGameState.private_state.completion_percentage },
            { key: 'participant.current_rankings', value: apiGameState.private_state.current_rankings },
            { key: 'participant.submitted_rankings_count', value: apiGameState.private_state.submitted_rankings_count }
          ]
          
          fieldsToUpdate.forEach(({ key, value }) => {
            if (shouldApplyUpdate(key, value, updateTimestamp)) {
              setNestedValue(gameState.value, key, value)
            }
          })
        }
        
        // Update participants list only if different
        const newParticipants = apiGameState.public_state?.other_participants?.map((p: any) => ({
          participant_id: p.participant_code,
          shape: p.specialty_shape,
          money: p.money,
          login_status: p.login_status
        })) || []
        
        // Maintain stable order for new participants
        if (stableParticipantOrder.value.length === 0 && newParticipants.length > 0) {
          stableParticipantOrder.value = newParticipants.map(p => p.participant_id)
          console.log('Established stable participant order in incremental update:', stableParticipantOrder.value)
        }
        
        if (shouldApplyUpdate('participants', newParticipants, updateTimestamp)) {
          gameState.value.participants = newParticipants
        }
        
        // Update communication level only if different
        const newCommunicationLevel = data.communication_level || 'chat'
        if (shouldApplyUpdate('communication_level', newCommunicationLevel, updateTimestamp)) {
          gameState.value.communication_level = newCommunicationLevel
        }
        
        // Update awareness dashboard setting only if different
        const newAwarenessEnabled = data.awareness_dashboard_enabled || false
        if (shouldApplyUpdate('awareness_dashboard_enabled', newAwarenessEnabled, updateTimestamp)) {
          gameState.value.awareness_dashboard_enabled = newAwarenessEnabled
        }
        
        // Update experiment config fields only if different
        if (apiGameState.public_state?.experiment_config) {
          const configFields = [
            'experiment_type', 'specialtyCost', 'regularCost', 'maxProductionNum', 'minTradePrice', 'maxTradePrice'
          ]
          
          configFields.forEach(field => {
            const newValue = apiGameState.public_state.experiment_config[field]
            if (newValue !== undefined) {
              const configKey = `experiment_config.${field}`
              if (shouldApplyUpdate(configKey, newValue, updateTimestamp)) {
                if (!gameState.value.experiment_config) gameState.value.experiment_config = {}
                gameState.value.experiment_config[field] = newValue
              }
            }
          })
        }
        
        // Update experiment status from public state if available
        console.log('🔄 Checking experiment status update:')
        console.log('  - API experiment status:', apiGameState.public_state?.experiment_status)
        console.log('  - Current experiment status:', gameState.value.experiment_config?.experiment_status)
        console.log('  - API experiment status type:', typeof apiGameState.public_state?.experiment_status)
        console.log('  - Is API experiment status truthy:', !!apiGameState.public_state?.experiment_status)
        
        // Only update experiment status if API provides a valid, non-empty status
        if (apiGameState.public_state?.experiment_status && 
            typeof apiGameState.public_state.experiment_status === 'string' && 
            apiGameState.public_state.experiment_status.trim() !== '') {
          
          if (shouldApplyUpdate('experiment_config.experiment_status', apiGameState.public_state.experiment_status, updateTimestamp)) {
            if (!gameState.value.experiment_config) gameState.value.experiment_config = {}
            gameState.value.experiment_config.experiment_status = apiGameState.public_state.experiment_status
          } else {
          }
        } else {
        }
        
      }
    } else if (response.status === 401) {
      console.warn('Authentication token expired, redirecting to login...')
      sessionStorage.clear()
      router.push('/login')
    } else {
      console.error('Failed to load incremental game state:', response.status)
    }
  } catch (error) {
    console.error('Error loading incremental game state:', error)
  }
  
  // Reconfigure interface after loading game state
  console.log('Game state loaded successfully')
  
  // Check if experiment type changed and reconfigure interface if needed
  const currentExperimentType = gameState.value.experiment_config?.experiment_type
  if (currentExperimentType && currentExperimentType !== interfaceConfig.value.myAction.type) {
    console.log('🔧 Experiment type changed, reconfiguring interface:', currentExperimentType)
    await autoConfigureInterface()
  }
}

// Data Loading
const loadGameState = async () => {
  const authToken = sessionStorage.getItem('auth_token')
  const participantCode = sessionStorage.getItem('participant_code')
  
  if (!authToken || !participantCode) {
    // Don't log error if we're not authenticated - this is expected during initialization
    // Only log if we're supposed to be authenticated
    if (participantId.value) {
      console.warn('Authentication data not available, redirecting to login...')
      sessionStorage.clear()
      router.push('/login')
    }
    return
  }

  try {
    const response = await fetch(`/api/game-state?participant=${participantCode}`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const data = await response.json()
      console.log('=== GAME STATE DEBUG ===')
      console.log('Full API response:', data)
      console.log('Game state loaded from database:', data.game_state)
      console.log('Raw API response:', data)
      
      // Map the API response to the expected frontend structure
      if (data.game_state) {
        // The API returns different structure than expected
        const apiGameState = data.game_state
        
        console.log('=== API GAME STATE STRUCTURE ===')
        console.log('API game state:', apiGameState)
        console.log('Public state:', apiGameState.public_state)
        console.log('Private state:', apiGameState.private_state)
        console.log('Private state keys:', Object.keys(apiGameState.private_state || {}))
        console.log('Production queue in private state:', apiGameState.private_state?.production_queue)
        console.log('Production queue type:', typeof apiGameState.private_state?.production_queue)
        console.log('Other participants from API:', apiGameState.public_state?.other_participants)
        console.log('Experiment config from API:', apiGameState.public_state?.experiment_config)
        console.log('Experiment status from API:', apiGameState.public_state?.experiment_status)
        console.log('Time remaining from API:', apiGameState.public_state?.time_remaining)
        console.log('Experiment status type:', typeof apiGameState.public_state?.experiment_status)
        console.log('Is experiment status truthy:', !!apiGameState.public_state?.experiment_status)
        console.log('Current experiment status before mapping:', gameState.value.experiment_config?.experiment_status)
        console.log('Private state money from API:', apiGameState.private_state?.money)
        console.log('Participant money from API:', data.participant?.money)
        
        // Preserve current experiment status and timer state to prevent glitches
        const currentExperimentStatus = gameState.value.experiment_config?.experiment_status
        const currentTimeRemaining = gameState.value.session_status?.time_remaining
        const currentTimerRunning = isTimerRunning.value
        
        // Check if we have a valid running state that should be preserved
        const hasValidRunningState = currentExperimentStatus === 'running' && 
                                    currentTimerRunning && 
                                    currentTimeRemaining !== undefined && 
                                    currentTimeRemaining > 0
        
                  console.log('🛡️ PRESERVING CURRENT STATE:', {
            currentExperimentStatus,
            currentTimeRemaining,
            currentTimerRunning,
            hasValidRunningState,
            apiExperimentStatus: apiGameState.public_state?.experiment_status,
            apiTimeRemaining: apiGameState.public_state?.time_remaining
          })
        
        gameState.value = {
          participant: apiGameState.private_state ? {
            participant_id: participantCode,
            money: apiGameState.private_state.money || data.participant?.money || 0,
            // Convert inventory from JSON objects to shape names array
            shapes_acquired: (() => {
              const inventory = apiGameState.private_state.inventory || []
              console.log('Raw inventory from API:', inventory)
              
              // Handle different inventory data formats
              let mapped: string[] = []
              if (Array.isArray(inventory)) {
                mapped = inventory.map((item: any) => {
                  if (typeof item === 'string') {
                    return item
                  } else if (item && typeof item === 'object' && item.shape) {
                    return item.shape
                  } else {
                    console.warn('Invalid inventory item format:', item)
                    return null
                  }
                }).filter((item: string | null) => item !== null) as string[]
              } else if (typeof inventory === 'string') {
                try {
                  const parsed = JSON.parse(inventory)
                  if (Array.isArray(parsed)) {
                    mapped = parsed.map((item: any) => 
                      typeof item === 'string' ? item : (item?.shape || null)
                    ).filter((item: string | null) => item !== null) as string[]
                  }
                } catch (e) {
                  console.error('Failed to parse inventory string:', e)
                  mapped = []
                }
              }
              
              console.log('Mapped inventory from API:', mapped)
              return mapped
            })(),
            shape: apiGameState.private_state.specialty_shape,
            orders: apiGameState.private_state.orders || [],
            // Fix production queue property names
            production_queue: (() => {
              const queue = apiGameState.private_state.production_queue || []
              console.log('Raw production queue from API:', queue)
              const mapped = queue.map((item: any) => ({
                id: item.production_id,
                shape: item.shape,
                time_remaining: item.time_remaining || 0, // Use the correct property name from backend
                status: item.status || 'unknown' // Include status field
              }))
              console.log('Mapped production queue:', mapped)
              return mapped
            })(),
            // Get costs from experiment config
            specialty_cost: apiGameState.public_state?.experiment_config?.specialtyCost || 8,
            regular_cost: apiGameState.public_state?.experiment_config?.regularCost || 25,
            orders_completed: apiGameState.private_state.orders_completed,
            total_orders: apiGameState.private_state.total_orders,
            completion_percentage: apiGameState.private_state.completion_percentage
          } : gameState.value.participant,
          
          participants: (() => {
            const mappedParticipants = apiGameState.public_state?.other_participants?.map((p: any) => ({
              participant_id: p.participant_code, // Map participant_code to participant_id for frontend compatibility
              shape: p.specialty_shape,
              money: p.money,
              login_status: p.login_status
            })) || []
            
            // Establish stable order on first load
            if (stableParticipantOrder.value.length === 0 && mappedParticipants.length > 0) {
              stableParticipantOrder.value = mappedParticipants.map(p => p.participant_id)
              console.log('Established stable participant order:', stableParticipantOrder.value)
            }
            
            return mappedParticipants
          })(),
          
          session_status: {
            time_remaining: (() => {
              // Preserve current timer if we have a valid running state
              if (hasValidRunningState) {
                console.log('🛡️ PRESERVING VALID RUNNING TIMER:', currentTimeRemaining)
                return currentTimeRemaining
              }
              
              // Preserve current timer if it's running and we have a valid current value
              if (currentTimerRunning && currentTimeRemaining !== undefined && currentTimeRemaining > 0) {
                console.log('🛡️ PRESERVING RUNNING TIMER:', currentTimeRemaining)
                return currentTimeRemaining
              }
              
              // Otherwise use API value
              return apiGameState.public_state?.time_remaining || 0
            })()
          },
          
          communication_level: data.communication_level || 'chat', // Map communication level from API response
          awareness_dashboard_enabled: data.awareness_dashboard_enabled || false, // Map awareness_dashboard_enabled from API response
          awareness_dashboard_config: data.awareness_dashboard_config || { // Map awareness dashboard configuration from API response
            showMoney: true,
            showProductionCount: true,
            showOrderProgress: true
          },
          experiment_interface_config: data.experiment_interface_config || {}, // Map experiment interface configuration from API response
          // Add experiment config for parameter access and session status
          experiment_config: {
            ...apiGameState.public_state?.experiment_config,
            experiment_status: (() => {
              // If we have a valid running state, always preserve it
              if (hasValidRunningState) {
                console.log('🛡️ PRESERVING VALID RUNNING STATE:', currentExperimentStatus)
                return currentExperimentStatus
              }
              
              // If API provides a valid experiment status, use it
              if (apiGameState.public_state?.experiment_status && 
                  typeof apiGameState.public_state.experiment_status === 'string' && 
                  apiGameState.public_state.experiment_status.trim() !== '') {
                return apiGameState.public_state.experiment_status
              }
              
              // If we have a current status and timer is running, preserve it
              if (currentExperimentStatus && 
                  (currentExperimentStatus === 'running' || 
                   currentExperimentStatus === 'paused') &&
                  currentTimerRunning) {
                console.log('🛡️ PRESERVING CURRENT EXPERIMENT STATUS:', currentExperimentStatus)
                return currentExperimentStatus
              }
              
              // Otherwise, use current status or default to idle
              return currentExperimentStatus || 'idle'
            })()
          }
        }
        
        console.log('Mapped game state:', gameState.value)
        console.log('Participant money after mapping:', gameState.value.participant?.money)
        console.log('Other participants:', gameState.value.participants)
        console.log('Communication level:', gameState.value.communication_level)
        console.log('Awareness dashboard enabled:', gameState.value.awareness_dashboard_enabled)
        console.log('Final experiment status after mapping:', gameState.value.experiment_config?.experiment_status)
        
        // Configuration consistency check
        
        // Debug production queue data
        console.log('Raw production queue from API:', apiGameState.private_state?.production_queue)
        console.log('Mapped production queue:', gameState.value.participant?.production_queue)
        console.log('Current production item computed:', currentProductionItem.value)
        
        // Initialize timer with game state time (only on initial load)
        const apiTimeRemaining = apiGameState.public_state?.time_remaining || 0
        if (hasValidRunningState) {
          console.log('🛡️ PRESERVING VALID RUNNING LOCAL TIMER:', timeRemaining.value)
        } else if (!currentTimerRunning) {
          timeRemaining.value = apiTimeRemaining
          console.log('Initialized timer with time from API:', timeRemaining.value)
        } else {
          console.log('🛡️ PRESERVING RUNNING LOCAL TIMER:', timeRemaining.value)
        }
        
        // Start/stop local timer based on experiment status
        const experimentStatus = gameState.value.experiment_config?.experiment_status
        console.log('Experiment status from loadGameState:', experimentStatus)
        
        if (hasValidRunningState) {
          console.log('🛡️ PRESERVING VALID RUNNING STATE - no timer changes needed')
        } else if (experimentStatus === 'running' && !currentTimerRunning) {
          startLocalTimer() // Start local timer for smooth countdown
        } else if (experimentStatus !== 'running' && currentTimerRunning) {
          stopLocalTimer() // Stop local timer when not running
        } else {
          console.log('🛡️ TIMER STATE PRESERVED - no changes needed')
        }
        
        // Don't reset production timer - let it continue for smooth countdown
        // productionTimer.value = 0
      }
    } else if (response.status === 401) {
      // Token expired or invalid, redirect to login
      console.warn('Authentication token expired, redirecting to login...')
      sessionStorage.clear()
      router.push('/login')
    } else {
      console.error('Failed to load game state:', response.status)
      // Load minimal mock data as fallback
      loadMockGameState()
    }
  } catch (error) {
    console.error('Error loading game state:', error)
    // Load minimal mock data as fallback
    loadMockGameState()
  }
  
  // Game state loaded successfully
  console.log('Game state loaded successfully')
}

const loadMessages = async () => {
  try {
    // Only load messages if we have a session ID
    if (!sessionId.value) {
      return
    }
    
    const authToken = sessionStorage.getItem('auth_token')
    if (!authToken) {
      console.error('No auth token available')
      return
    }

    const response = await fetch(`${BACKEND_URL}/api/messages?session_code=${encodeURIComponent(sessionId.value)}`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      throw new Error('Failed to load messages')
    }
    
    const data = await response.json()
    console.log('All messages data received:', data)
    
    // Map all messages to the expected format (like Researcher Dashboard)
    const allMessages = data.map((msg: any) => ({
      id: msg.message_id,
      sender: msg.sender,
      content: msg.content,
      timestamp: new Date(msg.timestamp),
      recipient: msg.recipient || null
    }))
    
    // Store all messages for conversation filtering
    messages.value = allMessages
    
    // Process all messages and update unread counts for all participants
    const lastReadTime = lastReadTimestamp.value
    
    // Clear previous unread counts
    unreadMessagesByParticipant.value.clear()
    
    // Process each message to update unread counts
    const currentDisplayName = extractDisplayName(participantId.value)
    
    allMessages.forEach((msg: Message) => {
      // Skip messages sent by current participant
      if (msg.sender === currentDisplayName) {
        return
      }
      
      const messageTime = new Date(msg.timestamp).getTime()
      
      // For broadcast messages (recipient is 'all' or null)
      if (msg.recipient === 'all' || msg.recipient === null) {
        if (messageTime > lastReadTime) {
          const currentCount = unreadMessagesByParticipant.value.get(msg.sender) || 0
          unreadMessagesByParticipant.value.set(msg.sender, currentCount + 1)
        }
      }
      // For direct messages to current participant
      else if (msg.recipient === currentDisplayName) {
        const lastReadTimeForParticipant = lastReadTimestampByParticipant.value.get(msg.sender) || 0
        if (messageTime > lastReadTimeForParticipant) {
          const currentCount = unreadMessagesByParticipant.value.get(msg.sender) || 0
          unreadMessagesByParticipant.value.set(msg.sender, currentCount + 1)
        }
      }
    })
    
    // Trigger reactivity update
    unreadMessagesByParticipant.value = new Map(unreadMessagesByParticipant.value)
    
    console.log('Updated unread message counts:', Object.fromEntries(unreadMessagesByParticipant.value))
    console.log('All messages loaded and stored for conversation filtering')
  } catch (error) {
    console.error('Error loading messages:', error)
  }
}

const loadAllTradeData = async () => {
  // console.log('=== LOADING TRADE DATA ===')
  // console.log('Session ID:', sessionId.value)
  // console.log('Current pending offers before load:', pendingOffers.value.length)
  // console.log('Current trade history before load:', tradeHistory.value.length)
  
  // Only load trade data if we have a session ID
  if (!sessionId.value) {
    return
  }
  
  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    console.error('No auth token available')
    return
  }

  try {
    // Get all trade offers for the current participant (not just for a specific target)
    const response = await fetch(`/api/participant-trades?all=true`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      }
    })

        console.log('Trade data API response status:', response.status)
    
    if (response.ok) {
      const data = await response.json()
      console.log('Raw trade data received:', data)
      console.log('Pending offers from API:', data.pending_offers)
      console.log('Completed trades from API:', data.completed_trades)
      
      // Format pending offers
      const formattedPendingOffers = data.pending_offers.map((offer: any) => {
        console.log(`Processing offer ${offer.transaction_id}: price=${offer.price}, proposer=${offer.proposer_code}, recipient=${offer.recipient_code}, transaction_status=${offer.transaction_status}, participant_role=${offer.participant_role}`)
        return {
          id: offer.transaction_id,
          offer_type: offer.participant_role || offer.offer_type, // Use participant_role for correct perspective, fallback to offer_type
          shape: offer.shape,
          quantity: offer.quantity, // Add quantity field
          price: offer.price,
          proposer_code: offer.proposer_code,
          recipient_code: offer.recipient_code,
          is_outgoing: offer.is_outgoing // Whether this participant initiated the offer
        }
      })
      console.log('Formatted pending offers:', formattedPendingOffers)
      
      // Format trade history
      const formattedTradeHistory = data.completed_trades.map((trade: any) => {
        console.log(`=== FORMATTING TRADE HISTORY ITEM ===`)
        console.log(`Transaction ID: ${trade.transaction_id}`)
        console.log(`Raw type from API: ${trade.type}`)
        console.log(`Transaction status: ${trade.transaction_status}`)
        console.log(`Shape: ${trade.shape}, Price: ${trade.price}`)
        console.log(`Proposer: ${trade.proposer_code}, Recipient: ${trade.recipient_code}`)
        console.log(`Timestamp: ${new Date().toISOString()}`)
        return {
          id: trade.transaction_id,
          type: trade.type, // Could be 'bought', 'sold', 'cancelled', 'declined'
          shape: trade.shape,
          quantity: trade.quantity, // Add quantity field
          price: trade.price,
          proposer_code: trade.proposer_code, // Add participant information for filtering
          recipient_code: trade.recipient_code // Add participant information for filtering
        }
      })
      console.log('Formatted trade history:', formattedTradeHistory)
      
      // Compare old and new prices to detect changes
      // console.log('=== PRICE COMPARISON ===')
      formattedPendingOffers.forEach((newOffer: TradeOffer) => {
        const oldOffer = pendingOffers.value.find((o: TradeOffer) => o.id === newOffer.id)
        if (oldOffer) {
          if (oldOffer.price !== newOffer.price) {
            console.log(`PRICE CHANGED for offer ${newOffer.id}: ${oldOffer.price} -> ${newOffer.price}`)
          } else {
            console.log(`Price unchanged for offer ${newOffer.id}: ${newOffer.price}`)
          }
        } else {
          console.log(`New offer ${newOffer.id}: ${newOffer.price}`)
        }
      })
      
      // Update the reactive arrays
      pendingOffers.value = formattedPendingOffers
      tradeHistory.value = formattedTradeHistory
      
      // Update notification dots for trade offers
      // Clear previous unread trade counts
      unreadTradeOffersByParticipant.value.clear()
      
      // Process all pending offers to update unread counts for all participants
      if (data.pending_offers && Array.isArray(data.pending_offers)) {
        data.pending_offers.forEach((offer: any) => {
          // Check if this is an incoming trade offer (not from current user)
          const currentDisplayName = extractDisplayName(participantId.value)
          const isIncomingTradeOffer = offer.proposer_code !== currentDisplayName && offer.recipient_code === currentDisplayName
          
          if (isIncomingTradeOffer) {
            console.log(`Found incoming trade offer from ${offer.proposer_code}`)
            
            // Update unread count for the sender
            const currentCount = unreadTradeOffersByParticipant.value.get(offer.proposer_code) || 0
            unreadTradeOffersByParticipant.value.set(offer.proposer_code, currentCount + 1)
            
            console.log(`Updated unread trade count for ${offer.proposer_code} to ${currentCount + 1}`)
          }
        })
      }
      
      // Trigger reactivity update
      unreadTradeOffersByParticipant.value = new Map(unreadTradeOffersByParticipant.value)
      
      console.log('Updated unread trade counts:', Object.fromEntries(unreadTradeOffersByParticipant.value))
      console.log('All trade data loaded and notification dots updated')
    
      
    } else if (response.status === 401) {
      sessionStorage.clear()
      router.push('/login')
    } else {
      // Log the error response
      const errorText = await response.text()
      console.error('API Error Response:', errorText)
      try {
        const errorData = JSON.parse(errorText)
        console.error('Parsed error data:', errorData)
      } catch (e) {
        console.error('Could not parse error response as JSON')
      }
      console.error('Failed to load trade data:', response.status)
      // Fallback to empty arrays
      pendingOffers.value = []
      tradeHistory.value = []
    }
  } catch (error) {
    console.error('Error loading trade data:', error)
    // Fallback to empty arrays
    pendingOffers.value = []
    tradeHistory.value = []
  }
}



const loadMessageDataFor = async (playerId: string) => {
  // Validate playerId (allow 'all' for broadcast mode)
  if (!playerId || (playerId !== 'all' && playerId.trim() === '')) {
    console.warn('Invalid playerId provided to loadMessageDataFor:', playerId)
    return
  }
  scrollToBottom()
}

const loadMockGameState = () => {
  // Get starting money from experiment config if available
  const startingMoney = gameState.value.experiment_config?.startingMoney || 300
  
  gameState.value = {
    participant: {
      participant_id: participantId.value,
      money: startingMoney,
      shapes_acquired: ['circle', 'square'],
      shape: 'triangle',
      orders: ['circle', 'square', 'diamond', 'pentagon', 'circle', 'square', 'diamond', 'pentagon'],
      production_queue: [],
      specialty_cost: gameState.value.experiment_config?.specialtyCost || 10, // Use config value
      regular_cost: gameState.value.experiment_config?.regularCost || 25, // Use config value
      orders_completed: 0, // Mock orders_completed
      total_orders: 8, // Mock total_orders
      completion_percentage: 0 // Mock completion_percentage
    },
    participants: [], // Empty array to avoid loading data for non-existent participants
    session_status: {
      time_remaining: 600
    },
    communication_level: 'chat', // Mock communication level
    awareness_dashboard_enabled: false, // Mock awareness_dashboard_enabled
    experiment_config: {
      ...gameState.value.experiment_config,
      experiment_status: gameState.value.experiment_config?.experiment_status || 'idle' // Preserve experiment status
    }
  }
}

const initializeWebSocket = () => {
  socket = io(BACKEND_URL, {
    transports: ['websocket', 'polling'],
    timeout: 60000, // Match server ping_timeout
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    // Add ping/pong configuration to match server
    pingTimeout: 60000,
    pingInterval: 25000
  })
  
  socket.on('connect', async () => {
    console.log('Connected to game server')
    console.log('Registering participant:', participantId.value, 'for session:', sessionId.value)
    socket.emit('register_participant', {
      participant_code: participantId.value,
      participant_type: 'human',
      session_code: sessionId.value
    })
    
    // Subscribe to real-time updates for this session
    socket.emit('subscribe_to_updates', { sessionId: sessionId.value })
    console.log(`📡 Subscribed to updates for session: ${sessionId.value}`)
    
    // WebSocket connected - interface will be configured in onMounted
    console.log('WebSocket connected, interface configuration will be handled in onMounted')
  })

  // Note: Removed onAny event logger as it might not be available

  socket.on('participant_registered', (data: any) => {
    console.log('Participant registration confirmed:', data)
    // Registration is successful, we can now proceed with loading data
    if (isAuthenticated()) {
      loadGameStateIncremental() // Use incremental update to preserve experiment status
    }
  })

  socket.on('error', (data: any) => {
    console.error('WebSocket error received:', data)
    // Handle WebSocket errors gracefully
    if (data.message) {
      console.error('WebSocket error message:', data.message)
    }
  })

  socket.on('disconnect', (reason: string) => {
    console.log('Disconnected from game server:', reason)
  })

  socket.on('connect_error', (error: any) => {
    console.error('WebSocket connection error:', error)
  })
  
  socket.on('reconnect', (attemptNumber: number) => {
    console.log(`🔄 Reconnected to WebSocket server (attempt ${attemptNumber})`)
    isConnected.value = true
    
    // Re-register and re-subscribe after reconnection
    if (participantId.value && sessionId.value) {
      socket.emit('register_participant', {
        participant_code: participantId.value,
        participant_type: 'human',
        session_code: sessionId.value
      })
      
      socket.emit('subscribe_to_updates', { sessionId: sessionId.value })
      
      // Use incremental update to preserve timer state during reconnection
      loadGameStateIncremental()
      
      // Only refresh timer state if we don't have a running local timer AND experiment is not running
      if (!isTimerRunning.value && gameState.value.experiment_config?.experiment_status !== 'running') {
        fetch(`/api/experiment/timer-state?session_code=${encodeURIComponent(sessionId.value)}`)
          .then(response => response.json())
          .then(data => {
            console.log('🔄 Refreshed timer state after reconnection:', data)
            
            // Only update timer if we don't have a local timer running
            if (!isTimerRunning.value) {
              timeRemaining.value = data.time_remaining
              lastWebSocketTimerUpdate.value = Date.now()
              
              if (data.experiment_status && gameState.value.experiment_config) {
                gameState.value.experiment_config.experiment_status = data.experiment_status
                
                switch (data.experiment_status) {
                  case 'running':
                    startLocalTimer()
                    break
                  case 'paused':
                  case 'completed':
                  case 'idle':
                    stopLocalTimer()
                    break
                }
              }
            } else {
            }
          })
          .catch(error => console.error('Error refreshing timer state after reconnection:', error))
      } else {
      }
    }
  })
  
  // Listen for server heartbeat and respond
  socket.on('heartbeat', (data: any) => {
    console.log('💓 Server heartbeat received:', data)
    socket.emit('heartbeat_response', { timestamp: new Date().toISOString() })
  })

  socket.on('timer_update', (data: any) => {
    
    // Only process timer updates for the current session
    const currentSessionCode = sessionId.value
    if (data.session_code && data.session_code !== currentSessionCode) {
      return
    }
    
    const eventTimestamp = Date.now()
    
    // Always update the timer with WebSocket values when experiment is running
    // This ensures the timer stays synchronized with the server
    if (data.experiment_status === 'running') {
      
      // Update the timer value
      timeRemaining.value = data.time_remaining
      lastWebSocketTimerUpdate.value = eventTimestamp
      
      // If local timer is not running, start it
      if (!isTimerRunning.value) {
        timerStartTime.value = Date.now()
        timerInitialDuration.value = data.time_remaining
        startLocalTimer()
      } else {
        // If local timer is running, update the initial duration to sync with server
        timerInitialDuration.value = data.time_remaining
        timerStartTime.value = Date.now() // Reset start time to sync with server
      }
      
      // Update session status
      if (!gameState.value.session_status) {
        gameState.value.session_status = {}
      }
      gameState.value.session_status.time_remaining = data.time_remaining
    } else {
      // For non-running states, only update if it's a newer value
      if (shouldApplyUpdate('session_status.time_remaining', data.time_remaining, eventTimestamp)) {
        timeRemaining.value = data.time_remaining
        lastWebSocketTimerUpdate.value = eventTimestamp
        
        if (!gameState.value.session_status) {
          gameState.value.session_status = {}
        }
        gameState.value.session_status.time_remaining = data.time_remaining
      }
    }
    
    // Update experiment status only if it's different and not a downgrade from running to idle
    if (data.experiment_status) {
      const currentStatus = gameState.value.experiment_config?.experiment_status
      
      // Prevent status updates if session has already ended to avoid flickering
      if (sessionHasEnded.value) {
        console.log('🛡️ Session has already ended, ignoring experiment status update to prevent flickering')
        return
      }
      
      // Only block suspicious status changes during active timer
      if (currentStatus === 'running' && data.experiment_status === 'idle' && isTimerRunning.value && timeRemaining.value > 0) {
        console.log('🛡️ BLOCKING SUSPICIOUS STATUS CHANGE: running -> idle during active timer (preserving running status)')
        return
      }
      
      if (shouldApplyUpdate('experiment_config.experiment_status', data.experiment_status, eventTimestamp)) {
        if (!gameState.value.experiment_config) {
          gameState.value.experiment_config = {}
        }
        
        const oldStatus = gameState.value.experiment_config.experiment_status
        gameState.value.experiment_config.experiment_status = data.experiment_status
        
        console.log(`🔄 Experiment status changed from '${oldStatus}' to '${data.experiment_status}'`)
        
        // Start/stop local timer based on status change
        switch (data.experiment_status) {
          case 'running':
            console.log('✅ Experiment status updated to running via WebSocket')
            if (!isTimerRunning.value) {
              // Initialize timer with the time from WebSocket
              timeRemaining.value = data.time_remaining || 900
              timerStartTime.value = Date.now()
              timerInitialDuration.value = data.time_remaining || 900
              startLocalTimer() // Start local timer for smooth countdown
            }
            
            // If session just started running and we have an auto-start popup open, close it
            if (showAutoStartPopup.value) {
              console.log('Session started via timer update, closing auto-start popup')
              closeAutoStartPopup()
            }
            break
          case 'paused':
            console.log('⏸️ Experiment status updated to paused via WebSocket')
            stopLocalTimer() // Stop local timer when paused
            break
          case 'completed':
            console.log('✅ Experiment status updated to completed via WebSocket')
            stopLocalTimer() // Stop local timer when completed
            break
          case 'idle':
            console.log('⏳ Experiment status updated to idle via WebSocket')
            stopLocalTimer() // Stop local timer when idle
            break
        }
      } else {
        console.log(`⏱️ Timer updated: ${data.time_remaining}s remaining, status unchanged: ${data.experiment_status}`)
      }
    }
  })

  socket.on('game_state_update', (data: any) => {
    console.log('Received game state update:', data)
    if (data.game_state) {
      gameState.value = data.game_state
    }
  })

  socket.on('experiment_type_changed', (data: any) => {
    console.log('🔧 Received experiment type change notification:', data)
    if (data.experiment_type && data.session_code === sessionId.value) {
      console.log('🔧 Reconfiguring interface due to experiment type change')
      autoConfigureInterface()
    }
  })

  socket.on('experiment_reset', (data: any) => {
    console.log('🔄 Received experiment reset notification:', data)
    if (data.session_code === sessionId.value) {
      console.log('🔄 Experiment has been reset, clearing investment history')
      clearInvestmentHistory()
      // Reload game state to get fresh data
      loadGameStateIncremental()
    }
  })

  socket.on('timer_reset', (data: any) => {
    console.log('⏰ Received timer reset notification:', data)
    if (data.session_code === sessionId.value) {
      console.log('⏰ Timer has been reset, clearing investment history')
      clearInvestmentHistory()
      // Reload game state to get fresh data
      loadGameStateIncremental()
    }
  })

  socket.on('new_message', (data: any) => {
    console.log('Received new message:', data)
    
    // Check if this event has already been processed
    const eventId = `new_message_${data.message_id || data.sender}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    // Check if this message involves the current participant
    const currentDisplayName = extractDisplayName(participantId.value)
    const senderDisplayName = data.sender ? extractDisplayName(data.sender) : null
    const recipientDisplayName = data.recipient ? extractDisplayName(data.recipient) : null
    
    const messageInvolvesMe = senderDisplayName === currentDisplayName || recipientDisplayName === currentDisplayName
    console.log('Message involves me:', messageInvolvesMe)
    
    // Update unread count for incoming messages (not from current user)
    if (senderDisplayName !== currentDisplayName && messageInvolvesMe) {
      console.log('New unread message received, updating unread count for participant:', senderDisplayName)
      
      // Update unread count for the sender immediately for real-time notification dots
      const currentCount = unreadMessagesByParticipant.value.get(senderDisplayName) || 0
      unreadMessagesByParticipant.value.set(senderDisplayName, currentCount + 1)
      
      console.log('Updated unread count for', senderDisplayName, 'to', currentCount + 1)
      
      // Force Vue reactivity update for notification dots
      nextTick(() => {
        unreadMessagesByParticipant.value = new Map(unreadMessagesByParticipant.value)
      })
    }
    
    // Always load all messages to update notification dots for all participants
    loadMessages()
    
    // Only refresh messages if we're currently viewing the relevant conversation
    // This prevents clearing messages when viewing other conversations
    if (messageInvolvesMe) {
      const shouldRefresh = (() => {
        if (gameState.value.communication_level === 'broadcast') {
          // In broadcast mode, only refresh if we're viewing broadcast messages
          return currentTab.value === 'message'
        } else if (gameState.value.communication_level === 'chat' && selectedPlayer.value) {
          // In chat mode, only refresh if the message involves the currently selected player
          const selectedDisplayName = extractDisplayName(selectedPlayer.value.participant_id)
          const isFromSelectedPlayer = senderDisplayName === selectedDisplayName
          const isToSelectedPlayer = recipientDisplayName === selectedDisplayName
          return isFromSelectedPlayer || isToSelectedPlayer
        }
        return false
      })()
      
      if (shouldRefresh) {
        console.log('Message involves current conversation, refreshing messages...')
        // loadMessages() will handle all messages, and computed properties will filter correctly
        loadMessages()
      } else {
      }
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  socket.on('new_trade_offer', (data: any) => {
    console.log('Received new trade offer:', data)
    
    // Check if this event has already been processed
    const eventId = `new_trade_offer_${data.transaction_id || data.sender}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    // Check if this is an incoming trade offer (not from current user)
    const currentDisplayName = extractDisplayName(participantId.value)
    const senderDisplayName = data.sender ? extractDisplayName(data.sender) : null
    const targetDisplayName = data.target ? extractDisplayName(data.target) : null
    const isIncomingTradeOffer = senderDisplayName !== currentDisplayName && targetDisplayName === currentDisplayName
    if (isIncomingTradeOffer) {
      console.log('New incoming trade offer received, updating notification dots for participant:', data.sender)
      
      // Update unread count for the sender immediately for real-time notification dots
      const currentCount = unreadTradeOffersByParticipant.value.get(data.sender) || 0
      unreadTradeOffersByParticipant.value.set(data.sender, currentCount + 1)
      
      console.log('Updated unread trade count for', data.sender, 'to', currentCount + 1)
      
      // Force Vue reactivity update for notification dots
      nextTick(() => {
        unreadTradeOffersByParticipant.value = new Map(unreadTradeOffersByParticipant.value)
      })
    }
    
    // Always load all trade data to update notification dots for all participants
    loadAllTradeData()
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  socket.on('trade_offer_response', (data: any) => {
    console.log('=== TRADE OFFER RESPONSE RECEIVED ===')
    console.log('Response data:', data)
    
    // Check if this event has already been processed
    const eventId = `trade_offer_response_${data.transaction_id}_${data.response}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    console.log('My participant ID:', participantId.value)
    console.log('Selected player:', selectedPlayer.value?.participant_id)
    
    // Clear trade notifications for the sender of the trade offer
    const currentDisplayName = extractDisplayName(participantId.value)
    const senderDisplayName = data.sender ? extractDisplayName(data.sender) : null
    
    if (senderDisplayName && senderDisplayName !== currentDisplayName) {
      unreadTradeOffersByParticipant.value.delete(senderDisplayName)
      console.log('Cleared trade notifications for participant:', senderDisplayName)
      
      // Force Vue reactivity update for notification dots
      nextTick(() => {
        unreadTradeOffersByParticipant.value = new Map(unreadTradeOffersByParticipant.value)
      })
    }
    
    // Always load all trade data to update notification dots for all participants
    loadAllTradeData()
    
    // IMPORTANT: Always refresh game state from backend to ensure inventory synchronization
    // Don't rely on incremental updates from WebSocket events for inventory
    console.log('Trade offer response - refreshing game state from backend to ensure inventory sync')
    if (isAuthenticated()) {
      loadGameStateIncremental()
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  socket.on('trade_completed', (data: any) => {
    console.log('=== TRADE COMPLETED EVENT ===')
    console.log('Trade data:', data)
    
    // Check if this event has already been processed
    const eventId = `trade_completed_${data.transaction_id}_${data.seller}_${data.buyer}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    console.log('My participant ID:', participantId.value)
    console.log('Current inventory before trade processing:', gameState.value.participant?.shapes_acquired)
    
    // Always refresh trade data and game state if this participant was involved
    const currentDisplayName = extractDisplayName(participantId.value)
    const sellerDisplayName = data.seller ? extractDisplayName(data.seller) : null
    const buyerDisplayName = data.buyer ? extractDisplayName(data.buyer) : null
    const acceptedByDisplayName = data.accepted_by ? extractDisplayName(data.accepted_by) : null
    
    const tradeInvolvesMe = (sellerDisplayName && sellerDisplayName === currentDisplayName) || 
                           (buyerDisplayName && buyerDisplayName === currentDisplayName) ||
                           (acceptedByDisplayName && acceptedByDisplayName === currentDisplayName)
    
    console.log('Trade involves me:', tradeInvolvesMe)
    console.log('I am seller:', sellerDisplayName === currentDisplayName)
    console.log('I am buyer:', buyerDisplayName === currentDisplayName)
    
    if (tradeInvolvesMe) {
      console.log('Processing trade completion...')
      
      // Clear trade notifications for the other participant in the trade
      if (sellerDisplayName && sellerDisplayName !== currentDisplayName) {
        unreadTradeOffersByParticipant.value.delete(sellerDisplayName)
        console.log('Cleared trade notifications for seller:', sellerDisplayName)
      } else if (buyerDisplayName && buyerDisplayName !== currentDisplayName) {
        unreadTradeOffersByParticipant.value.delete(buyerDisplayName)
        console.log('Cleared trade notifications for buyer:', buyerDisplayName)
      }
      
      // Force Vue reactivity update for notification dots
      nextTick(() => {
        unreadTradeOffersByParticipant.value = new Map(unreadTradeOffersByParticipant.value)
      })
      
      // Clear any inventory protection to ensure trade completion updates are applied
      if (recentlyAddedShapes.value.size > 0) {
        console.log('Clearing inventory protection for trade completion')
        recentlyAddedShapes.value.clear()
      }
      
      // IMPORTANT: Don't update inventory locally anymore
      // Instead, immediately refresh game state from backend to ensure synchronization
      console.log('Trade completed - refreshing game state from backend to ensure inventory sync')
      console.log('Current inventory before refresh:', gameState.value.participant?.shapes_acquired)
      
      // Immediately refresh game state to get the correct inventory from backend
      if (isAuthenticated()) {
        loadGameStateIncremental()
      }
      
      // Log inventory after refresh
      setTimeout(() => {
        console.log('Inventory after trade completion refresh:', gameState.value.participant?.shapes_acquired)
      }, 1000)
      
      console.log('Game state refreshed after trade completion')
    }
    
    // Always load all trade data to update notification dots for all participants
    loadAllTradeData()
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  // Add general trade update handler to catch any trade-related updates
  socket.on('trade_update', (data: any) => {
    console.log('General trade update received:', data)
    
    // Check if this event has already been processed
    const eventId = `trade_update_${data.transaction_id || 'general'}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    // Always load all trade data to update notification dots for all participants
    loadAllTradeData()
    
    // IMPORTANT: Always refresh game state from backend to ensure inventory synchronization
    // Don't rely on incremental updates from WebSocket events for inventory
    console.log('General trade update - refreshing game state from backend to ensure inventory sync')
    if (isAuthenticated()) {
      loadGameStateIncremental()
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  // Add specific handler for any trade offer changes
  socket.on('trade_offer_updated', (data: any) => {
    console.log('=== TRADE OFFER UPDATED ===')
    console.log('Update data:', data)
    
    // Check if this event has already been processed
    const eventId = `trade_offer_updated_${data.transaction_id}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    console.log('My participant ID:', participantId.value)
    console.log('Selected player:', selectedPlayer.value?.participant_id)
    
    // Always load all trade data to update notification dots for all participants
    loadAllTradeData()
    
    // Also refresh again after a short delay to ensure we get the latest data
    setTimeout(() => {
      console.log('Refreshing trade data again after update...')
      loadAllTradeData()
    }, 1000)
    
    // IMPORTANT: Always refresh game state from backend to ensure inventory synchronization
    // Don't rely on incremental updates from WebSocket events for inventory
    console.log('Trade offer updated - refreshing game state from backend to ensure inventory sync')
    if (isAuthenticated()) {
      loadGameStateIncremental()
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  // Add general message update handler to catch any message-related updates
  socket.on('message_update', (data: any) => {
    console.log('General message update received:', data)
    
    // Check if this event has already been processed
    const eventId = `message_update_${data.message_id || 'general'}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    // Always load all messages to update notification dots for all participants
    loadMessages()
    
    // Only refresh messages if we're currently viewing the message tab
    // This prevents clearing messages when viewing other tabs
    if (currentTab.value === 'message') {
      console.log('Currently viewing message tab, refreshing messages...')
      // loadMessages() will handle all messages, and computed properties will filter correctly
      loadMessages()
    } else {
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  // Add handlers for participant connection events
  socket.on('participant_connected', (data: any) => {
    console.log('Participant connected:', data)
    
    // Check if this event has already been processed
    const eventId = `participant_connected_${data.participant_code}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    // Refresh game state to update participant list (use incremental update)
    if (isAuthenticated()) {
      loadGameStateIncremental()
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  socket.on('participant_disconnected', (data: any) => {
    console.log('Participant disconnected:', data)
    
    // Check if this event has already been processed
    const eventId = `participant_disconnected_${data.participant_code}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    // Refresh game state to update participant list (use incremental update)
    if (isAuthenticated()) {
      loadGameStateIncremental()
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  // Note: Removed specific experiment control event handlers
  // The timer_update event should handle all timer and status updates

  socket.on('participants_updated', (data: any) => {
    console.log('Participants list updated:', data)
    
    // Check if this event has already been processed
    const eventId = `participants_updated_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    const eventTimestamp = Date.now()
    
    // Update the participants list in game state
    if (data.participants) {
      // Add new participants to stable order if they don't exist
      const newParticipantIds = data.participants.map((p: any) => p.participant_code || p.participant_id)
      newParticipantIds.forEach((participantId: string) => {
        if (!stableParticipantOrder.value.includes(participantId)) {
          stableParticipantOrder.value.push(participantId)
          console.log('Added new participant to stable order:', participantId)
        }
      })
      
      applyIncrementalUpdate('participants', data.participants, eventTimestamp)
    } else {
      // Fallback: reload entire game state (use incremental update)
      if (isAuthenticated()) {
        loadGameStateIncremental()
      }
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  // Listen for production events
  socket.on('production_started', (data: any) => {
    console.log('Production started by participant:', data)
    
    // Check if this event has already been processed
    const eventId = `production_started_${data.participant_code}_${data.shape}_${data.production_id}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    // Apply incremental updates for all participants' production
    const eventTimestamp = Date.now()
    
    // Update production queue if provided
    if (data.new_production_queue !== undefined) {
      applyIncrementalUpdate('participant.production_queue', data.new_production_queue, eventTimestamp)
    }
    
    // Update production count if provided (for all participants including ourselves)
    if (data.new_production_count !== undefined) {
      applyIncrementalUpdate('participant.specialty_production_used', data.new_production_count, eventTimestamp)
    }
    
    // Refresh awareness dashboard data to update production counts for all participants
    loadAwarenessDashboardData()
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  // Listen for production completion events
  socket.on('production_completed', (data: any) => {
    console.log('Production completed by participant:', data)
    
    // Check if this event has already been processed
    const eventId = `production_completed_${data.participant_code}_${data.shape}_${data.production_id}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    // If it's my production, clear the production state and refresh inventory
    if (data.participant_code === participantId.value) {
      console.log(`✅ Production completed: ${data.shape} is now available in your inventory!`)
      
      // Mark this production as completed to prevent duplicates
      if (data.production_id) {
        completedProductionItems.value.add(data.production_id)
        console.log(`Marked production ${data.production_id} as completed`)
      }
      
      // Only clear if we haven't already cleared it via timer
      if (currentProduction.value && currentProduction.value.id === data.production_id) {
        // Clear production state
        currentProduction.value = null
        isProductionInProgress.value = false
        explicitlyStartedProduction.value = false
        console.log('Production state cleared via WebSocket')
        
        // Force reactive update
        nextTick(() => {
          console.log('Production completion WebSocket reactive update completed')
        })
      } else {
        console.log('Production state already cleared or different production ID')
      }
      
      // IMPORTANT: Refresh game state to get updated inventory from backend
      loadGameState()
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  // Add general production update handler to catch any production-related updates
  socket.on('production_update', (data: any) => {
    console.log('General production update received:', data)
    
    // Check if this event has already been processed
    const eventId = `production_update_${data.participant_code}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    // Apply incremental updates for all participants' production
    const eventTimestamp = Date.now()
    
    // Update production queue if provided
    if (data.production_queue !== undefined) {
      applyIncrementalUpdate('participant.production_queue', data.production_queue, eventTimestamp)
    }
    
    // Update production count if provided (for all participants including ourselves)
    if (data.production_count !== undefined) {
      applyIncrementalUpdate('participant.specialty_production_used', data.production_count, eventTimestamp)
    }
    
    // Refresh awareness dashboard data to update production counts for all participants
    loadAwarenessDashboardData()
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  // Listen for order fulfillment events
  socket.on('orders_fulfilled', (data: any) => {
    console.log('Orders fulfilled by participant:', data)
    
    // Check if this event has already been processed
    const eventId = `orders_fulfilled_${data.participant_code}_${data.orders_fulfilled}_${data.score_gained}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    // If it's my order fulfillment, show notification and update local state
    if (data.participant_code === participantId.value) {
      // Show success notification (in addition to the API response)
      console.log(`You fulfilled ${data.orders_fulfilled} orders and gained $${data.score_gained}!`)
      
      // If we don't already have local protection (meaning the API call didn't handle this),
      // we need to update the orders locally via WebSocket event
      if (recentlyFulfilledOrders.value.size === 0 && data.orders_fulfilled > 0) {
        console.log('No local protection active, updating orders via WebSocket event')
        
        // Use the new_orders array from the WebSocket if available, otherwise fallback to approximation
        if (data.new_orders !== undefined) {
          console.log('Using exact new_orders array from WebSocket event')
          gameState.value.participant.orders = data.new_orders
        } else if (gameState.value.participant?.orders) {
          console.log('Fallback: approximating order removal')
          // Remove the fulfilled orders from the end of the array
          // This is an approximation since we don't know which specific orders were fulfilled
          const currentOrders = [...gameState.value.participant.orders]
          const newOrders = currentOrders.slice(0, -data.orders_fulfilled)
          gameState.value.participant.orders = newOrders
        }
        
        // Add protection to prevent backend overwrite
        const protectionKey = `websocket_fulfilled_${Date.now()}`
        recentlyFulfilledOrders.value.add(protectionKey)
        
        // Remove protection after backend processing
        setTimeout(() => {
          recentlyFulfilledOrders.value.delete(protectionKey)
          console.log(`🔓 Removed WebSocket order fulfillment protection: ${protectionKey}`)
        }, 5000)
        
        const remainingOrders = gameState.value.participant?.orders?.length || 0
        console.log(`Updated orders via WebSocket: ${remainingOrders} orders remaining`)
      } else {
      }
    }
    
    // Apply incremental updates for money and orders completed
    const eventTimestamp = Date.now()
    
    // Update money if provided
    if (data.new_money !== undefined) {
      applyIncrementalUpdate('participant.money', data.new_money, eventTimestamp)
    }
    
    // Update orders completed if provided
    if (data.new_orders_completed !== undefined) {
      applyIncrementalUpdate('participant.orders_completed', data.new_orders_completed, eventTimestamp)
    }
    
    // Update inventory if provided via WebSocket (always apply for order fulfillment events)
    if (data.new_inventory !== undefined) {
      console.log('Updating inventory via WebSocket event:', data.new_inventory)
      applyIncrementalUpdate('participant.shapes_acquired', data.new_inventory, eventTimestamp)
    }
    
    // Refresh awareness dashboard data if enabled
    if (awarenessDashboardEnabled.value) {
      loadAwarenessDashboardData()
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })



  // Listen for participant status updates (money, orders, etc.)
  socket.on('participant_status_update', (data: any) => {
    console.log('Participant status update received:', data)
    
    // Check if this event has already been processed
    const eventId = `participant_status_${data.participant_code}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    const eventTimestamp = Date.now()
    
    // Apply incremental updates for specific fields
    if (data.money !== undefined) {
      applyIncrementalUpdate('participant.money', data.money, eventTimestamp)
    }
    
    if (data.orders_completed !== undefined) {
      applyIncrementalUpdate('participant.orders_completed', data.orders_completed, eventTimestamp)
    }
    
    if (data.completion_percentage !== undefined) {
      applyIncrementalUpdate('participant.completion_percentage', data.completion_percentage, eventTimestamp)
    }
    
    // Refresh awareness dashboard data if enabled
    if (awarenessDashboardEnabled.value) {
      loadAwarenessDashboardData()
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  // Listen for configuration updates
  socket.on('config_updated', (data: any) => {
    console.log('Configuration update received:', data)
    
    // Only process updates for the current session
    if (data.session_code && data.session_code !== sessionId.value) {
      console.log('⏱️ Ignoring config update for different session:', data.session_code)
      return
    }
    
    // Update communication level if provided
    if (data.communicationLevel) {
      gameState.value.communication_level = data.communicationLevel
      console.log('✅ Communication level updated via WebSocket:', data.communicationLevel)
    }
    
    // Update awareness dashboard setting if provided
    if (data.awarenessDashboard !== undefined) {
      gameState.value.awareness_dashboard_enabled = data.awarenessDashboard === 'on'
      console.log('✅ Awareness dashboard setting updated via WebSocket:', data.awarenessDashboard)
    }
  })

  // Listen for money updates
  socket.on('money_updated', (data: any) => {
    console.log('Money updated:', data)
    
    // Check if this event has already been processed
    const eventId = `money_updated_${data.participant_code}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    // If it's my money update, refresh game state to get updated money from backend
    if (data.participant_code === participantId.value) {
      console.log('Money updated - refreshing game state from backend to ensure money sync')
      loadGameState()
    }
    
    // Refresh awareness dashboard data if enabled
    if (awarenessDashboardEnabled.value) {
      loadAwarenessDashboardData()
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })

  // Listen for session status updates
  socket.on('session_status_update', (data: any) => {
    console.log('Session status update received:', data)
    console.log('Session status update details:', {
      experiment_status: data.experiment_status,
      timestamp: new Date().toISOString()
    })
    const eventTimestamp = Date.now()
    
    if (data.experiment_status) {
      // Prevent status updates if session has already ended to avoid flickering
      if (sessionHasEnded.value) {
        console.log('🛡️ Session has already ended, ignoring session status update to prevent flickering')
        return
      }
      
      if (shouldApplyUpdate('experiment_config.experiment_status', data.experiment_status, eventTimestamp)) {
        if (!gameState.value.experiment_config) {
          gameState.value.experiment_config = {}
        }
        gameState.value.experiment_config.experiment_status = data.experiment_status
        console.log('Session status updated via WebSocket:', data.experiment_status)
        
        // Start/stop local timer based on experiment status
        if (data.experiment_status === 'running') {
          // Initialize local timer with current game state time
          if (gameState.value.session_status?.time_remaining) {
            timeRemaining.value = gameState.value.session_status.time_remaining
            console.log('⏰ Session status: Starting local timer with time:', timeRemaining.value)
          }
          if (!isTimerRunning.value) {
            startLocalTimer() // Start local timer for smooth countdown
          }
          
          // If session just started running and we have an auto-start popup open, close it
          if (showAutoStartPopup.value) {
            console.log('Session started via WebSocket, closing auto-start popup')
            closeAutoStartPopup()
          }
        } else {
          console.log('⏰ Session status: Stopping local timer - status:', data.experiment_status)
          stopLocalTimer() // Stop local timer when not running
        }
      }
    }
  })

  // Listen for trade offer cancellations
  socket.on('trade_offer_cancelled', (data: any) => {
    console.log('=== TRADE OFFER CANCELLED WEBSOCKET EVENT RECEIVED ===')
    console.log('Cancellation data:', data)
    console.log('Current participant ID:', participantId.value)
    console.log('Selected player:', selectedPlayer.value?.participant_id)
    
    // Check if this event has already been processed
    const eventId = `trade_offer_cancelled_${data.transaction_id}_${data.canceller}_${data.timestamp || Date.now()}`
    if (isEventProcessed(eventId)) {
      return
    }
    
    console.log('My participant ID:', participantId.value)
    console.log('Selected player:', selectedPlayer.value?.participant_id)
    
    // Load trade data with a short delay to ensure backend processing is complete
    setTimeout(() => {
      console.log('Refreshing trade data after WebSocket cancellation event...')
      loadAllTradeData()
    }, 300) // Short delay to ensure backend processing is complete
    
    // IMPORTANT: Always refresh game state from backend to ensure inventory synchronization
    // Don't rely on incremental updates from WebSocket events for inventory
    console.log('Trade offer cancelled - refreshing game state from backend to ensure inventory sync')
    if (isAuthenticated()) {
      loadGameStateIncremental()
    }
    
    // Mark event as processed
    markEventProcessed(eventId)
  })
}

const logout = async () => {
  const authToken = sessionStorage.getItem('auth_token')
  
  if (authToken) {
    try {
      // Call logout endpoint
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      })
    } catch (error) {
      console.error('Logout error:', error)
    }
  }
  
  // Clear local storage and redirect
  sessionStorage.clear()
  
  // Disconnect WebSocket
  if (socket) {
    socket.disconnect()
  }
  
  router.push('/login')
}

const returnToLogin = () => {
  console.log('Returning to login page after session ended')
  
  // Clear local storage
  sessionStorage.clear()
  
  // Disconnect WebSocket
  if (socket) {
    socket.disconnect()
  }
  
  // Redirect to the login page
  window.location.href = `http://localhost:3000/login`
}

// Lifecycle
onMounted(async () => {
  // Check authentication
  const authToken = sessionStorage.getItem('auth_token')
  const participantCode = sessionStorage.getItem('participant_code')
  const storedParticipantId = sessionStorage.getItem('participant_id')
  
  if (!authToken || !participantCode || !storedParticipantId) {
    // Redirect to login if not authenticated
    router.push('/login')
    return
  }
  
  // Set participant info from stored authentication
  participantId.value = participantCode
  sessionId.value = sessionStorage.getItem('session_code') || ''
  
  // Check if we have a valid session code
  if (!sessionId.value) {
    console.error('No session code found in sessionStorage')
    sessionStorage.clear()
    router.push('/login')
    return
  }
  
  // Initialize WebSocket with authenticated user
  initializeWebSocket()
  
  // Load initial game state from database first
  await loadGameState()
  
  // Load ECL configuration if this is an ECL experiment
  if (isECLExperiment.value) {
    await loadECLConfig()
    await loadECLState()
  }
  
  // Auto-configure interface based on experiment type AFTER game state is loaded
  const configSuccess = await autoConfigureInterface()
  
  // If initial configuration failed, set up periodic retry
  if (!configSuccess) {
    const checkInterval = setInterval(async () => {
      const retrySuccess = await autoConfigureInterface()
      if (retrySuccess) {
        clearInterval(checkInterval)
      }
    }, 2000)
    
    // Clear interval after 30 seconds
    setTimeout(() => {
      clearInterval(checkInterval)
    }, 30000)
  }
  
  // Additional check: Force configuration if still showing default type
  setTimeout(async () => {
    const currentType = interfaceConfig.value.myAction.type
    
    // If we're still showing the default shapefactory type, try to reconfigure
    if (currentType === 'shapefactory') {
      await autoConfigureInterface()
    }
  }, 1000)
  
  console.log('Participant interface initialized with:', {
    participantId: participantId.value,
    sessionId: sessionId.value,
    authToken: authToken ? 'present' : 'missing',
    currentInterfaceConfig: interfaceConfig.value
  })
  
  // Verify token is still valid
  try {
    const response = await fetch('/api/auth/verify', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ token: authToken })
    })
    
    if (!response.ok) {
      // Token invalid, redirect to login
      sessionStorage.clear()
      router.push('/login')
      return
    }
  } catch (error) {
    console.error('Token verification failed:', error)
    router.push('/login')
    return
  }
  

  // Reset session ended flag on component mount (only if session is not already completed)
  if (gameState.value.experiment_config?.experiment_status !== 'completed' && 
      gameState.value.experiment_config?.experiment_status !== 'stopped' && 
      gameState.value.experiment_config?.experiment_status !== 'ended') {
    sessionHasEnded.value = false
    console.log('Component mounted: Reset session ended flag')
  } else {
    // If session was previously completed, set the flag to prevent any further changes
    sessionHasEnded.value = true
    console.log('Component mounted: Session was previously completed, setting session ended flag')
  }

  // Initialize unread counts for all participants
  await initializeUnreadCounts()
  
  // Load initial messages for all participants to set up notification dots
  await loadMessages()

  // Load initial trade data for all participants to set up notification dots
  await loadAllTradeData()

  // Initialize timer if experiment is already running
  if (gameState.value.experiment_config?.experiment_status === 'running' && 
      gameState.value.session_status?.time_remaining) {
    console.log('⏰ Page load: Experiment is running, initializing timer')
    timeRemaining.value = gameState.value.session_status.time_remaining
    if (!isTimerRunning.value) {
      startLocalTimer()
    }
  }

  // Load initial awareness dashboard data (always load for factory panel data source)
  await loadAwarenessDashboardData()

  // Load assigned essays for essay ranking experiments
  if (interfaceConfig.value.myAction?.type === 'essayranking') {
    console.log('🔄 Detected essay ranking experiment, loading essays...')
    await loadAssignedEssays()
    // Set up periodic refresh for essays every 5 seconds
    const essayRefreshInterval = setInterval(async () => {
      if (interfaceConfig.value.myAction?.type === 'essayranking') {
        await loadAssignedEssays()
      } else {
        clearInterval(essayRefreshInterval)
      }
    }, 5000)
    
    // Store interval for cleanup
    onUnmounted(() => {
      clearInterval(essayRefreshInterval)
    })
  }

  // Check if session should start automatically (only if not previously completed)
  if (gameState.value.experiment_config?.experiment_status !== 'completed' && 
      gameState.value.experiment_config?.experiment_status !== 'stopped' && 
      gameState.value.experiment_config?.experiment_status !== 'ended') {
    await checkAndStartSession()
  } else {
  }

  // Note: Removed production queue sync - no longer needed with single production system

  // Auto-select first participant if none is selected and participants are available
  if (!selectedPlayer.value && otherParticipants.value.length > 0) {
    const firstParticipant = otherParticipants.value[0]
    // Validate that the participant has a valid ID before selecting
    if (firstParticipant && firstParticipant.participant_id && firstParticipant.participant_id.trim() !== '') {
      console.log('Auto-selecting first participant after game state load:', firstParticipant.participant_id)
      selectPlayer(firstParticipant)
    } else {
      console.warn('Skipping auto-selection of invalid participant after game state load:', firstParticipant)
    }
  }
  
  // Add page visibility change handler to refresh timer when tab becomes visible
  const handleVisibilityChange = () => {
    if (document.hidden) {
      if (isTimerRunning.value) {
        console.log('🔄 Background timer active - will recalculate when tab becomes visible')
      }
    } else {
      // Tab became visible - sync timer state
      console.log('🔄 Tab became visible, syncing timer state...')
      
      // If we have a running timer, recalculate the time remaining based on elapsed time
      if (isTimerRunning.value && gameState.value.experiment_config?.experiment_status === 'running') {
        const elapsedSeconds = Math.floor((Date.now() - timerStartTime.value) / 1000)
        const calculatedTimeRemaining = Math.max(0, timerInitialDuration.value - elapsedSeconds)
        
        // Update the timer value if there's a significant difference
        if (Math.abs(calculatedTimeRemaining - timeRemaining.value) > 2) {
          timeRemaining.value = calculatedTimeRemaining
        }
        
        // If timer has reached 0, mark experiment as completed
        if (calculatedTimeRemaining === 0) {
          isTimerRunning.value = false
          if (gameState.value.experiment_config) {
            gameState.value.experiment_config.experiment_status = 'completed'
          }
        }
      }
      
      // Only call incremental update if we don't have a running timer to avoid overwriting experiment status
      if (!isTimerRunning.value) {
        loadGameStateIncremental()
      } else {
      }
      
      // Only refresh timer state from server if we don't have a running local timer AND experiment is not running
      if (sessionId.value && !isTimerRunning.value && gameState.value.experiment_config?.experiment_status !== 'running') {
        fetch(`/api/experiment/timer-state?session_code=${encodeURIComponent(sessionId.value)}`)
          .then(response => response.json())
          .then(data => {
            console.log('🔄 Refreshed timer state after tab visibility change:', data)
            
            // Only update timer if we don't have a local timer running
            if (!isTimerRunning.value) {
              timeRemaining.value = data.time_remaining
              lastWebSocketTimerUpdate.value = Date.now()
              
              // Update experiment status
              if (data.experiment_status && gameState.value.experiment_config) {
                gameState.value.experiment_config.experiment_status = data.experiment_status
                
                switch (data.experiment_status) {
                  case 'running':
                    startLocalTimer()
                    break
                  case 'paused':
                  case 'completed':
                  case 'idle':
                    stopLocalTimer()
                    break
                }
              }
            } else {
            }
          })
          .catch(error => console.error('Error refreshing timer state:', error))
      } else if (isTimerRunning.value) {
      }
    }
  }
  
  document.addEventListener('visibilitychange', handleVisibilityChange)
  
  // Add window focus/blur handlers for additional timer accuracy
  const handleWindowFocus = () => {
    if (isTimerRunning.value && gameState.value.experiment_config?.experiment_status === 'running') {
      const elapsedSeconds = Math.floor((Date.now() - timerStartTime.value) / 1000)
      const calculatedTimeRemaining = Math.max(0, timerInitialDuration.value - elapsedSeconds)
      
      // Update the timer value if there's a significant difference
      if (Math.abs(calculatedTimeRemaining - timeRemaining.value) > 1) {
        timeRemaining.value = calculatedTimeRemaining
      }
    }
  }
  
  const handleWindowBlur = () => {
    if (isTimerRunning.value) {
      console.log('🔄 Window blurred, timer continues running in background')
    }
  }
  
  window.addEventListener('focus', handleWindowFocus)
  window.addEventListener('blur', handleWindowBlur)

  // Load initial messages based on communication mode
  if (isBroadcastMode.value) {
    console.log('Loading initial broadcast messages...')
    loadMessages()
  } else if (isChatMode.value) {
    console.log('Chat mode enabled - messages will load when a player is selected')
    // In chat mode, messages are loaded when a player is selected
  } else {
    console.log('No chat mode - messages disabled')
  }

  // Session status is now updated via WebSocket events and debounced

  // Add awareness dashboard refresh interval (less frequent)
  const awarenessDashboardRefreshInterval = setInterval(() => {
    if (isAuthenticated()) {
      loadAwarenessDashboardData()
    }
  }, 5000) // Refresh every 5 seconds (less frequent to reduce conflicts)

  // Add notification dots refresh interval to ensure real-time updates
  const notificationDotsRefreshInterval = setInterval(() => {
    if (isAuthenticated()) {
      // Load all messages for all participants to update notification dots
      loadMessages()
      
      // Load all trade data for all participants to update notification dots
      loadAllTradeData()
      
      // Only refresh game state if we don't have recent operations to prevent glitches
      if (recentlyAddedShapes.value.size === 0 && recentlyFulfilledOrders.value.size === 0) {
        loadGameStateIncremental()
      } else {
      }
    }
  }, 3000) // Refresh every 3 seconds (increased from 2 seconds to reduce conflicts)

  // Add real-time session status monitoring (every second)
  const sessionStatusMonitorInterval = setInterval(() => {
    if (isAuthenticated()) {
      // Check more frequently during auto-start countdown
      if (showAutoStartPopup.value && autoStartCountdown.value > 0) {
        // Check every 500ms during countdown for immediate response
        return
      }
      
      if (!isTimerRunning.value) {
        // Only check if we don't have a local timer running to avoid conflicts
        checkSessionStatusRealTime()
      }
    }
  }, 1000) // Check every second for real-time updates

  // Add more frequent monitoring during auto-start countdown
  const autoStartStatusMonitorInterval = setInterval(() => {
    if (isAuthenticated() && showAutoStartPopup.value && autoStartCountdown.value > 0) {
      // Check every 500ms during countdown for immediate response
      checkSessionStatusRealTime()
    }
  }, 500) // Check every 500ms during countdown

  // Add production timer for real-time countdown
  const productionTimerInterval = setInterval(() => {
    // Update production timer countdown
    updateProductionTimer()
  }, 1000) // Update every second

  // Add periodic processing of completed productions (less frequent)
  const completedProductionsInterval = setInterval(() => {
    if (isAuthenticated()) {
      processCompletedProductions()
    }
  }, 15000) // Process completed productions every 15 seconds (less frequent)

  // Add cleanup for completed production items tracking set
  const cleanupCompletedItemsInterval = setInterval(() => {
    // Clean up tracking set if it gets too large (shouldn't happen in normal operation)
    if (completedProductionItems.value.size > 100) {
      console.log('Cleaning up completed production items tracking set')
      completedProductionItems.value.clear()
    }

  }, 60000) // Clean up every 60 seconds (less frequent)

  // Store interval for cleanup on component unmount
  onUnmounted(() => {
    if (socket) {
      socket.disconnect()
    }
    // Clean up the debounce timeout
    if (loadGameStateTimeout) {
      clearTimeout(loadGameStateTimeout)
    }
    // Clean up session status debounce timeout
    if (sessionStatusDebounceTimeout) {
      clearTimeout(sessionStatusDebounceTimeout)
    }
    
    // Reset session ended flag
    sessionHasEnded.value = false
    clearInterval(productionTimerInterval)
    clearInterval(completedProductionsInterval)
    clearInterval(cleanupCompletedItemsInterval)
    clearInterval(awarenessDashboardRefreshInterval)
    clearInterval(notificationDotsRefreshInterval)
    clearInterval(sessionStatusMonitorInterval)
    clearInterval(autoStartStatusMonitorInterval)
    
    // Clean up auto-start interval
    if (autoStartInterval.value) {
      clearInterval(autoStartInterval.value)
    }
    
    stopLocalTimer()
    
    // Clean up unread tracking
    unreadMessagesByParticipant.value.clear()
    unreadTradeOffersByParticipant.value.clear()
    
    // Clean up recently added shapes tracking
    recentlyAddedShapes.value.clear()
    
    // Clean up recently fulfilled orders tracking
    recentlyFulfilledOrders.value.clear()
    
    // Clean up event listeners
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    window.removeEventListener('focus', handleWindowFocus)
    window.removeEventListener('blur', handleWindowBlur)


  })
})

// Watch for experiment status changes to manage local timer
watch(() => gameState.value.experiment_config?.experiment_status, (newStatus, oldStatus) => {
  if (newStatus !== oldStatus) {
    console.log('Experiment status changed via watch:', { oldStatus, newStatus, timestamp: new Date().toISOString() })
    
    // Start/stop local timer based on experiment status
    if (newStatus === 'running') {
      // Initialize local timer with current game state time
      if (gameState.value.session_status?.time_remaining) {
        timeRemaining.value = gameState.value.session_status.time_remaining
        console.log('⏰ Watch: Starting local timer with time:', timeRemaining.value)
      }
      if (!isTimerRunning.value) {
        startLocalTimer() // Start local timer for smooth countdown
      }
    } else {
      console.log('⏰ Watch: Stopping local timer - status:', newStatus)
      stopLocalTimer() // Stop local timer when not running
    }
    
    // If session just started running and we have an auto-start popup open, close it
    if (newStatus === 'running' && showAutoStartPopup.value) {
      console.log('Session started, closing auto-start popup')
      closeAutoStartPopup()
    }
  }
}, { immediate: false })

// Watch for production queue changes to update current production
watch(() => gameState.value.participant?.production_queue, (newQueue, oldQueue) => {
  if (newQueue !== oldQueue) {
    console.log('Production queue changed:', { 
      newQueue, 
      oldQueue, 
      currentProduction: currentProduction.value,
      timestamp: new Date().toISOString() 
    })
    
    // Let the computed property handle the update
    console.log('Backend production queue updated, will be handled by computed property')
  }
}, { immediate: false })

// Watch for order selection to show fulfillment popup
watch(selectedOrders, (newSelected, oldSelected) => {
  if (newSelected.length === 1 && oldSelected.length === 0) {
    // User just selected a single order
    const orderIndex = newSelected[0]
    const orders = gameState.value.participant?.orders || []
    if (orders[orderIndex]) {
      selectedOrderShape.value = orders[orderIndex]
      selectedOrderIndex.value = orderIndex
      showOrderFulfillmentPopup.value = true
    }
  } else if (newSelected.length === 0 && oldSelected.length > 0) {
    // User deselected all orders, close popup if open
    if (showOrderFulfillmentPopup.value) {
      closeOrderFulfillmentPopup()
    }
  }
}, { immediate: false })

// Add shape to inventory when production completes
const addShapeToInventory = (shape: string) => {
  console.log(`=== ADDING SHAPE FROM PRODUCTION ===`)
  console.log(`Shape: ${shape}`)
  console.log(`Current inventory before:`, gameState.value.participant?.shapes_acquired)
  
  if (gameState.value.participant) {
    if (!gameState.value.participant.shapes_acquired) {
      gameState.value.participant.shapes_acquired = []
    }
    gameState.value.participant.shapes_acquired.push(shape)
    console.log(`✅ Added ${shape} to inventory immediately. Current inventory:`, gameState.value.participant.shapes_acquired)
    
    // Mark this shape as recently added to prevent backend overwrites
    const shapeKey = `${shape}_${Date.now()}`
    recentlyAddedShapes.value.add(shapeKey)
    console.log(`🔒 Protected shape from backend overwrite: ${shapeKey}`)
    
    // Force a reactive update immediately for instant feedback
    // Use immediate reactive update for fastest possible UI feedback
    gameState.value.participant.shapes_acquired = [...gameState.value.participant.shapes_acquired]
    console.log(`✅ Production reactive update completed. Final inventory:`, gameState.value.participant.shapes_acquired)
    
    // Remove protection after a short delay to allow normal backend sync
    setTimeout(() => {
      recentlyAddedShapes.value.delete(shapeKey)
      console.log(`🔓 Removed protection for shape: ${shapeKey}`)
    }, 3000) // Protect for 3 seconds to prevent glitches
  }
}

// Add shape to inventory when trade completes (for buyer)
const addShapeToInventoryFromTrade = (shape: string, quantity: number = 1) => {
  console.log(`=== ADDING SHAPES FROM TRADE ===`)
  console.log(`Shape: ${shape}, Quantity: ${quantity}`)
  console.log(`Current inventory before:`, gameState.value.participant?.shapes_acquired)
  
  if (gameState.value.participant) {
    if (!gameState.value.participant.shapes_acquired) {
      gameState.value.participant.shapes_acquired = []
    }
    // Add the specified quantity of shapes
    for (let i = 0; i < quantity; i++) {
      gameState.value.participant.shapes_acquired.push(shape)
      console.log(`Added shape ${i + 1}/${quantity}: ${shape}`)
    }
    console.log(`Final inventory after trade:`, gameState.value.participant.shapes_acquired)
    
    // Force a reactive update immediately for instant UI feedback
    nextTick(() => {
      // Force Vue to detect the inventory change
      gameState.value.participant!.shapes_acquired = [...gameState.value.participant!.shapes_acquired]
      console.log(`Reactive update completed. Final inventory:`, gameState.value.participant!.shapes_acquired)
    })
  }
}

// Remove shape from inventory when trade completes (for seller)
const removeShapeFromInventoryFromTrade = (shape: string, quantity: number = 1) => {
  if (gameState.value.participant && gameState.value.participant.shapes_acquired) {
    const inventory = gameState.value.participant.shapes_acquired
    let removedCount = 0
    
    // Remove the specified quantity of shapes
    for (let i = 0; i < quantity && removedCount < quantity; i++) {
      const index = inventory.indexOf(shape)
      if (index !== -1) {
        inventory.splice(index, 1)
        removedCount++
      }
    }
    
    console.log(`Removed ${removedCount}x ${shape} from inventory from trade. Current inventory:`, inventory)
    
    // Force a reactive update immediately for instant UI feedback
    nextTick(() => {
      // Force Vue to detect the inventory change
      gameState.value.participant!.shapes_acquired = [...inventory]
    })
  }
}


// Function to process completed productions on the backend
const processCompletedProductions = async () => {
  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    console.error('No auth token available')
    return
  }

  try {
    console.log('🏭 Processing completed productions on backend...')
    const response = await fetch('/api/process-completed-productions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      }
    })

    if (response.ok) {
      const result = await response.json()
      if (result.success && result.processed_count > 0) {
        console.log(`✅ Processed ${result.processed_count} completed production items on backend`)
        // Don't refresh game state here since the timer already handled the UI updates
        // This prevents duplicate completion messages
        // The backend processing is just to ensure server state is updated
        
        // After backend processing, we can allow normal inventory sync again
        // The protection will be removed automatically after 3 seconds
        console.log(`🔄 Backend processing complete - inventory protection will expire soon`)
      } else {
        console.log('ℹ️ No completed productions to process on backend')
      }
    } else if (response.status === 401) {
      sessionStorage.clear()
      router.push('/login')
    } else {
      console.error('Failed to process completed productions:', response.status)
    }
  } catch (error) {
    console.error('Error processing completed productions:', error)
  }
}

const cancelTradeOffer = async (offerId: string) => {
  console.log('=== CANCELLING TRADE OFFER ===')
  console.log('Offer ID:', offerId)
  
  if (!isSessionActive.value) {
    alert('Session is not active. Please wait for the researcher to start the session.')
    return
  }

  const authToken = sessionStorage.getItem('auth_token')
  if (!authToken) {
    router.push('/login')
    return
  }

  try {
    // Find the offer to get its details for immediate UI update
    const offer = pendingOffers.value.find((o: TradeOffer) => o.id === offerId)
    if (!offer) {
      console.error('Offer not found for immediate update:', offerId)
    } else {
      console.log('Found offer for immediate update:', offer)
    }

    console.log('Sending API request to cancel trade offer...')
    const apiResponse = await fetch('/api/cancel-trade-offer', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        transaction_id: offerId
      })
    })

    console.log('API response status:', apiResponse.status)
    
    if (apiResponse.ok) {
      const result = await apiResponse.json()
      console.log('API response result:', result)
      
      // Check if the API call was actually successful
      if (result.success === false) {
        console.error('API returned success: false:', result.error)
        alert(`Error: ${result.error}`)
        return
      }
      
      // Remove from pending offers immediately for instant UI feedback
      if (offer) {
        const offerIndex = pendingOffers.value.findIndex((o: TradeOffer) => o.id === offerId)
        if (offerIndex !== -1) {
          console.log('Removing offer from pending offers at index:', offerIndex)
          pendingOffers.value.splice(offerIndex, 1)
        }
        console.log('Updated pending offers count:', pendingOffers.value.length)
        
        // Don't add to trade history immediately - let the backend API response handle it
        // This prevents the flicker between 'cancelled' (red) and the backend response
      }
      
      alert('Trade offer cancelled!')
      
      // Refresh trade data and game state with a single delayed call
      // This prevents race conditions from multiple rapid API calls
      setTimeout(() => {
        console.log('Refreshing trade data and game state after backend processing...')
        loadAllTradeData()
        if (isAuthenticated()) {
          loadGameStateIncremental()
        }
      }, 500) // Wait 500ms for backend processing to complete
      
    } else if (apiResponse.status === 401) {
      sessionStorage.clear()
      router.push('/login')
    } else {
      // Log the error response
      const errorText = await apiResponse.text()
      console.error('API Error Response:', errorText)
      try {
        const errorData = JSON.parse(errorText)
        const errorMessage = errorData.error || errorData.message || 'Unknown error occurred'
        console.error('Parsed API error:', errorMessage)
        alert(`Error: ${errorMessage}`)
      } catch (e) {
        console.error('Could not parse error response as JSON')
        alert(`Error: ${errorText}`)
      }
    }
  } catch (error) {
    console.error('Error cancelling trade offer:', error)
    alert('Network error. Please try again.')
  }
}

// ECL-specific methods
const loadECLConfig = async () => {
  try {
    const authToken = sessionStorage.getItem('auth_token')
    const response = await fetch(`${BACKEND_URL}/api/experiment/config?session_code=${sessionId.value}`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    })
    const result = await response.json()
    
    if (result.success && result.config.experiment_type === 'custom_ecl') {
      // Load the full ECL configuration from the top level of the config
      eclConfig.value = {
        // Include metadata from ecl_config section
        ...(result.config.ecl_config || {}),
        // Include the actual ECL configuration data
        views: result.config.views || {},
        types: result.config.types || {},
        objects: result.config.objects || {},
        variables: result.config.variables || {},
        actions: result.config.actions || {},
        constraints: result.config.constraints || [],
        policies: result.config.policies || []
      }
      console.log('🔧 ECL Config loaded:', eclConfig.value)
      
      // Configure interface after ECL config is loaded
      await configureInterface()
    }
  } catch (error) {
    console.error('Failed to load ECL config:', error)
  }
}

const loadECLState = async () => {
  try {
    const authToken = sessionStorage.getItem('auth_token')
    const response = await fetch(`${BACKEND_URL}/api/experiment/ecl/state?session_code=${sessionId.value}&participant_code=${participantId.value}`, {
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    })
    const result = await response.json()
    
    if (result.success) {
      eclState.value = result.state
      // Initialize local state with default values
      eclLocalState.value = {
        action_kind: 'invest',
        invest_type: 'individual',
        amount: 0
      }
    }
  } catch (error) {
    console.error('Failed to load ECL state:', error)
  }
}

const getECLValue = (path) => {
  if (!path || !eclState.value) return 'N/A'
  
  // Simple path resolution for now
  const parts = path.split('.')
  let value = eclState.value
  
  for (const part of parts) {
    if (value && typeof value === 'object') {
      value = value[part]
    } else {
      return 'N/A'
    }
  }
  
  return value || 'N/A'
}

const executeECLAction = async (actionName, inputs) => {
  if (!isSessionActive.value) return
  
  try {
    // Prepare action inputs from local state
    const actionInputs = {}
    for (const input of inputs) {
      const value = eclLocalState.value[input.from.replace('$local.', '')]
      actionInputs[input.name] = value
    }
    
    const authToken = sessionStorage.getItem('auth_token')
    const response = await fetch(`${BACKEND_URL}/api/experiment/ecl/action`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        session_code: sessionId.value,
        participant_code: participantId.value,
        action: actionName,
        inputs: actionInputs
      })
    })
    
    const result = await response.json()
    
    if (result.success) {
      // Reload state after action
      await loadECLState()
      alert('Action executed successfully!')
    } else {
      alert('Action failed: ' + (result.error || 'Unknown error'))
    }
  } catch (error) {
    console.error('Action execution error:', error)
    alert('Action error: ' + error.message)
  }
}

// ECL uses existing message functionality - no separate ECL message method needed

const formatMessageTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString()
}

</script>

<style scoped>
/* All styles are now in the unified-styles.css file */


/* Session Status Indicator */
.session-status-indicator {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.session-status-indicator.idle {
  background-color: #f8f9fa;
  color: #6c757d;
  border: 1px solid #dee2e6;
}

.session-status-indicator.running {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.session-status-indicator.paused {
  background-color: #fff3cd;
  color: #856404;
  border: 1px solid #ffeaa7;
}

.session-status-indicator.completed {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.session-status-indicator.stopped {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.session-status-indicator.ended {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.status-text {
  font-size: 11px;
}

.session-warning {
  background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%);
  color: white;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  margin-top: 8px;
  text-align: center;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.7; }
  100% { opacity: 1; }
}

/* Session Overlay */
.session-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

/* Session Overlay Transitions */
.session-overlay-enter-active,
.session-overlay-leave-active {
  transition: all 0.3s ease;
}

.session-overlay-enter-from {
  opacity: 0;
  backdrop-filter: blur(0px);
}

.session-overlay-leave-to {
  opacity: 0;
  backdrop-filter: blur(0px);
}

.session-overlay-enter-to,
.session-overlay-leave-from {
  opacity: 1;
  backdrop-filter: blur(2px);
}

.session-overlay-content {
  background: white;
  padding: 40px;
  border-radius: 12px;
  text-align: center;
  max-width: 400px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}

.session-overlay-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.session-overlay-content h3 {
  margin: 0 0 12px 0;
  color: #333;
  font-size: 20px;
  font-weight: 600;
}

.session-overlay-content p {
  margin: 0 0 8px 0;
  color: #666;
  font-size: 14px;
  line-height: 1.5;
}

.session-overlay-content p:last-child {
  margin-bottom: 0;
}

/* Session Overlay Actions */
.session-overlay-actions {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #e9ecef;
}

.return-to-login-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.return-to-login-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
  background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%);
}

.return-to-login-btn:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

/* Disabled content styling */
.disabled-content {
  opacity: 0.7;
  pointer-events: none;
}

.disabled-content .panel {
  filter: grayscale(0.3);
}

/* Content Disabled Transitions */
.content-disabled-enter-active,
.content-disabled-leave-active {
  transition: all 0.3s ease;
}

.content-disabled-enter-from,
.content-disabled-leave-to {
  opacity: 0.7;
  filter: grayscale(0.3);
}

.content-disabled-enter-to,
.content-disabled-leave-from {
  opacity: 1;
  filter: grayscale(0);
}

/* Disabled state styles */
.production-dropdown:disabled,
.trade-input:disabled,
.message-input:disabled,
.order-checkbox:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  background-color: #f8f9fa;
}

.order-btn:disabled,
.propose-btn:disabled,
.send-btn:disabled,
.accept-btn:disabled,
.decline-btn:disabled,
.cancel-btn:disabled,
.btn.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  background-color: #6c757d !important;
  color: #fff !important;
}

.order-btn:disabled:hover,
.propose-btn:disabled:hover,
.send-btn:disabled:hover,
.accept-btn:disabled:hover,
.decline-btn:disabled:hover,
.cancel-btn:disabled:hover,
.btn.primary:disabled:hover {
  background-color: #6c757d !important;
  transform: none !important;
}

/* Main content layout - two columns with optional third column */
.main-content {
  display: flex;
  gap: 16px;
  height: calc(100vh - 80px); /* Adjust for header */
  padding: 0px 16px 16px 0; /* Remove left padding to connect with header */
}

/* Left column - Status + Factory + Orders (2-sub-column layout) */
.column-left {
  display: flex;
  flex-direction: row;
  gap: 16px;
  width: 30%; /* Back to 50% width */
  height: 100%; /* Ensure full height */
}

/* Left sub-column - Status + Factory */
.left-sub-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

/* Right sub-column - Orders (Taller) */
.right-sub-column {
  width: 40%;
  height: 100%; /* Full height for the sub-column */
}

/* Make the Orders panel taller */
.tall-panel {
  height: 100%; /* Full height */
  display: flex;
  flex-direction: column;
}

.tall-panel .panel-body {
  flex: 1; /* Take remaining space */
  display: flex;
  flex-direction: column;
}

.tall-panel .orders-grid {
  flex: 1; /* Take remaining space */
  display: flex;
  flex-direction: column;
}

.tall-panel .orders-list {
  flex: 1; /* Take remaining space */
  overflow-y: auto; /* Allow scrolling if needed */
}

/* Right column - Social interface */
.column-right {
  width: 60%; 
}

/* Production queue styling */
.queue-item.completed {
  opacity: 0.6;
  background-color: #f0f0f0;
  border-left: 4px solid #28a745;
}

.queue-item.completed span {
  color: #666;
}

/* Awareness dashboard column - only when enabled */
.column-awareness {
  width: 30%; /* Additional column for awareness dashboard */
}

/* Broadcast mode specific styles */
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

.broadcast-message {
  background: #f8f9fa;
  border-left: 4px solid #667eea;
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 0 6px 6px 0;
}

/* Override broadcast message styling for current user */
.broadcast-message.my-message {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-left: 4px solid #667eea;
  margin-left: 20px;
  margin-right: 0;
  box-shadow: 0 2px 6px rgba(102, 126, 234, 0.3);
  align-self: flex-end;
  max-width: 80%;
}

.broadcast-message.my-message .message-sender {
  color: rgba(255, 255, 255, 0.9);
  font-weight: 600;
  font-size: 12px;
  margin-bottom: 4px;
}

.broadcast-message.my-message .message-content {
  color: white;
  font-size: 14px;
  line-height: 1.4;
}

.broadcast-message.my-message .message-time {
  color: rgba(255, 255, 255, 0.7);
  font-size: 11px;
  margin-top: 4px;
}

/* Override broadcast message styling for other participants */
.broadcast-message.other-message {
  background: #f8f9fa;
  color: #333;
  border-left: 4px solid #667eea;
  margin-right: 20px;
  margin-left: 0;
  align-self: flex-start;
  max-width: 80%;
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

/* Chat mode styles */
.chat-mode {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 8px;
}

/* Message input area for broadcast */
.message-input-area .send-btn {
  background: #667eea;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.3s;
}

.message-input-area .send-btn:hover {
  background: #5a6fd8;
}

/* Disabled state for no chat mode */
.no-chat-mode .interaction-tabs {
  opacity: 0.6;
}

.no-chat-mode .tab-btn[data-tab="message"] {
  display: none;
}

/* Awareness Dashboard Styles */
.awareness-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.awareness-panel .panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* Prevent panel body overflow */
  min-height: 0; /* Allow flex item to shrink */
}

.awareness-info {
  background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
  color: white;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 12px;
  flex-shrink: 0; /* Don't allow info section to shrink */
}

.awareness-info p {
  margin: 0;
  font-size: 12px;
  opacity: 0.9;
}

.participants-status-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto; /* Enable vertical scrolling */
  overflow-x: hidden; /* Hide horizontal overflow */
  flex: 1; /* Take remaining space */
  padding-right: 4px; /* Add some padding for scrollbar */
  min-height: 0; /* Allow flex item to shrink */
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

.participant-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #f0f0f0;
  gap: 12px;
}

.participant-name {
  font-weight: 600;
  font-size: 14px;
  color: #333;
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

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-label {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.stat-value {
  font-size: 12px;
  font-weight: 600;
}

.stat-value.money {
  color: #28a745;
}

.stat-value.orders {
  color: #007bff;
}

.completion-percentage {
  font-size: 10px;
  color: #666;
  font-weight: normal;
}

.progress-container {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
  width: 100%
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: #f0f0f0;
  border-radius: 3px;
  overflow: hidden;
  min-width: 100px;
  width: 100px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4CAF50 0%, #45a049 100%);
  transition: width 0.3s ease;
  border-radius: 3px;
}

/* Order fulfillment popup styles */
.order-fulfillment-form {
  text-align: center;
}

.order-fulfillment-form p {
  margin-bottom: 16px;
  font-size: 16px;
  color: #333;
}

.order-details {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 16px;
}

.shape-display {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: #333;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #dee2e6;
}

/* Trade history styles */
.history-item {
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 6px;
  background-color: #f8f9fa;
  border-left: 4px solid #28a745;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  line-height: 1.4;
}

.history-item:last-child {
  margin-bottom: 0;
}

/* Successful trade styling */
.history-item:not(.declined-trade) .trade-status {
  background-color: #d4edda;
  color: #155724;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
}

/* Declined trade styling */
.declined-trade {
  opacity: 0.7;
  background-color: #f8f9fa;
  border-left: 4px solid #dc3545;
}

.declined-trade .trade-status.declined {
  background-color: #f8d7da !important;
  color: #721c24 !important;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
}

.declined-trade .trade-status.cancelled {
  background-color: #f8d7da !important;
  color: #721c24 !important;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
}

.trade-history-list {
  overflow-y: auto;
  padding-right: 4px;
}


/* Trade history section styling */
.trade-history-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  max-height: 350px;
}

.trade-history-section h4 {
  margin-bottom: 8px;
  flex-shrink: 0;
}

.trade-history-section .trade-history-list {
  flex: 1;
  max-height: 300px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

/* Trade tab content layout */
.trade-tab-content {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.trade-tab-content .propose-trade {
  flex-shrink: 0;
}

.trade-tab-content .trade-section:not(.trade-history-section) {
  flex-shrink: 0;
}

.original-offer-actions {
  display: flex;
  gap: 8px;
}

/* Auto-start popup styles */
.auto-start-overlay {
  z-index: 2000; /* Higher than other modals */
}

.auto-start-modal {
  max-width: 400px;
  text-align: center;
}

.auto-start-content {
  padding: 20px 0;
}

.countdown-display {
  margin-bottom: 20px;
}

.countdown-number {
  font-size: 48px;
  font-weight: bold;
  color: #667eea;
  margin-bottom: 8px;
}

.countdown-label {
  font-size: 16px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.auto-start-message {
  font-size: 18px;
  color: #333;
  margin-bottom: 20px;
  font-weight: 500;
}

.auto-start-progress {
  margin-top: 20px;
  width: 100%;
  display: flex;
  justify-content: center;
}

.auto-start-progress .progress-bar {
  width: 100%;
  max-width: 300px;
  height: 12px;
  background: #f0f0f0;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
}

.auto-start-progress .progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  transition: width 0.3s ease;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

/* DayTrader-specific styles */
.daytrader-action {
  margin-bottom: 20px;
}

.trade-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.trade-sentence {
  background: #f8fafc;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.sentence-builder {
  margin: 0;
  font-size: 14px;
  color: #374151;
  line-height: 1.6;
}

.inline-select, .inline-input {
  padding: 4px 8px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 14px;
  background: white;
  margin: 0 4px;
}

.inline-input {
  width: 60px;
  text-align: center;
}

.propose-btn {
  padding: 10px 20px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.propose-btn:hover:not(:disabled) {
  background: #2563eb;
}

.propose-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

/* Task Instruction Styles */
.task-instructions {
  padding: 16px;
}

.instruction-content h4 {
  margin: 0 0 12px 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
}

.instruction-content p {
  margin: 0;
  color: #666;
  line-height: 1.5;
  font-size: 14px;
}

.default-task {
  padding: 16px;
}

.task-content p {
  margin: 0;
  color: #666;
  font-style: italic;
  text-align: center;
}


/* Essay Viewer Modal Styles */
.essay-viewer-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.essay-viewer-content {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
  animation: modalSlideIn 0.3s ease-out;
}

@keyframes modalSlideIn {
  from {
    opacity: 0;
    transform: scale(0.9) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.essay-viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: white;
}

.essay-viewer-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.close-essay-btn {
  background: none;
  border: none;
  color: white;
  font-size: 24px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s ease;
}

.close-essay-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.essay-viewer-body {
  padding: 24px;
  max-height: calc(90vh - 80px);
  overflow-y: auto;
}

.essay-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.essay-info {
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
  border-left: 4px solid #3b82f6;
}

.essay-info p {
  margin: 0 0 8px 0;
  font-size: 14px;
}

.essay-info p:last-child {
  margin-bottom: 0;
}


.essay-actions {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.download-essay-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
}

.download-essay-btn:hover {
  background: linear-gradient(135deg, #2563eb, #1e40af);
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(59, 130, 246, 0.4);
}

.download-essay-btn:active {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
}

.download-essay-btn i {
  font-size: 16px;
}

/* Current Rankings Display Styles */
.current-rankings-section {
  margin-top: 20px;
}

/* Make ranking items wider and more spacious */
.current-rankings-section .component-list-item {
  padding: 12px 16px;
  font-size: 14px;
}

.essay-title {
  display: block;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

</style>