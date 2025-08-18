import os
import logging
import notion_client

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_notion_client():
    """Инициализирует и возвращает клиент Notion."""
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        logger.error("NOTION_TOKEN не найден в переменных окружения.")
        return None
    return notion_client.Client(auth=notion_token)

def get_database_properties(database_id: str) -> dict | None:
    """
    Получает свойства базы данных Notion, особенно опции для полей типа 'select'.
    """
    notion = get_notion_client()
    if not notion:
        return None

    try:
        response = notion.databases.retrieve(database_id=database_id)
        properties = {}
        for name, prop_data in response.get('properties', {}).items():
            if prop_data.get('type') in ['select', 'multi_select']:
                properties[name] = {
                    'type': prop_data['type'],
                    'options': [opt['name'] for opt in prop_data[prop_data['type']]['options']]
                }
        return properties
    except notion_client.APIResponseError as e:
        logger.error(f"Ошибка при получении свойств базы данных {database_id}: {e}")
        return None

def update_page_properties(page_id: str, properties_to_update: dict):
    """
    Обновляет свойства существующей страницы Notion.
    """
    notion = get_notion_client()
    if not notion:
        return None

    try:
        notion.pages.update(page_id=page_id, properties=properties_to_update)
        logger.info(f"Успешно обновлена страница с ID: {page_id}")
        return True
    except notion_client.APIResponseError as e:
        logger.error(f"Ошибка при обновлении страницы {page_id}: {e}")
        return False

def create_notion_page(database_id: str, title_property_name: str, title_text: str) -> dict | None:
    """
    Создает простую страницу в Notion с одним свойством Title.
    """
    notion = get_notion_client()
    if not notion:
        return None

    try:
        new_page_data = {
            "parent": {"database_id": database_id},
            "properties": {
                title_property_name: {
                    "title": [{"text": {"content": title_text}}]
                }
            }
        }
        response = notion.pages.create(**new_page_data)
        logger.info("Успешно создана новая страница в Notion.")
        return response
    except notion_client.APIResponseError as e:
        logger.error(f"Ошибка при создании страницы Notion: {e}")
        return None

def create_link_page(database_id: str, title_prop: str, url_prop: str, tags_prop: str, data: dict):
    """
    Создает страницу для ссылки в Notion с кастомными названиями свойств.
    """
    notion = get_notion_client()
    if not notion:
        return None

    page_properties = {
        title_prop: {"title": [{"text": {"content": data.get('title', 'Без заголовка')}}]},
        url_prop: {"url": data.get('url')},
        tags_prop: {"multi_select": [{"name": tag} for tag in data.get('tags', [])]}
    }

    try:
        new_page_response = notion.pages.create(
            parent={"database_id": database_id},
            properties=page_properties
        )
        page_id = new_page_response['id']
        logger.info(f"Успешно создана страница для ссылки с ID: {page_id}")

        # Добавляем саммари как контент на страницу
        summary = data.get('summary')
        if summary:
            summary_blocks = []
            for p in summary.split('\n'):
                if p: # Игнорируем пустые строки
                    summary_blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": p}}]}
                    })

            if summary_blocks:
                notion.blocks.children.append(block_id=page_id, children=summary_blocks)
                logger.info(f"Успешно добавлено саммари на страницу {page_id}")

        return new_page_response
    except notion_client.APIResponseError as e:
        logger.error(f"Ошибка при создании страницы для ссылки: {e}")
        return None
