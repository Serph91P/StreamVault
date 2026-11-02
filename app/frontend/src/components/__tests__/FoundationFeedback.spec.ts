import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import EmptyState from '../EmptyState.vue'
import ToastContainer from '../ToastContainer.vue'
import { useToast } from '@/composables/useToast'

// A state must never imply an empty collection or completed mutation by accident.
describe('foundation presentation contract', () => {
  it.each([
    ['unknown', 'status', 'Noch nicht geladen'],
    ['loading', 'status', 'Wird geladen'],
    ['confirmed-empty', 'status', 'Noch keine Einträge'],
    ['filter-empty', 'status', 'Keine passenden Einträge'],
    ['fresh', 'status', 'Aktuell'],
    ['stale', 'status', 'Nicht aktuell'],
    ['offline', 'status', 'Keine Verbindung'],
    ['forbidden', 'alert', 'Kein Zugriff'],
    ['error', 'alert', 'Laden fehlgeschlagen'],
    ['pending', 'status', 'Wird verarbeitet'],
    ['confirmed-success', 'status', 'Abgeschlossen'],
    ['partial', 'status', 'Teilweise abgeschlossen'],
    ['failure', 'alert', 'Aktion fehlgeschlagen'],
  ] as const)('renders %s distinctly with an announced name', (state, role, title) => {
    const wrapper = mount(EmptyState, { props: { state, variant: 'inline' } })
    expect(wrapper.get('[role]').attributes('role')).toBe(role)
    expect(wrapper.get('h2').text()).toBe(title)
    expect(wrapper.attributes('aria-busy')).toBe(['loading', 'pending'].includes(state) ? 'true' : 'false')
    wrapper.unmount()
  })

  it('keeps the last confirmed timestamp and retry visible without replacing owner content', async () => {
    const wrapper = mount(EmptyState, { props: {
      state: 'stale', title: 'Kanäle nicht aktuell', updatedAt: '2026-01-02T10:00:00Z', retryLabel: 'Erneut versuchen',
    }, slots: { default: '<p>Gespeicherter Kanal bleibt sichtbar</p>' } })
    expect(wrapper.get('time').attributes('datetime')).toBe('2026-01-02T10:00:00Z')
    expect(wrapper.text()).toContain('Gespeicherter Kanal bleibt sichtbar')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toEqual([[]])
    wrapper.unmount()
  })
})

describe('existing toast queue accessibility', () => {
  afterEach(() => { useToast().clear(); vi.useRealTimers(); document.body.innerHTML = '' })

  it('announces status and urgent errors, and dismisses only the chosen toast with a named button', async () => {
    vi.useFakeTimers()
    const wrapper = mount(ToastContainer, { attachTo: document.body })
    useToast().info('Auftrag angenommen, Ergebnis steht noch aus')
    useToast().error('Speichern fehlgeschlagen')
    await nextTick()
    expect(document.querySelector('[role="status"]')?.textContent).toContain('Ergebnis steht noch aus')
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('Speichern fehlgeschlagen')
    const close = document.querySelector<HTMLButtonElement>('[role="alert"] button')!
    expect(close.getAttribute('aria-label')).toBe('Meldung schließen')
    close.click()
    await nextTick()
    expect(useToast().toasts.value.map(toast => toast.type)).toEqual(['info'])
    wrapper.unmount()
  })
})
