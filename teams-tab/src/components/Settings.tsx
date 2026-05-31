import { useState } from 'react'
import * as api from '../api'
import type { AuthState } from '../types'

interface Props { auth: AuthState; onLogin: (a: AuthState) => void; onLogout: () => void }

export default function Settings({ auth, onLogin, onLogout }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleLogin = async () => {
    if (!email || !password) { setError('E-mail e senha são obrigatórios.'); return }
    setLoading(true); setError(null)
    try {
      const data = await api.login(email, password)
      let teamId = data.team_id ?? null
      let teamName = ''
      if (!teamId && data.role === 'manager') {
        const team = await api.getMyTeam(data.access_token).catch(() => null)
        teamId = team?.teamId ?? null
        teamName = team?.teamName ?? ''
      }
      onLogin({ jwtToken: data.access_token, role: data.role as 'manager' | 'employee', teamId, teamName, name: data.name, email: data.email })
      setPassword('')
    } catch (e) {
      setError(`Falha no login: ${e instanceof Error ? e.message : String(e)}`)
    } finally { setLoading(false) }
  }

  if (auth.jwtToken) return (
    <div>
      <p>Conectado: <strong>{auth.name ?? auth.email}</strong> ({auth.role === 'manager' ? 'Gestor' : 'Funcionário'})</p>
      {auth.teamName && <p>Equipe: {auth.teamName}</p>}
      <button onClick={onLogout}>Sair</button>
    </div>
  )

  return (
    <div>
      <h3>AgileMood — Entrar</h3>
      <input type="email" placeholder="E-mail" value={email} onChange={e => setEmail(e.target.value)} /><br />
      <input type="password" placeholder="Senha" value={password} onChange={e => setPassword(e.target.value)} /><br />
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <button onClick={handleLogin} disabled={loading}>{loading ? 'Conectando...' : 'Entrar'}</button>
    </div>
  )
}
