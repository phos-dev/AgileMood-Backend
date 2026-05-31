import { useEffect, useState } from 'react'
import * as microsoftTeams from '@microsoft/teams-js'

export default function ConfigPage() {
  const [teamId, setTeamId] = useState('')

  useEffect(() => {
    microsoftTeams.pages.config.registerOnSaveHandler(saveEvent => {
      microsoftTeams.pages.config.setConfig({
        contentUrl: `${window.location.origin}${window.location.pathname}?teamId=${teamId}`,
        websiteUrl: `${window.location.origin}${window.location.pathname}?teamId=${teamId}`,
        suggestedDisplayName: 'AgileMood',
        entityId: `agile-mood-${teamId}`,
      })
      saveEvent.notifySuccess()
    })
    microsoftTeams.pages.config.setValidityState(teamId.trim().length > 0)
  }, [teamId])

  return (
    <div style={{ padding: 24 }}>
      <h2>Configurar AgileMood</h2>
      <p>ID da equipe AgileMood:</p>
      <input type="number" value={teamId} onChange={e => setTeamId(e.target.value)} placeholder="Ex: 42"
             style={{ width: '100%', padding: 8, fontSize: 16 }} />
    </div>
  )
}
