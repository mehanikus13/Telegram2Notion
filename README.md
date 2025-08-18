# Telegram2Notion Бот

Этот телеграм-бот позволяет быстро сохранять ваши идеи и задачи в Notion с помощью простого интерфейса с кнопками. Бот умеет обрабатывать как текстовые, так и голосовые сообщения.

## Функционал

-   **Простой интерфейс**: Две кнопки "Идея" и "Задача" для быстрой классификации записей.
-   **Гибкость**: Сохраняет записи в разные базы данных Notion в зависимости от выбранной категории.
-   **Анализ ссылок**: При отправке ссылки бот автоматически извлекает контент страницы, генерирует краткое саммари и теги с помощью OpenAI, а затем сохраняет всё в отдельную базу данных.
-   **Транскрипция голоса**: Автоматически расшифровывает голосовые сообщения с помощью OpenAI Whisper и сохраняет их как текст.
-   **Поддержка форматов**: Принимает текст, голосовые сообщения и ссылки.

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
2.  **Важно**: Основная колонка в обеих базах должна называться `Name` и иметь тип `Title`. Либо задайте имена колонок через переменные `.env` (см. ниже).
3.  Откройте страницу с базой данных в Notion.
4.  Скопируйте URL страницы. Он будет выглядеть примерно так: `https://www.notion.so/your-workspace/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX?v=...`
5.  Часть `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` — это и есть ID вашей базы данных. Скопируйте его.
6.  Вставьте ID в соответствующие поля в `.env`.
7.  **Не забудьте "пригласить" вашу интеграцию в обе базы данных!** Нажмите на три точки в правом верхнем углу базы данных, выберите "Add connections" и найдите вашу интеграцию по имени.

#### `OPENAI_API_KEY`
1.  Перейдите на страницу [API ключей OpenAI](https://platform.openai.com/account/api-keys).
2.  Нажмите "Create new secret key".
3.  Скопируйте ключ и вставьте его в `.env`.

#### База данных для Ссылок (`NOTION_DATABASE_ID_LINK`)
Для работы функции сохранения ссылок вам потребуется третья база данных со специфической структурой.

1.  Создайте новую базу данных в Notion.
2.  Добавьте в нее следующие столбцы (properties) с **точными** именами и типами, либо задайте их в `.env`:
    -   `Name` (тип `Title`) - для заголовка страницы. Можно переопределить через `NOTION_LINK_TITLE_PROP`.
    -   `URL` (тип `URL`) - для оригинальной ссылки. Можно переопределить через `NOTION_LINK_URL_PROP`.
    -   `Tags` (тип `Multi-select`) - для сгенерированных тегов. Можно переопределить через `NOTION_LINK_TAGS_PROP`.
3.  Скопируйте ID этой базы данных и вставьте в поле `NOTION_DATABASE_ID_LINK` в вашем `.env` файле.
4.  Не забудьте дать доступ вашей интеграции к этой базе данных, как вы делали для баз "Идей" и "Задач".

Пример заполненного `.env` файла:
```
TELEGRAM_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
NOTION_TOKEN=secret_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
NOTION_DATABASE_ID_IDEA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
NOTION_DATABASE_ID_TASK=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
NOTION_DATABASE_ID_LINK=cccccccccccccccccccccccccccccccc
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_IDEA_TITLE_PROP=Name
NOTION_TASK_TITLE_PROP=Name
NOTION_TASK_TYPE_PROP=Тип
NOTION_TASK_IMPORTANCE_PROP=Важность
NOTION_TASK_SPEED_PROP=Скорость
NOTION_TASK_INTEREST_PROP=Интерес
NOTION_LINK_TITLE_PROP=Name
NOTION_LINK_URL_PROP=URL
NOTION_LINK_TAGS_PROP=Tags
```

## 5. Запуск бота

После того как вы настроили `.env` файл, запустите бота командой:

```bash
python bot.py
```

Бот начнет работать и будет готов принимать ваши команды в Telegram.

## 6. Как пользоваться

1.  Найдите вашего бота в Telegram и отправьте ему команду `/start`.
2.  Нажмите на одну из кнопок: "Идея", "Задача" или "Ссылка".
3.  В зависимости от выбора:
    -   Для **Идеи** или **Задачи**: отправьте текстовое или голосовое сообщение.
    -   Для **Ссылки**: отправьте URL-адрес.
4.  Бот обработает ваш запрос, сохранит его в соответствующую базу данных в Notion и пришлет подтверждение.
5.  Для отмены текущей операции в любой момент используйте команду `/cancel`.