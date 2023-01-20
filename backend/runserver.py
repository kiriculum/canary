import os

import environ
import uvicorn
from apscheduler.triggers.cron import CronTrigger
from django.core.management import call_command

from config.settings import MARKETS_SCHEDULER

env = environ.Env(SERVER_PORT=(int, 80), SERVER_HOST=(str, '0.0.0.0'), SERVER_RELOAD=(bool, False))
env.read_env('.env')


def setup_jobs():
    daily_market_update = 'sync allmarkets'
    daily_bonds_update = 'sync currentrates'
    trigger = CronTrigger(hour=23, minute=59, second=59)

    MARKETS_SCHEDULER.add_job(call_command, trigger, args=[daily_market_update])
    MARKETS_SCHEDULER.add_job(call_command, trigger, args=[daily_bonds_update])


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    uvicorn.run('config.asgi:app', host=env('SERVER_HOST'), port=env('SERVER_PORT'), reload=env('SERVER_RELOAD'))


if __name__ == '__main__':
    main()
    setup_jobs()
