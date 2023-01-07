from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd
from django.core.management import CommandError
from django.db import transaction
from pandas import Series

from markets.models import TreasuryRates
import logging

logger = logging.getLogger('django')


class TreasuryRatesType(Enum):
    """Available rates types of US Dep of Treasury"""
    ParYieldCurve = 'daily_treasury_yield_curve'
    ParRealYieldCurve = 'daily_treasury_real_yield_curve'  # Not supported currently


class TreasuryParYieldAdapter:
    """Adapter class to check and transform data from CSV file to database model"""
    model = TreasuryRates
    column_to_field_map = {
        'Date': 'date',
        '1 Mo': 'month1',
        '2 Mo': 'month2',
        '3 Mo': 'month3',
        '4 Mo': 'month4',
        '6 Mo': 'month6',
        '1 Yr': 'year1',
        '2 Yr': 'year2',
        '3 Yr': 'year3',
        '5 Yr': 'year5',
        '7 Yr': 'year7',
        '10 Yr': 'year10',
        '20 Yr': 'year20',
        '30 Yr': 'year30',
    }
    transforms = {
        'date': lambda x: datetime.strptime(x, '%m/%d/%Y')
    }

    @classmethod
    def validate_and_store(cls, row: Series) -> bool:
        # Retrieve and prepare data from a row
        row_dict = {value: row.get(key) for key, value in cls.column_to_field_map.items()}
        # Make transforms
        for t, func in cls.transforms.items():
            row_dict[t] = func(row_dict[t])
        # Update or create a record in DB
        res = cls.model.objects.update_or_create(date=row_dict['date'], defaults=row_dict)
        return res[1]


class TreasuryRatesSyncer:
    rates_types_to_adapter = {
        TreasuryRatesType.ParYieldCurve: TreasuryParYieldAdapter,
    }

    monthly_url = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/' \
                  'daily-treasury-rates.csv/all/{}?type={}&_format=csv'
    yearly_url = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/' \
                 'daily-treasury-rates.csv/{}/all?type={}&_format=csv'

    @classmethod
    def sync(cls, rate_type: TreasuryRatesType, year: int, month: Optional[int] = None) -> tuple[int, int]:
        if month:
            url = cls.monthly_url.format(f'{year}{month:02}', rate_type.value)
        else:
            url = cls.yearly_url.format(year, rate_type.value)

        logger.info(f'Downloading rates CSV archive for year {year}{" month " + str(month) if month else ""}')
        rates = pd.read_csv(url)

        adapter = cls.rates_types_to_adapter.get(rate_type)
        if not adapter:
            raise CommandError(f'No database model/adapter found for given rates type: {rate_type}')

        logger.info('Processing started')
        total = 0  # Number of rows in CSV
        created = 0  # Number of new DB records created
        with transaction.atomic():  # Single commit to DB for all the writes
            for total, row in enumerate(rates.iterrows(), 1):
                created += adapter.validate_and_store(row[1])
        logger.info('Sync finished')

        return total, created


class SyncExecutor:
    types = ['allrates', 'currentrates']

    @classmethod
    def execute(cls, sync_type: list[str]):
        if sync_type not in cls.types:
            raise CommandError(f'Wrong sync type: {sync_type}')
        res = getattr(cls, f'sync_{sync_type}')()
        logger.info(res)

    @classmethod
    def sync_allrates(cls) -> str:
        now = datetime.now()
        all_res = [
            TreasuryRatesSyncer.sync(TreasuryRatesType.ParYieldCurve, now.year),
            TreasuryRatesSyncer.sync(TreasuryRatesType.ParYieldCurve, now.year - 1),
            TreasuryRatesSyncer.sync(TreasuryRatesType.ParYieldCurve, now.year - 2),
        ]
        all_res = list(map(sum, zip(*all_res)))  # Sum results of all syncs
        return f'Rates were synced with US Treasury for past three years\n' \
               f'Total records found - {all_res[0]}, Inserted new records - {all_res[1]}'

    @classmethod
    def sync_currentrates(cls) -> str:
        now = datetime.now()
        res = TreasuryRatesSyncer.sync(TreasuryRatesType.ParYieldCurve, now.year, month=now.month)

        return f'Rates were synced with US Treasury for current month\n' \
               f'Total records found - {res[0]}, Inserted new records - {res[1]}'
