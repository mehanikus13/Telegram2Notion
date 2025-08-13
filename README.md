# Telegram2Notion Бот

Этот телеграм-бот позволяет быстро сохранять ваши идеи и задачи в Notion с помощью простого интерфейса с кнопками. Бот умеет обрабатывать как текстовые, так и голосовые сообщения.

## Функционал

-   **Простой интерфейс**: Две кнопки "Идея" и "Задача" для быстрой классификации записей.
-   **Гибкость**: Сохраняет записи в разные базы данных Notion в зависимости от выбранной категории.
-   **Транскрипция голоса**: Автоматически расшифровывает голосовые сообщения с помощью OpenAI Whisper и сохраняет их как текст.
-   **Поддержка форматов**: Принимает как текстовые, так и голосовые сообщения.

## Установка и настройка

### 1. Клонирование репозитория
```bash
git clone https://github.com/ваш-логин/Telegram2Notion.git
cd Telegram2Notion
```

### 2. Установка ffmpeg

Для обработки голосовых сообщений боту требуется `ffmpeg`. Установите его с помощью менеджера пакетов вашей системы.

-   **На macOS (используя Homebrew):**
    ```bash
    brew install ffmpeg
    ```
-   **На Debian/Ubuntu:**
    ```bash
    sudo apt update && sudo apt install ffmpeg
    ```
-   **На Windows (используя Chocolatey):**
    ```bash
    choco install ffmpeg
    ```

### 3. Создание виртуального окружения и установка зависимостей
Рекомендуется использовать виртуальное окружение для изоляции зависимостей проекта.

```bash
# Создание виртуального окружения
python -m venv venv

# Активация (Windows)
venv\Scripts\activate

# Активация (macOS/Linux)
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Вам нужно создать файл `.env` в корневой директории проекта. Вы можете скопировать и переименовать `.env.example`.

```bash
cp .env.example .env
```

Теперь откройте файл `.env` и заполните его вашими данными.

#### `TELEGRAM_TOKEN`
1.  Найдите бота `@BotFather` в Telegram.
2.  Отправьте ему команду `/newbot`.
3.  Следуйте инструкциям, чтобы создать нового бота.
4.  BotFather пришлет вам токен. Скопируйте его в `.env`.

#### `NOTION_TOKEN`
1.  Перейдите на страницу [ваших интеграций Notion](https://www.notion.so/my-integrations).
2.  Нажмите "New integration".
3.  Дайте интеграции имя (например, "Telegram Bot") и выберите рабочее пространство.
4.  Нажмите "Submit".
5.  Скопируйте "Internal Integration Token" и вставьте его в `.env`.

#### `NOTION_DATABASE_ID_IDEA` и `NOTION_DATABASE_ID_TASK`
1.  Создайте в Notion две базы данных (Database - Full page): одну для идей, другую для задач.
2.  **Важно**: Основная колонка в обеих базах должна называться `Name` и иметь тип `Title`.
3.  Откройте страницу с базой данных в Notion.
4.  Скопируйте URL страницы. Он будет выглядеть примерно так: `https://www.notion.so/your-workspace/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX?v=...`
5.  Часть `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` — это и есть ID вашей базы данных. Скопируйте его.
6.  Вставьте ID в соответствующие поля в `.env`.
7.  **Не забудьте "пригласить" вашу интеграцию в обе базы данных!** Нажмите на три точки в правом верхнем углу базы данных, выберите "Add connections" и найдите вашу интеграцию по имени.

#### `OPENAI_API_KEY`
1.  Перейдите на страницу [API ключей OpenAI](https://platform.openai.com/account/api-keys).
2.  Нажмите "Create new secret key".
3.  Скопируйте ключ и вставьте его в `.env`.

Пример заполненного `.env` файла:
```
TELEGRAM_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
NOTION_TOKEN=secret_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
NOTION_DATABASE_ID_IDEA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
NOTION_DATABASE_ID_TASK=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## 5. Запуск бота

После того как вы настроили `.env` файл, запустите бота командой:

```bash
python bot.py
```

Бот начнет работать и будет готов принимать ваши команды в Telegram.

## 6. Как пользоваться

1.  Найдите вашего бота в Telegram и отправьте ему команду `/start`.
2.  Нажмите на кнопку "Идея" или "Задача".
3.  Отправьте текстовое или голосовое сообщение.
4.  Бот сохранит ваше сообщение в соответствующую базу данных в Notion и пришлет подтверждение.
5.  Для отмены текущей операции в любой момент используйте команду `/cancel`.