import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def render_template():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Применение stealth для обхода детекции
        await page.add_init_script("""
        delete navigator.__proto__.webdriver;
        window.chrome = {runtime: {}};
        """)

        # Открытие HTML-файла
        html_path = Path('template/template.html').resolve()
        await page.goto(f'file://{html_path}')

        # Установка размера экрана (700x470)
        await page.set_viewport_size({"width": 700, "height": 490})

        # Сделать скриншот
        await page.screenshot(path="output.png", full_page=False)

        await browser.close()

# Запуск
asyncio.run(render_template())