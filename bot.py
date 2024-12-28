import json
import logging
import datetime
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    filename="bot_actions.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding='utf-8'
)

# === Класс для работы с историческими фактами ===
class HistoricalFacts:
    def __init__(self, language='ru'):
        self.language = language
        self.facts = self.load_facts()
        self.saved_facts = {}

    def load_facts(self):
        try:
            with open(f'facts_{self.language}.json', 'r', encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            print("Файл с фактами не найден!")
            return {}

    def save_facts(self):
        with open(f'facts_{self.language}.json', 'w', encoding='utf-8') as file:
            json.dump(self.facts, file, ensure_ascii=False, indent=4)

    def get_facts_for_date(self, month_day, category=None):
        facts_for_date = self.facts.get(month_day, [])
        if category:
            return [fact for fact in facts_for_date if fact.get('category') == category]
        return facts_for_date

    def save_favorite_fact(self, user_id, fact):
        if user_id not in self.saved_facts:
            self.saved_facts[user_id] = []
        self.saved_facts[user_id].append(fact)

    def get_favorite_facts(self, user_id):
        return self.saved_facts.get(user_id, [])

# === Telegram-бот ===
class HistoryBot(HistoricalFacts):
    def __init__(self, token, language='ru'):
        super().__init__(language)
        self.app = Application.builder().token(token).build()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info(f"Пользователь {update.message.from_user.id} вызвал команду /start")
        keyboard = [
            [InlineKeyboardButton("Факты на сегодня", callback_data='facts_today')],
            [InlineKeyboardButton("Поиск фактов по категории", callback_data='search_category')],
            [InlineKeyboardButton("Сохранённые факты", callback_data='saved_facts')],
            [InlineKeyboardButton("Случайный факт", callback_data='random_fact')],
            [InlineKeyboardButton("Игры", callback_data='games')],
            [InlineKeyboardButton("Сменить язык", callback_data='change_language')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Добро пожаловать! Выберите действие:", reply_markup=reply_markup
        )

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        logging.info(f"Пользователь {query.from_user.id} нажал кнопку {query.data}")
        await query.answer()

        if query.data == 'facts_today':
            today = datetime.date.today()
            month_day = f"{today.month:02d}-{today.day:02d}"
            facts = self.get_facts_for_date(month_day)
            if facts:
                message = "\n".join([f"- {fact['text']} ({fact['category']})" for fact in facts])
                await query.edit_message_text(f"Сегодня в истории:\n{message}")
            else:
                await query.edit_message_text("На сегодня фактов нет.")

        elif query.data == 'search_category':
            keyboard = [
                [InlineKeyboardButton("Наука", callback_data='category_science')],
                [InlineKeyboardButton("Культура", callback_data='category_culture')],
                [InlineKeyboardButton("Политика", callback_data='category_politics')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Выберите категорию:", reply_markup=reply_markup)

        elif query.data.startswith('category_'):
            category = query.data.split('_')[1]
            today = datetime.date.today()
            month_day = f"{today.month:02d}-{today.day:02d}"
            facts = self.get_facts_for_date(month_day, category=category)
            if facts:
                message = "\n".join([f"- {fact['text']}" for fact in facts])
                await query.edit_message_text(f"Факты на сегодня в категории '{category}':\n{message}")
            else:
                await query.edit_message_text(f"Фактов в категории '{category}' нет.")

        elif query.data == 'random_fact':
            all_facts = [fact for facts in self.facts.values() for fact in facts]
            if all_facts:
                random_fact = random.choice(all_facts)
                context.user_data['fact_to_save'] = random_fact
                keyboard = [
                    [InlineKeyboardButton("Сохранить факт", callback_data='save_fact')],
                    [InlineKeyboardButton("Не сохранять", callback_data='dismiss_fact')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    f"Случайный факт:\n{random_fact['text']} ({random_fact['category']})",
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text("Фактов пока нет.")

        elif query.data == 'save_fact':
            fact_to_save = context.user_data.get('fact_to_save')
            if fact_to_save:
                user_id = query.from_user.id
                self.save_favorite_fact(user_id, fact_to_save['text'])
                await query.edit_message_text("Факт сохранён!")
            else:
                await query.edit_message_text("Ошибка: Нет факта для сохранения.")

        elif query.data == 'dismiss_fact':
            await query.edit_message_text("Факт не сохранён.")

        elif query.data == 'saved_facts':
            user_id = query.from_user.id
            saved = self.get_favorite_facts(user_id)
            if saved:
                message = "\n".join([f"{idx+1}. {fact}" for idx, fact in enumerate(saved)])
                message += "\n\nВведите номер факта, который хотите удалить."
                await query.edit_message_text(f"Ваши сохранённые факты:\n{message}")
                context.user_data['awaiting_fact_number'] = True
            else:
                await query.edit_message_text("У вас пока нет сохранённых фактов.")

        elif query.data == 'games':
            keyboard = [[InlineKeyboardButton("Угадай год", callback_data='game_guess_year')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Выберите игру:", reply_markup=reply_markup)

        elif query.data == 'game_guess_year':
            fact = random.choice([fact for facts in self.facts.values() for fact in facts])
            fact_text = fact['text']
            correct_year = fact_text.split(' — ')[0].strip()
            fact_without_year = fact_text.split(' — ', 1)[1].strip()  # Убираем год из текста факта
            context.user_data['game_fact'] = fact
            context.user_data['correct_year'] = correct_year
            await query.edit_message_text(
                f"Игра 'Угадай год':\n{fact_without_year}\n\nВ каком году произошло это событие?"
            )

        elif query.data == 'change_language':
            keyboard = [
                [InlineKeyboardButton("Русский", callback_data='set_language_ru')],
                [InlineKeyboardButton("English", callback_data='set_language_en')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Выберите язык:", reply_markup=reply_markup)

        elif query.data.startswith('set_language_'):
            new_language = query.data.split('_')[-1]
            if new_language in ['ru', 'en']:
                self.language = new_language
                self.facts = self.load_facts()
                await query.edit_message_text(f"Язык изменён на {'Русский' if new_language == 'ru' else 'English'}.")
            else:
                await query.edit_message_text("Неверный выбор языка.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        text = update.message.text.strip()
        logging.info(f"Пользователь {user_id} отправил сообщение: {text}")

        if 'game_fact' in context.user_data and 'correct_year' in context.user_data:
            correct_year = context.user_data['correct_year']
            if text.isdigit():
                if text == correct_year:
                    await update.message.reply_text("Правильно! 🎉")
                    logging.info(f"Пользователь {user_id} правильно угадал год {correct_year}.")
                else:
                    await update.message.reply_text(f"Неправильно. Правильный ответ: {correct_year}.")
                    logging.info(f"Пользователь {user_id} ошибся. Правильный год: {correct_year}.")
                del context.user_data['game_fact']
                del context.user_data['correct_year']
            else:
                await update.message.reply_text("Пожалуйста, введите год в числовом формате.")

        elif context.user_data.get('awaiting_fact_number'):
            saved_facts = self.get_favorite_facts(user_id)
            if text.isdigit():
                fact_index = int(text) - 1
                if 0 <= fact_index < len(saved_facts):
                    deleted_fact = saved_facts.pop(fact_index)
                    await update.message.reply_text(f"Факт удалён: {deleted_fact}")
                    self.saved_facts[user_id] = saved_facts
                else:
                    await update.message.reply_text("Неверный номер факта.")
            else:
                await update.message.reply_text("Пожалуйста, введите номер факта.")
            context.user_data['awaiting_fact_number'] = False

        else:
            await update.message.reply_text("Я не понимаю этого сообщения. Используйте команды меню.")

    def run(self):
        logging.info("Запуск бота...")
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CallbackQueryHandler(self.handle_button))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.run_polling()

# Запуск бота
if __name__ == "__main__":
    token = "7921916797:AAGE3aSbTh4AX8biwZTjnu8D17PgtYrP-9M"
    bot = HistoryBot(token=token)
    bot.run()
