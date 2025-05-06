<script setup lang="ts">
defineProps<{
  position?: 'top' | 'right' | 'bottom' | 'left'
}>()
</script>

<template>
  <div class="tooltip-container">
    <span class="tooltip-icon">?</span>
    <div class="tooltip-content" :class="position || 'top'">
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
  width: 18px;
  height: 18px;
  background-color: rgba(255, 255, 255, 0.15);
  color: #ffffff;
  border-radius: 50%;
  font-size: 12px;
  font-weight: bold;
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

.tooltip-container:hover .tooltip-content {
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