// Source-derived from src/router/index.ts. Dynamic route parameters use mock-safe values
// solely to collect route-state evidence; failures are retained in the baseline JSON.
export const frontendBaselineScenarios = [
  { routeName: 'home', path: '/', readinessSelector: '.home-view' },
  { routeName: 'welcome', path: '/welcome', readinessSelector: '.onboarding-view' },
  { routeName: 'streamers', path: '/streamers', readinessSelector: '.streamers-view' },
  { routeName: 'videos', path: '/videos', readinessSelector: '.videos-view' },
  { routeName: 'video-player', path: '/videos/1', readinessSelector: '.video-player-view' },
  { routeName: 'subscriptions', path: '/subscriptions', readinessSelector: '.subscriptions-view' },
  { routeName: 'add-streamer', path: '/add-streamer', readinessSelector: '.add-streamer-view' },
  { routeName: 'add-streamer-manual', path: '/add-streamer/manual', readinessSelector: '.add-streamer-view' },
  { routeName: 'add-streamer-import', path: '/add-streamer/import', readinessSelector: '.add-streamer-view' },
  { routeName: 'setup', path: '/auth/setup', readinessSelector: '.onboarding-view' },
  { routeName: 'onboarding', path: '/onboarding', readinessSelector: '.onboarding-view' },
  { routeName: 'login', path: '/auth/login', readinessSelector: '.login-view' },
  { routeName: 'admin', path: '/admin', readinessSelector: '.admin-view' },
  { routeName: 'settings', path: '/settings', readinessSelector: '.settings-view' },
  { routeName: 'streamer-detail', path: '/streamers/1', readinessSelector: '.streamer-detail-view' },
  { routeName: 'stream-player', path: '/streamer/1/stream/1/watch', readinessSelector: '.video-player-view' },
  { routeName: 'live-player', path: '/live/streamer-alpha', readinessSelector: '.live-player-view' },
] as const
