print("🚀 БОТ ЗАПУСКАЕТСЯ...")

import os
import sys
import logging
import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta

# ФИКС ДЛЯ Python 3.13
if sys.version_info >= (3, 13):
    print("Python 3.13 - применяю фикс...")
    import types
    imghdr = types.ModuleType('imghdr')
    imghdr.what = lambda x: None
    sys.modules['imghdr'] = imghdr

# НОВЫЙ ИМПОРТ ДЛЯ python-telegram-bot v20+
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

print("✅ Библиотеки загружены")

# ====================== КОНФИГУРАЦИЯ ======================
TOKEN = "8256725006:AAFV-2zx2OWxQdAP0Nxe9k4lYzq7_ofnyIw"
ADMIN_ID = 7979729060
ADMIN_USERNAME = "@profitclickadmin"

# КОНФИГУРАЦИЯ ЮKАССЫ
YOOKASSA_SHOP_ID = "1241024"
YOOKASSA_SECRET_KEY = "test_dovNMVr5Rjt6Ez5W5atO2a1RDpzNKLlQh6dcp-fDpsI"
YOOKASSA_API_URL = "https://api.yookassa.ru/v3/" if not YOOKASSA_SECRET_KEY.startswith("test_") else "https://api.yookassa.ru/v3/"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# ====================== БАЗА ДАННЫХ ======================
import json

class SimpleDB:
    def __init__(self):
        self.data = {}
        self.payments = {}  # Храним ожидающие платежи
    
    def get(self, user_id, key, default=None):
        if user_id not in self.data:
            self.data[user_id] = {}
        return self.data[user_id].get(key, default)
    
    def set(self, user_id, key, value):
        if user_id not in self.data:
            self.data[user_id] = {}
        self.data[user_id][key] = value
    
    def add(self, user_id, key, amount):
        current = self.get(user_id, key, 0)
        self.set(user_id, key, current + amount)
        return current + amount
    
    def has(self, user_id, key):
        return self.get(user_id, key, False)
    
    def append(self, user_id, key, value):
        """Добавить элемент в список"""
        if user_id not in self.data:
            self.data[user_id] = {}
        if key not in self.data[user_id]:
            self.data[user_id][key] = []
        if not isinstance(self.data[user_id][key], list):
            self.data[user_id][key] = []
        self.data[user_id][key].append(value)
    
    def get_list(self, user_id, key):
        """Получить список"""
        if user_id not in self.data:
            self.data[user_id] = {}
        if key not in self.data[user_id]:
            self.data[user_id][key] = []
        return self.data[user_id].get(key, [])
    
    def create_payment(self, payment_id, user_id, amount, description=""):
        """Создать запись о платеже"""
        self.payments[payment_id] = {
            "user_id": user_id,
            "amount": amount,
            "description": description,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        return payment_id
    
    def get_payment(self, payment_id):
        """Получить информацию о платеже"""
        return self.payments.get(payment_id)
    
    def update_payment_status(self, payment_id, status):
        """Обновить статус платежа"""
        if payment_id in self.payments:
            self.payments[payment_id]["status"] = status
            self.payments[payment_id]["updated_at"] = datetime.now().isoformat()
            return True
        return False

db = SimpleDB()

# ====================== ЮKАССА КЛИЕНТ ======================
import aiohttp
import base64

class YooKassaClient:
    def __init__(self, shop_id, secret_key):
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.auth = base64.b64encode(f"{shop_id}:{secret_key}".encode()).decode()
        self.base_url = "https://api.yookassa.ru/v3/"
        if secret_key.startswith("test_"):
            self.base_url = "https://api.yookassa.ru/v3/"
    
    async def create_payment(self, amount, description, return_url=None, metadata=None):
        """Создать платеж в ЮKасса"""
        payment_id = str(uuid.uuid4())
        
        headers = {
            "Idempotence-Key": payment_id,
            "Authorization": f"Basic {self.auth}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": {
                "value": str(amount),
                "currency": "RUB"
            },
            "payment_method_data": {
                "type": "bank_card"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url or "https://t.me/ProffitClick_bot"
            },
            "capture": True,
            "description": description,
            "metadata": metadata or {}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}payments",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "id": data.get("id"),
                            "status": data.get("status"),
                            "confirmation_url": data.get("confirmation", {}).get("confirmation_url"),
                            "amount": amount,
                            "description": description
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"YooKassa API error: {error_text}")
                        return None
        except Exception as e:
            logger.error(f"YooKassa create_payment error: {e}")
            return None
    
    async def check_payment(self, payment_id):
        """Проверить статус платежа"""
        headers = {
            "Authorization": f"Basic {self.auth}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}payments/{payment_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "id": data.get("id"),
                            "status": data.get("status"),
                            "paid": data.get("paid", False),
                            "amount": float(data.get("amount", {}).get("value", 0))
                        }
                    else:
                        return None
        except Exception as e:
            logger.error(f"YooKassa check_payment error: {e}")
            return None

# Создаем клиент ЮKассы
yookassa = YooKassaClient(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)

# ====================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======================
def add_transaction(user_id, transaction_type, amount, description=""):
    """Добавить транзакцию в историю"""
    transaction = {
        "date": datetime.now().isoformat(),
        "type": transaction_type,
        "amount": amount,
        "description": description
    }
    db.append(user_id, "transactions", transaction)
    return transaction

def get_referral_code(user_id):
    """Получить или создать реферальный код"""
    code = db.get(user_id, "referral_code")
    if not code:
        code = f"REF{user_id}"
        db.set(user_id, "referral_code", code)
    return code

def get_referrer(user_id):
    """Получить ID реферера пользователя"""
    return db.get(user_id, "referred_by")

def add_referral(referrer_id, referred_id):
    """Добавить реферала"""
    db.append(referrer_id, "referrals", referred_id)
    db.set(referred_id, "referred_by", referrer_id)
    
    # Бонус рефереру
    bonus = 50
    db.add(referrer_id, "balance", bonus)
    add_transaction(referrer_id, "referral", bonus, f"Бонус за приглашение пользователя {referred_id}")
    
    # Бонус новому пользователю
    db.add(referred_id, "balance", 25)
    add_transaction(referred_id, "bonus", 25, "Бонус за регистрацию по реферальной ссылке")
    
    return bonus

def check_daily_bonus(user_id):
    """Проверить и выдать ежедневный бонус"""
    today = datetime.now().date().isoformat()
    last_bonus_date = db.get(user_id, "last_daily_bonus_date")
    streak = db.get(user_id, "daily_streak", 0)
    
    if last_bonus_date == today:
        return None, streak
    
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    
    if last_bonus_date == yesterday:
        streak += 1
    else:
        streak = 1
    
    bonus = min(10 + (streak * 5), 100)
    
    db.set(user_id, "last_daily_bonus_date", today)
    db.set(user_id, "daily_streak", streak)
    db.add(user_id, "balance", bonus)
    add_transaction(user_id, "bonus", bonus, f"Ежедневный бонус (стрик: {streak} дней)")
    
    return bonus, streak

def check_achievements(user_id):
    """Проверить и выдать достижения"""
    balance = db.get(user_id, "balance", 0)
    completed_tasks = len(db.get_list(user_id, "completed_tasks"))
    referrals_count = len(db.get_list(user_id, "referrals"))
    purchased_items = len(db.get_list(user_id, "purchased_items"))
    achievements = db.get_list(user_id, "achievements")
    new_achievements = []
    
    # Финансовые достижения
    if balance >= 1000000 and "millionaire" not in achievements:
        achievements.append("millionaire")
        new_achievements.append("💰 Миллионер")
        db.add(user_id, "balance", 1000)
        add_transaction(user_id, "bonus", 1000, "Награда за достижение: Миллионер")
    
    if balance >= 100000 and "rich" not in achievements:
        achievements.append("rich")
        new_achievements.append("💵 Богач")
        db.add(user_id, "balance", 500)
        add_transaction(user_id, "bonus", 500, "Награда за достижение: Богач")
    
    if balance >= 10000 and "wealthy" not in achievements:
        achievements.append("wealthy")
        new_achievements.append("💴 Состоятельный")
        db.add(user_id, "balance", 200)
        add_transaction(user_id, "bonus", 200, "Награда за достижение: Состоятельный")
    
    # Достижения по заданиям
    if completed_tasks >= 1 and "first_task" not in achievements:
        achievements.append("first_task")
        new_achievements.append("🎯 Первое задание")
        db.add(user_id, "balance", 50)
        add_transaction(user_id, "bonus", 50, "Награда за достижение: Первое задание")
    
    if completed_tasks >= 100 and "task_master" not in achievements:
        achievements.append("task_master")
        new_achievements.append("🏆 Мастер заданий")
        db.add(user_id, "balance", 1000)
        add_transaction(user_id, "bonus", 1000, "Награда за достижение: Мастер заданий")
    
    if completed_tasks >= 50 and "task_pro" not in achievements:
        achievements.append("task_pro")
        new_achievements.append("⭐ Профи заданий")
        db.add(user_id, "balance", 500)
        add_transaction(user_id, "bonus", 500, "Награда за достижение: Профи заданий")
    
    if completed_tasks >= 10 and "task_beginner" not in achievements:
        achievements.append("task_beginner")
        new_achievements.append("🌱 Новичок")
        db.add(user_id, "balance", 100)
        add_transaction(user_id, "bonus", 100, "Награда за достижение: Новичок")
    
    # Реферальные достижения
    if referrals_count >= 10 and "referral_king" not in achievements:
        achievements.append("referral_king")
        new_achievements.append("👑 Король рефералов")
        db.add(user_id, "balance", 500)
        add_transaction(user_id, "bonus", 500, "Награда за достижение: Король рефералов")
    
    if referrals_count >= 5 and "referral_pro" not in achievements:
        achievements.append("referral_pro")
        new_achievements.append("🤝 Реферальный профи")
        db.add(user_id, "balance", 200)
        add_transaction(user_id, "bonus", 200, "Награда за достижение: Реферальный профи")
    
    # Новые достижения
    if purchased_items >= 5 and "shopper" not in achievements:
        achievements.append("shopper")
        new_achievements.append("🛒 Шопоголик")
        db.add(user_id, "balance", 300)
        add_transaction(user_id, "bonus", 300, "Награда за достижение: Шопоголик")
    
    if balance >= 5000 and "investor" not in achievements:
        achievements.append("investor")
        new_achievements.append("📈 Инвестор")
        db.add(user_id, "balance", 200)
        add_transaction(user_id, "bonus", 200, "Награда за достижение: Инвестор")
    
    db.set(user_id, "achievements", achievements)
    return new_achievements

def get_user_rating(user_id):
    """Рассчитать рейтинг пользователя"""
    balance = db.get(user_id, "balance", 0)
    completed_tasks = len(db.get_list(user_id, "completed_tasks"))
    referrals_count = len(db.get_list(user_id, "referrals"))
    purchased_items = len(db.get_list(user_id, "purchased_items"))
    achievements_count = len(db.get_list(user_id, "achievements"))
    
    # Формула рейтинга
    rating = (
        balance * 0.001 +  # 0.1% от баланса
        completed_tasks * 10 +  # 10 очков за задание
        referrals_count * 50 +  # 50 очков за реферала
        purchased_items * 30 +  # 30 очков за покупку
        achievements_count * 100  # 100 очков за достижение
    )
    
    return int(rating)

def get_top_users(limit=10):
    """Получить топ пользователей по рейтингу"""
    all_users = db.data.keys()
    user_ratings = []
    
    for user_id in all_users:
        rating = get_user_rating(user_id)
        if rating > 0:
            user_ratings.append((user_id, rating))
    
    user_ratings.sort(key=lambda x: x[1], reverse=True)
    return user_ratings[:limit]

# ====================== ГЛАВНОЕ МЕНЮ ======================
def main_menu_keyboard():
    keyboard = [
        ["🏆 Задания", "💼 Работа"],
        ["💳 Банковские карты", "💰 Кредиты"],
        ["🛡 Страхование", "🏠 Недвижимость"],
        ["✈️ Туризм и путешествия", "🏢 Бизнес"],
        ["📊 Брокерские счета", "🌟 Подписки"],
        ["📱 SIM-карты", "🎓 Курсы"],
        ["💰 Баланс", "📞 Связь с админом"],
        ["👤 Профиль"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ====================== ОБНОВЛЕННЫЕ КУРСЫ С ПРАВИЛЬНЫМИ ССЫЛКАМИ ======================
COURSES = {
    "course_1": {
        "title": "🎨 Основы графического дизайна",
        "price": 50,
        "description": "Базовый курс по графическому дизайну для начинающих",
        "link": "https://www.youtube.com/playlist?list=PLrFZoKDwH7Ng6c7KHYdqjZ2keb5jzpZ0E",
        "youtube_playlist": "https://www.youtube.com/playlist?list=PLrFZoKDwH7Ng6c7KHYdqjZ2keb5jzpZ0E"
    },
    "course_2": {
        "title": "📸 Фотошоп с Нуля",
        "price": 100,
        "description": "Полный курс Adobe Photoshop для новичков",
        "link": "https://www.youtube.com/playlist?list=PLWOT_kf44zD7ve4dwdhYd2VfgCSeYUcgS",
        "youtube_playlist": "https://www.youtube.com/playlist?list=PLWOT_kf44zD7ve4dwdhYd2VfgCSeYUcgS"
    },
    "course_3": {
        "title": "🐍 Python для начинающих",
        "price": 80,
        "description": "Полный курс Python с нуля - программирование для новичков",
        "link": "https://www.youtube.com/playlist?list=PLDyJYA6aTY1lPWXBPk0gw6gR8fEtPDGKa",
        "youtube_playlist": "https://www.youtube.com/playlist?list=PLDyJYA6aTY1lPWXBPk0gw6gR8fEtPDGKa"
    },
    "course_4": {
        "title": "💻 JavaScript с нуля",
        "price": 120,
        "description": "Изучи JavaScript за 10 часов - полный курс для новичков",
        "link": "https://www.youtube.com/playlist?list=PLDyJYA6aTY1kJIwbYHzGOuvSMNTfqksmk",
        "youtube_playlist": "https://www.youtube.com/playlist?list=PLDyJYA6aTY1kJIwbYHzGOuvSMNTfqksmk"
    },
    "course_5": {
        "title": "🎬 Видеомонтаж в Premiere Pro",
        "price": 150,
        "description": "Профессиональный видеомонтаж в Adobe Premiere Pro с нуля",
        "link": "https://www.youtube.com/results?search_query=Premiere+Pro+полный+курс+на+русском+playlist",
        "youtube_playlist": "https://www.youtube.com/results?search_query=Premiere+Pro+полный+курс+на+русском+playlist"
    },
    "course_6": {
        "title": "📱 Разработка мобильных приложений",
        "price": 180,
        "description": "Создание приложений для Android и iOS с нуля",
        "link": "https://www.youtube.com/results?search_query=mobile+apps+playlist+Гоша+Дударь",
        "youtube_playlist": "https://www.youtube.com/results?search_query=mobile+apps+playlist+Гоша+Дударь"
    },
    "course_7": {
        "title": "🌐 Веб-разработка HTML/CSS",
        "price": 70,
        "description": "Создание сайтов с нуля - HTML, CSS, основы верстки",
        "link": "https://www.youtube.com/playlist?list=PLdzeMLV8u_l4j9IITwTtiGJUiWQmO7YUB",
        "youtube_playlist": "https://www.youtube.com/playlist?list=PLdzeMLV8u_l4j9IITwTtiGJUiWQmO7YUB"
    },
    "course_8": {
        "title": "📊 Excel для бизнеса",
        "price": 90,
        "description": "Продвинутый Excel: формулы, графики, анализ данных",
        "link": "https://www.youtube.com/results?search_query=Excel+полный+курс+для+бизнеса+playlist",
        "youtube_playlist": "https://www.youtube.com/results?search_query=Excel+полный+курс+для+бизнеса+playlist"
    },
    "course_9": {
        "title": "🎯 SMM и продвижение в соцсетях",
        "price": 130,
        "description": "Как продвигать бизнес в Instagram, VK, Telegram",
        "link": "https://www.youtube.com/results?search_query=SMM+курс+для+начинающих+playlist",
        "youtube_playlist": "https://www.youtube.com/results?search_query=SMM+курс+для+начинающих+playlist"
    },
    "course_10": {
        "title": "💰 Криптовалюты и блокчейн",
        "price": 200,
        "description": "Полный курс по криптовалютам, блокчейну и инвестициям",
        "link": "https://www.youtube.com/results?search_query=криптовалюты+блокчейн+курс+playlist",
        "youtube_playlist": "https://www.youtube.com/results?search_query=криптовалюты+блокчейн+курс+playlist"
    },
    "course_11": {
        "title": "🎨 Figma для дизайнеров",
        "price": 110,
        "description": "Профессиональный дизайн интерфейсов в Figma с нуля",
        "link": "https://www.youtube.com/playlist?list=PLM2Q6lcZo4MexclJrYxA0Is42qWBBuHpB",
        "youtube_playlist": "https://www.youtube.com/playlist?list=PLM2Q6lcZo4MexclJrYxA0Is42qWBBuHpB"
    },
    "course_12": {
        "title": "🤖 Машинное обучение и AI",
        "price": 190,
        "description": "Введение в искусственный интеллект и машинное обучение",
        "link": "https://www.youtube.com/playlist?list=PLA0M1Bcd0w8zxDIDOTQHsX68MCDOAJDtj",
        "youtube_playlist": "https://www.youtube.com/playlist?list=PLA0M1Bcd0w8zxDIDOTQHsX68MCDOAJDtj"
    }
}

# ====================== ВСЕ ЗАДАНИЯ И СЕРВИСЫ ======================
TASK_DATA = {
    "task_1": {
        "title": "Лендинг с заданиями и наградами",
        "link": "https://yandex.ru/project/browser/bonus/multioffer/affiliate_4prod?source=pWRP8eS1VsC2X59560&partner_string=P89XvN11U6RuE47077&cliddbro=14444288&clidmbro=14444289&cliddefault=14444291&clidpp=14444285",
        "description": "Выполните задания и получите награды от Яндекса",
        "category": "Задания"
    },
    "task_2": {
        "title": "Яндекс.Браузер на ПК – до 500₽ за установку",
        "link": "https://download.cdn.yandex.net/yandex-tag/weboffer/YandexDownloader.exe?partner=946133&yabrowser=y&yaqsearch=y&yahomepage=y&banerid=1314444296&clid1=14444293&clid5=14444286&clid6=14444287&clid8=14444284&hash=4665b8e76c413b00338cf14156dfe0ed&.exe",
        "description": "Установите Яндекс.Браузер на ПК и получите до 500₽",
        "category": "Задания"
    },
    "task_3": {
        "title": "Яндекс.Браузер на смартфон – до 200₽",
        "link": "https://redirect.appmetrica.yandex.com/serve/1038458303094476620?partner_id=831050&appmetrica_js_redirect=0&full=0&clid=14444292&banerid=1314444290",
        "description": "Установите Яндекс.Браузер на смартфон и получите до 200₽",
        "category": "Задания"
    },
    "task_4": {
        "title": "Яндекс.Поиск – 15% дохода от рекламы",
        "link": "https://ya.ru/search/?clid=14444295&text=",
        "description": "Подключите поиск Яндекса и получайте 15% дохода от рекламы",
        "category": "Задания"
    },
    "task_5": {
        "title": "Яндекс.Приложение с Алисой – 150₽ за установку",
        "link": "https://redirect.appmetrica.yandex.com/serve/1110515897115706063?clid=14444294&appmetrica_js_redirect=0",
        "description": "Установите приложение Яндекс с Алисой и получите 150₽",
        "category": "Задания"
    },
    "job_1": {
        "title": "Яндекс.Курьер",
        "link": "https://ya.cc/8Ro9Lk",
        "description": "Требования: Телефон Android 7+ или iPhone, мед. книжка",
        "category": "Работа"
    },
    "job_2": {
        "title": "Стать партнёром Альфа-Банк",
        "link": "https://svoy.alfabank.ru/ref/885537",
        "description": "Доход 50 000–100 000 ₽ в месяц",
        "category": "Работа"
    },
    "job_3": {
        "title": "Брокер Альфа-Банк – ЗП 500-1 000 000₽",
        "link": "https://alfabank.ru/make-money/investments/brokerskij-schyot/?platformId=alfapartners_msv_investment-ba_885537_3469359",
        "description": "Требования: Понимание финансовых инструментов",
        "category": "Работа"
    },
    "card_1": {
        "title": "T-BANK Дебетовая карта Black 500₽",
        "link": "https://tbank.ru/baf/AGH0q6iLOEi",
        "description": "Оформите карту и получите 500₽",
        "category": "Банковские карты"
    },
    "card_2": {
        "title": "T-BANK Исламская карта 700₽",
        "link": "https://tbank.ru/baf/Ahw0N0HVPr5",
        "description": "Оформите карту и получите 700₽",
        "category": "Банковские карты"
    },
    "card_3": {
        "title": "ALL Airlines Debit 500₽",
        "link": "https://trk.ppdu.ru/click/dQ6F5iXw?erid=2SDnjeBaaR6",
        "description": "Оформите карту и получите 500₽",
        "category": "Банковские карты"
    },
    "card_4": {
        "title": "T-BANK Кредитная карта Platinum 500₽",
        "link": "https://tbank.ru/baf/7UJLwbFRVjE",
        "description": "Оформите карту и получите 500₽",
        "category": "Банковские карты"
    },
    "card_5": {
        "title": "ПСБ Банк 'Твой Кешбэк' 700₽",
        "link": "https://trk.ppdu.ru/click/WBiFitrR?erid=2SDnjehD1C8",
        "description": "Оформите карту и получите 700₽",
        "category": "Банковские карты"
    },
    "card_6": {
        "title": "ВТБ Банк Кредитная карта 2000₽",
        "link": "https://trk.ppdu.ru/click/GRSeIMLG?erid=2SDnjeGCc2T",
        "description": "Оформите карту и получите 2000₽",
        "category": "Банковские карты"
    },
    "card_7": {
        "title": "Плати по миру Виртуальная карта USD 5000₽",
        "link": "https://trk.ppdu.ru/click/1HeoyraF?erid=2SDnjdQghsC",
        "description": "Оформите карту и получите 5000₽",
        "category": "Банковские карты"
    },
    "card_8": {
        "title": "Альфа-Карта с любимым кэшбэком – 4000₽",
        "link": "https://alfabank.ru/lp/retail/dc/flexible-agent/?platformId=alfapartners_msv_DC-flexible_885537_3469097",
        "description": "Все преимущества Альфа-Карты + любимый кэшбэк",
        "category": "Банковские карты"
    },
    "card_9": {
        "title": "Карта к Семейному счёту – 2500₽",
        "link": "https://alfa.me/-iUM8W?url=https%3A%2F%2Fsvoy.alfabank.ru%2Fapi%2Fsso%2Fproxy%3Fproduct_id%3DSK%26id%3D885537&id=885537",
        "description": "Карта для семейного счёта Альфа-Банка",
        "category": "Банковские карты"
    },
    "card_10": {
        "title": "Кредитная карта 60 дней без % – 8500₽",
        "link": "https://alfabank.ru/get-money/credit-cards/land/60-days-partners/?platformId=alfapartners_msv_CC-60_885537_3469224",
        "description": "Бесплатное обслуживание и кэшбэк",
        "category": "Банковские карты"
    },
    "card_11": {
        "title": "Детская карта – 3500₽",
        "link": "https://alfabank.ru/make-money/investments/brokerskij-schyot/?platformId=alfapartners_msv_DC-childcard_885537_3469164",
        "description": "Карта для ребёнка от 6 до 14 лет",
        "category": "Банковские карты"
    },
    "credit_1": {
        "title": "Альфа-Банк Кредит наличными 5000₽",
        "link": "https://alfabank.ru/get-money/credit/credit-cash/welcome/?platformId=alfapartners_msv_PIL-PIL_885537_4921952",
        "description": "Оформите кредит и получите 5000₽",
        "category": "Кредиты"
    },
    "credit_2": {
        "title": "Кредит на большие планы 2500₽",
        "link": "https://alfabank.ru/get-money/credit/credit-cash/form-online-pod-zalog/?platformId=alfapartners_msv_PIMB_885537_0",
        "description": "Оформите кредит и получите 2500₽",
        "category": "Кредиты"
    },
    "credit_3": {
        "title": "Ипотека 250 000₽",
        "link": "https://alfa.me/y-6Bns?url=https%3A%2F%2Fipoteka.alfabank.ru%2Fam",
        "description": "Оформите ипотеку и получите 250 000₽",
        "category": "Кредиты"
    },
    "credit_4": {
        "title": "Предодобренный кредит 25 000₽",
        "link": "https://alfa.me/0WwZ1h?url=https%3A%2F%2Fweb.alfabank.ru%2Fupsale-credits%2Fcredits%2FRP",
        "description": "Получите предодобренный кредит на 25 000₽",
        "category": "Кредиты"
    },
    "insur_1": {
        "title": "Zetta — спортсмены 1000₽",
        "link": "https://trk.ppdu.ru/click/Z07fQfwV?erid=2SDnje1GhqB",
        "description": "Оформите страховку и получите 1000₽",
        "category": "Страхование"
    },
    "insur_2": {
        "title": "Zetta школьники",
        "link": "https://trk.ppdu.ru/click/jKAsGV7v?erid=2SDnjdoXrY9",
        "description": "Оформите страховку для школьников",
        "category": "Страхование"
    },
    "insur_3": {
        "title": "Сберстрахование 2500₽",
        "link": "https://trk.ppdu.ru/click/uROD6qbL?erid=2SDnjeitzV5",
        "description": "Оформите страховку и получите 2500₽",
        "category": "Страхование"
    },
    "insur_4": {
        "title": "Т-Страхование ВЗР/Недвижимость",
        "link": "https://trk.ppdu.ru/click/88PEHkIJ?erid=2SDnjf1Gc5U",
        "description": "Оформите страховку ВЗР или недвижимости",
        "category": "Страхование"
    },
    "estate_1": {
        "title": "Яндекс.Аренда — 30 000₽",
        "link": "https://arenda.yandex.ru/referral/G1XEQDX490/promocode/",
        "description": "Сдайте или снимите жилье и получите 30 000₽",
        "category": "Недвижимость"
    },
    "tour_1": {
        "title": "AVIASALES — 5000₽",
        "link": "https://trk.ppdu.ru/click/HnqEhAGs?erid=2VtzqvwYBcc",
        "description": "Купите билеты и получите 5000₽",
        "category": "Туризм"
    },
    "tour_2": {
        "title": "Яндекс.Путешествия — 3000₽",
        "link": "https://trk.ppdu.ru/click/APUFJ8oK?erid=2SDnjezfxS3",
        "description": "Забронируйте и получите 3000₽",
        "category": "Туризм"
    },
    "tour_3": {
        "title": "KIWITAXI — 5000₽",
        "link": "https://trk.ppdu.ru/click/HdFuG4Xi?erid=2VtzqumW7vm",
        "description": "Закажите трансфер и получите 5000₽",
        "category": "Туризм"
    },
    "biz_1": {
        "title": "Регистрация бизнеса 25 000₽",
        "link": "https://alfabank.ru/sme/start/partner/ag/?platformId=alfapartners_msv_RKOregbiz_885537_3469325",
        "description": "Зарегистрируйте бизнес и получите 25 000₽",
        "category": "Бизнес"
    },
    "biz_2": {
        "title": "Расчётный счёт 2000₽",
        "link": "https://alfabank.ru/sme/partner/ag/?platformId=alfapartners_msv_rko-anketa_885537_3469333",
        "description": "Откройте расчетный счет и получите 2000₽",
        "category": "Бизнес"
    },
    "biz_3": {
        "title": "Интернет-эквайринг 15 000₽",
        "link": "https://alfabank.ru/sme/payservice/msv-intacq/?platformId=alfapartners_msv_intacq_885537_3469340",
        "description": "Подключите эквайринг и получите 15 000₽",
        "category": "Бизнес"
    },
    "broker_1": {
        "title": "Брокерский счёт – 12 500₽",
        "link": "https://alfabank.ru/make-money/investments/brokerskij-schyot/?platformId=alfapartners_msv_investment-ba_885537_3469359",
        "description": "Нужен для покупки и продажи акций, облигаций",
        "category": "Брокерские счета"
    },
    "sub_1": {
        "title": "Alfa Only Premium — 2500₽",
        "link": "https://alfabank.ru/everyday/package/premium/?platformId=alfapartners_msv_DC-premium_885537_3469276",
        "description": "Оформите подписку и получите 2500₽",
        "category": "Подписки"
    },
    "sim_1": {
        "title": "Альфа-Мобайл — 500₽",
        "link": "https://alfa.me/SIM_alfapartners_msv?prefilledDataID=alfapartnersmsv_885537",
        "description": "Оформите SIM-карту и получите 500₽",
        "category": "SIM-карты"
    }
}

# ====================== КОМАНДЫ ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    balance = db.get(user.id, "balance", 0)
    
    if context.args and len(context.args) > 0:
        ref_code = context.args[0]
        if ref_code.startswith("REF"):
            try:
                referrer_id = int(ref_code[3:])
                if referrer_id != user.id and not get_referrer(user.id):
                    add_referral(referrer_id, user.id)
            except:
                pass
    
    new_achievements = check_achievements(user.id)
    
    welcome_text = f"👋 Привет, {user.first_name}!\n\n"
    welcome_text += f"💰 Твой баланс: {balance}₽\n\n"
    
    if new_achievements:
        welcome_text += "🎉 **Новые достижения:**\n"
        for ach in new_achievements:
            welcome_text += f"✅ {ach}\n"
        welcome_text += "\n"
    
    welcome_text += "Я бот-помощник по партнерским программам.\n"
    welcome_text += "Выберите категорию из меню ниже:"
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📞 По всем вопросам: {ADMIN_USERNAME}\n\n"
        "📋 Как работает бот:\n"
        "1. Выберите категорию\n2. Перейдите по ссылке\n"
        "3. Выполните задание\n4. Нажмите 'Выполнил задание'\n"
        "5. Отправьте данные\n\n"
        "💳 **Пополнение баланса:**\n"
        "• Через меню '💰 Баланс'\n"
        "• Автоматическое зачисление через ЮKассу\n\n"
        "👤 **Профиль:**\n"
        "• Баланс и рейтинг\n"
        "• Мои покупки\n"
        "• Ежедневные бонусы\n"
        "• Реферальная система",
        reply_markup=main_menu_keyboard()
    )

# ====================== АДМИН КОМАНДЫ ======================
async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "💰 **Выдача баланса**\n\n"
            "Использование:\n"
            "/addbalance <сумма> - выдать себе баланс\n"
            "/addbalance <сумма> <user_id> - выдать баланс пользователю\n\n"
            "Примеры:\n"
            "/addbalance 1000 - выдать себе 1000₽\n"
            "/addbalance 500 123456789 - выдать 500₽ пользователю с ID 123456789",
            parse_mode='Markdown'
        )
        return
    
    try:
        amount = int(context.args[0])
        
        if len(context.args) > 1:
            target_user_id = int(context.args[1])
            db.add(target_user_id, "balance", amount)
            new_balance = db.get(target_user_id, "balance", 0)
            add_transaction(target_user_id, "deposit", amount, "Пополнение баланса администратором")
            
            await update.message.reply_text(
                f"✅ Баланс выдан!\n\n"
                f"👤 Пользователь ID: {target_user_id}\n"
                f"💰 Выдано: {amount}₽\n"
                f"📊 Новый баланс: {new_balance}₽"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"💰 Вам начислено {amount}₽\n\nВаш баланс: {new_balance}₽"
                )
            except:
                pass
        else:
            db.add(user.id, "balance", amount)
            new_balance = db.get(user.id, "balance", 0)
            add_transaction(user.id, "deposit", amount, "Пополнение баланса администратором")
            
            await update.message.reply_text(
                f"✅ Баланс выдан!\n\n"
                f"💰 Выдано: {amount}₽\n"
                f"📊 Ваш баланс: {new_balance}₽"
            )
    
    except ValueError:
        await update.message.reply_text("❌ Неверный формат! Используйте числа.\nПример: /addbalance 1000", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        logger.error(f"Ошибка в add_balance: {e}")

# ====================== БАЛАНС И ЮKАССА ======================
async def balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    balance = db.get(user.id, "balance", 0)
    
    keyboard = [
        [InlineKeyboardButton("💳 Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton("📊 История операций", callback_data="history")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    await update.message.reply_text(
        f"💰 **Твой баланс:** {balance}₽\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("50₽", callback_data="deposit_50")],
        [InlineKeyboardButton("100₽", callback_data="deposit_100")],
        [InlineKeyboardButton("500₽", callback_data="deposit_500")],
        [InlineKeyboardButton("1000₽", callback_data="deposit_1000")],
        [InlineKeyboardButton("5000₽", callback_data="deposit_5000")],
        [InlineKeyboardButton("◀️ Назад", callback_data="balance_menu")]
    ]
    
    await query.edit_message_text(
        "💳 **Пополнение баланса**\n\n"
        "Выберите сумму для пополнения:\n\n"
        "✅ Автоматическое зачисление через ЮKассу\n"
        "⏱ Мгновенное пополнение баланса\n"
        "🔒 Безопасные платежи",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def process_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    query = update.callback_query
    user = query.from_user
    
    await query.answer()
    
    # Создаем платеж в ЮKасса
    payment_data = await yookassa.create_payment(
        amount=amount,
        description=f"Пополнение баланса на {amount}₽",
        return_url="https://t.me/ProffitClick_bot",
        metadata={
            "user_id": user.id,
            "username": user.username or "",
            "type": "balance_deposit"
        }
    )
    
    if not payment_data or not payment_data.get("confirmation_url"):
        await query.edit_message_text(
            "❌ Ошибка при создании платежа. Попробуйте позже.",
            parse_mode='Markdown'
        )
        return
    
    # Сохраняем информацию о платеже
    payment_id = payment_data["id"]
    db.create_payment(payment_id, user.id, amount, f"Пополнение баланса на {amount}₽")
    
    keyboard = [
        [InlineKeyboardButton("🔗 Перейти к оплате", url=payment_data["confirmation_url"])],
        [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_payment_{payment_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="deposit")]
    ]
    
    await query.edit_message_text(
        f"💳 **Пополнение баланса на {amount}₽**\n\n"
        f"🆔 ID платежа: `{payment_id}`\n"
        f"💰 Сумма: {amount}₽\n\n"
        "1. Нажмите 'Перейти к оплате'\n"
        "2. Оплатите счет\n"
        "3. Нажмите 'Проверить оплату'\n\n"
        "✅ Баланс пополнится автоматически после оплаты",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def check_payment_status(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_id: str):
    query = update.callback_query
    user = query.from_user
    
    await query.answer("🔍 Проверяем оплату...")
    
    # Проверяем статус платежа в ЮKасса
    payment_info = await yookassa.check_payment(payment_id)
    
    if not payment_info:
        await query.edit_message_text(
            "❌ Не удалось проверить платеж. Попробуйте позже.",
            parse_mode='Markdown'
        )
        return
    
    payment_db = db.get_payment(payment_id)
    
    if payment_info["status"] == "succeeded" and payment_info["paid"]:
        # Платеж успешен
        if payment_db and payment_db["status"] != "succeeded":
            # Зачисляем средства
            amount = payment_info["amount"]
            db.add(user.id, "balance", amount)
            db.update_payment_status(payment_id, "succeeded")
            add_transaction(user.id, "deposit", amount, f"Пополнение баланса через ЮKассу (ID: {payment_id})")
            
            new_balance = db.get(user.id, "balance", 0)
            
            keyboard = [
                [InlineKeyboardButton("💰 Перейти к балансу", callback_data="balance_menu")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            
            await query.edit_message_text(
                f"✅ **Оплата успешно завершена!**\n\n"
                f"💰 Зачислено: {amount}₽\n"
                f"📊 Ваш баланс: {new_balance}₽\n\n"
                "Спасибо за оплату!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            # Платеж уже обработан
            await query.edit_message_text(
                "✅ Этот платеж уже был обработан ранее.",
                parse_mode='Markdown'
            )
    
    elif payment_info["status"] == "pending":
        # Платеж в ожидании
        keyboard = [
            [InlineKeyboardButton("🔄 Проверить снова", callback_data=f"check_payment_{payment_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="deposit")]
        ]
        
        await query.edit_message_text(
            f"⏳ **Ожидание оплаты**\n\n"
            f"🆔 ID платежа: `{payment_id}`\n"
            f"💰 Сумма: {payment_info['amount']}₽\n\n"
            "Платеж еще не поступил. Если вы оплатили, подождите несколько минут и проверьте снова.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif payment_info["status"] == "canceled":
        # Платеж отменен
        db.update_payment_status(payment_id, "canceled")
        
        keyboard = [
            [InlineKeyboardButton("💳 Попробовать снова", callback_data="deposit")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            "❌ **Платеж отменен**\n\n"
            "Платеж был отменен или произошла ошибка оплаты.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    else:
        # Неизвестный статус
        await query.edit_message_text(
            f"❓ **Статус платежа:** {payment_info['status']}\n\n"
            "Попробуйте проверить позже.",
            parse_mode='Markdown'
        )

# ====================== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ (ВСЕ В ОДНОМ) ======================
async def profile_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Проверяем ежедневный бонус
    bonus, streak = check_daily_bonus(user_id)
    
    balance = db.get(user_id, "balance", 0)
    completed_tasks = len(db.get_list(user_id, "completed_tasks"))
    referrals = db.get_list(user_id, "referrals")
    achievements = db.get_list(user_id, "achievements")
    transactions = db.get_list(user_id, "transactions")
    rating = get_user_rating(user_id)
    
    # Получаем все купленные курсы
    purchased_courses = []
    for course_id in COURSES:
        if db.has(user_id, f"course_{course_id}"):
            purchased_courses.append(course_id)
    
    total_earned = sum([t["amount"] for t in transactions if t["amount"] > 0])
    total_spent = abs(sum([t["amount"] for t in transactions if t["amount"] < 0]))
    
    text = f"👤 **ПРОФИЛЬ {user.first_name}**\n\n"
    
    # Баланс
    text += f"💰 **Баланс:** {balance}₽\n"
    text += f"📊 Заработано всего: {total_earned}₽\n"
    text += f"💸 Потрачено всего: {total_spent}₽\n\n"
    
    # Ежедневный бонус
    if bonus is not None:
        text += f"🎁 **Ежедневный бонус:** {bonus}₽ ✅\n"
    text += f"🔥 **Стрик бонусов:** {streak} дней\n\n"
    
    # Статистика
    text += f"✅ **Выполнено заданий:** {completed_tasks}\n"
    text += f"🤝 **Приглашено друзей:** {len(referrals)}\n"
    text += f"🏆 **Достижений:** {len(achievements)}\n"
    text += f"⭐ **Рейтинг:** {rating} очков\n\n"
    
    # Реферальная ссылка
    referral_code = get_referral_code(user_id)
    bot_info = await context.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={referral_code}"
    text += f"🔗 **Реферальная ссылка:**\n`{referral_link}`\n\n"
    
    # Мои покупки
    if purchased_courses:
        text += "🛒 **Мои покупки:**\n"
        for i, course_id in enumerate(purchased_courses[:3], 1):
            course = COURSES[course_id]
            text += f"{i}. {course['title']}\n"
        if len(purchased_courses) > 3:
            text += f"... и еще {len(purchased_courses) - 3}\n"
        text += "\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 История операций", callback_data="history")],
        [InlineKeyboardButton("🤝 Реферальная система", callback_data="referral_menu")],
        [InlineKeyboardButton("🏆 Все достижения", callback_data="all_achievements")],
        [InlineKeyboardButton("🛒 Все покупки", callback_data="all_purchases")],
        [InlineKeyboardButton("🏆 Рейтинги", callback_data="ratings_menu")]
    ]
    
    # Добавляем кнопку пополнения, если баланс низкий
    if balance < 100:
        keyboard.insert(0, [InlineKeyboardButton("💳 Пополнить баланс", callback_data="deposit")])
    
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def all_purchases_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    
    await query.answer()
    
    # Получаем все купленные курсы
    purchased_courses = []
    for course_id in COURSES:
        if db.has(user_id, f"course_{course_id}"):
            purchased_courses.append(course_id)
    
    # Получаем историю покупок
    purchases = db.get_list(user_id, "purchased_items")
    
    if not purchased_courses and not purchases:
        await query.edit_message_text(
            "🛒 **Мои покупки**\n\n"
            "У вас пока нет покупок.\n\n"
            "🎓 Посмотрите доступные курсы в разделе '🎓 Курсы'",
            parse_mode='Markdown'
        )
        return
    
    text = "🛒 **Все мои покупки**\n\n"
    
    if purchased_courses:
        text += "🎓 **Купленные курсы:**\n\n"
        for i, course_id in enumerate(purchased_courses, 1):
            course = COURSES[course_id]
            text += f"{i}. **{course['title']}** - {course['price']}₽\n"
        
        keyboard = []
        for course_id in purchased_courses:
            course = COURSES[course_id]
            keyboard.append([
                InlineKeyboardButton(
                    f"📖 {course['title']}",
                    callback_data=f"open_course_{course_id}"
                )
            ])
        
        if purchases:
            text += "\n📋 **История покупок:**\n"
            recent_purchases = purchases[-5:][::-1]
            for purchase in recent_purchases:
                date = datetime.fromisoformat(purchase["date"]).strftime("%d.%m.%Y")
                text += f"• {date} - {purchase['description']} - {purchase['amount']}₽\n"
        
        keyboard.append([InlineKeyboardButton("◀️ Назад в профиль", callback_data="profile_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        # Только история покупок
        text += "📋 **История покупок:**\n\n"
        for purchase in purchases[-10:][::-1]:
            date = datetime.fromisoformat(purchase["date"]).strftime("%d.%m.%Y %H:%M")
            text += f"• {date}\n{purchase['description']} - {purchase['amount']}₽\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🎓 Смотреть курсы", callback_data="courses_menu")],
            [InlineKeyboardButton("◀️ Назад в профиль", callback_data="profile_menu")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def open_course(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    user = query.from_user
    
    await query.answer()
    
    course = COURSES[course_id]
    
    keyboard = [
        [InlineKeyboardButton("🎬 Открыть плейлист YouTube", url=course["youtube_playlist"])],
        [InlineKeyboardButton("⬅️ Назад к покупкам", callback_data="all_purchases")]
    ]
    
    await query.edit_message_text(
        f"🎓 **{course['title']}**\n\n"
        f"💰 Цена покупки: {course['price']}₽\n"
        f"📚 Описание: {course['description']}\n\n"
        f"🔗 **Доступ к материалам:**\n"
        f"Нажмите кнопку ниже, чтобы открыть полный плейлист курса на YouTube.\n\n"
        f"🎯 **Рекомендации:**\n"
        f"• Смотрите уроки по порядку\n"
        f"• Практикуйтесь после каждого урока\n"
        f"• Задавайте вопросы в комментариях\n"
        f"• Делайте заметки",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ====================== РЕЙТИНГИ ======================
async def ratings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Получаем топ пользователей
    top_users = get_top_users(limit=15)
    
    # Получаем позицию текущего пользователя
    user_rating = get_user_rating(user_id)
    user_position = None
    
    for i, (uid, rating) in enumerate(top_users, 1):
        if uid == user_id:
            user_position = i
            break
    
    text = "🏆 **Рейтинги пользователей**\n\n"
    
    if user_position:
        text += f"⭐ **Ваша позиция:** #{user_position}\n"
        text += f"📊 **Ваш рейтинг:** {user_rating} очков\n\n"
    
    text += "**Топ-15 пользователей:**\n\n"
    
    for i, (uid, rating) in enumerate(top_users[:15], 1):
        medal = ""
        if i == 1:
            medal = "🥇 "
        elif i == 2:
            medal = "🥈 "
        elif i == 3:
            medal = "🥉 "
        
        if uid == user_id:
            text += f"{i}. {medal}👤 **Вы** - {rating} очков ⭐\n"
        else:
            # Пытаемся получить имя пользователя
            try:
                chat = await context.bot.get_chat(uid)
                name = chat.first_name or f"Пользователь {uid}"
                username = f" (@{chat.username})" if chat.username else ""
                text += f"{i}. {medal}👤 {name}{username} - {rating} очков\n"
            except:
                text += f"{i}. {medal}👤 Пользователь {uid} - {rating} очков\n"
    
    text += "\n📈 **Как считается рейтинг:**\n"
    text += "• Баланс × 0.001\n"
    text += "• Задания × 10\n"
    text += "• Рефералы × 50\n"
    text += "• Покупки × 30\n"
    text += "• Достижения × 100\n"
    
    keyboard = [
        [InlineKeyboardButton("👤 Мой профиль", callback_data="profile_menu")],
        [InlineKeyboardButton("🤝 Рефералы", callback_data="referral_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ====================== ИСТОРИЯ ОПЕРАЦИЙ ======================
async def history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id
    
    transactions = db.get_list(user_id, "transactions")
    
    if not transactions:
        text = "📊 **История операций**\n\n"
        text += "У вас пока нет операций."
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="balance_menu")]]
        
        if query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return
    
    recent_transactions = transactions[-10:][::-1]
    text = "📊 **История операций**\n\n"
    text += f"Всего операций: {len(transactions)}\n\n"
    
    type_icons = {
        "deposit": "💳",
        "withdraw": "💸",
        "bonus": "🎁",
        "referral": "🤝",
        "purchase": "🛒",
        "payment": "💎"
    }
    
    type_names = {
        "deposit": "Пополнение",
        "withdraw": "Списание",
        "bonus": "Бонус",
        "referral": "Реферал",
        "purchase": "Покупка",
        "payment": "Оплата"
    }
    
    for trans in recent_transactions:
        date = datetime.fromisoformat(trans["date"]).strftime("%d.%m.%Y %H:%M")
        icon = type_icons.get(trans["type"], "💰")
        type_name = type_names.get(trans["type"], trans["type"])
        amount = trans["amount"]
        sign = "+" if amount > 0 else ""
        
        text += f"{icon} {date}\n"
        text += f"{type_name}: {sign}{amount}₽\n"
        
        if trans.get("description"):
            text += f" {trans['description']}\n"
        text += "\n"
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data="balance_menu")]
    ]
    
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ====================== РЕФЕРАЛЬНАЯ СИСТЕМА ======================
async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    referral_code = get_referral_code(user_id)
    referrals = db.get_list(user_id, "referrals")
    
    bot_info = await context.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={referral_code}"
    
    total_earned = sum([t["amount"] for t in db.get_list(user_id, "transactions") if t.get("type") == "referral"])
    
    text = "🤝 **Реферальная система**\n\n"
    text += f"📎 Ваша реферальная ссылка:\n{referral_link}\n\n"
    text += f"👥 Приглашено друзей: {len(referrals)}\n"
    text += f"💰 Заработано на рефералах: {total_earned}₽\n\n"
    text += "💡 За каждого приглашенного друга вы получаете 50₽!\n"
    text += "А ваш друг получает 25₽ бонусом при регистрации.\n\n"
    text += "📊 **Топ рефералов:**\n"
    
    all_users = db.data.keys()
    referral_stats = []
    
    for uid in all_users:
        refs = db.get_list(uid, "referrals")
        if refs:
            referral_stats.append((uid, len(refs)))
    
    referral_stats.sort(key=lambda x: x[1], reverse=True)
    top_referrals = referral_stats[:5]
    
    for i, (uid, count) in enumerate(top_referrals, 1):
        if uid == user_id:
            text += f"{i}. 👤 Вы - {count} рефералов ⭐\n"
        else:
            text += f"{i}. 👤 Пользователь {uid} - {count} рефералов\n"
    
    keyboard = [
        [InlineKeyboardButton("📋 Скопировать ссылку", callback_data="copy_referral")],
        [InlineKeyboardButton("🏆 Рейтинги", callback_data="ratings_menu")],
        [InlineKeyboardButton("◀️ Назад", callback_data="profile_menu")]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def all_achievements_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_achievements = db.get_list(user_id, "achievements")
    
    all_achievements = {
        "first_task": {"name": "🎯 Первое задание", "desc": "Выполните первое задание", "reward": "50₽"},
        "task_beginner": {"name": "🌱 Новичок", "desc": "Выполните 10 заданий", "reward": "100₽"},
        "task_pro": {"name": "⭐ Профи заданий", "desc": "Выполните 50 заданий", "reward": "500₽"},
        "task_master": {"name": "🏆 Мастер заданий", "desc": "Выполните 100 заданий", "reward": "1000₽"},
        "wealthy": {"name": "💴 Состоятельный", "desc": "Накопите 10,000₽", "reward": "200₽"},
        "rich": {"name": "💵 Богач", "desc": "Накопите 100,000₽", "reward": "500₽"},
        "millionaire": {"name": "💰 Миллионер", "desc": "Накопите 1,000,000₽", "reward": "1000₽"},
        "referral_pro": {"name": "🤝 Реферальный профи", "desc": "Пригласите 5 друзей", "reward": "200₽"},
        "referral_king": {"name": "👑 Король рефералов", "desc": "Пригласите 10 друзей", "reward": "500₽"},
        "shopper": {"name": "🛒 Шопоголик", "desc": "Купите 5+ товаров/курсов", "reward": "300₽"},
        "investor": {"name": "📈 Инвестор", "desc": "Накопите 5,000₽ на балансе", "reward": "200₽"}
    }
    
    text = "🏆 **Все достижения**\n\n"
    
    for ach_id, ach_info in all_achievements.items():
        if ach_id in user_achievements:
            text += f"✅ {ach_info['name']}\n"
            text += f"   {ach_info['desc']}\n"
            text += f"   🎁 Награда: {ach_info['reward']}\n\n"
        else:
            text += f"❌ {ach_info['name']}\n"
            text += f"   {ach_info['desc']}\n"
            text += f"   🎁 Награда: {ach_info['reward']}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад в профиль", callback_data="profile_menu")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ====================== КУРСЫ (БЕЗ ПРЕДПРОСМОТРА) ======================
async def courses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for course_id, course in COURSES.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{course['title']} - {course['price']}₽",
                callback_data=f"view_course_{course_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")])
    
    await update.message.reply_text(
        "🎓 **Доступные курсы:**\n\n"
        "Выберите курс для покупки:\n\n"
        "🎬 Каждый курс включает полный плейлист YouTube уроков\n"
        "📚 Практические задания и материалы\n"
        "✅ Доступ навсегда после покупки",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def buy_course(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id):
    query = update.callback_query
    user = query.from_user
    
    if not query:
        return
    
    await query.answer()
    
    course = COURSES[course_id]
    
    if db.has(user.id, f"course_{course_id}"):
        await query.answer("✅ У вас уже есть этот курс!", show_alert=True)
        
        keyboard = [
            [InlineKeyboardButton("🎬 Открыть плейлист", url=course["youtube_playlist"])],
            [InlineKeyboardButton("◀️ Назад к курсам", callback_data="back_to_courses")]
        ]
        
        await query.edit_message_text(
            f"🎓 **{course['title']}**\n\n"
            f"💰 Цена: {course['price']}₽\n\n"
            f"✅ **Вы уже приобрели этот курс!**\n\n"
            f"🔗 Ссылка на плейлист:\n{course['youtube_playlist']}\n\n"
            "Нажмите кнопку ниже, чтобы открыть плейлист.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    balance = db.get(user.id, "balance", 0)
    
    if balance >= course['price']:
        # Покупка курса
        db.add(user.id, "balance", -course['price'])
        db.set(user.id, f"course_{course_id}", True)
        
        # Добавляем в историю покупок
        purchase_record = {
            "date": datetime.now().isoformat(),
            "type": "purchase",
            "amount": -course['price'],
            "description": f"Курс: {course['title']}",
            "course_id": course_id
        }
        db.append(user.id, "purchased_items", purchase_record)
        
        add_transaction(user.id, "purchase", -course['price'], f"Покупка курса: {course['title']}")
        
        # Проверяем достижения
        check_achievements(user.id)
        
        # Уведомление администратору
        admin_msg = (
            f"🎓 НОВАЯ ПОКУПКА КУРСА\n\n"
            f"👤 Пользователь: @{user.username or 'без username'}\n"
            f"🆔 ID: {user.id}\n"
            f"💳 Курс: {course['title']}\n"
            f"💰 Сумма: {course['price']}₽\n"
            f"📊 Новый баланс: {db.get(user.id, 'balance', 0)}₽"
        )
        
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу: {e}")
        
        keyboard = [
            [InlineKeyboardButton("🎬 Открыть плейлист", url=course["youtube_playlist"])],
            [InlineKeyboardButton("🎓 Другие курсы", callback_data="back_to_courses")]
        ]
        
        await query.edit_message_text(
            f"🎉 **Поздравляем с покупкой!**\n\n"
            f"🎓 **{course['title']}**\n\n"
            f"💰 СписаноВ: {course['price']}₽\n"
            f"📊 Новый баланс: {db.get(user.id, 'balance', 0)}₽\n\n"
            f"🔗 **Ссылка на плейлист курса:**\n{course['youtube_playlist']}\n\n"
            "Нажмите кнопку ниже, чтобы начать обучение!\n\n"
            "🎯 **Советы:**\n"
            "• Смотрите уроки по порядку\n"
            "• Выполняйте практические задания\n"
            "• Задавайте вопросы в комментариях\n"
            "• Делитесь прогрессом с друзьями",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        
        keyboard = [
            [InlineKeyboardButton("💳 Пополнить баланс", callback_data="deposit")],
            [InlineKeyboardButton("◀️ Назад к курсам", callback_data="back_to_courses")]
        ]
        
        await query.edit_message_text(
            f"🎓 **{course['title']}**\n\n"
            f"💰 Цена: {course['price']}₽\n"
            f"📊 Ваш баланс: {balance}₽\n\n"
            "❌ Недостаточно средств для покупки!\n\n"
            f"💳 Пополните баланс через меню '💰 Баланс'\n"
            "✅ Быстрое пополнение через ЮKассу",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ====================== ОБРАБОТКА МЕНЮ ======================
async def show_tasks(message):
    keyboard = [
        [InlineKeyboardButton("Лендинг с заданиями", callback_data="task_1")],
        [InlineKeyboardButton("Яндекс.Браузер ПК", callback_data="task_2")],
        [InlineKeyboardButton("Яндекс.Браузер смартфон", callback_data="task_3")],
        [InlineKeyboardButton("Яндекс.Поиск", callback_data="task_4")],
        [InlineKeyboardButton("Приложение с Алисой", callback_data="task_5")]
    ]
    await message.reply_text("🏆 Задания Яндекса:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_jobs(message):
    keyboard = [
        [InlineKeyboardButton("Яндекс.Курьер", callback_data="job_1")],
        [InlineKeyboardButton("Партнёр Альфа-Банк", callback_data="job_2")],
        [InlineKeyboardButton("Брокер Альфа-Банк", callback_data="job_3")]
    ]
    await message.reply_text("💼 Работа:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_cards(message):
    keyboard = [
        [InlineKeyboardButton("T-BANK Black 500₽", callback_data="card_1")],
        [InlineKeyboardButton("T-BANK Исламская 700₽", callback_data="card_2")],
        [InlineKeyboardButton("ALL Airlines 500₽", callback_data="card_3")],
        [InlineKeyboardButton("T-BANK Platinum 500₽", callback_data="card_4")],
        [InlineKeyboardButton("ПСБ Кешбэк 700₽", callback_data="card_5")],
        [InlineKeyboardButton("ВТБ Кредитная 2000₽", callback_data="card_6")],
        [InlineKeyboardButton("Плати по миру 5000₽", callback_data="card_7")],
        [InlineKeyboardButton("Альфа-Карта 4000₽", callback_data="card_8")],
        [InlineKeyboardButton("Семейный счёт 2500₽", callback_data="card_9")],
        [InlineKeyboardButton("60 дней без % 8500₽", callback_data="card_10")],
        [InlineKeyboardButton("Детская карта 3500₽", callback_data="card_11")]
    ]
    await message.reply_text("💳 Банковские карты:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_credits(message):
    keyboard = [
        [InlineKeyboardButton("Кредит наличными 5000₽", callback_data="credit_1")],
        [InlineKeyboardButton("Кредит на планы 2500₽", callback_data="credit_2")],
        [InlineKeyboardButton("Ипотека 250 000₽", callback_data="credit_3")],
        [InlineKeyboardButton("Предодобренный 25 000₽", callback_data="credit_4")]
    ]
    await message.reply_text("💰 Кредиты:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_insurance(message):
    keyboard = [
        [InlineKeyboardButton("Zetta спортсмены 1000₽", callback_data="insur_1")],
        [InlineKeyboardButton("Zetta школьники", callback_data="insur_2")],
        [InlineKeyboardButton("Сберстрахование 2500₽", callback_data="insur_3")],
        [InlineKeyboardButton("Т-Страхование", callback_data="insur_4")]
    ]
    await message.reply_text("🛡 Страхование:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_real_estate(message):
    keyboard = [
        [InlineKeyboardButton("Яндекс.Аренда 30 000₽", callback_data="estate_1")]
    ]
    await message.reply_text("🏠 Недвижимость:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_tourism(message):
    keyboard = [
        [InlineKeyboardButton("AVIASALES 5000₽", callback_data="tour_1")],
        [InlineKeyboardButton("Яндекс.Путешествия 3000₽", callback_data="tour_2")],
        [InlineKeyboardButton("KIWITAXI 5000₽", callback_data="tour_3")]
    ]
    await message.reply_text("✈️ Туризм:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_business(message):
    keyboard = [
        [InlineKeyboardButton("Регистрация бизнеса 25 000₽", callback_data="biz_1")],
        [InlineKeyboardButton("Расчётный счёт 2000₽", callback_data="biz_2")],
        [InlineKeyboardButton("Интернет-эквайринг 15 000₽", callback_data="biz_3")]
    ]
    await message.reply_text("🏢 Бизнес:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_brokerage(message):
    keyboard = [
        [InlineKeyboardButton("Брокерский счёт 12 500₽", callback_data="broker_1")]
    ]
    await message.reply_text("📊 Брокерские счета:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_subscriptions(message):
    keyboard = [
        [InlineKeyboardButton("Alfa Only Premium 2500₽", callback_data="sub_1")]
    ]
    await message.reply_text("🌟 Подписки:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_sim_cards(message):
    keyboard = [
        [InlineKeyboardButton("Альфа-Мобайл 500₽", callback_data="sim_1")]
    ]
    await message.reply_text("📱 SIM-карты:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🏆 Задания":
        await show_tasks(update.message)
    elif text == "💼 Работа":
        await show_jobs(update.message)
    elif text == "💳 Банковские карты":
        await show_cards(update.message)
    elif text == "💰 Кредиты":
        await show_credits(update.message)
    elif text == "🛡 Страхование":
        await show_insurance(update.message)
    elif text == "🏠 Недвижимость":
        await show_real_estate(update.message)
    elif text == "✈️ Туризм и путешествия":
        await show_tourism(update.message)
    elif text == "🏢 Бизнес":
        await show_business(update.message)
    elif text == "📊 Брокерские счета":
        await show_brokerage(update.message)
    elif text == "🌟 Подписки":
        await show_subscriptions(update.message)
    elif text == "📱 SIM-карты":
        await show_sim_cards(update.message)
    elif text == "🎓 Курсы":
        await courses_menu(update, context)
    elif text == "💰 Баланс":
        await balance_menu(update, context)
    elif text == "👤 Профиль":
        await profile_menu(update, context)
    elif text == "📞 Связь с админом":
        await update.message.reply_text(
            f"📞 Связь с администратором:\n\n"
            f"Telegram: {ADMIN_USERNAME}\n\n"
            "Напишите админу для решения вопросов:\n"
            "• Проблемы с заданиями\n"
            "• Вопросы по выплатам\n"
            "• Технические проблемы\n"
            "• Предложения по улучшению",
            reply_markup=main_menu_keyboard()
        )

# ====================== ОБРАБОТКА КНОПОК ======================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if not query:
        return
    
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "main_menu":
        user = query.from_user
        balance = db.get(user.id, "balance", 0)
        
        await query.message.reply_text(
            f"👋 Добро пожаловать, {user.first_name}!\n"
            f"💰 Твой баланс: {balance}₽",
            reply_markup=main_menu_keyboard()
        )
        return
    
    if data == "balance_menu":
        await balance_menu(Update(update.update_id, message=query.message), context)
        return
    
    if data == "history":
        update_obj = Update(update.update_id, callback_query=query)
        await history_menu(update_obj, context)
        return
    
    if data == "profile_menu":
        update_obj = Update(update.update_id, message=query.message)
        await profile_menu(update_obj, context)
        return
    
    if data == "all_purchases":
        await all_purchases_menu(update, context)
        return
    
    if data == "referral_menu":
        update_obj = Update(update.update_id, message=query.message)
        await referral_menu(update_obj, context)
        return
    
    if data == "ratings_menu":
        update_obj = Update(update.update_id, message=query.message)
        await ratings_menu(update_obj, context)
        return
    
    if data == "all_achievements":
        await all_achievements_menu(update, context)
        return
    
    if data == "copy_referral":
        user_id = query.from_user.id
        referral_code = get_referral_code(user_id)
        bot_info = await context.bot.get_me()
        referral_link = f"https://t.me/{bot_info.username}?start={referral_code}"
        await query.answer(f"Ссылка: {referral_link}", show_alert=True)
        return
    
    if data == "deposit":
        await deposit_menu(update, context)
        return
    
    if data.startswith("deposit_"):
        try:
            amount = int(data.split("_")[1])
            await process_deposit(update, context, amount)
        except ValueError:
            await query.answer("❌ Ошибка суммы", show_alert=True)
        return
    
    if data.startswith("check_payment_"):
        payment_id = data.replace("check_payment_", "")
        await check_payment_status(update, context, payment_id)
        return
    
    if data.startswith("open_course_"):
        course_id = data.replace("open_course_", "")
        await open_course(update, context, course_id)
        return
    
    if data.startswith("view_course_"):
        course_id = data.replace("view_course_", "")
        course = COURSES[course_id]
        
        keyboard = [
            [InlineKeyboardButton(f"🛒 Купить за {course['price']}₽", callback_data=f"buy_{course_id}")],
            [InlineKeyboardButton("◀️ Назад к курсам", callback_data="back_to_courses")]
        ]
        
        await query.edit_message_text(
            f"🎓 **{course['title']}**\n\n"
            f"💰 Цена: {course['price']}₽\n"
            f"📚 Описание: {course['description']}\n\n"
            f"🎬 **После покупки вы получите доступ к полному плейлисту на YouTube.**\n\n"
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    if data == "back_to_courses":
        keyboard = []
        for course_id, course in COURSES.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"{course['title']} - {course['price']}₽",
                    callback_data=f"view_course_{course_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")])
        
        await query.edit_message_text(
            "🎓 **Доступные курсы:**\n\n"
            "Выберите курс для покупки:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    if data.startswith("buy_"):
        course_id = data.replace("buy_", "")
        await buy_course(update, context, course_id)
        return
    
    if data == "fill_form":
        task_id = db.get(user_id, "current_task")
        if task_id:
            task_info = TASK_DATA.get(task_id)
            if task_info:
                db.set(user_id, "waiting_form", True)
                await query.message.reply_text(
                    f"📝 **{task_info['title']}**\n\n"
                    "Отправьте данные в формате:\n"
                    "Имя Фамилия Телефон Номер_карты @username\n\n"
                    "Пример:\nИван Иванов +79991234567 1234567812345678 @ivanov"
                )
        return
    
    if data in TASK_DATA:
        task_info = TASK_DATA[data]
        db.set(user_id, "current_task", data)
        
        keyboard = [
            [InlineKeyboardButton("🔗 Перейти по ссылке", url=task_info['link'])],
            [InlineKeyboardButton("✅ Выполнил задание", callback_data="fill_form")]
        ]
        
        await query.message.reply_text(
            f"**{task_info['title']}**\n\n{task_info['description']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ====================== ОБРАБОТКА СООБЩЕНИЙ ======================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if db.get(user_id, "waiting_form", False):
        user_message = update.message.text.strip()
        parts = user_message.split()
        
        if len(parts) < 5:
            await update.message.reply_text("❌ Неверный формат! Нужно: Имя Фамилия Телефон Номер_карты @username")
            return
        
        name = parts[0]
        surname = parts[1]
        phone = parts[2]
        card_number = parts[3]
        username = parts[4] if parts[4].startswith('@') else '@' + parts[4]
        
        task_id = db.get(user_id, "current_task", "unknown")
        task_info = TASK_DATA.get(task_id, {"title": "Неизвестно"})
        
        admin_msg = (
            f"📋 НОВАЯ ЗАЯВКА\n\n"
            f"👤 От: @{update.effective_user.username}\n"
            f"📛 Имя: {name} {surname}\n"
            f"📱 Телефон: {phone}\n"
            f"💳 Карта: {card_number}\n"
            f"🔗 Username: {username}\n"
            f"🎯 Задание: {task_info['title']}\n"
            f"🆔 ID пользователя: {user_id}"
        )
        
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
            logger.info(f"✅ Данные отправлены админу от {user_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу: {e}")
            await update.message.reply_text("❌ Ошибка отправки. Попробуйте позже.")
            return
        
        task_id = db.get(user_id, "current_task")
        if task_id:
            completed_tasks = db.get_list(user_id, "completed_tasks")
            if task_id not in completed_tasks:
                db.append(user_id, "completed_tasks", task_id)
                
                new_achievements = check_achievements(user_id)
                if new_achievements:
                    achievements_text = "\n\n🎉 **Новые достижения:**\n"
                    for ach in new_achievements:
                        achievements_text += f"✅ {ach}\n"
                else:
                    achievements_text = ""
            else:
                achievements_text = ""
        else:
            achievements_text = ""
        
        await update.message.reply_text(
            "✅ Спасибо! Данные отправлены администратору.\n\n"
            f"Ожидайте выплаты. Вопросы: {ADMIN_USERNAME}" + achievements_text,
            reply_markup=main_menu_keyboard(),
            parse_mode='Markdown'
        )
        
        db.set(user_id, "waiting_form", False)
        return
    
    await handle_main_menu(update, context)

# ====================== ОБРАБОТКА ОШИБОК ======================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок для стабильной работы"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    if isinstance(context.error, Exception):
        logger.error(f"Error details: {context.error}", exc_info=context.error)
    
    return True

# ====================== ЗАПУСК ======================
def main():
    print("=" * 60)
    print("🚀 БОТ ЗАПУСКАЕТСЯ НА KOYEB")
    print(f"💳 ЮKасса: {YOOKASSA_SHOP_ID}")
    print("=" * 60)
    
    try:
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("balance", balance_menu))
        application.add_handler(CommandHandler("courses", courses_menu))
        application.add_handler(CommandHandler("addbalance", add_balance))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        application.add_error_handler(error_handler)
        
        print("✅ Бот инициализирован")
        print("💳 ЮKасса подключена")
        print("📡 Запускаю polling...")
        
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        print("🤖 Бот готов к работе!")
        print("=" * 60)
        print(f"📊 Заданий: {len(TASK_DATA)}")
        print(f"🎓 Курсов: {len(COURSES)}")
        print(f"👤 Админ: {ADMIN_USERNAME}")
        print(f"💳 ЮKасса: ✅ Активна")
        print(f"👤 Профиль: ✅ Все в одном")
        print("=" * 60)
    
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
