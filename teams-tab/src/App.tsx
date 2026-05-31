import { useEffect, useState } from 'react'
import * as microsoftTeams from '@microsoft/teams-js'
import { loadAuth, saveAuth, clearAuth } from './auth'
import type { AuthState } from './types'
import Settings from './components/Settings'
import RF06RegisterFeeling from './components/RF06RegisterFeeling'
import RF07Messages from './components/RF07Messages'
import RF03Dashboard from './components/RF03Dashboard'
import ConfigPage from './ConfigPage'

type TabKey = 'register' | 'messages' | 'dashboard' | 'settings'
const EMPTY: AuthState = { jwtToken: null, role: null, teamId: null, teamName: null, name: null, email: null }

export default function App() {
  const [auth, setAuth] = useState<AuthState>(() => {
    const raw = loadAuth()
    return raw?.jwtToken ? (raw as unknown as AuthState) : EMPTY
  })
  const [tab, setTab] = useState<TabKey>('register')
  const [isConfig, setIsConfig] = useState(false)

  useEffect(() => {
    microsoftTeams.app.getContext().then(ctx => {
      if (ctx.page.id === 'config') setIsConfig(true)
      const urlTeamId = new URLSearchParams(window.location.search).get('teamId')
      if (urlTeamId && !auth.teamId) setAuth(prev => ({ ...prev, teamId: Number(urlTeamId) }))
    }).catch(() => {
      const urlTeamId = new URLSearchParams(window.location.search).get('teamId')
      if (urlTeamId && !auth.teamId) setAuth(prev => ({ ...prev, teamId: Number(urlTeamId) }))
    })
  }, [])

  if (isConfig) return <ConfigPage />

  const tabs: { key: TabKey; label: string; managerOnly?: true }[] = [
    { key: 'register', label: 'Registrar' },
    { key: 'messages', label: 'Mensagens' },
    { key: 'dashboard', label: 'Dashboard', managerOnly: true },
    { key: 'settings', label: 'Configurações' },
  ]

  return (
    <div style={{ fontFamily: 'Segoe UI, sans-serif', maxWidth: 720, margin: '0 auto', padding: 16 }}>
      <nav style={{ display: 'flex', gap: 8, marginBottom: 16, borderBottom: '1px solid #e5e7eb', paddingBottom: 8 }}>
        {tabs.filter(t => !t.managerOnly || auth.role === 'manager').map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            padding: '6px 14px', border: 'none', borderRadius: 4, cursor: 'pointer',
            background: tab === t.key ? '#4F46E5' : '#f3f4f6',
            color: tab === t.key ? '#fff' : '#111', fontWeight: tab === t.key ? 600 : 400,
          }}>{t.label}</button>
        ))}
      </nav>
      {tab === 'settings' && <Settings auth={auth} onLogin={a => { saveAuth(a); setAuth(a) }} onLogout={() => { clearAuth(); setAuth(EMPTY) }} />}
      {tab === 'register' && <RF06RegisterFeeling teamId={auth.teamId} />}
      {tab === 'messages' && <RF07Messages auth={auth} />}
      {tab === 'dashboard' && <RF03Dashboard auth={auth} />}
    </div>
  )
}
