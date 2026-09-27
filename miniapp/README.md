# Telegram Mini App для Basketball Lev Bot

Мини-приложение для просмотра детальной статистики, турнирных таблиц и управления командой.

## Структура

```
miniapp/
├── api/                  # FastAPI backend
│   ├── main.py          # Основное приложение
│   ├── auth.py          # Аутентификация Telegram
│   ├── database.py      # Работа с БД
│   ├── models.py        # Pydantic модели
│   └── requirements.txt # Зависимости Python
│
├── frontend/            # React + TypeScript frontend
│   ├── src/
│   │   ├── components/  # UI компоненты
│   │   ├── pages/       # Страницы
│   │   ├── hooks/       # React hooks
│   │   ├── api/         # API клиент
│   │   └── types/       # TypeScript типы
│   ├── package.json
│   └── vite.config.ts
│
└── README.md
```

## Быстрый старт

### 1. Установка зависимостей API

```bash
cd miniapp/api
pip install -r requirements.txt
```

### 2. Установка зависимостей Frontend

```bash
cd miniapp/frontend
npm install
```

### 3. Запуск в режиме разработки

**API (терминал 1):**
```bash
cd miniapp/api
uvicorn main:app --reload --port 8080
```

**Frontend (терминал 2):**
```bash
cd miniapp/frontend
npm run dev
```

Frontend будет доступен на `http://localhost:5173`
API будет доступен на `http://localhost:8080`

## Деплой

### Frontend (Vercel/Netlify)

1. Создайте проект на Vercel/Netlify
2. Укажите директорию `miniapp/frontend`
3. Build command: `npm run build`
4. Output directory: `dist`
5. Добавьте переменную окружения `VITE_API_URL` с URL вашего API

### API (VPS)

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Запустите через uvicorn:
```bash
uvicorn miniapp.api.main:app --host 0.0.0.0 --port 8080
```

3. Или используйте systemd service для автозапуска

### Nginx конфигурация (пример)

```nginx
server {
    listen 443 ssl http2;
    server_name miniapp.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Frontend (статика)
    location / {
        root /var/www/miniapp/dist;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Настройка бота

После деплоя добавьте URL мини-приложения в `.env`:

```env
MINIAPP_URL=https://miniapp.yourdomain.com
```

## Регистрация Mini App в BotFather

1. Откройте @BotFather
2. Выберите вашего бота
3. `/setmenubutton` - установить кнопку меню
4. Отправьте URL мини-приложения

Или используйте `/newapp` для создания нового приложения.

## API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/profile` | Профиль текущего пользователя |
| GET | `/api/profile/{user_id}` | Профиль игрока по ID |
| GET | `/api/leaderboard` | Таблица лидеров |
| GET | `/api/tournaments/solo` | Одиночный турнир |
| GET | `/api/tournaments/team` | Командный турнир |
| GET | `/api/team/my` | Команда текущего пользователя |
| GET | `/api/team/{team_id}` | Информация о команде |
| GET | `/api/balance` | Баланс пользователя |
| GET | `/api/ledger` | История транзакций |

## Аутентификация

API использует Telegram initData для аутентификации.

Frontend автоматически передаёт initData через заголовок `X-Telegram-Init-Data`.

Валидация выполняется на бэкенде согласно [документации Telegram](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).

## Разработка без Telegram

В режиме разработки (`npm run dev`) приложение использует моковые данные, когда не запущено внутри Telegram.

Это позволяет тестировать UI локально без необходимости запускать в мобильном клиенте.
