import logging
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from django.core.management import CommandError
from django.db import transaction
from django.db.models import QuerySet
from pandas import Series

from config.data_sources import us_treasury_monthly_rates, us_treasury_yearly_rates, company_asset_filename, \
    top500_url, company_details_url, yahoo_finance_url, local_codes_to_yahoo
from config.settings import ROOT_DIR
from markets.models import TreasuryRates, Company, Top500, Share, Asset, YahooAssetPrice, YahooStockPrice, Model

logger = logging.getLogger('django-sync')


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

    monthly_url = us_treasury_monthly_rates
    yearly_url = us_treasury_yearly_rates

    @classmethod
    def sync_bonds(cls, rate_type: TreasuryRatesType, year: int, month: Optional[int] = None) -> None:
        """Sync treasure rates for given year or month"""
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

        logger.info(f'Rates were synced with US Treasury.\n'
                    f'Total records found - {total}, Inserted new records - {created}')


class CompanyAssetSyncer:
    companies_file = ROOT_DIR / company_asset_filename

    @classmethod
    def sync_localassets(cls) -> None:
        if not cls.companies_file.exists():
            raise CommandError(f'File with companies and assets not found in path: {cls.companies_file}')
        logger.info(f'Syncing companies and assets from file: {company_asset_filename}')
        companies_df = pd.read_excel(cls.companies_file, sheet_name='companies')

        total = len(companies_df.index)
        res = Company.objects.bulk_create(  # DB bulk insertion
            [Company(sector=getattr(row, 'sector'), name=getattr(row, 'company'), code=getattr(row, 'ticker'))
             for row in companies_df.itertuples(index=False)],
            update_conflicts=True, update_fields=['sector', 'name'], unique_fields=['code']
        )
        logger.info(f'Companies were synced\nInserted/updated {len(res)} records out of total {total}\n')

        assets_df = pd.read_excel(cls.companies_file, sheet_name='assets')

        total = len(assets_df.index)
        res = Asset.objects.bulk_create(  # DB bulk insertion
            [Asset(name=getattr(row, 'name'), code=getattr(row, 'ticker'))
             for row in assets_df.itertuples(index=False)],
            update_conflicts=True, update_fields=['name'], unique_fields=['code']
        )
        logger.info(f'Assets were synced\nInserted/updated {len(res)} records out of total {total}\n')


class MarketSharesSyncer:
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 '
                             '(KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

    @classmethod
    def sync_top500(cls) -> None:
        """Sync today's top500 companies"""
        logger.info('Syncing top500')
        data = requests.get(top500_url, headers=cls.headers).text
        soup = BeautifulSoup(data, 'lxml')
        top500_list = []  # Company codes
        tbody = soup.select_one('div.col-lg-7 tbody')

        for row in tbody.find_all('tr'):  # Find and collect all present companies
            cols = row.find_all('td')
            top500_list.append(cols[2].next.text.upper())

        companies = Company.objects.filter(code__in=top500_list)
        res = Top500.objects.bulk_create(
            [Top500(company=company, date=date.today()) for company in companies], ignore_conflicts=True)
        logger.info(f'Synced {len(res)} companies of today\'s top500')

    @classmethod
    def sync_shares_count(cls) -> None:
        """Sync share counts for the last available top500"""
        logger.info('Syncing shares count for current top500 companies')
        share_obj_list = []
        last_top500 = Company.objects.last_top500()
        not_found = []

        total = last_top500.count()
        updated = 0
        logger.info(f'Going to fetch and process data for {total} companies')
        for index, company in enumerate(last_top500):
            url = company_details_url.format(company.code)
            try:  # Exceeding the site's request limitations
                data = requests.get(url).text
            except requests.TooManyRedirects:
                broke = company.code
                break
            soup = BeautifulSoup(data, 'lxml')

            tbody = soup.find_all('tbody')
            if not tbody:  # No table for a company on the site
                logger.warning(f'No table with share details found on site for company {company.code}')
                not_found.append(company.code)
                continue
            table = tbody[1]
            for row in table.find_all('tr'):
                cols = row.find_all('td')
                report_date = datetime.strptime(cols[0].text, '%Y-%m-%d').date()
                try:  # Sometimes the table on the site have rows with no count for a date
                    count = int(cols[1].text.replace(',', ''))
                except ValueError:
                    continue
                share_obj_list.append(Share(company=company, date=report_date, count=count))
            updated += 1
            if index and not index % 50:
                logger.info(f'Synced shares count for {index} out of {total} companies')
        else:  # No breaks
            broke = None
        if broke:
            logger.warning(f'Syncing was stopped while dealing with company {broke}". '
                           f'It\'s probably because of site\'s request limitations')
        Share.objects.bulk_create(share_obj_list, ignore_conflicts=True)
        logger.info(f'Synced shares for {updated} companies out of {total}.')
        logger.warning("Not found share count for: " + ", ".join(not_found)) if not_found else None

    @staticmethod
    def cast_dataframe(series: Series):
        if series.name == 'volume':
            return series.apply(int)
        return series.apply(lambda x: round(float(x), 4))

    @classmethod
    def transform_code(cls, code: str) -> str:
        """Try to transform a local code to a Yahoo code"""
        if len(code) > 6:
            return code
        if '.' in code:
            if code[-1] == 'V':
                return code + 'I'
            code = code.replace('.', '-')
            if code[-1] == 'U':
                return code + 'N'
        return code

    @classmethod
    def sync_assetprices(cls) -> None:
        query = Asset.objects.all()
        cls.base_sync_prices(query, 'asset', YahooAssetPrice)

    @classmethod
    def sync_stockprices(cls) -> None:
        last_top500 = Top500.objects.last_top500()
        query = Company.objects.filter(top500__in=last_top500)
        cls.base_sync_prices(query, 'company', YahooStockPrice)

    @classmethod
    def base_sync_prices(cls, query: QuerySet, item_name: str, price_model: type[Model], force: bool = False) -> None:
        """Sync stock prices for top500 from Yahoo Finance"""
        total = query.count()
        logger.info(f'Starting sync prices for {total} companies/assets')
        updated = 0
        error_skipped = []
        already_fresh = []

        for updated, item in enumerate(query, 1):
            yahoo_code = item.code
            if item_name == 'company':
                yahoo_code = local_codes_to_yahoo.get(item.code, cls.transform_code(item.code))
            last_price = price_model.objects.filter(**{item_name: item}).order_by('-date').first()
            to = datetime(*date.today().timetuple()[0:3])
            since = to - timedelta(days=365 * 25)  # Fetch data for 25 years by default
            if last_price:  # 3 days offset to interleave
                since = datetime(*last_price.date.timetuple()[0:3]) - timedelta(days=3)
            if force:
                since = to - timedelta(days=365 * 25)  # Force fetching for 25 years
            if to - since <= timedelta(days=4):  # Skip if period distance is less than 1 day
                already_fresh.append(item.code)
                continue
            url = yahoo_finance_url.format(yahoo_code, int(since.timestamp()), int(to.timestamp()))
            try:
                prices = pd.read_csv(url)
            except requests.TooManyRedirects:
                error_skipped.append([item.code])
                continue
            # Process price DataFrame

            prices.index = pd.DatetimeIndex(prices['Date'].apply(lambda x: datetime.strptime(x, '%Y-%m-%d')))
            prices = prices[~prices.index.duplicated(keep='first')]
            prices.drop('Date', axis=1, inplace=True)
            prices.columns = list(map(str.lower, prices.columns))
            prices = prices.resample('D').interpolate(limit=30)
            prices = prices.apply(cls.cast_dataframe)
            prices.dropna(inplace=True)

            stock_prices = [  # Building SQL QuerySet
                price_model(
                    date=row.Index.date(), open=row.open, high=row.high, low=row.low, close=row.close,
                    volume=row.volume, **{item_name: item}) for row in prices.itertuples()
            ]
            price_model.objects.bulk_create(stock_prices, ignore_conflicts=True)
            if updated and not updated % 50:
                logger.info(f'Synced prices for {updated} {item_name}s')
        logger.info(f'Synced prices for {updated} {item_name} of {query.count()}.\n'
                    f'{len(already_fresh)} {"".join(["[", " ,".join(already_fresh[:5]), "...", "]"])} '
                    f'{item_name}s are already up-to-date. {error_skipped} were skipped due to network errors')


class SyncExecutor:
    """Main sync executor"""
    types = ['localassets', 'allrates', 'currentrates', 'top500', 'marketshares', 'prices', 'allmarkets', 'setup',
             'daily']

    @classmethod
    def execute(cls, sync_type: list[str]):
        """Fetch option and run specified sync"""
        if sync_type not in cls.types:
            raise CommandError(f'Wrong sync type: {sync_type}')
        res = getattr(cls, f'sync_{sync_type}')()
        logger.info(res)

    @classmethod
    def sync_allrates(cls) -> str:
        """Sync treasury rates for 3 years"""
        now = datetime.now()
        [
            TreasuryRatesSyncer.sync_bonds(TreasuryRatesType.ParYieldCurve, now.year - i) for i in range(15)
        ]
        return 'Sync rates for last three years finished\n'

    @classmethod
    def sync_currentrates(cls) -> str:
        """Sync treasury rates for current month"""
        now = datetime.now()
        TreasuryRatesSyncer.sync_bonds(TreasuryRatesType.ParYieldCurve, now.year, month=now.month)
        return 'Sync rates for current month finished\n'

    @classmethod
    def sync_top500(cls) -> str:
        MarketSharesSyncer.sync_top500()
        return 'Sync top500 finished\n'

    @classmethod
    def sync_marketshares(cls) -> str:
        MarketSharesSyncer.sync_shares_count()
        return 'Sync market shares count finished\n'

    @classmethod
    def sync_prices(cls) -> str:
        MarketSharesSyncer.sync_stockprices()
        MarketSharesSyncer.sync_assetprices()
        return 'Sync shares and assets prices finished\n'

    @classmethod
    def sync_allmarkets(cls) -> str:
        """Sync top500, share counts and market prices"""
        logger.info('Starting all market values sync')
        MarketSharesSyncer.sync_top500()
        MarketSharesSyncer.sync_shares_count()
        MarketSharesSyncer.sync_stockprices()
        MarketSharesSyncer.sync_assetprices()
        return 'Sync market shares finished\n'

    @classmethod
    def sync_daily(cls) -> str:
        res = cls.sync_currentrates()
        logger.info(res)
        return cls.sync_allmarkets()

    @classmethod
    def sync_localassets(cls) -> str:
        CompanyAssetSyncer.sync_localassets()
        return 'Sync local companies and assets finished\n'

    @classmethod
    def sync_setup(cls) -> str:
        logger.info('Starting initial setup sync')
        now = datetime.now()
        CompanyAssetSyncer.sync_localassets()
        [TreasuryRatesSyncer.sync_bonds(TreasuryRatesType.ParYieldCurve, i) for i in range(now.year, 1998, -1)]
        MarketSharesSyncer.sync_top500()
        MarketSharesSyncer.sync_shares_count()
        MarketSharesSyncer.sync_stockprices()
        MarketSharesSyncer.sync_assetprices()

        return 'Initial setup sync finished\n'
