import { useEffect, useState } from 'react'
import * as api from '../api'
import type { Emotion } from '../types'

export default function RF06RegisterFeeling({ teamId }: { teamId: number | null }) {
  const [emotions, setEmotions] = useState<Emotion[]>([])
  const [emotionId, setEmotionId] = useState<number | null>(null)
  const [intensity, setIntensity] = useState(3)
  const [notes, setNotes] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!teamId) return
    api.getEmotions(teamId).then(data => {
      setEmotions(data)
      if (data.length > 0) setEmotionId(data[0].id)
    }).catch(e => setError(String(e)))
  }, [teamId])

  if (!teamId) return <p>Configure a equipe nas Configurações.</p>

  if (submitted) return (
    <div>
      <p>✅ Sentimento registrado!</p>
      <p style={{ color: '#4F46E5' }}>🛡️ Enviado de forma anónima.</p>
      <button onClick={() => { setSubmitted(false); setNotes('') }}>Registrar novamente</button>
    </div>
  )

  return (
    <div>
      <p style={{ color: '#4F46E5', fontWeight: 'bold' }}>🛡️ Este registo é sempre anónimo.</p>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <label>Emoção<br />
        <select value={emotionId ?? ''} onChange={e => setEmotionId(Number(e.target.value))}>
          {emotions.map(em => <option key={em.id} value={em.id}>{em.emoji ? `${em.emoji} ` : ''}{em.name}</option>)}
        </select>
      </label><br />
      <label>Intensidade: {intensity}/5<br />
        <input type="range" min={1} max={5} value={intensity} step={1} onChange={e => setIntensity(Number(e.target.value))} />
      </label><br />
      <label>Notas (opcional)<br />
        <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3} />
      </label><br />
      <button onClick={async () => {
        if (!emotionId) return
        setLoading(true); setError(null)
        try { await api.submitEmotion(teamId, emotionId, intensity, notes); setSubmitted(true) }
        catch (e) { setError(String(e)) }
        finally { setLoading(false) }
      }} disabled={loading || !emotionId}>
        {loading ? 'Enviando...' : 'Registrar (anónimo)'}
      </button>
    </div>
  )
}
