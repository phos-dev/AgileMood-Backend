import { useEffect, useState } from 'react'
import * as api from '../api'
import type { AuthState, FeedbackMessage } from '../types'

export default function RF07Messages({ auth }: { auth: AuthState }) {
  const [messages, setMessages] = useState<FeedbackMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!auth.jwtToken) { setLoading(false); return }
    api.getMessages(auth.jwtToken)
      .then(setMessages)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [auth.jwtToken])

  if (!auth.jwtToken) return <p>Faça login nas Configurações.</p>
  if (loading) return <p>Carregando...</p>
  if (error) return <p style={{ color: 'red' }}>{error}</p>
  if (!messages.length) return <p>Nenhuma mensagem recebida ainda.</p>

  return (
    <div>
      <h3>Mensagens do Gestor</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #eee', padding: '6px 0', width: 110 }}>Data</th>
            <th style={{ textAlign: 'left', borderBottom: '1px solid #eee', padding: '6px 0' }}>Mensagem</th>
          </tr>
        </thead>
        <tbody>
          {messages.map(msg => (
            <tr key={msg.id}>
              <td style={{ padding: '6px 0', verticalAlign: 'top' }}>
                {new Date(msg.created_at).toLocaleDateString('pt-BR')}
              </td>
              <td style={{ padding: '6px 0' }}>{msg.content}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
