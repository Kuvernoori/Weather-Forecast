import os
import requests
from zoneinfo import ZoneInfo
from datetime import time, datetime

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, Defaults
)

from storage import load_user_cities, save_user_cities
from subscription_storage import load_subscriptions, save_subscriptions

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_TOKEN = os.getenv("OPENWEATHER_TOKEN")

almaty_tz = ZoneInfo("Asia/Almaty")
defaults = Defaults(tzinfo=almaty_tz)

user_cities = load_user_cities()
subscriptions = load_subscriptions()

last_sent = {}
def get_weather_forecast(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_TOKEN}&units=metric&lang=ru"
    response = requests.get(url)
    if response.status_code != 200:
        return None

    data = response.json()
    forecast_list = data.get("list", [])
    today = datetime.now(almaty_tz).date()

    result = [f"🌤 Прогноз погоды на сегодня в {city.title()}:\n"]
    has_data = False

    for item in forecast_list:
        forecast_time = datetime.fromtimestamp(item["dt"], tz=almaty_tz)
        if forecast_time.date() != today:
            continue

        temp = item["main"]["temp"]
        weather_desc = item["weather"][0]["description"]
        pop = item.get("pop", 0) * 100
        clouds = item["clouds"]["all"]
        wind = item["wind"]["speed"]
        time_str = forecast_time.strftime("%H:%M")

        line = f"🕒 {time_str} | 🌡 {temp:.0f}°C | {weather_desc.capitalize()}"
        if pop >= 20:
            line += f" | 🌧 Осадки: {pop:.0f}%"
        if clouds >= 70:
            line += f" | ☁️ Облачность: {clouds}%"
        if wind >= 5:
            line += f" | 💨 Ветер: {wind:.0f} м/с"

        result.append(line)
        has_data = True

    if not has_data:
        result.append("Сегодня прогноз отсутствует или ещё не доступен.")

    return "\n".join(result)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Привет! Чтобы установить твой город, напиши команду:\n"
        "/setcity <название города>\n"
        "Чтобы подписаться на ежедневную погоду, напиши /dailyweather\n"
    )
    if update.message:
        await update.message.reply_text(text)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        city = " ".join(context.args)
        forecast = get_weather_forecast(city)
        if forecast:
            user_id = str(update.effective_user.id)
            user_cities[user_id] = city
            save_user_cities(user_cities)
            text = f"Город установлен: {city}\n\n{forecast}"
        else:
            text = "Не удалось найти такой город. Попробуйте снова."
    else:
        text = "Пожалуйста, укажи город после команды. Например: /setcity Москва"

    if update.message:
        await update.message.reply_text(text)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


async def send_daily_weather_check(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(almaty_tz)
    user_id = context.job.data["user_id"]


    if last_sent.get(user_id) == now.date():
        return

    print(f"[send_daily_weather_check] Запуск в {now.time()}")
    if time(8, 0) <= now.time() <= time(8, 30):
        city = user_cities.get(user_id)
        if city:
            forecast = get_weather_forecast(city)
            if forecast:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=f"Доброе утро! Вот прогноз погоды на сегодня:\n\n{forecast}"
                )
            else:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=f"Не удалось получить прогноз погоды для города {city}."
                )
        else:
            await context.bot.send_message(
                chat_id=int(user_id),
                text="Вы не установили город. Используйте команду /setcity <город>."
            )

        last_sent[user_id] = now.date()

async def start_daily_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_id_str = str(user_id)

    if user_id_str not in user_cities:
        await update.message.reply_text("Сначала установите город с помощью команды /setcity")
        return

    current_jobs = context.job_queue.get_jobs_by_name(user_id_str)
    for job in current_jobs:
        job.schedule_removal()

    context.job_queue.run_repeating(
        send_daily_weather_check,
        interval=60,
        first=1,
        data={"user_id": user_id_str},
        name=user_id_str,
    )
    print(f"[start_daily_weather] Задача подписки запущена для пользователя {user_id_str}")
    await update.message.reply_text("Подписка на ежедневную рассылку погоды активирована!")


async def test_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    job_context = {"user_id": str(update.effective_user.id)}
    context.job = type("obj", (object,), {"data": job_context})
    await send_daily_weather_check(context)


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).defaults(defaults).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setcity", set_city))
    app.add_handler(CommandHandler("dailyweather", start_daily_weather))
    app.add_handler(CommandHandler("testweather", test_weather))

    print("✅ Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
