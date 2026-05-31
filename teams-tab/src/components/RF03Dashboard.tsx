import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'
import * as api from '../api'
import type { AuthState, EmojiReport, IntensityReport } from '../types'

function last7Days() {
  const end = new Date(), start = new Date()
  start.setDate(end.getDate() - 7)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  return { start: fmt(start), end: fmt(end) }
}

export default function RF03Dashboard({ auth }: { auth: AuthState }) {
  const [dist, setDist] = useState<EmojiReport | null>(null)
  const [intens, setIntens] = useState<IntensityReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!auth.jwtToken || !auth.teamId) return
    const { start, end } = last7Days()
    Promise.all([
      api.getDistribution(auth.jwtToken, auth.teamId, start, end),
      api.getIntensity(auth.jwtToken, auth.teamId, start, end),
    ]).then(([d, i]) => { setDist(d); setIntens(i) })
      .catch(e => setError(String(e)))
  }, [auth.jwtToken, auth.teamId])

  if (!auth.jwtToken || !auth.teamId) return <p>Faça login como gestor nas Configurações.</p>
  if (error) return <p style={{ color: 'red' }}>{error}</p>
  if (!dist) return <p>Carregando...</p>

  return (
    <div>
      <h3>Dashboard — últimos 7 dias</h3>
      {dist.alert && <p><strong>Alerta:</strong> {dist.alert}</p>}
      <p>Emoções negativas: <strong>{dist.negative_emotion_ratio.toFixed(1)}%</strong></p>
      <h4>Frequência por emoção</h4>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={dist.emoji_distribution}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="emotion_name" tick={{ fontSize: 11 }} />
          <YAxis /><Tooltip />
          <Bar dataKey="frequency" fill="#4F46E5" />
        </BarChart>
      </ResponsiveContainer>
      <h4>Intensidade média</h4>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={intens?.average_intensity ?? []}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="emotion_name" tick={{ fontSize: 11 }} />
          <YAxis domain={[0, 5]} /><Tooltip />
          <Bar dataKey="avg_intensity" fill="#f59e0b" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
