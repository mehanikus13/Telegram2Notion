import os
import logging
import notion_client

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_notion_page(database_id: str, text: str):
    """
    Создает новую запись в указанной базе данных Notion.

    Args:
        database_id: ID базы данных Notion.
        text: Текст для заголовка новой страницы.
    """
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        logger.error("NOTION_TOKEN не найден в переменных окружения.")
        return

    notion = notion_client.Client(auth=notion_token)

    try:
        new_page_data = {
            "parent": {"database_id": database_id},
            "properties": {
                "Name": {  # 'Name' - это стандартное имя для основного столбца Title
                    "title": [
                        {
                            "text": {
                                "content": text
                            }
                        }
                    ]
                }
            }
        }

        response = notion.pages.create(**new_page_data)
        logger.info("Успешно создана новая страница в Notion.")
        return response

    except notion_client.APIResponseError as e:
        logger.error(f"Ошибка при работе с Notion API: {e}")
        return None


def create_link_page(database_id: str, title: str, summary: str, url: str, tags: list):
    """
    Создает новую страницу для ссылки в Notion с заголовком, URL, тегами и саммари.
    """
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        logger.error("NOTION_TOKEN не найден в переменных окружения.")
        return None

    notion = notion_client.Client(auth=notion_token)

    # 1. Создаем страницу с основными свойствами
    try:
        page_properties = {
            "Name": {"title": [{"text": {"content": title}}]},
            "URL": {"url": url},
            "Tags": {"multi_select": [{"name": tag} for tag in tags]}
        }

        new_page_response = notion.pages.create(
            parent={"database_id": database_id},
            properties=page_properties
        )
        page_id = new_page_response['id']
        logger.info(f"Успешно создана страница Notion с ID: {page_id}")

    except notion_client.APIResponseError as e:
        logger.error(f"Ошибка при создании страницы Notion: {e}")
        logger.error("Убедитесь, что в базе данных есть свойства 'Name' (Title), 'URL' (URL) и 'Tags' (Multi-select).")
        return None

    # 2. Добавляем саммари как контент на страницу
    try:
        if summary:
            # Разделяем саммари на параграфы
            summary_blocks = []
            for paragraph in summary.split('\n'):
                if paragraph: # Пропускаем пустые строки
                    summary_blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": paragraph}}]
                        }
                    })

            if summary_blocks:
                notion.blocks.children.append(
                    block_id=page_id,
                    children=summary_blocks
                )
                logger.info(f"Успешно добавлено саммари на страницу {page_id}")

    except notion_client.APIResponseError as e:
        logger.error(f"Ошибка при добавлении контента на страницу Notion: {e}")
        # Страница уже создана, так что не возвращаем ошибку, а просто логируем

    return new_page_response
