/** Presentation only: API/store owners choose the state; this contract never infers success. */
export const presentationStates = {
  unknown: { title: 'Noch nicht geladen', tone: 'neutral' },
  loading: { title: 'Wird geladen', tone: 'info' },
  'confirmed-empty': { title: 'Noch keine Einträge', tone: 'neutral' },
  'filter-empty': { title: 'Keine passenden Einträge', tone: 'neutral' },
  fresh: { title: 'Aktuell', tone: 'neutral' },
  stale: { title: 'Nicht aktuell', tone: 'warning' },
  offline: { title: 'Keine Verbindung', tone: 'warning' },
  forbidden: { title: 'Kein Zugriff', tone: 'danger' },
  error: { title: 'Laden fehlgeschlagen', tone: 'danger' },
  pending: { title: 'Wird verarbeitet', tone: 'info' },
  'confirmed-success': { title: 'Abgeschlossen', tone: 'success' },
  partial: { title: 'Teilweise abgeschlossen', tone: 'warning' },
  failure: { title: 'Aktion fehlgeschlagen', tone: 'danger' },
} as const

export type PresentationState = keyof typeof presentationStates
