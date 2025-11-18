<template>
  <!-- SVG Icon Sprite (loaded inline for reliability) -->
  <svg xmlns="http://www.w3.org/2000/svg" style="display: none;" aria-hidden="true">
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
      
      <!-- Alert Triangle (Warning) -->
      <symbol id="icon-alert-triangle" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/>
        <line x1="12" y1="17" x2="12.01" y2="17"/>
      </symbol>
    </defs>
  </svg>

  <div class="app">
    <!-- Show header and navigation ONLY on authenticated pages -->
    <template v-if="!isAuthPage">
      <!-- Simplified Header (no navigation - moved to BottomNav/SidebarNav) -->
      <header class="app-header">
        <div class="header-content">
          <!-- Mobile: Hamburger Menu Button (< 768px) -->
          <button 
            @click="toggleMobileMenu" 
            class="hamburger-btn"
            aria-label="Open menu"
          >
            <svg class="hamburger-icon">
              <use href="#icon-menu" />
            </svg>
          </button>
          
          <router-link to="/" class="app-logo">StreamVault</router-link>
          
          <div class="header-right">
            <!-- Background Queue Monitor (always visible) -->
            <BackgroundQueueMonitor />
            
            <!-- Desktop: Full nav actions (≥ 768px) -->
            <div class="nav-actions desktop-only">
              <div class="notification-bell-container">
                <button @click="toggleNotifications" class="notification-bell" :class="{ 'has-unread': unreadCount > 0 }">
                  <svg class="bell-icon">
                    <use href="#icon-bell" />
                  </svg>
                  <span v-if="unreadCount > 0" class="notification-count">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
                </button>
              </div>
              <!-- Theme Toggle -->
              <ThemeToggle />
              <button @click="logout" class="logout-btn">
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>
      
      <!-- Mobile Menu Overlay -->
      <Teleport to="body">
        <div 
          v-if="showMobileMenu" 
          class="mobile-menu-overlay"
          @click.self="closeMobileMenu"
        >
          <div class="mobile-menu">
            <button @click="closeMobileMenu" class="mobile-menu-close" aria-label="Close menu">
              <svg class="close-icon">
                <use href="#icon-x" />
              </svg>
            </button>
            
            <nav class="mobile-menu-nav">
              <div class="notification-bell-container">
                <button @click="handleMobileNotifications" class="notification-bell" :class="{ 'has-unread': unreadCount > 0 }">
                  <svg class="bell-icon">
                    <use href="#icon-bell" />
                  </svg>
                  <span class="nav-label">Notifications</span>
                  <span v-if="unreadCount > 0" class="notification-count">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
                </button>
              </div>
              
              <div class="mobile-theme-toggle">
                <ThemeToggle />
              </div>
              
              <button @click="handleMobileLogout" class="mobile-logout-btn">
                <svg class="logout-icon">
                  <use href="#icon-log-out" />
                </svg>
                <span>Logout</span>
              </button>
            </nav>
          </div>
        </div>
      </Teleport>    
      <!-- Notification overlay -->
      <div v-if="showNotifications" class="notification-overlay">
        <NotificationFeed 
          @notifications-read="markAsRead" 
          @close-panel="closeNotificationPanel"
          @clear-all="clearAllNotifications"
        />
      </div>
    </template>
    
    <!-- Toast notifications (always visible) -->
    <ToastNotification 
      v-for="toast in activeToasts" 
      :key="toast.id"
      :message="toast.message"
      :type="toast.type"
      :duration="toast.duration"
      :data="toast.data"
      @dismiss="removeToast"
    />
    
    <!-- Navigation Wrapper with Bottom Nav + Sidebar (only on authenticated pages) -->
    <NavigationWrapper v-if="!isAuthPage">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </NavigationWrapper>
    
    <!-- Auth pages without navigation -->
    <router-view v-else v-slot="{ Component }">
      <transition name="page" mode="out-in">
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
import ToastNotification from '@/components/ToastNotification.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import NavigationWrapper from '@/components/navigation/NavigationWrapper.vue'
import '@/styles/main.scss'
import { ref, onMounted, watch, provide, computed } from 'vue'
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

// Initialize toast system
const toast = useToast()

// Check if current route is an auth page
const route = useRoute()
const isAuthPage = computed(() => {
  const authPaths = ['/auth/login', '/auth/setup', '/welcome']
  return authPaths.includes(route.path)
})

// Mobile menu state
const showMobileMenu = ref(false)

const toggleMobileMenu = () => {
  showMobileMenu.value = !showMobileMenu.value
  // Prevent body scroll when menu is open
  if (showMobileMenu.value) {
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
}

const closeMobileMenu = () => {
  showMobileMenu.value = false
  document.body.style.overflow = ''
}

const handleMobileNotifications = () => {
  closeMobileMenu()
  toggleNotifications()
}

const handleMobileLogout = () => {
  closeMobileMenu()
  logout()
}

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

// Toast notification management
const activeToasts = ref([])

const { messages } = useWebSocket()
const { logout: authLogout, checkStoredAuth } = useAuth()

// PWA-compatible logout function
async function logout() {
  if (confirm('Are you sure you want to logout?')) {
    await authLogout()
  }
}

// Toast notification functions
function addToast(message, type = 'info', duration = 5000, data = null) {
  const id = `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  
  const toast = {
    id,
    message,
    type,
    duration,
    data
  }
  
  activeToasts.value.push(toast)
  
  // Auto-remove after duration (unless duration is 0 for persistent toasts)
  if (duration > 0) {
    setTimeout(() => {
      removeToast(id)
    }, duration)
  }
}

function removeToast(toastId) {
  const index = activeToasts.value.findIndex(toast => toast.id === toastId)
  if (index > -1) {
    activeToasts.value.splice(index, 1)
  }
}

// Process toast notifications from WebSocket
function processToastNotification(message) {
  if (message.type === 'toast_notification') {
    const { 
      message: toastMessage, 
      type = 'info', 
      duration = 5000, 
      data = null 
    } = message.data || {}
    
    if (toastMessage) {
      addToast(toastMessage, type, duration, data)
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

// Add notification to localStorage - similar to NotificationFeed logic
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
    
    // Add new notification to beginning
    notifications.unshift(newNotification)
    
    // Limit notifications
    if (notifications.length > 100) {
      notifications = notifications.slice(0, 100)
    }
    
    // Save back to localStorage
    localStorage.setItem('streamvault_notifications', JSON.stringify(notifications))
    

    
    // Update unread count
    updateUnreadCountFromStorage()
    
    // Dispatch event for other components
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
    
    messagesToProcess.forEach((message, index) => {
      processWebSocketMessage(message)
    })
    
    previousMessageCount = newLength
  }
}, { immediate: false })

function toggleNotifications() {
  showNotifications.value = !showNotifications.value
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
    messages.value.forEach((message, index) => {
      processWebSocketMessage(message)
    })
  }
  
  // Listen for clicks outside the notification area to close it
  document.addEventListener('click', (event) => {
    const notificationFeed = document.querySelector('.notification-feed')
    const notificationBell = document.querySelector('.notification-bell')

    if (showNotifications.value && 
        notificationFeed && 
        notificationBell && 
        !notificationFeed.contains(event.target) && 
        !notificationBell.contains(event.target)) {
      closeNotificationPanel() // Use the proper close function instead of just setting the value
    }
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

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

/* Modern Header Styles (Phase 1 Enhanced) */
.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  width: 100%;
  height: 64px;
  z-index: 1100;

  /* Glassmorphism effect */
  background: rgba(var(--background-card-rgb), 0.85);
  backdrop-filter: blur(24px) saturate(180%);
  border-bottom: 1px solid var(--border-color);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);

  /* Smooth theme transitions */
  transition: background-color 300ms var(--vue-ease-out),
              border-color 300ms var(--vue-ease-out);
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  width: 100%;
  max-width: 100%;
  padding: 0 var(--spacing-6, 1.5rem);
  gap: var(--spacing-4, 1rem);
}

.app-logo {
  font-size: var(--text-xl, 1.25rem);
  font-weight: var(--font-bold, 700);
  color: var(--primary-color);
  text-decoration: none;
  line-height: 1;

  /* Smooth transition */
  transition: color var(--duration-200, 200ms) var(--vue-ease-out);

  &:hover {
    color: var(--accent-color);
  }

  /* Focus-visible for keyboard navigation */
  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 4px;
    border-radius: var(--radius-sm, 4px);
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-3, 0.75rem);
  height: 100%;
}

/* Navigation actions styles */
.nav-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-3, 0.75rem);
  height: 100%;
}

/* Mobile: Hide hamburger button on desktop */
.hamburger-btn {
  display: none; /* Hidden by default (desktop) */
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  padding: 0;
  background: transparent;
  border: none;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 200ms ease-out;
  
  .hamburger-icon {
    width: 24px;
    height: 24px;
  }
  
  &:hover {
    background: var(--background-hover);
    border-radius: var(--radius-md);
  }
  
  &:active {
    transform: scale(0.95);
  }
}

/* Show hamburger on mobile */
@include m.respond-below('md') {  // < 767px
  .hamburger-btn {
    display: flex;
  }
}

/* Desktop: Hide nav actions on mobile */
.desktop-only {
  display: flex; /* Shown by default */
}

@include m.respond-below('md') {  // < 767px
  .desktop-only {
    display: none; /* Hidden on mobile */
  }
}

/* Mobile Menu Overlay */
.mobile-menu-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  justify-content: flex-start;  /* Changed from flex-end - menu now appears on LEFT */
  animation: fadeIn 200ms ease-out;
}

@media (min-width: 768px) {
  .mobile-menu-overlay {
    display: none; /* Never show on desktop */
  }
}

.mobile-menu {
  width: 280px;
  height: 100%;
  background: var(--background-card);
  box-shadow: var(--shadow-xl);
  animation: slideInLeft 300ms ease-out;  /* Changed from slideInRight */
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(20px);
  border-right: 1px solid var(--border-color);  /* Changed from border-left */
}

.mobile-menu-close {
  align-self: flex-end;
  width: 44px;
  height: 44px;
  margin: var(--spacing-4);
  padding: 0;
  background: transparent;
  border: none;
  color: var(--text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 200ms ease-out;
  
  .close-icon {
    width: 24px;
    height: 24px;
  }
  
  &:hover {
    background: var(--background-hover);
    border-radius: var(--radius-md);
  }
  
  &:active {
    transform: scale(0.95);
  }
}

.mobile-menu-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  padding: var(--spacing-4);
  
  .notification-bell-container {
    width: 100%;
    
    .notification-bell {
      width: 100%;
      justify-content: flex-start;
      gap: var(--spacing-3);
      padding: var(--spacing-3) var(--spacing-4);
      background: transparent;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg);
      transition: all 200ms ease-out;
      
      .nav-label {
        flex: 1;
        text-align: left;
        font-size: var(--text-base);
        font-weight: var(--font-medium);
      }
      
      &:hover {
        background: var(--background-hover);
        border-color: var(--primary-500);
      }
      
      &.has-unread {
        border-color: var(--danger-500);
      }
    }
  }
  
  .mobile-theme-toggle {
    width: 100%;
    padding: var(--spacing-3) var(--spacing-4);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    background: transparent;
    
    :deep(.theme-toggle) {
      width: 100%;
    }
  }
}

.mobile-logout-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-3);
  width: 100%;
  min-height: 44px;
  margin-top: auto; /* Push to bottom */
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--danger-color);
  color: white;
  border: none;
  border-radius: var(--radius-lg);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all 200ms ease-out;
  
  .logout-icon {
    width: 20px;
    height: 20px;
  }
  
  &:hover {
    background: var(--danger-600);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }
  
  &:active {
    transform: translateY(0);
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideInRight {
  from {
    transform: translateX(100%);
  }
  to {
    transform: translateX(0);
  }
}

@keyframes slideInLeft {
  from {
    transform: translateX(-100%);
  }
  to {
    transform: translateX(0);
  }
}

.notification-bell-container {
  position: relative;
}

.logout-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2, 0.5rem);
  min-height: 44px;
  padding: var(--spacing-2, 0.5rem) var(--spacing-4, 1rem);

  /* Colors */
  background: var(--danger-color);
  color: white;
  border: none;
  border-radius: var(--radius-lg, 12px);

  /* Typography */
  font-size: var(--text-sm, 0.875rem);
  font-weight: var(--font-medium, 500);
  line-height: 1;

  /* Interaction */
  cursor: pointer;
  transition: all var(--duration-200, 200ms) var(--vue-ease-out);

  &:hover {
    background: var(--danger-600, #dc2626);
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }

  &:active {
    transform: translateY(0);
    box-shadow: var(--shadow-sm);
  }

  &:focus-visible {
    outline: 2px solid var(--danger-color);
    outline-offset: 2px;
  }
}

.notification-bell {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;

  /* Touch-friendly sizing */
  min-width: 44px;
  min-height: 44px;
  width: 44px;
  height: 44px;
  padding: var(--spacing-2, 8px);

  /* Style */
  background: transparent;
  border: none;
  border-radius: 50%;
  color: var(--text-primary);

  /* Interaction */
  cursor: pointer;
  transition: all var(--duration-200, 200ms) var(--vue-ease-out);

  .bell-icon {
    width: 24px;
    height: 24px;
    stroke: currentColor;
    fill: none;
    transition: transform var(--duration-200, 200ms) var(--vue-ease-out);
  }

  &:hover {
    background-color: rgba(var(--primary-500-rgb), 0.1);
    color: var(--primary-color);

    .bell-icon {
      transform: scale(1.1);
    }
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

.notification-bell.has-unread .bell-icon {
  color: var(--primary-500);
  animation: bell-shake 1s cubic-bezier(.36,.07,.19,.97) both;
  transform-origin: top center;
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

.notification-count {
  position: absolute;
  top: 4px;
  right: 4px;
  background-color: var(--danger-500);
  color: white;
  border-radius: 50%;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

/* Notification overlay positioning */
.notification-overlay {
  position: fixed;
  top: 70px; /* Below the header */
  right: 20px;
  z-index: 1000;
  max-width: 400px;
  width: 90vw;
}

/* Mobile specific notification overlay */
@include m.respond-below('md') {  // < 767px
  .notification-overlay {
    top: 20px;
    right: 10px;
    left: 10px;
    width: auto;
    max-width: none;
  }
  
  .header-content {
    padding: 0 1rem;
  }
  
  .app-logo {
    font-size: 1.25rem;
  }
}
</style>
