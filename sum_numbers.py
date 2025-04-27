import logging
from telegram import ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler, ContextTypes
import requests
from datetime import date


TOKEN = '8070834822:AAGVoAwztDQFrRuOqB4rffcZ3klu4aUMejw'
ADMIN_ID = 1918076606
MAIL_ADDRESS = 'support@example.com'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

GETTING_FIRST_CURRENCY, GETTING_SECOND_CURRENCY = range(2)
AVAILABLE_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CNY", "KZT", "TRY", "CHF"]
CBRF_API_URL = 'https://www.cbr-xml-daily.ru/daily_json.js'


def calculate_deposit(initial_sum, interest_rate, years):
    return round(float(initial_sum) * (1 + float(interest_rate) / 100) ** float(years), 2)


async def start_command(update, context):
    keyboard = [
        [InlineKeyboardButton("Рассчитать итоговую сумму вклада", callback_data="deposit")],
        [InlineKeyboardButton("Отправить отзыв", callback_data="feedback")],
        [InlineKeyboardButton("Курс валют", callback_data="exchange_rate")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Доброго времени суток, я — бот-помощник по финансовой грамотности.\nЧто вы хотите сделать?",
        reply_markup=reply_markup
    )


async def button_callback(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "deposit":
        await query.edit_message_text(
            '''Напишите начальную сумму вклада, процент вклада и время, через которое вы хотите вывести деньги, 
            через пробел.''')

    elif query.data == "feedback":
        await query.edit_message_text(
            '''Большое спасибо за то, что оставляете обратную связь!\nПросим Вас написать отзыв, максимально точно 
            расписав весь Ваш опыт взаимодействия с ботом.''')
        context.user_data['awaiting_feedback'] = True
    elif query.data == "exchange_rate":
        await query.edit_message_text("Укажите валюту, из которой будете конвертировать (например, USD):")
        return GETTING_FIRST_CURRENCY


async def first_currency(update, context):
    first_currency = update.message.text.upper()
    if first_currency not in AVAILABLE_CURRENCIES:
        await update.message.reply_text("Указанная валюта не поддерживается. Используйте доступные коды валют.")
        return GETTING_FIRST_CURRENCY
    context.user_data['first_currency'] = first_currency
    await update.message.reply_text("Укажите валюту, в которую хотите конвертировать (например, EUR):")
    return GETTING_SECOND_CURRENCY


async def second_currency(update, context):
    second_currency = update.message.text.upper()
    if second_currency not in AVAILABLE_CURRENCIES:
        await update.message.reply_text("Указанная валюта не поддерживается. Используйте доступные коды валют.")
        return GETTING_SECOND_CURRENCY
    context.user_data['second_currency'] = second_currency

    first_currency = context.user_data['first_currency']
    second_currency = context.user_data['second_currency']

    response = requests.get(CBRF_API_URL)
    data = response.json()

    today = date.today().strftime("%d-%m-%Y")

    first_valute = next((v for k, v in data["Valute"].items() if v["CharCode"] == first_currency), None)
    second_valute = next((v for k, v in data["Valute"].items() if v["CharCode"] == second_currency), None)

    if first_valute is None or second_valute is None:
        await update.message.reply_text("Данные по указанным валютам временно недоступны.")
        return ConversationHandler.END

    exchange_rate = first_valute['Value'] / second_valute['Value']

    answer = f"Сегодня ({today}) курс {first_currency} к {second_currency}: {exchange_rate:.2f}"
    await update.message.reply_text(answer)
    return ConversationHandler.END


async def cancel(update, context):
    keyboard = [
        [InlineKeyboardButton("Рассчитать итоговую сумму вклада", callback_data="deposit")],
        [InlineKeyboardButton("Отправить отзыв", callback_data="feedback")],
        [InlineKeyboardButton("Курс валют", callback_data="exchange_rate")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('''Доброго времени суток, я — бот-помощник по финансовой грамотности. 
    Что вы хотите сделать?''', reply_markup=reply_markup)
    return ConversationHandler.END


async def process_input(update, context):
    message_text = update.message.text.strip()
    chat_id = update.effective_chat.id


    if 'awaiting_feedback' in context.user_data and context.user_data['awaiting_feedback']:
        del context.user_data['awaiting_feedback']
        feedback_text = f"Отзыв от пользователя {chat_id}:\n\n{message_text}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=feedback_text)
        await update.message.reply_text(
            f'''Ваш отзыв уже отправлен модераторам. Все пожелания будут учтены в обновлениях.\nЕсли возникли сбои 
            в работе бота, то наша поддержка обитает по адресу *{MAIL_ADDRESS}*''',
            parse_mode="Markdown")
        return

    user_input = message_text.split()
    if len(user_input) != 3:
        await update.message.reply_text(
            '''Неправильный формат данных. Отправьте три числа через пробел: начальная сумма, процентная ставка и срок 
            в годах.''')
        return
    else:
        try:
            initial_sum = float(user_input[0])
            interest_rate = float(user_input[1])
            years = float(user_input[2])

            final_amount = calculate_deposit(initial_sum, interest_rate, years)
            await update.message.reply_text(f"Ваш вклад вырастет до {final_amount} рублей.")
        except ValueError:
            await update.message.reply_text("Ошибка: введённые значения некорректны. Убедитесь, что ввели числа.")


def main():
    application = Application.builder().token(TOKEN).build()

    conversation_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback)],
        states={
            GETTING_FIRST_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, first_currency)],
            GETTING_SECOND_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, second_currency)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conversation_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_input))

    logger.info('Bot started')
    application.run_polling()

if __name__ == '__main__':
    main()