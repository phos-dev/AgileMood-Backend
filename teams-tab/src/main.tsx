import React from 'react'
import ReactDOM from 'react-dom/client'
import * as microsoftTeams from '@microsoft/teams-js'
import App from './App'

function render() {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode><App /></React.StrictMode>
  )
}

microsoftTeams.app.initialize().then(render).catch(render)
