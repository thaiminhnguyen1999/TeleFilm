import os
import logging
import requests
import streamlit as st
import telebot
from telebot import types
import paypalrestsdk

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define constants for PayPal configuration
PAYPAL_MODE = 'live'
PAYPAL_CLIENT_ID = st.secrets["PAYPAL_CLIENT_ID"]
PAYPAL_CLIENT_SECRET = st.secrets["PAYPAL_CLIENT_SECRET"]

# Initialize PayPal SDK
paypalrestsdk.configure({
    'mode': PAYPAL_MODE,
    'client_id': PAYPAL_CLIENT_ID,
    'client_secret': PAYPAL_CLIENT_SECRET
})

# Define constants for Free Forex API
FREE_FOREX_API_URL = 'https://www.freeforexapi.com/api/live'

# Initialize bot
bot = telebot.TeleBot(st.secrets["TELEGRAM_BOT_TOKEN"])

# Define conversation states
PAYMENT_AMOUNT, PAYMENT_CONFIRMATION, DONATE_CUSTOM, REGISTER, PACKAGE_CHOICE = range(5)

# Define helper functions for PayPal
def create_payment(amount, currency, description):
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "transactions": [{
            "amount": {
                "total": f"{amount:.2f}",
                "currency": currency
            },
            "description": description
        }],
        "redirect_urls": {
            "return_url": "http://localhost:3000/payment/execute",
            "cancel_url": "http://localhost:3000/"
        }
    })
    if payment.create():
        return payment
    else:
        return None

def get_exchange_rate():
    response = requests.get(f"{FREE_FOREX_API_URL}?pairs=USDCNH,USDVND")
    data = response.json()
    return data['rates']['USDVND']['rate']  # USD to VND

# Define command handlers
@bot.message_handler(commands=['start', 'openapp'])
def open_app(message):
    user = message.from_user
    msg = (
        f"Chào mừng bạn, **{user.first_name}**!\n"
        "Bạn đã bao giờ tự hỏi liệu có một ứng dụng dApp nào trên Telegram có thể xem phim trực tuyến miễn phí không? "
        "Câu trả lời là hoàn toàn có, mà còn là do người Việt Nam tạo ra. Với rất nhiều bộ phim khác nhau có bản lồng tiếng (vietdub) "
        "và phụ đề (vietsub), nhà phát triển **Nguyễn Thái Minh (@thaiminh0911)** đã tạo ra ứng dụng dApp chạy trên Telegram mang tên "
        "**TeleFilm**.\n"
        "Để có thể khởi chạy ứng dụng TeleFilm, bạn chỉ cần truy cập vào mục `Search` của **Telegram**, gõ `telefilm_dapp_bot` sau đó ấn vào con bot tên là "
        "**TeleFilm**, sau đó ấn vào nút `Start` (hoặc gõ `/start` hoặc `/openapp`) và ấn vào nút `Xem phim` bên dưới là có thể sử dụng.\n"
        "Đừng quên donate cho nhà phát triển để có thêm động lực up phim nữa nha (gõ `/donate` để donate)"
    )
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Xem phim", web_app=types.WebAppInfo("https://telefilm-dapp.glide.page")))
    bot.send_message(message.chat.id, msg, reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['info'])
def info(message):
    bot.send_message(message.chat.id, "TeleFilm (Phát triển bởi Nguyễn Thái Minh).\nPhiên bản: v1.0.1 Telegram dApp")

@bot.message_handler(commands=['donate'])
def donate(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("1$", callback_data='donate_1'))
    keyboard.add(types.InlineKeyboardButton("5$", callback_data='donate_5'))
    keyboard.add(types.InlineKeyboardButton("10$", callback_data='donate_10'))
    keyboard.add(types.InlineKeyboardButton("100$", callback_data='donate_100'))
    keyboard.add(types.InlineKeyboardButton("Tuỳ chỉnh", callback_data='donate_custom'))
    bot.send_message(message.chat.id, "Cảm ơn bạn đã donate. Bạn muốn donate bao nhiêu?", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('donate_'))
def donate_callback(call):
    amount = call.data.split('_')[1]
    if amount == 'custom':
        bot.send_message(call.message.chat.id, "Bạn muốn donate bao nhiêu (Đơn vị tiền tệ: $ cho Đô hoặc VND cho Đồng. Nhập ở cuối số tiền)?")
        bot.register_next_step_handler(call.message, donate_custom)
    else:
        amount = int(amount)
        user = call.from_user
        description = f"{user.username} has donated ${amount}"
        payment = create_payment(amount, "USD", description)
        if payment:
            approval_url = payment['links'][1]['href']
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("Thanh toán", url=approval_url))
            bot.send_message(call.message.chat.id, f"Đang chuyển hướng đến PayPal để thanh toán ${amount}.", reply_markup=keyboard)
        else:
            bot.send_message(call.message.chat.id, "Có lỗi xảy ra trong quá trình tạo thanh toán. Vui lòng thử lại sau.")

def donate_custom(message):
    amount_text = message.text
    exchange_rate = get_exchange_rate()
    if amount_text.endswith('$'):
        amount = float(amount_text[:-1])
        currency = 'USD'
    elif amount_text.endswith('VND'):
        amount = float(amount_text[:-3]) / exchange_rate  # Using live exchange rate
        currency = 'USD'
    else:
        bot.send_message(message.chat.id, "Định dạng số tiền không hợp lệ. Vui lòng nhập lại.")
        bot.register_next_step_handler(message, donate_custom)
        return
    
    if currency == 'USD' and amount < 0.5:
        bot.send_message(message.chat.id, "Số tiền của bạn phải trên 0.5$. Vui lòng nhập lại.")
        bot.register_next_step_handler(message, donate_custom)
        return
    elif currency == 'VND' and amount < (10000 / exchange_rate):
        bot.send_message(message.chat.id, "Số tiền của bạn phải trên 10000VND. Vui lòng nhập lại.")
        bot.register_next_step_handler(message, donate_custom)
        return
    
    user = message.from_user
    description = f"{user.username} has donated ${amount:.2f}"
    payment = create_payment(amount, currency, description)
    if payment:
        approval_url = payment['links'][1]['href']
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Thanh toán", url=approval_url))
        bot.send_message(message.chat.id, f"Đang chuyển hướng đến PayPal để thanh toán ${amount:.2f}.", reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, "Có lỗi xảy ra trong quá trình tạo thanh toán. Vui lòng thử lại sau.")

def check_payment(payment):
    if payment.execute({"payer_id": payment.payer.payer_info.payer_id}):
        return True
    else:
        return False

@bot.message_handler(commands=['register'])
def register(message):
    with open('pkg_table.jpg', 'rb') as photo:
        bot.send_photo(message.chat.id, photo)
    bot.send_message(message.chat.id, "Bạn muốn đăng kí gói nào (Xem bảng giá gói ở bên trên)?")
    bot.register_next_step_handler(message, package_choice)

def package_choice(message):
    package = message.text
    user = message.from_user
    logger.info(f"User {user.username} selected package {package}")

    if package not in ['ME2', 'ME3', 'ME4', 'ME5']:
        bot.send_message(message.chat.id, "Gói không hợp lệ. Vui lòng nhập lại.")
        bot.register_next_step_handler(message, package_choice)
        return
    
    package_amount = {
        'ME2': 2,
        'ME3': 5,
        'ME4': 7,
        'ME5': 10
    }
    amount = package_amount[package]
    description = f"{user.username} has subscribed to package {package}"
    payment = create_payment(amount, "USD", description)
    if payment:
        approval_url = payment['links'][1]['href']
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Thanh toán", url=approval_url))
        bot.send_message(message.chat.id, f"Bạn đang chuyển hướng đến trang Paypal để hoàn tất thanh toán đăng kí gói {package}", reply_markup=keyboard)
        if check_payment(payment):
            bot.send_message(message.chat.id, f"Thanh toán gói {package} thành công. Cảm ơn bạn đã đăng ký!", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Xem phim", web_app=types.WebAppInfo("https://telefilm-dapp.glide.page"))))
        else:
            bot.send_message(message.chat.id, f"Đăng kí gói {package} không thành công. Vui lòng thử lại.")
    else:
        bot.send_message(message.chat.id, "Có lỗi xảy ra trong quá trình tạo thanh toán. Vui lòng thử lại sau.")

if __name__ == '__main__':
    bot.polling(none_stop=True)
