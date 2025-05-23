import os
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from datetime import time, datetime

from storage import load_user_cities, save_user_cities

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_TOKEN = os.getenv("OPENWEATHER_TOKEN")

user_cities = load_user_cities()


def get_weather_forecast(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_TOKEN}&units=metric&lang=ru"
    response = requests.get(url)
    if response.status_code != 200:
        return None

    data = response.json()
    forecast_list = data["list"]
    today = datetime.now().date()

    result = [f"🌤 Прогноз погоды на сегодня в {city.title()}:\n"]
    has_data = False

    for item in forecast_list:
        forecast_time = datetime.fromtimestamp(item["dt"])
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
    await update.message.reply_text(
        "Привет! Чтобы установить город, напиши команду:\n"
        "/setcity <название города>\n"
        "Чтобы подписаться на ежедневную погоду, напиши /dailyweather\n"
        "Для тестовой проверки погоды напиши /testweather"
    )


async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        city = " ".join(context.args)
        forecast = get_weather_forecast(city)
        if forecast:
            user_id = str(update.effective_user.id)
            user_cities[user_id] = city
            save_user_cities(user_cities)
            await update.message.reply_text(f"Город установлен: {city}\n\n{forecast}")
        else:
            await update.message.reply_text("Не удалось найти такой город. Попробуйте снова.")
    else:
        await update.message.reply_text("Пожалуйста, укажи город после команды. Например: /setcity Москва")


async def send_daily_weather(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id = str(job_data["user_id"])
    city = user_cities.get(user_id)

    if city:
        forecast = get_weather_forecast(city)
        if forecast:
            await context.bot.send_message(chat_id=int(user_id), text=f"Доброе утро! Вот прогноз погоды на сегодня:\n\n{forecast}")
        else:
            await context.bot.send_message(chat_id=int(user_id), text=f"Не удалось получить прогноз погоды для города {city}.")
    else:
        await context.bot.send_message(chat_id=int(user_id), text="Вы не установили город. Используйте команду /setcity <город>.")


async def start_daily_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_id_str = str(user_id)

    if user_id_str not in user_cities:
        await update.message.reply_text("Сначала установите город с помощью команды /setcity")
        return

    current_jobs = context.job_queue.get_jobs_by_name(user_id_str)
    for job in current_jobs:
        job.schedule_removal()

    context.job_queue.run_daily(
        send_daily_weather,
        time=time(hour=8, minute=0),
        chat_id=user_id,
        name=user_id_str,
        data={"user_id": user_id}
    )

    await update.message.reply_text("Вы подписались на ежедневную рассылку прогноза в 8:00 утра!")


async def test_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    city = user_cities.get(user_id)
    if city:
        forecast = get_weather_forecast(city)
        if forecast:
            await update.message.reply_text(f"Тестовый прогноз погоды для {city}:\n\n{forecast}")
        else:
            await update.message.reply_text(f"Не удалось получить прогноз для города {city}.")
    else:
        await update.message.reply_text("Вы не установили город. Используйте команду /setcity <город>.")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setcity", set_city))
    app.add_handler(CommandHandler("dailyweather", start_daily_weather))
    app.add_handler(CommandHandler("testweather", test_weather))

    print("Бот запущен!")
    app.run_polling()


if __name__ == '__main__':
    main()
