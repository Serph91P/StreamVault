<template>
  <div class="page-view add-streamer-view">
    <!-- Header -->
    <div class="view-header">
      <button @click="goBack" class="btn-back" v-ripple>
        <svg class="icon">
          <use href="#icon-arrow-left" />
        </svg>
        <span>Back</span>
      </button>

      <div class="header-content">
        <h1 class="page-title">
          <svg class="icon-title">
            <use href="#icon-user-plus" />
          </svg>
          Add New Streamer
        </h1>
        <p class="page-subtitle">
          Track your favorite Twitch streamers and get notified when they go live
        </p>
      </div>
    </div>

    <!-- Content in Single GlassCard -->
    <GlassCard class="content-card">
      <!-- Manual Add Section -->
      <div class="add-section">
        <div class="section-header">
          <div class="section-icon-wrapper">
            <svg class="section-icon">
              <use href="#icon-user-plus" />
            </svg>
          </div>
          <div class="section-info">
            <h2 class="section-title">Add by Username</h2>
            <p class="section-description">
              Enter a Twitch username to add a streamer manually
            </p>
          </div>
        </div>

        <AddStreamerForm @streamer-added="handleStreamerAdded" />
      </div>

      <!-- Divider -->
      <div class="divider">
        <span class="divider-text">OR</span>
      </div>

      <!-- Import Section -->
      <div class="import-section">
        <div class="section-header">
          <div class="section-icon-wrapper import">
            <svg class="section-icon">
              <use href="#icon-download" />
            </svg>
          </div>
          <div class="section-info">
            <h2 class="section-title">Import from Twitch</h2>
            <p class="section-description">
              Import streamers you already follow on your Twitch account
            </p>
          </div>
        </div>

        <TwitchImportForm @streamers-imported="handleStreamersImported" />
      </div>

      <!-- Info Banner -->
      <div class="info-banner">
        <svg class="info-icon">
          <use href="#icon-info" />
        </svg>
        <div class="info-content">
          <p>
            StreamVault will automatically check if these streamers are live and start recording based on your settings.
          </p>
        </div>
      </div>
    </GlassCard>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import AddStreamerForm from '@/components/AddStreamerForm.vue'
import TwitchImportForm from '@/components/TwitchImportForm.vue'
import GlassCard from '@/components/cards/GlassCard.vue'

const router = useRouter()

const goBack = () => {
  router.back()
}

const handleStreamerAdded = () => {
  router.push('/streamers')
}

const handleStreamersImported = () => {
  router.push('/streamers')
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.add-streamer-view {
  // .page-view provides padding/sizing via global styles
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

// Header
.view-header {
  margin-bottom: var(--spacing-8);
  max-width: 1200px;
  margin-left: auto;
  margin-right: auto;
}

.btn-back {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--background-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: var(--spacing-6);

  .icon {
    width: 16px;
    height: 16px;
    fill: currentColor;
  }

  &:hover {
    background: var(--background-tertiary);
    color: var(--text-primary);
    border-color: var(--color-primary);
  }
}

.header-content {
  text-align: center;
}

.page-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-3);
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-3);
}

.icon-title {
  width: 32px;
  height: 32px;
  fill: var(--color-primary);
}

.page-subtitle {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  max-width: 600px;
  margin: 0 auto;
  line-height: 1.6;
}

// Main Content Card
.content-card {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--spacing-8);
  animation: slideUp 0.4s ease-out;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

// Sections
.add-section,
.import-section {
  margin-bottom: var(--spacing-8);
}

.section-header {
  display: flex;
  gap: var(--spacing-4);
  margin-bottom: var(--spacing-6);
  padding-bottom: var(--spacing-4);
  border-bottom: 1px solid var(--border-color);
}

.section-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.1) 0%, rgba(var(--color-accent-rgb), 0.1) 100%);
  border-radius: var(--radius-xl);
  flex-shrink: 0;

  &.import {
    background: linear-gradient(135deg, rgba(var(--color-accent-rgb), 0.1) 0%, rgba(var(--color-primary-rgb), 0.1) 100%);
  }
}

.section-icon {
  width: 28px;
  height: 28px;
  fill: var(--color-primary);
}

.section-info {
  flex: 1;
}

.section-title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-2);
}

.section-description {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}

// Divider
.divider {
  position: relative;
  text-align: center;
  margin: var(--spacing-8) 0;

  &::before,
  &::after {
    content: '';
    position: absolute;
    top: 50%;
    width: calc(50% - 40px);
    height: 1px;
    background: var(--border-color);
  }

  &::before {
    left: 0;
  }

  &::after {
    right: 0;
  }
}

.divider-text {
  display: inline-block;
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--background-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}

// Info Banner
.info-banner {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-3);
  padding: var(--spacing-5);
  background: rgba(var(--color-primary-rgb), 0.05);
  border: 1px solid rgba(var(--color-primary-rgb), 0.2);
  border-radius: var(--radius-xl);
  margin-top: var(--spacing-8);
}

.info-icon {
  width: 20px;
  height: 20px;
  fill: var(--color-primary);
  flex-shrink: 0;
  margin-top: 2px;
}

.info-content {
  flex: 1;

  p {
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
    line-height: 1.6;
    margin: 0;
  }
}

// Responsive
@include m.respond-below('md') {  // < 768px
  .add-streamer-view {
    padding: var(--spacing-4);
  }

  .content-card {
    padding: var(--spacing-6);
  }

  .page-title {
    font-size: var(--font-size-2xl);
  }

  .icon-title {
    width: 24px;
    height: 24px;
  }

  .section-header {
    flex-direction: column;
    text-align: center;
  }

  .section-icon-wrapper {
    margin: 0 auto;
  }

  .divider {
    margin: var(--spacing-6) 0;

    &::before,
    &::after {
      width: calc(50% - 30px);
    }
  }
}
</style>
