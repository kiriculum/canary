import os

import uvicorn
from apscheduler.triggers.cron import CronTrigger
from django.core.management import call_command

from config.settings import MARKETS_SCHEDULER


def setup_jobs():
    daily_market_update = 'sync allmarkets'
    daily_bonds_update = 'sync currentrates'
    trigger = CronTrigger(hour=23, minute=59, second=59)

    MARKETS_SCHEDULER.add_job(call_command, trigger, args=[daily_market_update])
    MARKETS_SCHEDULER.add_job(call_command, trigger, args=[daily_bonds_update])


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    uvicorn.run('config.asgi:app', host='0.0.0.0', port=80)


if __name__ == '__main__':
    main()
    setup_jobs()
