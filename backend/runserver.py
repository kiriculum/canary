import os

import environ
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management import execute_from_command_line

scheduler = BackgroundScheduler()
scheduler.start()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
env = environ.Env(SERVER_PORT=(int, 80), SERVER_HOST=(str, '0.0.0.0'), SERVER_RELOAD=(bool, False))
env.read_env('.env')


def setup_jobs():
    daily_update = ['manage.py', 'sync', 'daily']

    trigger = CronTrigger(hour=23, minute=59, second=59)
    scheduler.add_job(execute_from_command_line, trigger, args=[daily_update])


def main():
    uvicorn.run('config.asgi:app', host=env('SERVER_HOST'), port=env('SERVER_PORT'), reload=env('SERVER_RELOAD'))


def run_update(update: list[str]):
    execute_from_command_line(update)


if __name__ == '__main__':
    setup_jobs()
    main()
