from datetime import datetime
import json

def calculate_values(target_date: str) -> dict:
    """
    Принимает дату (например, '2025-04-06'), возвращает данные для шаблона
    """
    with open("data/data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # Сортировка дат
    dates = sorted(data.keys())
    if target_date not in dates:
        raise ValueError(f"Нет данных за дату {target_date}")

    # Находим предыдущую дату
    idx = dates.index(target_date)
    if idx == 0:
        raise ValueError("Нет предыдущих данных для сравнения")

    prev_date = dates[idx - 1]


    # Парсим даты
    target = datetime.strptime(target_date, "%Y-%m-%d")
    prev = datetime.strptime(prev_date, "%Y-%m-%d")

    # Форматируем как "DD.MM"
    month_old = prev.strftime("%d.%m")
    month_now = target.strftime("%d.%m")
    year = target.year  # Год как "YYYY"

    # Вычисление разницы
    current = data[target_date]
    previous = data[prev_date]

    services = []
    total = 0

    # Настройки: цена за единицу
    PRICES = {
        "cold": 50,    # Холодная вода
        "hot": 150,    # Горячая вода
        "light": 2,    # Свет
    }

    # Словарь для хранения diff
    diffs = {}

    # Расчёт основных услуг
    for key, name, css_class in [
        ("light", "Свет", "glow-svet"),
        ("cold", "Холодная вода", "glow-holodnaja"),
        ("hot", "Горячая вода", "glow-goryachaja"),
    ]:
        start = previous[key]
        end = current[key]
        diff = end - start
        diffs[key] = diff

        price = PRICES[key]
        total_service = diff * price
        total += total_service

        services.append({
            "name": name,
            "start": start,
            "end": end,
            "diff": f"{diff} м<sup>3</sup>",
            "price": f"{price} руб/м<sup>3</sup>",
            "total": f"{total_service} ₽",
            "class": css_class
        })

    # Расчёт водоотведения
    cold_diff = diffs.get("cold", 0)
    hot_diff = diffs.get("hot", 0)
    otvod_diff = cold_diff + hot_diff
    otvod_price = 50  # Цена за куб. метр водоотведения
    otvod_total = otvod_diff * otvod_price
    total += otvod_total

    services.append({
        "name": "Водоотведение",
        "start": "-",  # Не отображается в таблице
        "end": "-",    # Не отображается в таблице
        "diff": f"{otvod_diff} кВт",
        "price": f"{otvod_price} руб/кВт",
        "total": f"{otvod_total} ₽",
        "class": "glow-otvod"
    })

    return {
        "services": services,
        "total": f"{total} ₽",
        "year": str(year),
        "month_old": month_old,
        "month_now": month_now
    }