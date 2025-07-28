from datetime import datetime
import json
from data_handler import load_user_data
from constants import PRICES_KEY

def calculate_values(user_id: int, target_date: str) -> dict:
    data = load_user_data(user_id)
    dates = sorted([d for d in data.keys() if d != PRICES_KEY])
    if target_date not in dates:
        raise ValueError(f"Нет данных за дату {target_date}")
    idx = dates.index(target_date)
    if idx == 0:
        raise ValueError("Нет предыдущих данных для сравнения")
    prev_date = dates[idx - 1]
    prev = data[prev_date]
    curr = data[target_date]
    prices = data[PRICES_KEY]
    services = []
    total = 0
    # расчет по каждому счетчику
    for key, name in [('light','Свет'),('cold','Холодная вода'),('hot','Горячая вода')]:
        diff = curr.get(key,0) - prev.get(key,0)
        price = prices.get(key)
        cost = diff * price
        total += cost
        services.append({
            'name': name,
            'start': prev.get(key),
            'end': curr.get(key),
            'diff': diff,
            'price': price,
            'total': cost
        })
    # водоотведение
    otvod = services[1]['diff'] + services[2]['diff']
    price_o = prices.get('drainage')
    cost_o = otvod * price_o
    total += cost_o
    services.append({'name':'Водоотведение','diff':otvod,'price':price_o,'total':cost_o})
    return {'services': services, 'total': total,
            'year': datetime.strptime(target_date,'%Y-%m-%d').year,
            'month_old': datetime.strptime(prev_date,'%Y-%m-%d').strftime('%d.%m'),
            'month_now': datetime.strptime(target_date,'%Y-%m-%d').strftime('%d.%m')}