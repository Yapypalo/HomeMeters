import os
import json
from datetime import date
from constants import DATA_DIR, PRICES_KEY

def ensure_user_folder(user_id: int):
    base = os.path.join(DATA_DIR, str(user_id))
    # Создаем основную папку и подпапки
    os.makedirs(base, exist_ok=True)
    os.makedirs(os.path.join(base, 'photos'), exist_ok=True)
    os.makedirs(os.path.join(base, 'reports'), exist_ok=True)
    return base

def load_user_data(user_id: int) -> dict:
    path = os.path.join(ensure_user_folder(user_id), 'data.json')
    if not os.path.exists(path):
        # Инициализируем с нулевыми ценами
        data = {
            PRICES_KEY: {
                'cold': 0,
                'hot': 0,
                'light': 0,
                'drainage': 0
            }
        }
        _save(path, data)
        return data
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save(path: str, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Запись показаний на дату
def write_reading(user_id: int, meter: str, value: int, target_date: str=None):
    data = load_user_data(user_id)
    if target_date is None:
        target_date = date.today().isoformat()
    day = data.get(target_date, {})
    day[meter] = value
    data[target_date] = day
    _save(os.path.join(ensure_user_folder(user_id), 'data.json'), data)

# Изменение цен
def update_price(user_id: int, meter: str, new_price: float):
    data = load_user_data(user_id)
    data[PRICES_KEY][meter] = new_price
    _save(os.path.join(ensure_user_folder(user_id), 'data.json'), data)

# Получить список дат
def list_dates(user_id: int):
    data = load_user_data(user_id)
    return [d for d in data.keys() if d != PRICES_KEY]

# Загрузка данных за конкретную дату
def get_day_data(user_id: int, target_date: str) -> dict:
    data = load_user_data(user_id)
    return data.get(target_date, {})

def ensure_user_folder(user_id: int) -> str:
    """Создает и возвращает путь к папке пользователя"""
    user_folder = os.path.join('users_data', str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder