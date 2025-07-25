# HomeMeters

Удобный Telegram‑бот для учёта и автоматического формирования отчётов по показаниям счётчиков (электричество, горячая и холодная вода).

---

## 📋 Описание проекта

**HomeMeters** позволяет:
- Принимать от пользователя показания счётчиков через Telegram‑бота.
- Сохранять текстовые данные в JSON-файл.
- Принимать и сохранять фотографии счётчиков в папку по датам.
- Автоматически генерировать отчёт в формате PNG на основе HTML/CSS‑шаблона и отправлять его пользователю.
- В перспективе развёртываться в Docker-контейнере на домашнем сервере или VPS.

---

## ⚙️ Технологии

- **Python 3.12+**  
- **Telegram Bot API** (библиотека `python-telegram-bot`)  
- **Jinja2** — шаблонизация HTML  
- **HTML / CSS** — шаблон отчёта  
- **Playwright+Chromium** — конвертация HTML в PNG/PDF  
- **Docker** (`python:3.12-slim`)  
- **JSON** — хранение показаний  

---