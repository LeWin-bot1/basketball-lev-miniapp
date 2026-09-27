import React from 'react'
import ReactDOM from 'react-dom/client'
import WebApp from '@twa-dev/sdk'
import App from './App'
import './index.css'

// Инициализируем Telegram Web App SDK
WebApp.ready()

// Расширяем на весь экран
WebApp.expand()

// Устанавливаем цвета
WebApp.setHeaderColor('#f9a825')
WebApp.setBackgroundColor('#ffffff')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
