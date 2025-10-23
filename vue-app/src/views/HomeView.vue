<script setup lang="ts">
// Simple home page with navigation to different interfaces
</script>

<template>
  <div class="home-container">
    <div class="hero-section">
      <h1>Shape Factory Research Platform</h1>
      <p class="subtitle">Advanced simulation environment for studying human-AI collaboration in economic tasks</p>
      
      <div class="interface-cards">
        <!-- Researcher Dashboard Card -->
        <div class="interface-card researcher-card">
          <div class="card-icon">📊</div>
          <h2>Researcher Dashboard</h2>
          <p>Monitor experiments, configure settings, and analyze real-time participant interactions</p>
          <ul class="feature-list">
            <li>Real-time participant monitoring</li>
            <li>Experiment configuration controls</li>
            <li>Live trading and communication feeds</li>
            <li>Data export capabilities</li>
          </ul>
          <router-link to="/researcher" class="interface-btn researcher-btn">
            Access Dashboard
          </router-link>
        </div>

        <!-- Participant Interface Card -->
        <div class="interface-card participant-card">
          <div class="card-icon">🎮</div>
          <h2>Participant Interface</h2>
          <p>Engage in shape trading, production, and communication with other participants</p>
          <ul class="feature-list">
            <li>Shape production and inventory management</li>
            <li>Real-time trading with other participants</li>
            <li>Order fulfillment system</li>
            <li>Interactive communication tools</li>
          </ul>
          <router-link to="/login" class="interface-btn participant-btn">
            Join as Participant
          </router-link>
        </div>
      </div>

      <div class="system-info">
        <h3>System Features</h3>
        <div class="features-grid">
          <div class="feature-item">
            <div class="feature-icon">🔄</div>
            <h4>Real-time Synchronization</h4>
            <p>WebSocket-powered live updates across all interfaces</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">🗄️</div>
            <h4>PostgreSQL Database</h4>
            <p>Robust data storage for comprehensive research analytics</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">🤖</div>
            <h4>AI Agent Integration</h4>
            <p>Mixed human-AI experiments with configurable agent behaviors</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">📈</div>
            <h4>Research Analytics</h4>
            <p>Advanced metrics and data export for academic research</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.hero-section {
  max-width: 1200px;
  width: 100%;
  text-align: center;
}

.hero-section h1 {
  color: white;
  font-size: 3rem;
  margin-bottom: 1rem;
  font-weight: 700;
}

.subtitle {
  color: rgba(255, 255, 255, 0.9);
  font-size: 1.2rem;
  margin-bottom: 3rem;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
}

.interface-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 2rem;
  margin-bottom: 3rem;
}

.interface-card {
  background: white;
  border-radius: 12px;
  padding: 2rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.interface-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3);
}

.card-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.interface-card h2 {
  color: #333;
  margin-bottom: 1rem;
  font-size: 1.5rem;
}

.interface-card p {
  color: #666;
  margin-bottom: 1.5rem;
  line-height: 1.6;
}

.feature-list {
  list-style: none;
  padding: 0;
  margin-bottom: 2rem;
  text-align: left;
}

.feature-list li {
  color: #555;
  margin-bottom: 0.5rem;
  padding-left: 1.5rem;
  position: relative;
}

.feature-list li::before {
  content: "✓";
  color: #28a745;
  font-weight: bold;
  position: absolute;
  left: 0;
}

.interface-btn {
  display: inline-block;
  padding: 12px 24px;
  border-radius: 8px;
  text-decoration: none;
  font-weight: 600;
  transition: background-color 0.3s ease;
  color: white;
}

.researcher-btn {
  background: #667eea;
}

.researcher-btn:hover {
  background: #5a67d8;
}

.participant-btn {
  background: #48bb78;
}

.participant-btn:hover {
  background: #38a169;
}

.system-info {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 2rem;
  backdrop-filter: blur(10px);
}

.system-info h3 {
  color: white;
  margin-bottom: 2rem;
  font-size: 1.8rem;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
}

.feature-item {
  text-align: center;
  padding: 1rem;
}

.feature-icon {
  font-size: 2rem;
  margin-bottom: 1rem;
}

.feature-item h4 {
  color: white;
  margin-bottom: 0.5rem;
  font-size: 1.1rem;
}

.feature-item p {
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.9rem;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .hero-section h1 {
    font-size: 2rem;
  }
  
  .interface-cards {
    grid-template-columns: 1fr;
    gap: 1.5rem;
  }
  
  .features-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }
}
</style>
