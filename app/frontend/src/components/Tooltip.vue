<script setup lang="ts">
defineProps<{
  position?: 'top' | 'right' | 'bottom' | 'left',
  icon?: string,
  size?: 'small' | 'medium' | 'large',
  delay?: number,
  persistent?: boolean,
  customClass?: string
}>()
</script>

<template>
  <div class="tooltip-container" :class="[size || 'medium', customClass]">
    <span class="tooltip-icon" role="button" tabindex="0" aria-label="Show tooltip information">
      {{ icon || '?' }}
    </span>
    <div class="tooltip-content" 
         :class="[position || 'top', {'persistent': persistent}]"
         :style="{'transition-delay': `${delay || 0}ms`}"
         role="tooltip">
      <slot></slot>
    </div>
  </div>
</template>

<style scoped lang="scss">
.tooltip-container {
  position: relative;
  display: inline-block;
  cursor: pointer;
}

.tooltip-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(255, 255, 255, 0.15);
  color: var(--text-on-primary);
  border-radius: 50%;
  font-size: 12px;
  font-weight: bold;
}

/* Size variations */
.small .tooltip-icon {
  width: 16px;
  height: 16px;
  font-size: 10px;
}

.medium .tooltip-icon {
  width: 20px;
  height: 20px;
  font-size: 12px;
}

.large .tooltip-icon {
  width: 24px;
  height: 24px;
  font-size: 14px;
}

.tooltip-content {
  position: absolute;
  background-color: rgba(31, 31, 35, 0.95);
  color: var(--text-primary);
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  z-index: 1000;
  width: max-content;
  max-width: 250px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.2s ease, visibility 0.2s ease;
  pointer-events: none;
  line-height: 1.5;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

/* Positioning */
.tooltip-content.top {
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-bottom: 8px;
}

.tooltip-content.right {
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-left: 8px;
}

.tooltip-content.bottom {
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-top: 8px;
}

.tooltip-content.left {
  right: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-right: 8px;
}

/* Show tooltip on hover/focus */
.tooltip-container:hover .tooltip-content,
.tooltip-container:focus-within .tooltip-content,
.tooltip-container .tooltip-content.persistent {
  opacity: 1;
  visibility: visible;
}

/* Tooltip arrow */
.tooltip-content::before {
  content: "";
  position: absolute;
  width: 0;
  height: 0;
  border: 6px solid transparent;
}

.tooltip-content.top::before {
  bottom: -12px;
  left: 50%;
  transform: translateX(-50%);
  border-top-color: rgba(31, 31, 35, 0.95);
}

.tooltip-content.right::before {
  left: -12px;
  top: 50%;
  transform: translateY(-50%);
  border-right-color: rgba(31, 31, 35, 0.95);
}

.tooltip-content.bottom::before {
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  border-bottom-color: rgba(31, 31, 35, 0.95);
}

.tooltip-content.left::before {
  right: -12px;
  top: 50%;
  transform: translateY(-50%);
  border-left-color: rgba(31, 31, 35, 0.95);
}
</style>
