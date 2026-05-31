import type { Emotion, EmojiReport, IntensityReport, FeedbackMessage } from './types'

const BASE = import.meta.env.VITE_API_URL ?? 'https://api.agilemood.app'

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export async function login(email: string, password: string) {
  const res = await fetch(`${BASE}/user/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username: email, password }).toString(),
  })
  const { access_token } = await parseJson<{ access_token: string }>(res)
  const me = await parseJson<{ role: string; team_id: number | null; name: string; email: string }>(
    await fetch(`${BASE}/user/logged`, { headers: { Authorization: `Bearer ${access_token}` } })
  )
  return { access_token, ...me }
}

export async function getMyTeam(jwt: string) {
  const data = await parseJson<{ teams?: { id: number; name: string }[] }>(
    await fetch(`${BASE}/teams/`, { headers: { Authorization: `Bearer ${jwt}` } })
  )
  const teams = data.teams ?? []
  return teams.length > 0 ? { teamId: teams[0].id, teamName: teams[0].name } : null
}

export async function getEmotions(teamId: number): Promise<Emotion[]> {
  const data = await parseJson<{ emotions?: Emotion[] }>(
    await fetch(`${BASE}/emotions/public?team_id=${teamId}`)
  )
  return data.emotions ?? []
}

// RF06: is_anonymous=True ALWAYS forced — public endpoint, no JWT
export async function submitEmotion(teamId: number, emotionId: number, intensity: number, notes: string): Promise<void> {
  await parseJson(await fetch(`${BASE}/emotion_record/public?team_id=${teamId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ emotion_id: emotionId, intensity, notes, is_anonymous: true }),
  }))
}

export async function getDistribution(jwt: string, teamId: number, start: string, end: string): Promise<EmojiReport> {
  return parseJson(await fetch(
    `${BASE}/reports/emoji-distribution/${teamId}?start_date=${start}&end_date=${end}`,
    { headers: { Authorization: `Bearer ${jwt}` } }
  ))
}

export async function getIntensity(jwt: string, teamId: number, start: string, end: string): Promise<IntensityReport> {
  return parseJson(await fetch(
    `${BASE}/reports/average-intensity/${teamId}?start_date=${start}&end_date=${end}`,
    { headers: { Authorization: `Bearer ${jwt}` } }
  ))
}

export async function getMessages(jwt: string): Promise<FeedbackMessage[]> {
  const data = await parseJson<{ feedbacks?: FeedbackMessage[] } | FeedbackMessage[]>(
    await fetch(`${BASE}/feedback/`, { headers: { Authorization: `Bearer ${jwt}` } })
  )
  return Array.isArray(data) ? data : (data as { feedbacks?: FeedbackMessage[] }).feedbacks ?? []
}
