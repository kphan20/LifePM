from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from telegram.ext import ContextTypes, CallbackContext
from telegram.constants import ParseMode
from telegram._update import Update
from datetime import time, date
from zoneinfo import ZoneInfo
from dotenv import dotenv_values

from html import escape
import json
import urllib.request

cfg = dotenv_values(".env")

FLASK_URL = f"http://{cfg['FLASK_HOST']}:{cfg['FLASK_PORT']}"

def get_time_value(hours: int, mins: int):
    return time(hour=hours, minute=mins, tzinfo=ZoneInfo('America/New_York'))

def get_task_str(task):
    return f'Task Name: {task['title']}\nDue Date: {task['due_date']}\nTime Estimate: {task['time_cost']} minutes'

# handle the response after the question
async def handle_time_reply(update: Update, ctx: CallbackContext):
    text = update.message.text
    if not text.isnumeric():
        # TODO why is intellisense not working
        await ctx.bot.send_message(chat_id=ctx._chat_id, text="Invalid number. Please enter a new time in minutes.")
        return
    mins = int(text)
    endpoint = f"{FLASK_URL}/get_daily/{mins}"
    with urllib.request.urlopen(endpoint) as res:
        json_dict = json.loads(res.read())

    notifications = json_dict['notifs']
    tasks = json_dict['tasks']
    
    print("Chosen Tasks:\n")
    for task in tasks:
        print(get_task_str(task))
    print()
    print("Notifications:")
    for notif in notifications:
        print(get_task_str(notif))
    
    msg_str = 'List of tasks:\n'
    for task in tasks:
        edit_endpoint = escape(f"{FLASK_URL}/edit/{task['id']}")
        msg_str += f"Task Name: <a href='{edit_endpoint}'>{task['title']}</a> - {task['time_cost']} minutes"
        due_date = task['due_date']
        due_str = ''
        if due_date is not None:
            diff = date.fromisoformat(due_date) - date.today()
            diff_days = diff.days
            plural_str = "s" if abs(diff_days) == 1 else ""
            if diff_days < 0:
                due_str = f'\nDue {-diff_days} day{plural_str} ago'
            elif diff_days == 0:
                due_str = f'\nDue TODAY'
            else:
                due_str = f'\nDue in {diff_days} day{plural_str}'
            due_time = task['due_time']
            if due_time is not None:
                due_time = time.fromisoformat(due_time)
                meridien = "PM" if due_time.hour >= 12 else "AM"
                hour = due_time.hour
                if hour == 0:
                    hour = 12
                elif hour > 12:
                    hour -= 12
                due_str += f' at {hour}:{due_time.minute} {meridien}'
        due_str += '\n\n'
        msg_str += due_str
        
    await ctx.bot.send_message(chat_id=ctx._chat_id, text=msg_str, parse_mode=ParseMode.HTML)
    
# daily job to send the message
async def send_daily_message(ctx: ContextTypes.DEFAULT_TYPE):
    await ctx.bot.send_message(chat_id=ctx.job.chat_id, text="How much time for today (in minutes)?")

# setting the time in which this app sends out the daily message
async def update_job_time(update: Update, ctx: CallbackContext):
    new_time = ctx.args[0] # TODO add check for one argument?
    
    time_parts = new_time.split(':')
    
    if len(time_parts) != 2 or not time_parts[0].isnumeric() or not time_parts[1].isnumeric():
        await ctx.bot.send_message(chat_id=ctx._chat_id, text="Make sure the time is in the format HH:MM.")
        return

    hour, mins = int(time_parts[0]), int(time_parts[1])
    if hour < 0 or hour > 23 or mins < 0 or mins > 59:
        await ctx.bot.send_message(chat_id=ctx._chat_id, text="Make sure the time is in a valid 24 hour format.")
        return
    
    for job in ctx.job_queue.get_jobs_by_name(str(cfg['DAILY_JOB_ID'])):
        job.schedule_removal()
    
    ctx.job_queue.run_daily(send_daily_message, time=get_time_value(hour, mins), chat_id=update.effective_message.chat_id, name=str(cfg['DAILY_JOB_ID']), )
    await ctx.bot.send_message(chat_id=ctx._chat_id, text="The daily time has been updated successfully (hopefully)!")

app = ApplicationBuilder().token(cfg['TELEGRAM_TOKEN']).build()

app.add_handler(CommandHandler("update_time", update_job_time, has_args=1))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_reply)) # TODO potentially use filters.REPLY instead

app.job_queue.run_daily(send_daily_message, time=get_time_value(8, 0), name=str(cfg['DAILY_JOB_ID']))

app.run_polling(poll_interval=5.)