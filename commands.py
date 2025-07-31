from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from data_handler import write_reading, load_user_data, get_day_data, update_price, list_dates, ensure_user_folder
from datetime import date, datetime, timedelta
import asyncio
import re
import os
import json
import logging

# Настройка логирования для отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация показаний
METERS = [
    {'key': 'light', 'name': 'Свет', 'unit': 'кВт*ч', 'icon': '💡'},
    {'key': 'cold', 'name': 'Холодная вода', 'unit': 'м³', 'icon': '🧊'},
    {'key': 'hot', 'name': 'Горячая вода', 'unit': 'м³', 'icon': '🔥'}
]

# Конфигурация для цен
PRICE_ITEMS = [
    {'key': 'light', 'name': 'Свет', 'unit': 'кВт*ч'},
    {'key': 'cold', 'name': 'Холодная вода', 'unit': 'м³'},
    {'key': 'hot', 'name': 'Горячая вода', 'unit': 'м³'},
    {'key': 'drainage', 'name': 'Водоотведение', 'unit': 'м³'}
]

# Состояния для ConversationHandler
READING_STATE = 1
PRICE_MENU = 2
PRICE_WAITING = 3
VIEW_DATES = 4
VIEW_DETAILS = 5
EDIT_READING = 6
EDIT_DATE = 7
VIEW_REPORT = 8

async def delete_message_after_delay(chat_id: int, message_id: int, delay: int = 3, bot=None):
    """Удаляет сообщение через заданное количество секунд"""
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение: {e}")

async def handle_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фотографий от пользователя (не более 3-х в день)"""
    user_id = update.effective_user.id
    
    # Создаем папку пользователя, если не существует
    user_folder = ensure_user_folder(user_id)
    photos_folder = os.path.join(user_folder, 'photos')
    os.makedirs(photos_folder, exist_ok=True)
    
    # Создаем папку за текущую дату
    today = date.today().isoformat()
    today_folder = os.path.join(photos_folder, today)
    os.makedirs(today_folder, exist_ok=True)
    
    # Проверяем количество фото за сегодня
    existing_photos = [
        f for f in os.listdir(today_folder) 
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))
    ]
    
    if len(existing_photos) >= 3:
        msg = await update.message.reply_text(
            "📸 Вы достигли лимита в 3 фотографии за день.",
            reply_to_message_id=update.message.message_id
        )
        
        # Удаляем сообщение пользователя через 1 секунду
        asyncio.create_task(delete_message_after_delay(
            update.effective_chat.id, 
            update.message.message_id, 
            1, 
            context.bot
        ))
        
        # Удаляем сообщение бота через 3 секунды
        asyncio.create_task(delete_message_after_delay(
            update.effective_chat.id, 
            msg.message_id, 
            3, 
            context.bot
        ))
        return
    
    # Получаем самое большое фото
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    
    # Генерируем уникальное имя файла
    timestamp = int(datetime.now().timestamp())
    file_name = f"{timestamp}.jpg"
    file_path = os.path.join(today_folder, file_name)
    
    try:
        # Скачиваем и сохраняем фото
        await file.download_to_drive(file_path)
        
        # Отправляем подтверждение
        msg = await update.message.reply_text(
            f"📸 Фотография сохранена ({len(existing_photos)+1}/3)",
            reply_to_message_id=update.message.message_id
        )
        
        # Удаляем сообщение пользователя через 1.5 секунды
        asyncio.create_task(delete_message_after_delay(
            update.effective_chat.id, 
            update.message.message_id, 
            2, 
            context.bot
        ))
        
        # Удаляем сообщение бота через 3 секунды
        asyncio.create_task(delete_message_after_delay(
            update.effective_chat.id, 
            msg.message_id, 
            3, 
            context.bot
        ))
    except Exception as e:
        logger.error(f"Ошибка при сохранении фото: {e}")
        msg = await update.message.reply_text(
            "Произошла ошибка при сохранении фотографии.",
            reply_to_message_id=update.message.message_id
        )
        
        # Удаляем сообщение пользователя через 1.5 секунды
        asyncio.create_task(delete_message_after_delay(
            update.effective_chat.id, 
            update.message.message_id, 
            1.5, 
            context.bot
        ))
        
        # Удаляем сообщение бота через 3 секунды
        asyncio.create_task(delete_message_after_delay(
            update.effective_chat.id, 
            msg.message_id, 
            3, 
            context.bot
        ))

def get_system_status(user_id: int) -> str:
    """Проверяет системное состояние и возвращает соответствующее сообщение"""
    data = load_user_data(user_id)
    prices = data.get('prices', data.get('Prices', {}))
    
    # Проверяем, есть ли ненулевые цены
    has_non_zero_prices = any(prices.get(item['key'], 0) > 0 for item in PRICE_ITEMS)
    
    # Проверяем, есть ли данные за текущий месяц
    today = date.today().isoformat()
    current_month = today[:7]  # YYYY-MM
    has_current_month_data = False
    
    for date_str in data.keys():
        if date_str.startswith(current_month) and date_str != 'prices' and date_str != 'Prices':
            has_current_month_data = True
            break
    
    # Формируем сообщение
    if not has_non_zero_prices:
        return "⚠️ *Внимание!* Стоимость услуг не установлена. Пожалуйста, установите тарифы через меню 'Изменить стоимость'.\n\n"
    
    if not has_current_month_data:
        return "ℹ️ *Совет:* Вы еще не ввели показания за текущий месяц.\n\n"
    
    if has_current_month_data:
        return "✅ *Информация:* Показания за текущий месяц уже внесены.\n\n"
    
    return ""

def get_welcome_message(user_id: int = None):
    base_message = "👋 Добро пожаловать в бот учёта коммунальных платежей!\n\n"
    
    if user_id is not None:
        status_message = get_system_status(user_id)
        return status_message + base_message + (
            "Я помогу вам:\n"
            "• Фиксировать показания счётчиков\n"
            "• Рассчитывать стоимость услуг\n"
            "• Сравнивать расходы за разные периоды"
        )
    
    return base_message + (
        "Я помогу вам:\n"
        "• Фиксировать показания счётчиков\n"
        "• Рассчитывать стоимость услуг\n"
        "• Сравнивать расходы за разные периоды"
    )

def get_welcome_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Добавить данные", callback_data="add_data")],
        [InlineKeyboardButton("💰 Изменить стоимость", callback_data="price_menu")],
        [InlineKeyboardButton("📅 Посмотреть показания", callback_data="view_dates")],
        [InlineKeyboardButton("📊 Последний отчет", callback_data="view_last_report")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_price_menu_keyboard(user_id: int):
    """Генерация клавиатуры с текущими ценами"""
    data = load_user_data(user_id)
    # Исправлено: проверяем оба возможных ключа для совместимости.
    prices = data.get('prices', data.get('Prices', {}))
    
    keyboard = []
    for item in PRICE_ITEMS:
        price = prices.get(item['key'], 0)
        text = f"{item['name']} - {price:.2f} руб/{item['unit']}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"price_edit:{item['key']}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def format_date(date_str: str) -> str:
    """Форматирование даты из YYYY-MM-DD в ДД.ММ.ГГГГ"""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%d.%m.%Y')
    except:
        return date_str

def parse_date(date_str: str) -> str:
    """Парсинг даты из ДД.ММ.ГГГГ в YYYY-MM-DD"""
    try:
        # Попробуем разные форматы
        for fmt in ['%d.%m.%Y', '%d.%m.%y', '%d/%m/%Y', '%d/%m/%y']:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        # Если ничего не подошло, попробуем YYYY-MM-DD напрямую
        datetime.strptime(date_str, '%Y-%m-%d')
        return date_str
    except:
        return None

def get_last_month_date(today_date: str) -> str:
    """Возвращает дату ровно месяц назад от today_date"""
    today = datetime.strptime(today_date, '%Y-%m-%d')
    year = today.year
    month = today.month - 1
    if month == 0:
        month = 12
        year -= 1
    
    # Проверяем, существует ли такой день в предыдущем месяце
    try:
        last_month = date(year, month, today.day)
    except ValueError:
        # Если в предыдущем месяце меньше дней (например, 31 марта -> 28/29 февраля)
        # Берем последний день предыдущего месяца
        last_month = date(year, month, 1) - timedelta(days=1)
    
    return last_month.isoformat()

def generate_monthly_report(user_id: int, current_date: str, last_month_date: str) -> str:
    """Генерация текстового отчета за месяц в виде таблицы"""
    data = load_user_data(user_id)
    prices = data.get('prices', data.get('Prices', {}))
    
    # Форматируем даты для отображения
    prev_date_formatted = datetime.strptime(last_month_date, '%Y-%m-%d').strftime('%d.%m.%Y')
    curr_date_formatted = datetime.strptime(current_date, '%Y-%m-%d').strftime('%d.%m.%Y')
    
    # Заголовок отчета
    report = f"📊 *Ежемесячный отчет*\n"
    report += f"Период: {prev_date_formatted} — {curr_date_formatted}\n\n"
    
    # Заголовки таблицы (сокращенные для лучшего отображения на мобильных)
    table = "```\n"
    table += "Услуга | Пр | Тк | Разн | Тариф | Сумма\n"
    table += "-------|----|----|------|-------|------\n"
    
    # Получаем показания
    prev = data.get(last_month_date, {})
    curr = data.get(current_date, {})
    
    total_cost = 0
    services = []
    
    # Свет
    light_prev = prev.get('light', 0)
    light_curr = curr.get('light', 0)
    light_diff = light_curr - light_prev
    light_price = prices.get('light', 0)
    light_cost = light_diff * light_price
    total_cost += light_cost
    services.append({
        'name': 'Свет',
        'unit': 'кВт*ч',
        'icon': '💡',
        'prev': light_prev,
        'curr': light_curr,
        'diff': light_diff,
        'price': light_price,
        'cost': light_cost
    })
    
    # Холодная вода
    cold_prev = prev.get('cold', 0)
    cold_curr = curr.get('cold', 0)
    cold_diff = cold_curr - cold_prev
    cold_price = prices.get('cold', 0)
    cold_cost = cold_diff * cold_price
    total_cost += cold_cost
    services.append({
        'name': 'ХВ',
        'full_name': 'Холодная вода',
        'unit': 'м³',
        'icon': '🧊',
        'prev': cold_prev,
        'curr': cold_curr,
        'diff': cold_diff,
        'price': cold_price,
        'cost': cold_cost
    })
    
    # Горячая вода
    hot_prev = prev.get('hot', 0)
    hot_curr = curr.get('hot', 0)
    hot_diff = hot_curr - hot_prev
    hot_price = prices.get('hot', 0)
    hot_cost = hot_diff * hot_price
    total_cost += hot_cost
    services.append({
        'name': 'ГВ',
        'full_name': 'Горячая вода',
        'unit': 'м³',
        'icon': '🔥',
        'prev': hot_prev,
        'curr': hot_curr,
        'diff': hot_diff,
        'price': hot_price,
        'cost': hot_cost
    })
    
    # Водоотведение
    drainage_diff = cold_diff + hot_diff
    drainage_price = prices.get('drainage', 0)
    drainage_cost = drainage_diff * drainage_price
    total_cost += drainage_cost
    services.append({
        'name': 'Водоотв',
        'full_name': 'Водоотведение',
        'unit': 'м³',
        'icon': '💧',
        'prev': None,
        'curr': None,
        'diff': drainage_diff,
        'price': drainage_price,
        'cost': drainage_cost
    })
    
    # Формируем таблицу
    for service in services:
        # Используем короткое название для таблицы
        name = service['name'][:6].ljust(6)
        
        if service.get('prev') is None:
            prev = '—'.ljust(3)
            curr = '—'.ljust(3)
            diff = f"{service['diff']:.1f}".ljust(4)
        else:
            prev = str(service['prev'])[:3].ljust(3)
            curr = str(service['curr'])[:3].ljust(3)
            diff = str(service['diff'])[:4].ljust(4)
        
        price = f"{service['price']:.2f}"[:5].ljust(5)
        cost = f"{service['cost']:.2f}"[:6].ljust(6)
        
        table += f"{name} | {prev} | {curr} | {diff} | {price} | {cost}\n"
    
    table += "```"
    
    # Добавляем итоговую сумму
    report += table
    report += f"\n💰 *Итого*: {total_cost:.2f} руб"
    
    return report

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    load_user_data(user_id)
    
    # Удаляем предыдущий отчет, если он есть
    await delete_previous_report(update, context)
    
    # Отправляем приветственное сообщение с учетом состояния системы
    await update.message.reply_text(
        get_welcome_message(user_id),
        reply_markup=get_welcome_keyboard()
    )
    return ConversationHandler.END

async def delete_previous_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет предыдущее сообщение с отчетом, если оно существует"""
    if 'last_report_message_id' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['last_report_message_id']
            )
        except Exception as e:
            logger.info(f"Не удалось удалить предыдущий отчет: {e}")
        del context.user_data['last_report_message_id']

async def handle_add_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало процесса добавления показаний"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    user_id = update.effective_user.id
    current_date = date.today().isoformat()
    
    # Загружаем текущие показания за сегодня
    today_data = get_day_data(user_id, current_date)
    
    # Инициализируем данные
    context.user_data['readings'] = {}
    context.user_data['current_date'] = current_date
    context.user_data['entry_message_id'] = query.message.message_id
    
    # Заполняем текущие показания
    for meter in METERS:
        key = meter['key']
        if key in today_data:
            context.user_data['readings'][key] = today_data[key]
    
    # Определяем текущий шаг
    current_step = 0
    for i, meter in enumerate(METERS):
        if meter['key'] not in context.user_data['readings']:
            current_step = i
            break
    context.user_data['current_step'] = current_step
    
    # Показываем сообщение с текущими показаниями
    await show_reading_message(update, context)
    return READING_STATE

async def show_reading_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация и отправка сообщения с текущим состоянием"""
    today = date.today().strftime("%d-%m-%Y")
    msg = [f"{today}:"]
    
    for meter in METERS:
        value = context.user_data['readings'].get(meter['key'], None)
        icon = "✅" if value is not None else "❌"
        value_str = f"{value} {meter['unit']}" if value is not None else "--"
        msg.append(f"{icon} {meter['name']}{meter['icon']}: {value_str}")
    
    # Создаем клавиатуру
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="cancel_adding")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Редактируем сообщение
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=context.user_data['entry_message_id'],
        text="\n".join(msg),
        reply_markup=reply_markup
    )

async def show_price_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать меню изменения цен"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_id = query.message.message_id
    
    # Сохраняем контекст для будущих обновлений
    context.user_data['price_chat_id'] = chat_id
    context.user_data['price_message_id'] = message_id
    
    # Создаем сообщение с заголовком
    message_text = "Выберите какую стоимость показаний изменить:"
    
    # Редактируем сообщение с новой клавиатурой
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=message_text,
        reply_markup=get_price_menu_keyboard(user_id)
    )
    return PRICE_MENU

async def handle_price_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало редактирования цены"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    # Извлекаем ключ цены из callback_data
    _, price_key = query.data.split(":", 1)
    context.user_data['editing_price'] = price_key
    
    # Находим название услуги
    item = next(item for item in PRICE_ITEMS if item['key'] == price_key)
    
    # Показываем сообщение с просьбой ввести новое значение
    await context.bot.edit_message_text(
        chat_id=context.user_data['price_chat_id'],
        message_id=context.user_data['price_message_id'],
        text=f"Введите новую стоимость для {item['name']} (руб/{item['unit']}):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="cancel_price_edit")]])
    )
    return PRICE_WAITING

async def handle_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода новой цены с поддержкой запятых"""
    # Подготавливаем ввод: заменяем запятые на точки и удаляем лишние пробелы
    input_text = update.message.text.replace(',', '.').strip()
    
    # Проверяем формат числа с помощью регулярного выражения
    if not re.match(r'^\d*\.?\d+$', input_text):
        error_msg = await update.message.reply_text("Введите корректное число (например, 146.35 или 146,35)")
        
        # Удаляем сообщение об ошибке через 3 секунды
        await asyncio.sleep(3)
        await error_msg.delete()
        
        await update.message.delete()
        return PRICE_WAITING
    
    try:
        value = float(input_text)
        if value < 0:
            raise ValueError
    except ValueError:
        error_msg = await update.message.reply_text("Введите положительное число")
        
        # Удаляем сообщение об ошибке через 3 секунды
        await asyncio.sleep(3)
        await error_msg.delete()
        
        await update.message.delete()
        return PRICE_WAITING
    
    # Сохраняем новую цену
    user_id = update.effective_user.id
    price_key = context.user_data['editing_price']
    update_price(user_id, price_key, value)
    
    # Удаляем сообщение пользователя
    await update.message.delete()
    
    # Обновляем меню цен с сохраненным контекстом
    await refresh_price_menu(update, context)
    return PRICE_MENU

async def refresh_price_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновить меню цен с использованием сохраненного контекста"""
    chat_id = context.user_data.get('price_chat_id')
    message_id = context.user_data.get('price_message_id')
    
    if not chat_id or not message_id:
        # Если контекст утерян, возвращаемся в главное меню
        user_id = update.effective_user.id
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_welcome_message(user_id),
            reply_markup=get_welcome_keyboard()
        )
        return
    
    user_id = update.effective_user.id
    
    # Создаем сообщение с заголовком
    message_text = "Выберите какую стоимость показаний изменить:"
    
    try:
        # Обновляем сообщение с новой клавиатурой
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=message_text,
            reply_markup=get_price_menu_keyboard(user_id)
        )
    except Exception as e:
        logger.error(f"Error refreshing price menu: {e}")
        # Если произошла ошибка, возвращаемся в главное меню
        await context.bot.send_message(
            chat_id=chat_id,
            text=get_welcome_message(user_id),
            reply_markup=get_welcome_keyboard()
        )

async def view_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать список дат с показаниями"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_id = query.message.message_id
    
    # Сохраняем контекст
    context.user_data['view_chat_id'] = chat_id
    context.user_data['view_message_id'] = message_id
    
    # Получаем список дат
    dates = list_dates(user_id)
    
    if not dates:
        await query.edit_message_text(
            text="Нет данных для отображения. Сначала добавьте показания.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]])
        )
        return VIEW_DATES
    
    # Форматируем даты и сортируем по убыванию
    dates.sort(reverse=True)
    formatted_dates = [format_date(d) for d in dates]
    
    # Создаем клавиатуру с датами
    keyboard = []
    for i, (date_str, formatted) in enumerate(zip(dates, formatted_dates)):
        keyboard.append([InlineKeyboardButton(formatted, callback_data=f"date_detail:{date_str}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
    
    # Показываем список дат
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text="Выберите дату для просмотра показаний:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return VIEW_DATES

async def view_date_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать детали показаний за выбранную дату"""
    user_id = update.effective_user.id
    chat_id = context.user_data.get('view_chat_id', update.effective_chat.id)
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    # Определяем ID сообщения
    message_id = None
    if update.callback_query:
        await update.callback_query.answer()
        message_id = update.callback_query.message.message_id
    else:
        # Если вызов из другого места, используем сохраненный ID
        message_id = context.user_data.get('view_message_id')
    
    if not message_id:
        # Если все равно не получается определить, возвращаемся в главное меню
        await update.message.reply_text(
            get_welcome_message(user_id),
            reply_markup=get_welcome_keyboard()
        )
        return VIEW_DETAILS
    
    # Извлекаем дату из callback_data или из контекста
    date_str = None
    if update.callback_query and ':' in update.callback_query.data:
        _, date_str = update.callback_query.data.split(":", 1)
    else:
        date_str = context.user_data.get('current_view_date')
    
    if not date_str:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Ошибка: не указана дата",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="view_dates")]])
        )
        return VIEW_DETAILS
    
    # Сохраняем текущую дату для возможного редактирования
    context.user_data['current_view_date'] = date_str
    
    # Получаем данные за дату
    data = get_day_data(user_id, date_str)
    
    if not data:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Данные за эту дату отсутствуют.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="view_dates")]])
        )
        return VIEW_DETAILS
    
    # Форматируем сообщение
    formatted_date = format_date(date_str)
    message_text = f"Показания за {formatted_date}:\n\n"
    
    for meter in METERS:
        value = data.get(meter['key'])
        if value is not None:
            message_text += f"{meter['icon']} {meter['name']}: {value} {meter['unit']}\n"
    
    # Создаем клавиатуру с возможностью редактирования
    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать показания", callback_data=f"edit_reading:{date_str}")],
        [InlineKeyboardButton("🗓️ Изменить дату", callback_data=f"edit_date:{date_str}")],
        [InlineKeyboardButton("◀️ К списку дат", callback_data="view_dates")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_main")]
    ]
    
    # Показываем детали
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=message_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return VIEW_DETAILS

async def start_edit_reading(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало редактирования показаний за дату"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    # Извлекаем дату из callback_data
    _, date_str = query.data.split(":", 1)
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_id = query.message.message_id
    
    # Сохраняем контекст
    context.user_data['edit_original_date'] = date_str
    context.user_data['edit_new_date'] = date_str
    context.user_data['edit_chat_id'] = chat_id
    context.user_data['edit_message_id'] = message_id
    
    # Загружаем данные за дату
    data = get_day_data(user_id, date_str)
    
    # Инициализируем данные для редактирования
    context.user_data['readings'] = {}
    for meter in METERS:
        key = meter['key']
        if key in data:
            context.user_data['readings'][key] = data[key]
    
    # Определяем текущий шаг
    current_step = 0
    for i, meter in enumerate(METERS):
        if meter['key'] not in context.user_data['readings']:
            current_step = i
            break
    context.user_data['current_step'] = current_step
    
    # Показываем сообщение с текущими показаниями для редактирования
    await show_editing_message(update, context)
    return EDIT_READING

async def show_editing_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация и отправка сообщения с текущим состоянием редактирования"""
    original_date = context.user_data['edit_original_date']
    formatted_date = format_date(original_date)
    msg = [f"Редактирование данных за {formatted_date}:"]
    
    for meter in METERS:
        value = context.user_data['readings'].get(meter['key'], None)
        icon = "✅" if value is not None else "❌"
        value_str = f"{value} {meter['unit']}" if value is not None else "--"
        msg.append(f"{icon} {meter['name']}{meter['icon']}: {value_str}")
    
    # Создаем клавиатуру
    keyboard = [
        [InlineKeyboardButton("🗓️ Изменить дату", callback_data="edit_date_direct")],
        [InlineKeyboardButton("◀️ Отмена", callback_data="cancel_editing")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Редактируем сообщение
    await context.bot.edit_message_text(
        chat_id=context.user_data['edit_chat_id'],
        message_id=context.user_data['edit_message_id'],
        text="\n".join(msg),
        reply_markup=reply_markup
    )

async def handle_edit_reading(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Единый обработчик для редактирования показаний"""
    # Проверяем ввод
    try:
        value = int(update.message.text)
        if value < 0:
            raise ValueError
    except ValueError:
        error_msg = await update.message.reply_text("Введите целое положительное число")
        
        # Удаляем сообщение об ошибке через 3 секунды
        await asyncio.sleep(3)
        await error_msg.delete()
        
        await update.message.delete()
        return EDIT_READING
    
    # Сохраняем показание сразу в файл
    user_id = update.effective_user.id
    current_step = context.user_data['current_step']
    meter = METERS[current_step]
    original_date = context.user_data['edit_original_date']
    new_date = context.user_data['edit_new_date']
    
    # Сохраняем в файл
    write_reading(user_id, meter['key'], value, new_date)
    
    # Если дата изменилась, удаляем старую запись
    if original_date != new_date:
        data = load_user_data(user_id)
        if original_date in data and meter['key'] in data[original_date]:
            # Удаляем только текущее показание из старой даты
            del data[original_date][meter['key']]
            # Если после удаления других данных нет, удаляем дату
            if original_date in data and not data[original_date]:
                del data[original_date]
            _save_data(user_id, data)
    
    # Сохраняем в контекст
    context.user_data['readings'][meter['key']] = value
    
    # Удаляем сообщение пользователя
    await update.message.delete()
    
    # Проверяем, все ли показания введены
    if current_step < len(METERS) - 1:
        context.user_data['current_step'] += 1
        await show_editing_message(update, context)
        return EDIT_READING
    else:
        # Возвращаемся к просмотру деталей
        await refresh_view_details(update, context)
        return VIEW_DETAILS

async def start_edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало процесса изменения даты"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    # Определяем, откуда вызвано изменение даты
    if query.data.startswith("edit_date:"):
        # Из режима просмотра деталей
        _, date_str = query.data.split(":", 1)
        context.user_data['edit_original_date'] = date_str
        context.user_data['edit_new_date'] = date_str
        context.user_data['edit_chat_id'] = update.effective_chat.id
        context.user_data['edit_message_id'] = query.message.message_id
    # Если вызов из режима редактирования показаний, данные уже сохранены
    
    # Показываем сообщение с запросом новой даты
    formatted_date = format_date(context.user_data['edit_original_date'])
    await context.bot.edit_message_text(
        chat_id=context.user_data['edit_chat_id'],
        message_id=context.user_data['edit_message_id'],
        text=f"Введите новую дату вместо {formatted_date} (в формате ДД.ММ.ГГГГ):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="cancel_edit_date")]])
    )
    return EDIT_DATE

async def handle_edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода новой даты"""
    logger.info(f"Начало обработки новой даты. Текст: {update.message.text}")
    
    # Парсим введенную дату
    new_date = parse_date(update.message.text.strip())
    original_date = context.user_data['edit_original_date']
    
    logger.info(f"Исходная дата: {original_date}, Новая дата: {new_date}")
    
    if not new_date:
        error_msg = await update.message.reply_text("Неверный формат даты. Используйте ДД.ММ.ГГГГ")
        
        # Удаляем сообщение об ошибке через 3 секунды
        await asyncio.sleep(3)
        await error_msg.delete()
        
        await update.message.delete()
        return EDIT_DATE
    
    # Сохраняем новую дату в контекст
    context.user_data['edit_new_date'] = new_date
    
    # Удаляем сообщение пользователя
    await update.message.delete()
    
    # Загружаем текущие данные
    user_id = update.effective_user.id
    data = load_user_data(user_id)
    
    # Проверяем существование исходной даты
    if original_date not in data:
        logger.error(f"Исходная дата {original_date} не найдена в данных")
        error_msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Ошибка: исходная дата не найдена"
        )
        await asyncio.sleep(3)
        await error_msg.delete()
        await view_dates(update, context)
        return VIEW_DATES
    
    # Логируем текущее состояние данных
    logger.info(f"Текущие данные до изменения: {data}")
    
    # Сохраняем показания
    readings_data = data[original_date]
    
    # Удаляем исходную дату
    del data[original_date]
    
    # Обрабатываем новую дату
    if new_date in data:
        logger.info(f"Дата {new_date} уже существует, объединяем данные")
        # Объединяем данные с существующей датой
        for key, value in readings_data.items():
            data[new_date][key] = value
    else:
        logger.info(f"Создаем новую запись для даты {new_date}")
        # Создаем новую запись
        data[new_date] = readings_data
    
    # Сохраняем обновленные данные
    _save_data(user_id, data)
    
    # Проверяем, что данные сохранились
    updated_data = load_user_data(user_id)
    logger.info(f"Данные после сохранения: {updated_data}")
    
    # Обновляем контекст
    context.user_data['current_view_date'] = new_date
    context.user_data['edit_original_date'] = new_date
    context.user_data['edit_new_date'] = new_date
    
    logger.info(f"Дата успешно изменена с {original_date} на {new_date}")
    
    # Если мы в режиме редактирования показаний, продолжаем редактирование
    if 'readings' in context.user_data:
        await show_editing_message(update, context)
        return EDIT_READING
    # Если мы просто меняли дату из просмотра, обновляем детали
    else:
        # Возвращаемся к просмотру деталей с новой датой
        await view_date_details(update, context)
        return VIEW_DETAILS

async def refresh_view_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обновить детали показаний без callback-запроса"""
    user_id = update.effective_user.id
    chat_id = context.user_data.get('view_chat_id', update.effective_chat.id)
    
    # Определяем ID сообщения
    message_id = context.user_data.get('view_message_id')
    if not message_id and update.callback_query:
        message_id = update.callback_query.message.message_id
    elif not message_id and update.message:
        message_id = update.message.message_id
    
    if not message_id:
        # Если все равно не получается определить, возвращаемся в главное меню
        await update.message.reply_text(
            get_welcome_message(user_id),
            reply_markup=get_welcome_keyboard()
        )
        return VIEW_DETAILS
    
    # Используем сохраненную дату
    date_str = context.user_data.get('current_view_date', context.user_data.get('edit_original_date'))
    
    if not date_str:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Ошибка: не указана дата",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="view_dates")]])
        )
        return VIEW_DETAILS
    
    # Получаем данные за дату
    data = get_day_data(user_id, date_str)
    
    if not data:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Данные за эту дату отсутствуют.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="view_dates")]])
        )
        return VIEW_DETAILS
    
    # Форматируем сообщение
    formatted_date = format_date(date_str)
    message_text = f"Показания за {formatted_date}:\n\n"
    
    for meter in METERS:
        value = data.get(meter['key'])
        if value is not None:
            message_text += f"{meter['icon']} {meter['name']}: {value} {meter['unit']}\n"
    
    # Создаем клавиатуру с возможностью редактирования
    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать показания", callback_data=f"edit_reading:{date_str}")],
        [InlineKeyboardButton("🗓️ Изменить дату", callback_data=f"edit_date:{date_str}")],
        [InlineKeyboardButton("◀️ К списку дат", callback_data="view_dates")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_main")]
    ]
    
    # Показываем детали
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=message_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return VIEW_DETAILS

async def cancel_editing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена редактирования показаний"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    # Возвращаемся к просмотру деталей
    date_str = context.user_data.get('current_view_date', context.user_data.get('edit_original_date'))
    if date_str:
        await refresh_view_details(update, context)
    else:
        if query:
            await query.edit_message_text(
                text=get_welcome_message(update.effective_user.id),
                reply_markup=get_welcome_keyboard()
            )
        else:
            await update.message.reply_text(
                text=get_welcome_message(update.effective_user.id),
                reply_markup=get_welcome_keyboard()
            )
    return VIEW_DETAILS

async def cancel_edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена изменения даты"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    # Возвращаемся к предыдущему состоянию
    if 'readings' in context.user_data:
        await show_editing_message(update, context)
        return EDIT_READING
    else:
        date_str = context.user_data.get('current_view_date', context.user_data.get('edit_original_date'))
        if date_str:
            await refresh_view_details(update, context)
        else:
            if query:
                await query.edit_message_text(
                    text=get_welcome_message(update.effective_user.id),
                    reply_markup=get_welcome_keyboard()
                )
            else:
                await update.message.reply_text(
                    text=get_welcome_message(update.effective_user.id),
                    reply_markup=get_welcome_keyboard()
                )
        return VIEW_DETAILS

async def cancel_price_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена редактирования цены"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    await refresh_price_menu(update, context)
    return PRICE_MENU

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    await query.edit_message_text(
        text=get_welcome_message(update.effective_user.id),
        reply_markup=get_welcome_keyboard()
    )
    return ConversationHandler.END

async def cancel_adding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена процесса добавления"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    # Возвращаем стартовое сообщение
    await query.edit_message_text(
        text=get_welcome_message(update.effective_user.id),
        reply_markup=get_welcome_keyboard()
    )
    return ConversationHandler.END

async def view_last_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать последний отчет"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем предыдущий отчет
    await delete_previous_report(update, context)
    
    if 'last_report' in context.user_data:
        report_msg = await query.message.reply_text(
            context.user_data['last_report'],
            parse_mode='Markdown'
        )
        context.user_data['last_report_message_id'] = report_msg.message_id
    else:
        # Редактируем текущее сообщение вместо отправки нового
        await query.edit_message_text(
            text="⚠️ Последний отчет не найден.",
            reply_markup=None
        )
        
        # Ждем 3 секунды
        await asyncio.sleep(1.2)
        
        # Возвращаем исходное меню
        await query.edit_message_text(
            text=get_welcome_message(update.effective_user.id),
            reply_markup=get_welcome_keyboard()
        )
    
    return VIEW_REPORT

async def handle_reading(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Единый обработчик для всех показаний"""
    # Сохраняем chat_id до удаления сообщения
    chat_id = update.effective_chat.id
    
    # Проверяем ввод
    try:
        value = int(update.message.text)
        if value < 0:
            raise ValueError
    except ValueError:
        error_msg = await update.message.reply_text("Введите целое положительное число")
        
        # Удаляем сообщение об ошибке через 3 секунды
        await asyncio.sleep(3)
        await error_msg.delete()
        
        await update.message.delete()
        return READING_STATE
    
    # Сохраняем показание сразу в файл
    user_id = update.effective_user.id
    current_step = context.user_data['current_step']
    meter = METERS[current_step]
    current_date = context.user_data['current_date']
    
    write_reading(user_id, meter['key'], value, current_date)
    context.user_data['readings'][meter['key']] = value
    
    # Удаляем сообщение пользователя
    await update.message.delete()
    
    # Проверяем, все ли показания введены
    if current_step < len(METERS) - 1:
        context.user_data['current_step'] += 1
        await show_reading_message(update, context)
        return READING_STATE
    else:
        # Проверяем, есть ли данные за месяц назад
        last_month_date = get_last_month_date(current_date)
        data = load_user_data(user_id)
        
        # Проверяем наличие данных за текущую дату и дату месяц назад
        if last_month_date in data and current_date in data:
            # Проверяем наличие всех необходимых показаний
            required_keys = ['light', 'cold', 'hot']
            prev_data = data[last_month_date]
            curr_data = data[current_date]
            
            if all(key in prev_data for key in required_keys) and all(key in curr_data for key in required_keys):
                # Генерируем отчет
                report = generate_monthly_report(user_id, current_date, last_month_date)
                
                # Сохраняем отчет
                context.user_data['last_report'] = report
                
                # Отправляем отчет как отдельное сообщение
                report_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=report,
                    parse_mode='Markdown'
                )
                context.user_data['last_report_message_id'] = report_msg.message_id
        
        # Возвращаем стартовое сообщение с уведомлением
        success_msg = (
            "✅ Показания успешно сохранены!\n\n" + 
            get_welcome_message(user_id)
        )
        
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=context.user_data['entry_message_id'],
            text=success_msg,
            reply_markup=get_welcome_keyboard()
        )
        return ConversationHandler.END

# Вспомогательная функция для сохранения данных
def _save_data(user_id: int,  data: dict):
    from data_handler import _save
    from data_handler import ensure_user_folder
    file_path = os.path.join(ensure_user_folder(user_id), 'data.json')
    logger.info(f"Сохранение данных в файл: {file_path}")
    logger.info(f"Данные для сохранения: {data}")
    _save(file_path, data)
    
    # Проверка сохранения
    with open(file_path, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    logger.info(f"Проверка сохранения: {saved_data}")

# Основной обработчик диалогов
conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('start', start),
        CallbackQueryHandler(handle_add_data, pattern='^add_data$'),
        CallbackQueryHandler(show_price_menu, pattern='^price_menu$'),
        CallbackQueryHandler(view_dates, pattern='^view_dates$'),
        CallbackQueryHandler(view_last_report, pattern='^view_last_report$')
    ],
    states={
        READING_STATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reading),
            CallbackQueryHandler(cancel_adding, pattern='^cancel_adding$')
        ],
        PRICE_MENU: [
            CallbackQueryHandler(handle_price_edit, pattern='^price_edit:'),
            CallbackQueryHandler(back_to_main, pattern='^back_to_main$')
        ],
        PRICE_WAITING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price_input),
            CallbackQueryHandler(cancel_price_edit, pattern='^cancel_price_edit$')
        ],
        VIEW_DATES: [
            CallbackQueryHandler(view_date_details, pattern='^date_detail:'),
            CallbackQueryHandler(back_to_main, pattern='^back_to_main$')
        ],
        VIEW_DETAILS: [
            CallbackQueryHandler(start_edit_reading, pattern='^edit_reading:'),
            CallbackQueryHandler(start_edit_date, pattern='^edit_date:'),
            CallbackQueryHandler(view_dates, pattern='^view_dates$'),
            CallbackQueryHandler(back_to_main, pattern='^back_to_main$')
        ],
        EDIT_READING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_reading),
            CallbackQueryHandler(start_edit_date, pattern='^edit_date_direct$'),
            CallbackQueryHandler(cancel_editing, pattern='^cancel_editing$')
        ],
        EDIT_DATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_date),
            CallbackQueryHandler(cancel_edit_date, pattern='^cancel_edit_date$')
        ],
        VIEW_REPORT: [
            CallbackQueryHandler(back_to_main, pattern='^back_to_main$'),
            CallbackQueryHandler(handle_add_data, pattern='^add_data$'),
            CallbackQueryHandler(show_price_menu, pattern='^price_menu$'),
            CallbackQueryHandler(view_dates, pattern='^view_dates$')
        ]
    },
    fallbacks=[
        CallbackQueryHandler(back_to_main, pattern='^back_to_main$'),
        CallbackQueryHandler(cancel_adding, pattern='^cancel_adding$'),
        CallbackQueryHandler(cancel_price_edit, pattern='^cancel_price_edit$'),
        CallbackQueryHandler(cancel_editing, pattern='^cancel_editing$'),
        CallbackQueryHandler(cancel_edit_date, pattern='^cancel_edit_date$')
    ],
)

