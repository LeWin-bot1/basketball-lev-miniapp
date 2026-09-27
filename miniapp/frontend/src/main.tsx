import React from 'react'
import ReactDOM from 'react-dom/client'
import WebApp from '@twa-dev/sdk'
import App from './App'
import './index.css'

try {
  WebApp.ready()
  WebApp.expand()
  WebApp.setHeaderColor('#f9a825')
  WebApp.setBackgroundColor('#ffffff')
} catch (error) {
  console.warn('Telegram WebApp init skipped', error)
}

const root = document.getElementById('root')
if (root) {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}
