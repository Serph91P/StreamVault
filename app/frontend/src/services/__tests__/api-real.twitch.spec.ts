import { afterEach, describe, expect, it, vi } from 'vitest'
vi.mock('@/router', () => ({ default: { push: vi.fn() } }))
vi.mock('@/services/storage', () => ({ appStorage: {} }))
import { authApi } from '@/services/api-real'
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks() })

describe('real Twitch facade backend shapes', () => {
  it('sends the selected channel list directly and returns unwrapped result arrays', async () => {
    const channels = [{ id: '123', login: 'synthetic', display_name: 'Synthetic' }]
    const result = { imported: [{ username: 'synthetic', id: 933 }], failed: [], already_exists: [] }
    const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify(result), { headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', fetch)
    await expect(authApi.importStreamers(channels)).resolves.toEqual(result)
    expect(fetch).toHaveBeenCalledWith('/api/twitch/import-streamers', expect.objectContaining({ method: 'POST', credentials: 'include', body: JSON.stringify(channels) }))
  })
  it('carries only the permitted add-page return state to the auth URL endpoint', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ auth_url: 'https://example.invalid' }), { headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', fetch)
    await authApi.getAuthUrl('/add-streamer')
    expect(fetch).toHaveBeenCalledWith('/api/twitch/auth-url?state=%2Fadd-streamer', expect.objectContaining({ method: 'GET' }))
  })
})
