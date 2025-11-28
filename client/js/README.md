# Client JavaScript Structure

## Структура директорий

```
client/js/
├── core/           # Основная логика приложения
│   └── App.js      # Главный класс приложения
├── services/       # Сервисы для работы с API
│   ├── ApiClient.js         # Клиент для backend API
│   ├── GmailService.js      # Сервис для работы с Gmail (popup)
│   └── GmailApiService.js   # Сервис для работы с Gmail API (background)
├── ui/             # UI компоненты
│   ├── ThemeManager.js      # Управление темой
│   ├── SenderList.js        # Список отправителей
│   ├── EmailList.js         # Список писем
│   ├── ConversationPanel.js # Панель чата
│   └── InsightsPanel.js     # Панель инсайтов
└── utils/          # Утилиты
    ├── dom.js               # Работа с DOM
    └── formatting.js        # Форматирование данных
```

## Описание модулей

### Core

- **App.js** - Главный класс приложения, инициализирует все компоненты и управляет взаимодействием между ними

### Services

- **ApiClient.js** - Клиент для взаимодействия с backend API (анализ писем, недельные отчёты)
- **GmailService.js** - Сервис для работы с Gmail через chrome.runtime.sendMessage (используется в popup)
- **GmailApiService.js** - Сервис для прямой работы с Gmail API (используется в background script)

### UI Components

- **ThemeManager.js** - Управление темой (светлая/тёмная)
- **SenderList.js** - Отображение и выбор отправителей
- **EmailList.js** - Отображение списка писем, выбор писем, превью
- **ConversationPanel.js** - Панель чата с агентом
- **InsightsPanel.js** - Отображение результатов анализа (фильтры, рассылки, автоответы)

### Utils

- **dom.js** - Утилиты для работы с DOM
- **formatting.js** - Утилиты для форматирования (HTML escaping, парсинг email, форматирование писем)

## Использование

Все модули используют ES6 модули (import/export). Главная точка входа - `popup.js`, который создаёт экземпляр класса `App`.
