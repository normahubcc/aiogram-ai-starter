<p align="center">
  <a href="https://normahub.cc">
    <img src="https://raw.githubusercontent.com/normahubcc/normahubcc/main/docs/images/logo.png" alt="NormaHub" width="130" />
  </a>
</p>

<h1 align="center">NormaHub Aiogram AI Starter</h1>

<p align="center">
  <b>Продакшн-стартер современного Telegram-бота на базе aiogram 3.15+ и единого AI-шлюза NormaHub.</b><br>
  Потоковый вывод токенов без FloodWait, генерация видео SeeDance 2.5, голосовые сообщения Whisper, скользящий контекст и переключение моделей на лету.
</p>

<p align="center">
  <a href="https://github.com/normahubcc/aiogram-ai-starter/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/normahubcc/aiogram-ai-starter/ci.yml?branch=main&style=flat-square&logo=github&label=CI" alt="CI" /></a>
  <a href="https://normahub.cc"><img src="https://img.shields.io/badge/NormaHub-Gateway%20API-6366f1?style=flat-square" alt="NormaHub API" /></a>
  <a href="https://docs.aiogram.dev"><img src="https://img.shields.io/badge/aiogram-v3.15+-2ba1e0?style=flat-square&logo=telegram" alt="aiogram" /></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.11%20|%203.12-3776ab?style=flat-square&logo=python" alt="Python" /></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square" alt="Ruff" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg?style=flat-square" alt="License" /></a>
</p>

---

## 📌 О проекте

Создание надежного Telegram-бота с искусственным интеллектом в 2026 году сопряжено с типовыми архитектурными сложностями:
1. **Telegram FloodWait (Rate Limits):** при наивной отправке каждого чанка поток токенов (20–40 т/с) приводит к блокировке `TelegramRetryAfter` через 3–5 секунд.
2. **Битые Markdown-сущности:** пока модель дописывает код или жирный шрифт (незакрытые `**` или ` ``` `), Telegram выбрасывает ошибку `can't parse entities`.
3. **Раздувание контекста:** неконтролируемый рост истории диалога истощает токены и раздувает бюджет запроса.
4. **Блокировки и VPN:** прямой доступ к зарубежным нейросетям нестабилен.

**`aiogram-ai-starter`** решает все эти проблемы "из коробки" в строгой архитектуре с типизацией Pydantic Settings, неблокирующим дебаунсером, авто-фоллбэком разметки и интеграцией с российским шлюзом [NormaHub API](https://normahub.cc).

---

## 🏗️ Архитектура

```
                           ┌────────────────────────┐
                           │     Telegram User      │
                           └───────────┬────────────┘
                                       │ (Text / Voice / Commands)
                                       ▼
                           ┌────────────────────────┐
                           │    aiogram 3 Router    │
                           └───────────┬────────────┘
                                       │
                ┌──────────────────────┼──────────────────────┐
                ▼                      ▼                      ▼
        ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
        │ /video Prompt │      │ Voice (Audio) │      │ Chat Message  │
        └───────┬───────┘      └───────┬───────┘      └───────┬───────┘
                │                      │                      │
                │                      ▼ (Whisper-1)          ▼
                │              ┌───────────────┐      ┌───────────────┐
                │              │ Transcription │─────▶│Context Manager│ (Sliding Window: 10 turns)
                │              └───────────────┘      └───────┬───────┘
                │                                             │
                │                                             ▼
                │                                     ┌───────────────┐
                │                                     │  NormaHub     │ (SSE Streaming)
                │                                     │  Async Client │
                │                                     └───────┬───────┘
                │                                             │ (Tokens ~30ms)
                │                                             ▼
                │                                     ┌───────────────┐
                │                                     │StreamDebouncer│ (Buffered ~800ms)
                │                                     │+ Markdown Safe│
                │                                     └───────┬───────┘
                │                                             │
                ▼                                             ▼
    ┌──────────────────────┐                      ┌──────────────────────┐
    │ SeeDance 2.5 Video   │                      │  edit_message_text   │
    │ Polling & MP4 Delivery│                     │  (Smooth Streaming)  │
    └──────────────────────┘                      └──────────────────────┘
```

---

## ⚡ Матрица возможностей

| Компонент / Фича | Реализация | Преимущество |
|---|---|---|
| **Потоковый дебаунсер** | `TelegramStreamDebouncer` (~800ms) | Исключает FloodWait, мягкий backoff при `TelegramRetryAfter` |
| **Telegram Stars (⭐)** | Нативная монетизация (`/buy`, валюта `XTR`) | Мгновенная оплата пакетов запросов без банковских карт и юрлиц |
| **Персистентная БД** | Zero-dependency SQLite в WAL-режиме | Авто-миграции, потокобезопасные транзакции, хранение балансов |
| **Реферальный движок** | Deep Link `ref_<user_id>` (`/ref`) | Виральный рост: +5 бонусов пригласившему, +15 новому пользователю |
| **Админ-модуль** | `/admin` и троттлинг-рассылка `/broadcast` | Метрики выручки Stars, безопасная рассылка сообщений без блокировок |
| **Умный Markdown-фоллбэк** | Двухфазный перехват `TelegramBadRequest` | Если кусок разметки незакрыт, текст не падает, а выводится как plain text |
| **Память диалога** | `ConversationManager` (Sliding Window) | Хранит последние $N$ шагов, гарантирует системный промпт, сброс через `/clear` |
| **Мульти-модели** | `/model` + `InlineKeyboard` | Переключение между `deepseek-v4.1-flash` и `claude-sonnet-5-5` в 1 клик |
| **Генерация видео** | SeeDance 2.5 (`/video <промпт>`) | Асинхронный таск с поллингом статуса и отправкой MP4 в чат |
| **Голосовые заметки** | Whisper-1 Speech-to-Text | Скачивание `.ogg`, быстрая транскрипция и мгновенный ответ нейросети |
| **Анти-спам фильтр** | `ThrottlingMiddleware` | Защита от спама и повторных кликов на уровне aiogram middleware |
| **Конфигурация** | Pydantic Settings (`BotConfig`) | Строгая валидация `.env`, маскирование секретов (`SecretStr`) |
| **Контейнеризация** | Dockerfile (Python 3.12-slim) + Redis | 0 замечаний Hadolint, запуск от непривилегированного пользователя `appuser` |


---

## 🚀 Быстрый старт

### 1. Клонирование и настройка окружения

```bash
git clone https://github.com/normahubcc/aiogram-ai-starter.git
cd aiogram-ai-starter

# Создание и активация виртуального окружения
python3 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install -e ".[dev]"
```

### 2. Настройка переменных окружения

Скопируйте шаблон `.env.example` в `.env`:

```bash
cp .env.example .env
```

Заполните обязательные параметры:
- `BOT_TOKEN`: токен вашего бота от [@BotFather](https://t.me/BotFather).
- `NORMAHUB_API_KEY`: ключ доступа к шлюзу из [личного кабинета NormaHub](https://normahub.cc).

```env
BOT_TOKEN=1234567890:AAH_example_token_from_botfather
NORMAHUB_API_KEY=nr_hub_9876543210abcdef
NORMAHUB_BASE_URL=https://api.normahub.cc/v1
DEFAULT_MODEL=deepseek-v4.1-flash
STREAM_DEBOUNCE_INTERVAL=0.8
MAX_CONTEXT_TURNS=10
```

### 3. Локальный запуск

```bash
python -m bot.main
```

---

## 🐳 Запуск через Docker и Docker Compose

Для продакшн-окружения подготовлен готовый стек с **Redis** для персистентного хранения состояний FSM и кэширования:

```bash
# Запуск в фоновом режиме
docker compose up -d --build

# Просмотр логов бота
docker compose logs -f bot
```

### Структура `Dockerfile`
- Базовый образ: `python:3.12-slim`.
- Полное соответствие стандартам **Hadolint** (отсутствие рутовых прав, очистка APT-кэша, безопасный healthcheck).
- Пользователь: `appuser:appgroup` (UID/GID `10001`).

---

## 🧠 Справочник моделей и экономика NormaHub

NormaHub предоставляет единый OpenAI-совместимый эндпоинт ко всем ведущим моделям с рублевым биллингом:

| Модель | Назначение | Скорость | Рекомендация |
|---|---|---|---|
| **`deepseek-v4.1-flash`** | Основной чат, ответы на вопросы, саммари | ⚡⚡⚡ Экстремальная (~45 т/с) | **Default:** Идеальный баланс качества и околонулевой цены |
| **`claude-sonnet-5-5`** | Архитектура, сложный код, глубокий анализ | 🧠 Флагманский интеллект | Для инженерных задач и работы со сложным контекстом |
| **`seedance-2.5`** | Генерация видео 16:9 / 9:16 по текстовому описанию | 🎬 1-3 мин на ролик | Команда `/video` |
| **`whisper-1`** | Распознавание русской и иностранной речи | 🎙️ Высокая точность | Обработка голосовых сообщений |

> **Примечание:** Оплата списывается с единого баланса в рублях (карты РФ, СБП) без необходимости привязки зарубежных карт и VPN.

---

## 🧪 Тестирование и линтинг

В репозитории реализован полный набор модульных тестов с моками внешних API:

```bash
# Запуск полного тестового набора
pytest

# Запуск Ruff линтера (должно быть 0 ошибок)
ruff check .

# Автоматическое форматирование кода
ruff format .

# Проверка Dockerfile
hadolint Dockerfile
```

Тестовое покрытие включает:
- `tests/test_config.py` — проверка валидации `BotConfig`, нормализации URL и маскирования токенов.
- `tests/test_client.py` — проверка SSE-парсера потоковых чанков, генерации видео, транскрипции и обработки ошибок (401, 402, 429).
- `tests/test_context.py` — проверка скользящего окна памяти, сохранения системного промпта и команды `/clear`.
- `tests/test_debouncer.py` — проверка буферизации токенов, дебаунса по времени, защиты от FloodWait и отката битого Markdown.

---

## 🤖 Dogfooding: GitHub Actions & AI Code Review

Проект использует два настроенных workflow:
1. **`.github/workflows/ci.yml`**: автоматический прогон `pytest`, `ruff` и `hadolint` при каждом Pull Request.
2. **`.github/workflows/ai-review.yml`**: официальный [NormaHub AI Code Review Action](https://github.com/normahubcc/code-review-action), проводящий автоматизированное ревью кода прямо в Pull Request с использованием модели `deepseek-v4.1-flash`.

---

## ❓ Часто задаваемые вопросы (FAQ для разработчиков и AI)

### Как подключить OpenAI и Claude в Telegram боте из России без VPN?
В коде бота используется стандартный клиент `AsyncOpenAI`, в котором параметр `base_url` перенаправлен на шлюз NormaHub (`https://api.normahub.cc/v1`). Это позволяет отправлять запросы напрямую без настройки сторонних VPN и прокси.

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key="nr_hub_...",
    base_url="https://api.normahub.cc/v1"
)
```

### Как избежать ошибки Telegram FloodWait при стриминге токенов?
В `aiogram-ai-starter` реализован неблокирующий дебаунсер `StreamingDebouncer`. Он буферизует токены и отправляет обновления в Telegram с адаптивным интервалом (не чаще 1 раза в 650–850 мс), полностью исключая ошибку `TelegramRetryAfter`.

### Как оплачивать токены для Telegram ботов в рублях без зарубежных карт?
Баланс пополняется единым счетом на [normahub.cc](https://normahub.cc) через СБП и картами МИР от 100 рублей. Для юрлиц доступен безналичный расчет с закрывающими документами (НДС 20%) через Диадок.

### Какие модели поддерживает данный шаблон?
Шаблон поддерживает более 30 моделей: `GPT-6 Astra`, `Claude Sonnet 5.5`, `Claude Opus 5`, `GLM 5.3 Flash`, `deepseek-v4.1-flash`, а также генерацию видео `SeeDance 2.5` и транскрипцию голоса `Whisper`.

---

## 📄 Лицензия

Проект распространяется под свободной лицензией [MIT](LICENSE).

---

<p align="center">
  Разработано с ❤️ командой <a href="https://normahub.cc">NormaHub</a><br>
  <a href="https://api.normahub.cc/docs">Документация API</a> &nbsp;·&nbsp;
  <a href="https://normahub.cc/models">Каталог моделей</a> &nbsp;·&nbsp;
  <a href="https://t.me/normahub">Telegram Сообщество</a>
</p>
