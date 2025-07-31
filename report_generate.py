# report_generator.py
from jinja2 import Template
from datetime import datetime
import os
import asyncio
from playwright.async_api import async_playwright
from data_handler import load_user_data, ensure_user_folder

async def generate_html_report(user_id: int, current_date: str, last_month_date: str) -> tuple:
    """Генерация HTML отчета с заполненными данными"""
    # Загружаем данные
    data = load_user_data(user_id)
    prices = data.get('prices', data.get('Prices', {}))
    
    # Форматируем даты
    prev_date = datetime.strptime(last_month_date, '%Y-%m-%d')
    curr_date = datetime.strptime(current_date, '%Y-%m-%d')
    
    prev_date_formatted = prev_date.strftime('%d.%m')
    curr_date_formatted = curr_date.strftime('%d.%m')
    year = curr_date.strftime('%Y')
    
    # Диапазон дат для имени файла
    date_range = f"{prev_date.strftime('%d-%m-%Y')} - {curr_date.strftime('%d-%m-%Y')}"
    
    # Получаем показания
    prev = data.get(last_month_date, {})
    curr = data.get(current_date, {})
    
    # Свет
    light_prev = prev.get('light', 0)
    light_curr = curr.get('light', 0)
    light_diff = light_curr - light_prev
    light_price = prices.get('light', 0)
    light_cost = light_diff * light_price
    
    # Холодная вода
    cold_prev = prev.get('cold', 0)
    cold_curr = curr.get('cold', 0)
    cold_diff = cold_curr - cold_prev
    cold_price = prices.get('cold', 0)
    cold_cost = cold_diff * cold_price
    
    # Горячая вода
    hot_prev = prev.get('hot', 0)
    hot_curr = curr.get('hot', 0)
    hot_diff = hot_curr - hot_prev
    hot_price = prices.get('hot', 0)
    hot_cost = hot_diff * hot_price
    
    # Водоотведение
    drainage_diff = cold_diff + hot_diff
    drainage_price = prices.get('drainage', 0)
    drainage_cost = drainage_diff * drainage_price
    
    # Общая сумма
    total_cost = light_cost + cold_cost + hot_cost + drainage_cost
    
    # Читаем HTML шаблон
    with open('template/template.html', 'r', encoding='utf-8') as file:
        template_content = file.read()
    
    template = Template(template_content)
    
    # Рендерим HTML с данными
    html_content = template.render(
        year=year,
        prev_date=prev_date_formatted,
        curr_date=curr_date_formatted,
        light_prev=light_prev,
        light_curr=light_curr,
        light_diff=light_diff,
        light_price=f"{light_price:.2f}",
        light_cost=f"{light_cost:.2f}",
        cold_prev=cold_prev,
        cold_curr=cold_curr,
        cold_diff=cold_diff,
        cold_price=f"{cold_price:.2f}",
        cold_cost=f"{cold_cost:.2f}",
        hot_prev=hot_prev,
        hot_curr=hot_curr,
        hot_diff=hot_diff,
        hot_price=f"{hot_price:.2f}",
        hot_cost=f"{hot_cost:.2f}",
        drainage_prev=cold_prev + hot_prev,
        drainage_curr=cold_curr + hot_curr,
        drainage_diff=f"{drainage_diff:.1f}",
        drainage_price=f"{drainage_price:.2f}",
        drainage_cost=f"{drainage_cost:.2f}",
        total_cost=f"{total_cost:.2f}"
    )
    
    return html_content, date_range

async def generate_report_image_async(html_content: str, output_path: str):
    """Асинхронная генерация изображения из HTML с использованием Playwright"""
    # Создаем директорию, если она не существует
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1000, 'height': 600})
        
        # Устанавливаем содержимое страницы
        await page.set_content(html_content)
        
        # Ждем, пока страница полностью загрузится и применятся стили
        await page.wait_for_timeout(2000)  # 2 секунды
        
        # Делаем скриншот
        await page.screenshot(path=output_path, type='png')
        
        await browser.close()

async def generate_and_save_graphical_report(user_id: int, current_date: str, last_month_date: str) -> str:
    """Генерация и сохранение графического отчета"""
    # Генерируем HTML отчет
    html_content, date_range = await generate_html_report(user_id, current_date, last_month_date)
    
    # Создаем путь для сохранения отчета
    user_folder = ensure_user_folder(user_id)
    report_folder = os.path.join(user_folder, 'reports')
    os.makedirs(report_folder, exist_ok=True)
    
    # Имя файла с диапазоном дат
    file_name = f"{date_range}.png"
    image_path = os.path.join(report_folder, file_name)
    
    # Если файл уже существует, добавляем метку времени
    if os.path.exists(image_path):
        timestamp = datetime.now().strftime('%H-%M-%S')
        file_name = f"{date_range} ({timestamp}).png"
        image_path = os.path.join(report_folder, file_name)
    
    try:
        # Асинхронно генерируем изображение
        await generate_report_image_async(html_content, image_path)
        return image_path
    except Exception as e:
        print(f"Ошибка при генерации графического отчета: {e}")
        return None