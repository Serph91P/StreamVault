<template>
  <!-- SVG Icon Sprite (loaded inline for reliability) - Teleported to body for global access -->
  <Teleport to="body">
    <svg xmlns="http://www.w3.org/2000/svg" style="display: none;" aria-hidden="true" id="svg-sprite">
      <defs>
      <!-- Home Icon -->
      <symbol id="icon-home" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
        <polyline points="9 22 9 12 15 12 15 22"/>
      </symbol>
      
      <!-- Users Icon -->
      <symbol id="icon-users" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
        <circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
        <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      </symbol>
      
      <!-- Video Icon -->
      <symbol id="icon-video" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="23 7 16 12 23 17 23 7"/>
        <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
      </symbol>
      
      <!-- Radio Icon (Live) -->
      <symbol id="icon-radio" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="2"/>
        <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"/>
      </symbol>
      
      <!-- Settings Icon -->
      <symbol id="icon-settings" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </symbol>
      
      <!-- Chevron Left -->
      <symbol id="icon-chevron-left" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="15 18 9 12 15 6"/>
      </symbol>
      
      <!-- Chevron Right -->
      <symbol id="icon-chevron-right" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="9 18 15 12 9 6"/>
      </symbol>
      
      <!-- Bell Icon -->
      <symbol id="icon-bell" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
        <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      </symbol>
      
      <!-- Briefcase Icon -->
      <symbol id="icon-briefcase" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
        <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
      </symbol>
      
      <!-- Sun Icon -->
      <symbol id="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="5"/>
        <line x1="12" y1="1" x2="12" y2="3"/>
        <line x1="12" y1="21" x2="12" y2="23"/>
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
        <line x1="1" y1="12" x2="3" y2="12"/>
        <line x1="21" y1="12" x2="23" y2="12"/>
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
      </symbol>
      
      <!-- Moon Icon -->
      <symbol id="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </symbol>
      
      <!-- Circle Icon (Recording Indicator) -->
      <symbol id="icon-circle" viewBox="0 0 24 24" fill="currentColor">
        <circle cx="12" cy="12" r="10"/>
      </symbol>
      
      <!-- Film Icon (Videos) -->
      <symbol id="icon-film" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/>
        <line x1="7" y1="2" x2="7" y2="22"/>
        <line x1="17" y1="2" x2="17" y2="22"/>
        <line x1="2" y1="12" x2="22" y2="12"/>
        <line x1="2" y1="7" x2="7" y2="7"/>
        <line x1="2" y1="17" x2="7" y2="17"/>
        <line x1="17" y1="17" x2="22" y2="17"/>
        <line x1="17" y1="7" x2="22" y2="7"/>
      </symbol>
      
      <!-- Arrow Right -->
      <symbol id="icon-arrow-right" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="5" y1="12" x2="19" y2="12"/>
        <polyline points="12 5 19 12 12 19"/>
      </symbol>
      
      <!-- Arrow Left -->
      <symbol id="icon-arrow-left" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="19" y1="12" x2="5" y2="12"/>
        <polyline points="12 19 5 12 12 5"/>
      </symbol>
      
      <!-- User Plus (Add User) -->
      <symbol id="icon-user-plus" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
        <circle cx="8.5" cy="7" r="4"/>
        <line x1="20" y1="8" x2="20" y2="14"/>
        <line x1="23" y1="11" x2="17" y2="11"/>
      </symbol>
      
      <!-- Video Off -->
      <symbol id="icon-video-off" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2m5.66 0H14a2 2 0 0 1 2 2v3.34l1 1L23 7v10"/>
        <line x1="1" y1="1" x2="23" y2="23"/>
      </symbol>
      
      <!-- Plus -->
      <symbol id="icon-plus" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="12" y1="5" x2="12" y2="19"/>
        <line x1="5" y1="12" x2="19" y2="12"/>
      </symbol>
      
      <!-- Trash -->
      <symbol id="icon-trash" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="3 6 5 6 21 6"/>
        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
        <line x1="10" y1="11" x2="10" y2="17"/>
        <line x1="14" y1="11" x2="14" y2="17"/>
      </symbol>
      
      <!-- Refresh -->
      <symbol id="icon-refresh" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 4 23 10 17 10"/>
        <polyline points="1 20 1 14 7 14"/>
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
      </symbol>
      
      <!-- Edit -->
      <symbol id="icon-edit" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
      </symbol>
      
      <!-- Check -->
      <symbol id="icon-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12"/>
      </symbol>
      
      <!-- X (Close) -->
      <symbol id="icon-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
      </symbol>
      
      <!-- Download -->
      <symbol id="icon-download" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
      </symbol>
      
      <!-- Gamepad -->
      <symbol id="icon-gamepad" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="6" y1="12" x2="10" y2="12"/>
        <line x1="8" y1="10" x2="8" y2="14"/>
        <line x1="15" y1="13" x2="15.01" y2="13"/>
        <line x1="18" y1="11" x2="18.01" y2="11"/>
        <rect x="2" y="6" width="20" height="12" rx="2"/>
      </symbol>
      
      <!-- Menu (Hamburger) -->
      <symbol id="icon-menu" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="12" x2="21" y2="12"/>
        <line x1="3" y1="6" x2="21" y2="6"/>
        <line x1="3" y1="18" x2="21" y2="18"/>
      </symbol>
      
      <!-- Log Out -->
      <symbol id="icon-log-out" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
        <polyline points="16 17 21 12 16 7"/>
        <line x1="21" y1="12" x2="9" y2="12"/>
      </symbol>
      
      <!-- Clock -->
      <symbol id="icon-clock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12 6 12 12 16 14"/>
      </symbol>
      
      <!-- More Vertical (3 dots menu) -->
      <symbol id="icon-more-vertical" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="1"/>
        <circle cx="12" cy="5" r="1"/>
        <circle cx="12" cy="19" r="1"/>
      </symbol>
      
      <!-- Play -->
      <symbol id="icon-play" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="5 3 19 12 5 21 5 3"/>
      </symbol>
      
      <!-- Eye (View) -->
            <!-- Eye (View) -->
      <symbol id="icon-eye" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
      </symbol>
      
      <!-- User (Single User) -->
      <symbol id="icon-user" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
      </symbol>
      
      <!-- Lock (Password) -->
      <symbol id="icon-lock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
      </symbol>
      
      <!-- Info (Information) -->
      <symbol id="icon-info" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="16" x2="12" y2="12"/>
        <line x1="12" y1="8" x2="12.01" y2="8"/>
      </symbol>
      
      <!-- Refresh CW (Clockwise Circular Arrow) -->
      <symbol id="icon-refresh-cw" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 4 23 10 17 10"/>
        <polyline points="1 20 1 14 7 14"/>
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
      </symbol>
      
      <!-- Search (Magnifying Glass) -->
      <symbol id="icon-search" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/>
        <path d="m21 21-4.35-4.35"/>
      </symbol>
      
      <!-- Grid (Grid Layout) -->
      <symbol id="icon-grid" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="7" height="7"/>
        <rect x="14" y="3" width="7" height="7"/>
        <rect x="14" y="14" width="7" height="7"/>
        <rect x="3" y="14" width="7" height="7"/>
      </symbol>
      
      <!-- List (List Layout) -->
      <symbol id="icon-list" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="8" y1="6" x2="21" y2="6"/>
        <line x1="8" y1="12" x2="21" y2="12"/>
        <line x1="8" y1="18" x2="21" y2="18"/>
        <line x1="3" y1="6" x2="3.01" y2="6"/>
        <line x1="3" y1="12" x2="3.01" y2="12"/>
        <line x1="3" y1="18" x2="3.01" y2="18"/>
      </symbol>
      
      <!-- User (Single User) -->
      <symbol id="icon-user" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
      </symbol>
      
      <!-- Lock (Password/Security) -->
      <symbol id="icon-lock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
      </symbol>
      
      <!-- Alert Circle (Error/Warning) -->
      <symbol id="icon-alert-circle" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </symbol>
      
      <!-- Log In (Enter/Sign In) -->
      <symbol id="icon-log-in" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
        <polyline points="10 17 15 12 10 7"/>
        <line x1="15" y1="12" x2="3" y2="12"/>
      </symbol>
      
      <!-- Filter (Funnel) -->
      <symbol id="icon-filter" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
      </symbol>
      
      <!-- Check Circle (Success/Completed) -->
      <symbol id="icon-check-circle" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
        <polyline points="22 4 12 14.01 9 11.01"/>
      </symbol>
      
      <!-- Check Square (Select/Multi-Select) -->
      <symbol id="icon-check-square" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="9 11 12 14 22 4"/>
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
      </symbol>
      
      <!-- Server -->
      <symbol id="icon-server" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="2" width="20" height="8" rx="2" ry="2"/>
        <rect x="2" y="14" width="20" height="8" rx="2" ry="2"/>
        <line x1="6" y1="6" x2="6.01" y2="6"/>
        <line x1="6" y1="18" x2="6.01" y2="18"/>
      </symbol>
      
      <!-- Link (External Link/Connection) -->
      <symbol id="icon-link" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </symbol>
      
      <!-- Star (Favorite) -->
      <symbol id="icon-star" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
      </symbol>
      
      <!-- Smartphone (Mobile/Phone) -->
      <symbol id="icon-smartphone" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="5" y="2" width="14" height="20" rx="2" ry="2"/>
        <line x1="12" y1="18" x2="12.01" y2="18"/>
      </symbol>

      <!-- Key (API Keys) -->
      <symbol id="icon-key" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>
      </symbol>
      
      <!-- Repeat (Circular Arrows/Refresh All) -->
      <symbol id="icon-repeat" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="17 1 21 5 17 9"/>
        <path d="M3 11V9a4 4 0 0 1 4-4h14"/>
        <polyline points="7 23 3 19 7 15"/>
        <path d="M21 13v2a4 4 0 0 1-4 4H3"/>
      </symbol>
      
      <!-- Trash-2 (Delete with Lid) -->
      <symbol id="icon-trash-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="3 6 5 6 21 6"/>
        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
        <line x1="10" y1="11" x2="10" y2="17"/>
        <line x1="14" y1="11" x2="14" y2="17"/>
      </symbol>
      
      <!-- Alert Triangle (Warning) -->
      <symbol id="icon-alert-triangle" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/>
        <line x1="12" y1="17" x2="12.01" y2="17"/>
      </symbol>
      
      <!-- RSS (Subscriptions/Feed) -->
      <symbol id="icon-rss" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 11a9 9 0 0 1 9 9"/>
        <path d="M4 4a16 16 0 0 1 16 16"/>
        <circle cx="5" cy="19" r="1"/>
      </symbol>
    </defs>
    </svg>
  </Teleport>

  <div class="app">
    <!-- Show header and navigation ONLY on authenticated pages -->
    <template v-if="!isAuthPage">
      <!-- Unified Glass Header -->
      <header class="app-header glass-header">
        <div class="header-content">
          <span class="app-logo" aria-label="StreamVault">StreamVault</span>
          
          <div class="header-actions">
            <!-- Background Queue Monitor (indicator hidden on mobile, panel still works) -->
            <BackgroundQueueMonitor ref="queueMonitorRef" />
            
            <!-- Desktop: Show all buttons inline -->
            <button
              ref="notificationBellRef"
              @click.stop="toggleNotifications"
              class="glass-btn-icon desktop-only"
              :class="{ 'has-badge': unreadCount > 0 }"
              aria-label="Notifications"
            >
              <svg>
                <use href="#icon-bell" />
              </svg>
              <span v-if="unreadCount > 0" class="badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
            </button>
            
            <div class="desktop-only">
              <ThemeToggle />
            </div>
            
            <button @click="logout" class="glass-btn-danger header-logout-btn desktop-only">
              <svg><use href="#icon-log-out" /></svg>
              <span class="logout-text">Logout</span>
            </button>
            
            <!-- Mobile: Hamburger menu -->
            <button
              @click.stop="toggleMobileMenu"
              class="glass-btn-icon mobile-only"
              aria-label="Menu"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
          </div>
        </div>
      </header>
      
      <!-- Mobile Menu Dropdown -->
      <Teleport to="body">
        <Transition name="fade">
          <div v-if="showMobileMenu" class="mobile-menu-backdrop" @click="closeMobileMenu"></div>
        </Transition>
        <Transition name="slide-down">
          <div v-if="showMobileMenu" class="mobile-menu-panel" @click.stop>
            <button
              @click.stop="openJobsFromMenu"
              class="mobile-menu-item"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 5v14M5 12h14" />
              </svg>
              <span>Background Jobs</span>
              <span v-if="jobCount > 0" class="badge mobile-badge">{{ jobCount }}</span>
            </button>
            <button
              @click.stop="openNotificationsFromMenu"
              class="mobile-menu-item"
            >
              <svg><use href="#icon-bell" /></svg>
              <span>Notifications</span>
              <span v-if="unreadCount > 0" class="badge mobile-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
            </button>
            <div class="mobile-menu-item theme-menu-item">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
              <span>Theme</span>
              <ThemeToggle />
            </div>
            <button @click="logoutFromMenu" class="mobile-menu-item mobile-menu-danger">
              <svg><use href="#icon-log-out" /></svg>
              <span>Logout</span>
            </button>
          </div>
        </Transition>
      </Teleport>
    
      <!-- Notification Panel -->
      <Teleport to="body">
        <Transition name="fade">
          <div v-if="showNotifications" class="glass-popup-backdrop" @click="closeNotificationPanel"></div>
        </Transition>
        <Transition name="slide-up">
          <div v-if="showNotifications" ref="notificationPanelRef" class="glass-popup-panel notification-panel">
            <div class="glass-popup-header">
              <h3>Notifications</h3>
              <button class="glass-btn-icon" @click="closeNotificationPanel" aria-label="Close notifications">
                <svg><use href="#icon-x" /></svg>
              </button>
            </div>
            <NotificationFeed 
              @notifications-read="markAsRead" 
              @close-panel="closeNotificationPanel"
              @clear-all="clearAllNotifications"
              @close="closeNotificationPanel"
            />
          </div>
        </Transition>
      </Teleport>
    </template>
    
    <!-- Navigation Wrapper with Bottom Nav + Sidebar (only on authenticated pages) -->
    <NavigationWrapper v-if="!isAuthPage">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in" @before-enter="scrollToTop">
          <component :is="Component" />
        </transition>
      </router-view>
    </NavigationWrapper>
    
    <!-- Auth pages without navigation -->
    <router-view v-else v-slot="{ Component }">
      <transition name="page" mode="out-in" @before-enter="scrollToTop">
        <component :is="Component" />
      </transition>
    </router-view>
    
    <!-- Toast Notification System (CRITICAL: Always visible) -->
    <ToastContainer />
    
    <!-- PWA Install Prompt -->
    <PWAInstallPrompt />
  </div>
</template>

<script setup>
import NotificationFeed from '@/components/NotificationFeed.vue'
import PWAInstallPrompt from '@/components/PWAInstallPrompt.vue'
import BackgroundQueueMonitor from '@/components/BackgroundQueueMonitor.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import NavigationWrapper from '@/components/navigation/NavigationWrapper.vue'
import '@/styles/main.scss'
import { ref, onMounted, onUnmounted, watch, provide, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useWebSocket } from '@/composables/useWebSocket'
import { useAuth } from '@/composables/useAuth'
import { useSystemAndRecordingStatus } from '@/composables/useSystemAndRecordingStatus'
import { useTheme } from '@/composables/useTheme'
import { useToast } from '@/composables/useToast'
import { notificationApi } from '@/services/api'

// Initialize theme
const { initializeTheme } = useTheme()
initializeTheme()

// Initialize toast system (centralized - handles all toast notifications via useToast)
const toast = useToast()

// Check if current route is an auth page
const route = useRoute()

// Scroll to top on every route change (belt-and-suspenders with router.afterEach)
watch(() => route.fullPath, () => {
  document.documentElement.scrollTop = 0
  document.body.scrollTop = 0
})

const isAuthPage = computed(() => {
  const authPaths = ['/auth/login', '/auth/setup', '/welcome']
  return authPaths.includes(route.path)
})

// Refs for click-outside detection
const notificationBellRef = ref(null)
const notificationPanelRef = ref(null)

// Provide hybrid status globally
const hybridStatus = useSystemAndRecordingStatus()
provide('hybridStatus', hybridStatus)

// Initialize hybrid status system
onMounted(() => {
  // Start the hybrid status system
  hybridStatus.fetchAllStatus()
})

const showNotifications = ref(false)
const unreadCount = ref(0)
const lastReadTimestamp = ref(localStorage.getItem('lastReadTimestamp') || '0')

const { messages } = useWebSocket()
const { logout: authLogout, checkStoredAuth } = useAuth()

// PWA-compatible logout function
async function logout() {
  if (confirm('Are you sure you want to logout?')) {
    await authLogout()
  }
}

// Mobile hamburger menu
const showMobileMenu = ref(false)
const queueMonitorRef = ref(null)

const jobCount = computed(() => {
  return queueMonitorRef.value?.taskCount?.value?.length ?? 0
})

function toggleMobileMenu() {
  showMobileMenu.value = !showMobileMenu.value
}

function closeMobileMenu() {
  showMobileMenu.value = false
}

function openJobsFromMenu() {
  closeMobileMenu()
  queueMonitorRef.value?.togglePanel()
}

function openNotificationsFromMenu() {
  closeMobileMenu()
  toggleNotifications()
}

async function logoutFromMenu() {
  closeMobileMenu()
  await logout()
}

// Scroll to top on page transitions (for out-in mode)
function scrollToTop() {
  document.documentElement.scrollTop = 0
  document.body.scrollTop = 0
}

// Process toast notifications from WebSocket - uses unified useToast system
function processToastNotification(message) {
  if (message.type === 'toast_notification') {
    const { 
      toast_type = 'info',    // Backend sends "toast_type", not "type"
      title = '',
      message: toastMessage, 
      duration = 5000
    } = message.data || {}
    
    // Combine title and message for display
    const displayMessage = title ? `${title}: ${toastMessage}` : toastMessage
    
    if (displayMessage) {
      // Use unified toast system
      toast.show(displayMessage, toast_type, duration)
    }
  }
  
  // CRITICAL: Listen for recording_failed WebSocket events
  if (message.type === 'recording_failed') {
    const streamer_name = message.data?.streamer_name || 'Unknown'
    const error_message = message.data?.error_message || 'Unknown error'
    
    toast.error(`Recording failed: ${streamer_name} - ${error_message}`, 5000)
    
    console.error('🚨 Recording failed:', {
      streamer: streamer_name,
      error: error_message,
      data: message.data
    })
  }
}

// PWA AUTH FIX: Check stored auth on app start
onMounted(async () => {
  await checkStoredAuth()
})

// WebSocket message processing - moved here so it runs even when notification panel is closed
const processWebSocketMessage = (message) => {
  if (!message || !message.type) {
    return
  }
  
  // Process toast notifications first
  if (message.type === 'toast_notification') {
    processToastNotification(message)
    return // Don't store toast notifications in regular notification history
  }
  
  // Skip connection status messages
  if (message.type === 'connection.status') {
    return
  }
  
  // Valid notification types for history
  const validTypes = [
    'stream.online', 
    'stream.offline',
    'channel.update',
    'stream.update',
    'recording.started',
    'recording.completed',
    'recording.failed',
    'test'
  ]
  
  if (validTypes.includes(message.type)) {
    addNotificationToStorage(message)
  }
}

// Add notification to localStorage with duplicate detection
const addNotificationToStorage = (message) => {
  try {
    const id = message.data?.test_id || `${message.type}_${Date.now()}_${Math.random()}`
    
    const timestamp = message.data?.timestamp 
      ? new Date(parseInt(message.data.timestamp) || message.data.timestamp).toISOString()
      : new Date().toISOString()
    
    const streamer_username = message.data?.username || 
                             message.data?.streamer_name || 
                             'Unknown'
    
    const newNotification = {
      id,
      type: message.type,
      timestamp,
      streamer_username,
      data: message.data || {}
    }
    
    // Get existing notifications
    let notifications = []
    try {
      const existing = localStorage.getItem('streamvault_notifications')
      if (existing) {
        notifications = JSON.parse(existing)
      }
    } catch (e) {
      notifications = []
    }
    
    // Duplicate detection function
    const isDuplicate = (existing, incoming) => {
      // Same type and streamer
      if (existing.type !== incoming.type || existing.streamer_username !== incoming.streamer_username) {
        return false
      }
      
      const timeDiff = Math.abs(new Date(existing.timestamp).getTime() - new Date(incoming.timestamp).getTime())
      
      // For stream updates, check if title is the same within 30 seconds
      if (incoming.type === 'channel.update' || incoming.type === 'stream.update') {
        const existingTitle = existing.data?.title || ''
        const incomingTitle = incoming.data?.title || ''
        if (existingTitle === incomingTitle && timeDiff < 30000) {
          return true
        }
      }
      
      // For stream.online/offline, check within 10 seconds
      if (incoming.type === 'stream.online' || incoming.type === 'stream.offline') {
        return timeDiff < 10000
      }
      
      // For recording events, check within 5 seconds
      if (incoming.type.startsWith('recording.')) {
        return timeDiff < 5000
      }
      
      return false
    }
    
    // Check for duplicate
    const existingIndex = notifications.findIndex(n => isDuplicate(n, newNotification))
    
    if (existingIndex >= 0) {
      // Update existing notification instead of adding duplicate
      notifications[existingIndex] = newNotification
    } else {
      // Add new notification to beginning
      notifications.unshift(newNotification)
    }
    
    // Limit notifications
    if (notifications.length > 100) {
      notifications = notifications.slice(0, 100)
    }
    
    // Save back to localStorage
    localStorage.setItem('streamvault_notifications', JSON.stringify(notifications))
    
    // Update unread count
    updateUnreadCountFromStorage()
    
    // Dispatch event for other components (NotificationFeed will reload from localStorage)
    window.dispatchEvent(new CustomEvent('notificationsUpdated', {
      detail: { count: notifications.length }
    }))
    
  } catch (error) {
    console.error('❌ App: Error adding notification to localStorage:', error)
  }
}

// Track previous message count to detect new messages
let previousMessageCount = 0

// Watch for new WebSocket messages
watch(() => messages.value.length, (newLength) => {
  if (newLength > previousMessageCount) {
    // Process only the new messages
    const newCount = newLength - previousMessageCount
    const messagesToProcess = messages.value.slice(-newCount)
    
    messagesToProcess.forEach((message, _index) => {
      processWebSocketMessage(message)
    })
    
    previousMessageCount = newLength
  }
}, { immediate: false })

function toggleNotifications() {
  showNotifications.value = !showNotifications.value
  // Lock/unlock body scroll when panel is open on mobile
  document.body.style.overflow = showNotifications.value ? 'hidden' : ''
}

function markAsRead() {
  unreadCount.value = 0
  lastReadTimestamp.value = Date.now().toString()
  localStorage.setItem('lastReadTimestamp', lastReadTimestamp.value)
}

async function clearAllNotifications() {
  try {
    // Clear on backend (sets last_cleared_timestamp)
    await notificationApi.clear()
  } catch (error) {
    console.error('Failed to clear notifications on backend:', error)
  }
  
  // Clear the notifications from localStorage
  localStorage.removeItem('streamvault_notifications')
  // Mark as read
  markAsRead()
  // Reset notification count
  unreadCount.value = 0
  // Dispatch event to notify other components
  window.dispatchEvent(new CustomEvent('notificationsUpdated', {
    detail: { count: 0 }
  }))
}

function closeNotificationPanel() {
  if (showNotifications.value) {
    showNotifications.value = false
    document.body.style.overflow = ''
    markAsRead() // Mark as read when panel closes
  }
}

// Function to update unread count from localStorage
function updateUnreadCountFromStorage() {
  const notificationsStr = localStorage.getItem('streamvault_notifications')
  
  if (notificationsStr) {
    try {
      const notifications = JSON.parse(notificationsStr)
      
      if (Array.isArray(notifications)) {
        // Only count real notification types, not connection status
        const validNotificationTypes = [
          'stream.online', 
          'stream.offline', 
          'channel.update',
          'stream.update',
          'recording.started',
          'recording.completed',
          'recording.failed',
          'test' // Add test notification type to be counted
        ]
        
        const unread = notifications.filter(n => {
          const notifTimestamp = new Date(n.timestamp).getTime()
          const isValidType = validNotificationTypes.includes(n.type)
          const isUnread = notifTimestamp > parseInt(lastReadTimestamp.value)
          
          return isValidType && isUnread
        })
        
        unreadCount.value = unread.length
      }
    } catch (e) {
      console.error('❌ App: Failed to parse notifications from localStorage', e)
    }
  } else {
    unreadCount.value = 0
  }
}

// Load notification state from backend on mount
onMounted(async () => {
  // Load backend notification state (last read/cleared timestamps)
  try {
    const backendState = await notificationApi.getState()
    if (backendState.last_cleared_timestamp) {
      // Use backend cleared timestamp if more recent than localStorage
      const backendCleared = new Date(backendState.last_cleared_timestamp).getTime()
      const localCleared = parseInt(lastReadTimestamp.value) || 0
      if (backendCleared > localCleared) {
        lastReadTimestamp.value = backendCleared.toString()
        localStorage.setItem('lastReadTimestamp', lastReadTimestamp.value)
      }
    }
  } catch (error) {
    console.error('Failed to load notification state from backend:', error)
  }
  
  updateUnreadCountFromStorage()
  
  // Set initial message count
  previousMessageCount = messages.value.length
  
  // Process any existing WebSocket messages
  if (messages.value.length > 0) {
    messages.value.forEach((message, _index) => {
      processWebSocketMessage(message)
    })
  }
  
  // Click-outside handler for notification panel using refs
  const handleClickOutside = (event) => {
    if (!showNotifications.value) return
    
    const bell = notificationBellRef.value
    const panel = notificationPanelRef.value
    
    // Don't close if clicking the bell itself or the panel
    if (bell && bell.contains(event.target)) return
    if (panel && panel.contains(event.target)) return
    
    closeNotificationPanel()
  }
  
  document.addEventListener('click', handleClickOutside)
  
  // Clean up on unmount
  onUnmounted(() => {
    document.removeEventListener('click', handleClickOutside)
  })
  
  // Listen for localStorage changes to update count
  window.addEventListener('storage', (e) => {
    if (e.key === 'streamvault_notifications') {
      updateUnreadCountFromStorage()
    }
  })
  
  // Listen for custom notifications updated event
  window.addEventListener('notificationsUpdated', () => {
    updateUnreadCountFromStorage()
  })
})

// Track the previous message count to detect actual changes
const previousMessageCountApp = ref(0)

// Watch for new messages and update unread count
watch(messages, (newMessages) => {
  if (!newMessages || newMessages.length === 0) return
  
  // Check if we have new messages
  if (newMessages.length > previousMessageCountApp.value) {
    // Get only the new messages since last check
    const newCount = newMessages.length - previousMessageCountApp.value
    const newMessagesToProcess = newMessages.slice(-newCount)
    
    // Update our counter for next time
    previousMessageCountApp.value = newMessages.length
    
    // Process each new message - but only count them, don't store them (NotificationFeed handles storage)
    newMessagesToProcess.forEach(newMessage => {
      
      // Only count specific notification types (exclude connection.status to prevent false positives)
      const notificationTypes = [
        'stream.online', 
        'stream.offline', 
        'channel.update',  
        'stream.update',
        'recording.started',
        'recording.completed',
        'recording.failed',
        'test'  
      ]
      
      // Only increment if it's a valid notification type AND panel is not currently shown
      if (notificationTypes.includes(newMessage.type) && !showNotifications.value) {
        // Check if this notification has already been counted
        const notificationTimestamp = newMessage.data?.timestamp || Date.now()
        if (parseInt(notificationTimestamp) > parseInt(lastReadTimestamp.value)) {
          unreadCount.value++
        }
      }
    })
  }
}, { deep: true, immediate: false }) // Don't process immediately
</script>

<style lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

// ============================================================================
// APP HEADER - Unified Glass Design
// ============================================================================

.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  z-index: 1100;
  
  // Glass effect
  background: var(--glass-bg-strong);
  backdrop-filter: blur(var(--glass-blur-lg));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg));
  border-bottom: 1px solid var(--glass-border);
  box-shadow: var(--glass-shadow-sm);
  
  @supports not (backdrop-filter: blur(1px)) {
    background: var(--glass-bg-solid);
  }
}

.app-header .header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 var(--spacing-4);
  
  @include m.respond-to('md') {
    padding: 0 var(--spacing-6);
  }
}

.app-logo {
  font-size: var(--text-lg);
  font-weight: v.$font-bold;
  color: var(--primary-color);
  line-height: 1;
  user-select: none;
  
  @include m.respond-to('md') {
    font-size: var(--text-xl);
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  
  @include m.respond-to('md') {
    gap: var(--spacing-2);
  }
}

// Hide elements on mobile, show on desktop
.desktop-only {
  display: none !important;
  
  @include m.respond-to('md') {
    display: flex !important;
    align-items: center;
  }
}

// Show elements on mobile only, hide on desktop
.mobile-only {
  display: flex;
  align-items: center;
  
  @include m.respond-to('md') {
    display: none;
  }
}

// ============================================================================
// MOBILE MENU
// ============================================================================

.mobile-menu-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 10000;
}

.mobile-menu-panel {
  position: fixed;
  top: 64px;
  right: var(--spacing-3);
  width: min(260px, 80vw);
  background: var(--glass-bg-strong);
  backdrop-filter: blur(var(--glass-blur-lg));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--glass-shadow-lg);
  z-index: 10001;
  padding: var(--spacing-2);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
  
  @supports not (backdrop-filter: blur(1px)) {
    background: var(--glass-bg-solid);
  }
}

.mobile-menu-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  background: none;
  border: none;
  border-radius: var(--radius-lg);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: background v.$duration-200 v.$ease-out;
  width: 100%;
  text-align: left;
  
  svg {
    width: 20px;
    height: 20px;
    stroke: var(--text-secondary);
    fill: none;
    flex-shrink: 0;
  }
  
  span {
    flex: 1;
  }
  
  .mobile-badge {
    position: static;
    min-width: 18px;
    height: 18px;
    padding: 0 4px;
    background: var(--danger-color);
    color: white;
    font-size: 10px;
    font-weight: v.$font-bold;
    border-radius: var(--radius-full);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  &:hover {
    background: var(--glass-bg-subtle);
  }
  
  &.mobile-menu-danger {
    color: var(--danger-color);
    
    svg {
      stroke: var(--danger-color);
    }
  }
}

.theme-menu-item {
  // Push the ThemeToggle to the right
  :deep(.icon-btn) {
    margin-left: auto;
  }
}

.header-logout-btn {
  padding: var(--spacing-2) var(--spacing-3) !important;
  min-height: 36px !important;
  font-size: v.$text-sm;
  
  // On mobile, show icon only
  .logout-text {
    display: none;
    
    @include m.respond-to('md') {
      display: inline;
    }
  }
}

// Bell shake animation for unread notifications
.glass-btn-icon.has-badge svg {
  animation: bell-shake 1s cubic-bezier(.36,.07,.19,.97) both;
  transform-origin: top center;
  color: var(--primary-color);
}

@keyframes bell-shake {
  0% { transform: rotate(0); }
  15% { transform: rotate(5deg); }
  30% { transform: rotate(-5deg); }
  45% { transform: rotate(4deg); }
  60% { transform: rotate(-4deg); }
  75% { transform: rotate(2deg); }
  85% { transform: rotate(-2deg); }
  92% { transform: rotate(1deg); }
  100% { transform: rotate(0); }
}

// ============================================================================
// NOTIFICATION PANEL — overrides on top of shared .glass-popup-panel
// ============================================================================

.notification-panel {
  // Hide the internal feed header — panel has its own header
  // Must beat scoped selector specificity: .feed-header[data-v-xxx]
  .notification-feed .feed-header {
    display: none !important;
  }
  
  @include m.respond-below('lg') {
    .notification-feed {
      flex: 1;
      overflow-y: auto;
    }
  }
}

// ============================================================================
// TRANSITIONS
// ============================================================================

// Fade transition for backdrop
.fade-enter-active,
.fade-leave-active {
  transition: opacity v.$duration-200 v.$ease-out;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

// Slide-up transition for bottom sheet / dropdown
.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform v.$duration-300 v.$ease-out, opacity v.$duration-200 v.$ease-out;
}
.slide-up-enter-from {
  transform: translateY(20px);
  opacity: 0;
}
.slide-up-leave-to {
  transform: translateY(10px);
  opacity: 0;
}

// Slide-down transition for mobile menu
.slide-down-enter-active,
.slide-down-leave-active {
  transition: transform v.$duration-200 v.$ease-out, opacity v.$duration-150 v.$ease-out;
}
.slide-down-enter-from {
  transform: translateY(-10px);
  opacity: 0;
}
.slide-down-leave-to {
  transform: translateY(-5px);
  opacity: 0;
}

// Page transitions
.page-enter-active,
.page-leave-active {
  transition: opacity v.$duration-200 v.$ease-out;
}
.page-enter-from,
.page-leave-to {
  opacity: 0;
}

// Mobile header styles
@include m.respond-below('md') {
  .app-header .header-content {
    padding: 0 var(--spacing-3);
  }
}
</style>
