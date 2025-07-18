import asyncio
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from playwright.async_api import async_playwright
import os
from calculate import calculate_values

# Настройка Jinja2
TEMPLATE_DIR = Path(__file__).parent
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

async def generate_image(target_date: str):
    try:
        # Вычисление данных
        data = calculate_values(target_date)
    except Exception as e:
        return f"Ошибка: {str(e)}"

    try:
        # Рендеринг HTML
        template = env.get_template("template/template.html")
        rendered_html = template.render(**data)

        # Сохранение временного HTML
        temp_file = TEMPLATE_DIR / "template/temp_rendered.html"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        # Рендеринг через Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Установка stealth
            await page.add_init_script("""
            delete navigator.__proto__.webdriver;
            window.chrome = {runtime: {}};
            """)

            # Открытие HTML
            html_path = temp_file.resolve()
            await page.goto(f"file://{html_path}")

            # Установка размера экрана
            await page.set_viewport_size({"width": 1920, "height": 900})
            await page.evaluate("() => document.body.style.zoom = 2")  # Масштабирование

            # Сделать скриншот
            await page.screenshot(path="data/reports/output.png", full_page=False, scale="device")

            await browser.close()

        # Удаление временного файла
        os.remove(temp_file)

    except Exception as e:
        return f"Ошибка генерации изображения: {str(e)}"

    return "data/reports/output.png"