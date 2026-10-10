import { describe, expect, it } from 'vitest'

import adminPanel from '@/components/admin/AdminPanel.vue?raw'
import statusCard from '@/components/cards/StatusCard.vue?raw'
import streamCard from '@/components/cards/StreamCard.vue?raw'
import videoCard from '@/components/cards/VideoCard.vue?raw'
import livePlayer from '@/views/LivePlayerView.vue?raw'
import subscriptions from '@/views/SubscriptionsView.vue?raw'
import videoPlayer from '@/views/VideoPlayerView.vue?raw'

const activeSurfaceConsumers = {
  AdminPanel: adminPanel,
  StatusCard: statusCard,
  StreamCard: streamCard,
  VideoCard: videoCard,
  LivePlayerView: livePlayer,
  SubscriptionsView: subscriptions,
  VideoPlayerView: videoPlayer,
}

describe('R3 active surface consumers', () => {
  it.each(Object.entries(activeSurfaceConsumers))('%s uses the opaque SurfaceCard primitive', (_name, source) => {
    expect(source).toContain('<SurfaceCard')
    expect(source).not.toMatch(/(?:<|import\s+)GlassCard/)
    expect(source).not.toContain('glass-card-content')
  })
})
