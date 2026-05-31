const KEY = 'agile_mood_auth'

export function saveAuth(state: object): void {
  localStorage.setItem(KEY, JSON.stringify(state))
}
export function loadAuth(): Record<string, unknown> | null {
  const raw = localStorage.getItem(KEY)
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}
export function clearAuth(): void { localStorage.removeItem(KEY) }
