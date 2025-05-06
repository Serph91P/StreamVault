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

<style scoped>
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
  color: #ffffff;
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
  width: 18px;
  height: 18px;
  font-size: 12px;
}

.large .tooltip-icon {
  width: 24px;
  height: 24px;
  font-size: 14px;
}

.tooltip-content {
  position: absolute;
  visibility: hidden;
  background-color: #2f2f2f;
  color: white;
  text-align: center;
  padding: 8px 12px;
  border-radius: 4px;
  width: max-content;
  max-width: 250px;
  opacity: 0;
  transition: opacity 0.2s, visibility 0.2s;
  z-index: 1000;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  font-size: 0.85rem;
}

.tooltip-container:hover .tooltip-content,
.tooltip-container:focus-within .tooltip-content {
  visibility: visible;
  opacity: 1;
}

/* Persistent tooltip will stay visible when hovering on tooltip content */
.tooltip-content.persistent:hover {
  visibility: visible;
  opacity: 1;
}

/* Position variations */
.tooltip-content.top {
  bottom: 125%;
  left: 50%;
  transform: translateX(-50%);
}

.tooltip-content.top::after {
  content: "";
  position: absolute;
  top: 100%;
  left: 50%;
  margin-left: -5px;
  border-width: 5px;
  border-style: solid;
  border-color: #2f2f2f transparent transparent transparent;
}

.tooltip-content.bottom {
  top: 125%;
  left: 50%;
  transform: translateX(-50%);
}

.tooltip-content.bottom::after {
  content: "";
  position: absolute;
  bottom: 100%;
  left: 50%;
  margin-left: -5px;
  border-width: 5px;
  border-style: solid;
  border-color: transparent transparent #2f2f2f transparent;
}

.tooltip-content.left {
  right: 125%;
  top: 50%;
  transform: translateY(-50%);
}

.tooltip-content.left::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 100%;
  margin-top: -5px;
  border-width: 5px;
  border-style: solid;
  border-color: transparent transparent transparent #2f2f2f;
}

.tooltip-content.right {
  left: 125%;
  top: 50%;
  transform: translateY(-50%);
}

.tooltip-content.right::after {
  content: "";
  position: absolute;
  top: 50%;
  right: 100%;
  margin-top: -5px;
  border-width: 5px;
  border-style: solid;
  border-color: transparent #2f2f2f transparent transparent;
}
</style>