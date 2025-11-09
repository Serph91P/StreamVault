<template>
  <div class="welcome-view">
    <div class="welcome-container">
      <!-- Hero Section -->
      <div class="hero-section">
        <div class="hero-icon-wrapper">
          <svg class="hero-icon">
            <use href="#icon-video" />
          </svg>
          <div class="hero-icon-glow"></div>
        </div>
        <h1 class="hero-title">Welcome to StreamVault!</h1>
        <p class="hero-subtitle">
          Your automated Twitch stream recording and management system
        </p>
      </div>

      <!-- Features Grid -->
      <div class="features-section">
        <h2 class="section-title">Getting Started</h2>
        <p class="section-description">Follow these steps to set up your stream recording system</p>

        <div class="features-grid">
          <!-- Step 1 -->
          <GlassCard class="feature-card" :hover="true">
            <div class="feature-number">1</div>
            <div class="feature-icon-wrapper">
              <svg class="feature-icon">
                <use href="#icon-settings" />
              </svg>
            </div>
            <h3 class="feature-title">Configure Settings</h3>
            <p class="feature-description">
              Set up your recording quality, storage preferences, and notification settings
            </p>
            <router-link to="/settings" class="feature-link" v-ripple>
              <span>Go to Settings</span>
              <svg class="link-icon">
                <use href="#icon-arrow-right" />
              </svg>
            </router-link>
          </GlassCard>

          <!-- Step 2 -->
          <GlassCard class="feature-card" :hover="true">
            <div class="feature-number">2</div>
            <div class="feature-icon-wrapper">
              <svg class="feature-icon">
                <use href="#icon-bell" />
              </svg>
            </div>
            <h3 class="feature-title">Enable Notifications</h3>
            <p class="feature-description">
              Get alerted when your favorite streamers go live or when recordings complete
            </p>
            <router-link to="/settings" class="feature-link" v-ripple>
              <span>Configure Notifications</span>
              <svg class="link-icon">
                <use href="#icon-arrow-right" />
              </svg>
            </router-link>
          </GlassCard>

          <!-- Step 3 -->
          <GlassCard class="feature-card" :hover="true">
            <div class="feature-number">3</div>
            <div class="feature-icon-wrapper">
              <svg class="feature-icon">
                <use href="#icon-users" />
              </svg>
            </div>
            <h3 class="feature-title">Add Streamers</h3>
            <p class="feature-description">
              Add your favorite Twitch streamers to start tracking and recording their content
            </p>
            <router-link to="/streamers" class="feature-link" v-ripple>
              <span>Manage Streamers</span>
              <svg class="link-icon">
                <use href="#icon-arrow-right" />
              </svg>
            </router-link>
          </GlassCard>
        </div>
      </div>

      <!-- Info Banner -->
      <GlassCard class="info-banner">
        <svg class="info-icon">
          <use href="#icon-info" />
        </svg>
        <div class="info-content">
          <h3 class="info-title">You're all set!</h3>
          <p class="info-description">
            You can change these settings anytime from the Settings page. StreamVault will automatically
            monitor your streamers and record their content based on your preferences.
          </p>
        </div>
      </GlassCard>

      <!-- Action Button -->
      <div class="action-section">
        <button @click="continueToHome" class="btn-continue" v-ripple>
          <span>Continue to Dashboard</span>
          <svg class="btn-icon">
            <use href="#icon-arrow-right" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Background Decoration -->
    <div class="background-decoration">
      <div class="decoration-grid"></div>
      <div class="decoration-glow decoration-glow-1"></div>
      <div class="decoration-glow decoration-glow-2"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import GlassCard from '@/components/cards/GlassCard.vue'

const router = useRouter()

function continueToHome() {
  localStorage.setItem('welcome_seen', '1')
  router.replace('/home')
}
</script>

<style scoped lang="scss">
.welcome-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-8) var(--spacing-4);
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, var(--background-primary) 0%, var(--background-secondary) 100%);
}

.welcome-container {
  width: 100%;
  max-width: 1200px;
  position: relative;
  z-index: 2;
  animation: fadeInUp 0.8s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

// Hero Section
.hero-section {
  text-align: center;
  margin-bottom: var(--spacing-16);
  animation: fadeIn 0.8s ease-out 0.2s both;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.hero-icon-wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 120px;
  height: 120px;
  margin-bottom: var(--spacing-6);
}

.hero-icon {
  width: 80px;
  height: 80px;
  fill: var(--color-primary);
  position: relative;
  z-index: 2;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-15px);
  }
}

.hero-icon-glow {
  position: absolute;
  inset: 0;
  background: var(--gradient-primary);
  border-radius: 50%;
  opacity: 0.2;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.2;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.3;
  }
}

.hero-title {
  font-size: var(--font-size-4xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-4);
  letter-spacing: -0.02em;
}

.hero-subtitle {
  font-size: var(--font-size-lg);
  color: var(--text-secondary);
  max-width: 600px;
  margin: 0 auto;
  line-height: 1.6;
}

// Features Section
.features-section {
  margin-bottom: var(--spacing-12);
}

.section-title {
  text-align: center;
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-3);
}

.section-description {
  text-align: center;
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-8);
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--spacing-6);
}

.feature-card {
  padding: var(--spacing-8);
  position: relative;
  overflow: visible;
  animation: scaleIn 0.6s ease-out both;

  &:nth-child(1) { animation-delay: 0.3s; }
  &:nth-child(2) { animation-delay: 0.4s; }
  &:nth-child(3) { animation-delay: 0.5s; }
}

@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.feature-number {
  position: absolute;
  top: var(--spacing-4);
  right: var(--spacing-4);
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gradient-primary);
  color: white;
  border-radius: 50%;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-bold);
  box-shadow: var(--shadow-md);
}

.feature-icon-wrapper {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.1) 0%, rgba(var(--color-accent-rgb), 0.1) 100%);
  border-radius: var(--radius-xl);
  margin-bottom: var(--spacing-4);
}

.feature-icon {
  width: 32px;
  height: 32px;
  fill: var(--color-primary);
}

.feature-title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-3);
}

.feature-description {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: var(--spacing-6);
}

.feature-link {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-5);
  background: var(--background-secondary);
  color: var(--color-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  text-decoration: none;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;

  &:hover {
    border-color: var(--color-primary);
    background: rgba(var(--color-primary-rgb), 0.05);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }
}

.link-icon {
  width: 16px;
  height: 16px;
  fill: currentColor;
  transition: transform 0.2s ease;

  .feature-link:hover & {
    transform: translateX(4px);
  }
}

// Info Banner
.info-banner {
  display: flex;
  gap: var(--spacing-4);
  padding: var(--spacing-6);
  margin-bottom: var(--spacing-8);
  animation: fadeIn 0.6s ease-out 0.6s both;
}

.info-icon {
  width: 24px;
  height: 24px;
  fill: var(--color-primary);
  flex-shrink: 0;
  margin-top: 2px;
}

.info-content {
  flex: 1;
}

.info-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-2);
}

.info-description {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}

// Action Section
.action-section {
  text-align: center;
  animation: fadeIn 0.6s ease-out 0.7s both;
}

.btn-continue {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-4) var(--spacing-8);
  background: var(--gradient-primary);
  color: white;
  border: none;
  border-radius: var(--radius-xl);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-lg);

  &:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 30px rgba(var(--color-primary-rgb), 0.3);
  }

  &:active {
    transform: translateY(-1px);
  }
}

.btn-icon {
  width: 20px;
  height: 20px;
  fill: currentColor;
  transition: transform 0.3s ease;

  .btn-continue:hover & {
    transform: translateX(4px);
  }
}

// Background Decoration
.background-decoration {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  overflow: hidden;
}

.decoration-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(var(--color-primary-rgb), 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--color-primary-rgb), 0.03) 1px, transparent 1px);
  background-size: 50px 50px;
  animation: gridMove 20s linear infinite;
}

@keyframes gridMove {
  from {
    transform: translate(0, 0);
  }
  to {
    transform: translate(50px, 50px);
  }
}

.decoration-glow {
  position: absolute;
  border-radius: 50%;
  background: var(--gradient-primary);
  filter: blur(80px);
  opacity: 0.1;
  animation: glowFloat 15s ease-in-out infinite;
}

.decoration-glow-1 {
  width: 400px;
  height: 400px;
  top: -200px;
  right: -100px;
  animation-delay: 0s;
}

.decoration-glow-2 {
  width: 300px;
  height: 300px;
  bottom: -150px;
  left: -75px;
  animation-delay: -7s;
}

@keyframes glowFloat {
  0%, 100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(50px, 30px);
  }
}

// Responsive
@media (max-width: 768px) {
  .welcome-view {
    padding: var(--spacing-6) var(--spacing-4);
  }

  .hero-title {
    font-size: var(--font-size-3xl);
  }

  .hero-subtitle {
    font-size: var(--font-size-base);
  }

  .hero-icon-wrapper {
    width: 96px;
    height: 96px;
  }

  .hero-icon {
    width: 64px;
    height: 64px;
  }

  .features-grid {
    grid-template-columns: 1fr;
    gap: var(--spacing-4);
  }

  .feature-card {
    padding: var(--spacing-6);
  }

  .section-title {
    font-size: var(--font-size-xl);
  }

  .btn-continue {
    width: 100%;
    justify-content: center;
  }

  .info-banner {
    flex-direction: column;
    text-align: center;
  }
}
</style>
