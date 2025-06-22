// PWA Installation Helper - Enhanced for Android Chrome
class PWAInstallHelper {
  constructor() {
    this.deferredPrompt = null;
    this.isInstalled = false;
    this.installSupported = false;
    this.listeners = new Map();
    
    this.init();
  }
  
  init() {
    // Check if already installed
    this.checkInstallStatus();
    
    // Listen for install prompt
    window.addEventListener('beforeinstallprompt', (e) => {
      console.log('🎉 beforeinstallprompt fired');
      e.preventDefault();
      this.deferredPrompt = e;
      this.installSupported = true;
      this.emit('installable', true);
    });
    
    // Listen for app installed
    window.addEventListener('appinstalled', () => {
      console.log('✅ PWA was installed');
      this.isInstalled = true;
      this.deferredPrompt = null;
      this.emit('installed', true);
    });
    
    // Check periodically for delayed prompt (Android Chrome behavior)
    let checkCount = 0;
    const checkInterval = setInterval(() => {
      checkCount++;
      
      if (this.deferredPrompt) {
        clearInterval(checkInterval);
        console.log(`✅ Install prompt became available after ${checkCount} checks`);
        return;
      }
      
      if (checkCount >= 60) { // 10 minutes
        clearInterval(checkInterval);
        console.log('❌ No install prompt after 10 minutes');
        this.emit('installable', false);
      }
    }, 10000);
    
    // For development/testing - force check after user interaction
    let interacted = false;
    const forceCheck = () => {
      if (!interacted) {
        interacted = true;
        setTimeout(() => {
          if (!this.deferredPrompt && !this.isInstalled) {
            console.log('🔍 Forcing install check after user interaction');
            this.checkInstallCriteria();
          }
        }, 5000);
      }
    };
    
    ['click', 'touchstart', 'scroll'].forEach(event => {
      document.addEventListener(event, forceCheck, { once: true });
    });
  }
  
  checkInstallStatus() {
    // Check various indicators that app is installed
    const standalone = window.matchMedia('(display-mode: standalone)').matches;
    const fullscreen = window.matchMedia('(display-mode: fullscreen)').matches;
    const minimalUi = window.matchMedia('(display-mode: minimal-ui)').matches;
    const iosStandalone = window.navigator.standalone === true;
    
    this.isInstalled = standalone || fullscreen || minimalUi || iosStandalone;
    
    if (this.isInstalled) {
      console.log('✅ PWA is already installed');
      this.emit('installed', true);
    }
    
    return this.isInstalled;
  }
  
  async checkInstallCriteria() {
    const criteria = {
      https: this.checkHTTPS(),
      manifest: await this.checkManifest(),
      serviceWorker: await this.checkServiceWorker(),
      icons: await this.checkIcons(),
      engagement: this.checkEngagement()
    };
    
    console.log('🔍 PWA Install Criteria:', criteria);
    this.emit('criteria', criteria);
    
    const allMet = Object.values(criteria).every(Boolean);
    if (allMet && !this.deferredPrompt && !this.isInstalled) {
      console.log('⚠️ All criteria met but no install prompt. Possible causes:');
      console.log('  - Browser already showed prompt and user dismissed it');
      console.log('  - Browser requires more user engagement');
      console.log('  - Browser-specific timing delays');
    }
    
    return criteria;
  }
  
  checkHTTPS() {
    return window.location.protocol === 'https:' || 
           window.location.hostname === 'localhost' ||
           window.location.hostname.includes('192.168.') ||
           window.location.hostname.includes('127.0.0.1');
  }
  
  async checkManifest() {
    try {
      const response = await fetch('/manifest.json');
      const manifest = await response.json();
      
      const required = ['name', 'start_url', 'display', 'icons'];
      const hasRequired = required.every(field => manifest[field]);
      
      if (hasRequired) {
        // Check icon requirements
        const hasLargeIcon = manifest.icons.some(icon => 
          icon.sizes.includes('512x512') || icon.sizes.includes('192x192')
        );
        return hasLargeIcon;
      }
      
      return false;
    } catch (error) {
      console.error('❌ Manifest check failed:', error);
      return false;
    }
  }
  
  async checkServiceWorker() {
    if (!('serviceWorker' in navigator)) {
      return false;
    }
    
    try {
      const registrations = await navigator.serviceWorker.getRegistrations();
      const hasActiveWorker = registrations.some(reg => 
        reg.active && reg.active.state === 'activated'
      );
      
      return hasActiveWorker || !!navigator.serviceWorker.controller;
    } catch (error) {
      console.error('❌ Service Worker check failed:', error);
      return false;
    }
  }
  
  async checkIcons() {
    try {
      const response = await fetch('/manifest.json');
      const manifest = await response.json();
      
      if (!manifest.icons || !Array.isArray(manifest.icons)) {
        return false;
      }
      
      // Check for required icon sizes
      const requiredSizes = ['192x192', '512x512'];
      const availableSizes = manifest.icons.map(icon => icon.sizes).flat();
      
      return requiredSizes.every(size => availableSizes.includes(size));
    } catch (error) {
      console.error('❌ Icons check failed:', error);
      return false;
    }
  }
  
  checkEngagement() {
    // Simple engagement check - has user been on site for at least 30 seconds?
    const startTime = window.performance.timing.navigationStart;
    const now = Date.now();
    const timeOnSite = (now - startTime) / 1000;
    
    return timeOnSite >= 30;
  }
  
  async install() {
    if (!this.deferredPrompt) {
      throw new Error('No install prompt available');
    }
    
    try {
      await this.deferredPrompt.prompt();
      const choiceResult = await this.deferredPrompt.userChoice;
      
      if (choiceResult.outcome === 'accepted') {
        console.log('✅ User accepted the install prompt');
        this.emit('installAccepted', true);
      } else {
        console.log('❌ User dismissed the install prompt');
        this.emit('installDismissed', true);
      }
      
      this.deferredPrompt = null;
      return choiceResult.outcome === 'accepted';
    } catch (error) {
      console.error('❌ Install failed:', error);
      throw error;
    }
  }
  
  getManualInstallInstructions() {
    const userAgent = navigator.userAgent.toLowerCase();
    
    if (userAgent.includes('android') && userAgent.includes('chrome')) {
      return {
        platform: 'Android Chrome',
        instructions: [
          'Tippen Sie auf das Menü (⋮) in der oberen rechten Ecke',
          'Wählen Sie "Zum Startbildschirm hinzufügen"',
          'Bestätigen Sie die Installation',
          'Die App erscheint auf Ihrem Startbildschirm'
        ]
      };
    } else if (userAgent.includes('iphone') || userAgent.includes('ipad')) {
      return {
        platform: 'iOS Safari',
        instructions: [
          'Tippen Sie auf das Teilen-Symbol',
          'Scrollen Sie nach unten und wählen Sie "Zum Home-Bildschirm"',
          'Geben Sie einen Namen ein und tippen Sie "Hinzufügen"',
          'Die App erscheint auf Ihrem Home-Bildschirm'
        ]
      };
    } else {
      return {
        platform: 'Desktop Browser',
        instructions: [
          'Schauen Sie nach einem Install-Symbol in der Adressleiste',
          'Oder verwenden Sie das Browser-Menü',
          'Suchen Sie nach "App installieren" oder ähnlichen Optionen'
        ]
      };
    }
  }
  
  // Event system
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }
  
  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => callback(data));
    }
  }
  
  // Getter properties
  get canInstall() {
    return !!this.deferredPrompt && !this.isInstalled;
  }
  
  get installStatus() {
    if (this.isInstalled) return 'installed';
    if (this.deferredPrompt) return 'installable';
    if (this.installSupported) return 'pending'; // Prompt was available but not now
    return 'not-supported';
  }
}

// Global instance
window.pwaHelper = new PWAInstallHelper();

// Debug function
window.debugPWA = () => {
  console.group('🔍 PWA Debug Info');
  console.log('Install Status:', window.pwaHelper.installStatus);
  console.log('Is Installed:', window.pwaHelper.isInstalled);
  console.log('Can Install:', window.pwaHelper.canInstall);
  console.log('Deferred Prompt:', !!window.pwaHelper.deferredPrompt);
  window.pwaHelper.checkInstallCriteria();
  console.groupEnd();
};

export default PWAInstallHelper;
