import os
import logging
import requests
from bs4 import BeautifulSoup
from openai import AsyncOpenAI

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Настройка клиента OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
else:
    logger.warning("OPENAI_API_KEY не найден. Модуль обработки URL не будет работать.")
    openai_client = None

def get_url_content(url: str) -> dict | None:
    """
    Получает содержимое веб-страницы по URL.
    Возвращает словарь с заголовком и основным текстом.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Проверка на HTTP ошибки

        soup = BeautifulSoup(response.text, 'html.parser')

        original_title = soup.title.string if soup.title else "Без заголовка"

        # Простой способ извлечь текст: взять все параграфы
        paragraphs = soup.find_all('p')
        text = "\n".join([p.get_text() for p in paragraphs])

        if not text:
            # Если параграфов нет, попробуем извлечь основной контент
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)

        return {"title": original_title, "text": text}
    except requests.RequestException as e:
        logger.error(f"Ошибка при загрузке URL {url}: {e}")
        return None

async def get_summary_and_tags_from_openai(text: str, original_title: str) -> dict | None:
    """
    Генерирует заголовок, саммари и теги для текста с помощью OpenAI.
    """
    if not openai_client:
        return None

    # Обрезаем текст, чтобы избежать превышения лимита токенов
    max_chars = 15000
    truncated_text = text[:max_chars]

    system_prompt = "You are an expert content analyst. Your task is to process the text from a web page and provide a concise title, a short summary, and relevant tags."
    user_prompt = f"""
    Here is the text from a web page. The original title was "{original_title}".

    Text:
    ---
    {truncated_text}
    ---

    Please analyze the text and provide the following in the specified format:
    1.  A new, concise, and engaging title for this content.
    2.  A summary of the content in 2-4 sentences.
    3.  A list of 3-5 relevant keywords or tags, separated by commas.

    Please format your response exactly as follows:
    Title: [Your generated title here]
    Summary: [Your generated summary here]
    Tags: [tag1, tag2, tag3]
    """

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
        )

        content = response.choices[0].message.content

        # Парсим структурированный ответ
        parsed_data = {}
        for line in content.split('\n'):
            if line.startswith("Title:"):
                parsed_data['title'] = line.replace("Title:", "").strip()
            elif line.startswith("Summary:"):
                parsed_data['summary'] = line.replace("Summary:", "").strip()
            elif line.startswith("Tags:"):
                tags_str = line.replace("Tags:", "").strip()
                parsed_data['tags'] = [tag.strip() for tag in tags_str.split(',')]

        if 'title' not in parsed_data or 'summary' not in parsed_data:
            raise ValueError("Не удалось распарсить ответ от OpenAI")

        return parsed_data
    except Exception as e:
        logger.error(f"Ошибка при работе с OpenAI API: {e}")
        return None


async def process_url(url: str) -> dict | None:
    """
    Полный процесс обработки URL: скачивание, анализ, генерация данных.
    """
    logger.info(f"Начинаю обработку URL: {url}")

    content = get_url_content(url)
    if not content or not content.get('text'):
        logger.warning("Не удалось извлечь контент со страницы.")
        return {"title": content.get('title') if content else url, "summary": "Не удалось извлечь основной текст.", "tags": [], "url": url}

    logger.info("Контент извлечен, отправляю в OpenAI для анализа...")

    processed_data = await get_summary_and_tags_from_openai(content['text'], content['title'])

    if not processed_data:
        logger.warning("Не удалось получить анализ от OpenAI. Использую исходный заголовок.")
        return {"title": content['title'], "summary": "Анализ не удался.", "tags": [], "url": url}

    processed_data['url'] = url
    logger.info(f"URL успешно обработан: {processed_data['title']}")

    return processed_data
