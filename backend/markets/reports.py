from datetime import timedelta, date
from itertools import chain

import pandas

from markets.models import YahooStockPrice, CompanyQuerySet, Share, Company, Asset, YahooAssetPrice


def get_price_changes_per_company(companies_qs: CompanyQuerySet, custom_since: date | None, custom_to: date | None):
    most_recent_date = YahooStockPrice.objects.first().date
    since = most_recent_date - timedelta(days=365)  # Query prices for 400 days by default
    custom_offset_since = 0
    custom_offset_to = 0
    if custom_since:
        since = custom_since if since > custom_since else since
        custom_offset_since = max(0, (date.today() - custom_since).days)
        if custom_to:
            custom_offset_to = min(max(0, (date.today() - custom_to).days), custom_offset_since)
    base_prices_qs = YahooStockPrice.objects.filter(date__gte=since - timedelta(days=5))

    df = pandas.DataFrame(list(base_prices_qs.values('date', 'company', 'close')))

    companies = list(companies_qs.values_list('pk', 'code', 'sector'))

    res = dict()
    for pk, code, sector in companies:
        company_res = {'code': code, 'sector': sector}
        company_df = df.loc[df['company'] == pk]
        if company_df.empty:  # No available prices found for a company
            continue
        cur_price = company_df['close'].iloc[0]
        company_res['current_price'] = cur_price
        for period_name, period in companies_qs.changes.items():
            if period > len(company_df.index):  # Period longer than available price history
                continue
            company_res[period_name] = round(cur_price / company_df['close'].iloc[period], 4)
        if custom_offset_since and custom_offset_since <= len(company_df.index):
            custom_price = cur_price
            if custom_offset_to and custom_offset_to < len(company_df.index):
                custom_price = company_df['close'].iloc[custom_offset_to]
                company_res['custom_price'] = custom_price
            company_res['change_custom'] = round(custom_price / company_df['close'].iloc[custom_offset_since], 4)
        res[pk] = company_res
    return res


def get_shares_per_company(company_perf: dict) -> None:
    since = date.today() - timedelta(days=366)
    base_shares_qs = Share.objects.filter(date__gte=since)

    df = pandas.DataFrame(list(base_shares_qs.values('company', 'count')))
    for pk, company_res in company_perf.items():
        company_df = df.loc[df['company'] == pk]
        if company_df.empty:  # No available share count found for a company
            continue
        company_res['shares'] = company_df['count'].iloc[0]


def get_sector_outstanding(sectors_perf: dict, companies_perf: dict) -> None:
    companies_perf_list = companies_perf.values()

    for sector, sector_perf in sectors_perf.items():
        fields = CompanyQuerySet.changes
        if 'sector_change_custom' in sector_perf:
            fields = chain(fields, ['change_custom'])
        for field in fields:
            lst = list(sorted(filter(lambda x: x.get('sector') == sector and not x.get(field) is None,
                                     companies_perf_list), key=lambda y: y.get(field), reverse=True))
            bot = reversed(lst[-3:])
            top = lst[:3]

            sector_perf[f'bot_{field}'] = list(map(lambda x: (x['code'], round((x[field] - 1) * 100, 1)), bot))
            sector_perf[f'top_{field}'] = list(map(lambda x: (x['code'], round((x[field] - 1) * 100, 1)), top))


def get_market_dynamics(custom_since=None, custom_to=None):
    company_qs = Company.objects.last_top500()
    companies_perf = get_price_changes_per_company(company_qs, custom_since, custom_to)
    get_shares_per_company(companies_perf)

    sector_fields = [
        'sector_value_day_ago',
        'sector_value_week_ago',
        'sector_value_month_ago',
        'sector_value_quart_ago',
        'sector_value_halfyear_ago',
        'sector_value_year_ago',
    ]

    sector_changes = [
        'sector_change_day', 'sector_change_week', 'sector_change_month',
        'sector_change_quart', 'sector_change_halfyear', 'sector_change_year'
    ]

    sectors_perf = {}
    sectors = set()

    # Get all sectors
    for company_id, perf in companies_perf.items():
        sectors.add(perf['sector'])

    # Preconfigure sector default values
    for sector in sectors:
        sectors_perf[sector] = {}
        sectors_perf[sector]['sector_value_today'] = 0
        if custom_since:
            sectors_perf[sector]['sector_value_custom'] = 0
            if custom_to:
                sectors_perf[sector]['sector_value_custom_to'] = 0
        for sector_field in sector_fields:
            sectors_perf[sector][sector_field] = 0

    # Calculate sector values (sums) for dates
    for _, perf in companies_perf.items():
        sector_perf = sectors_perf[perf['sector']]
        shares = perf.get('shares')
        cur_price = perf.get('current_price')
        if not (shares and cur_price):  # No price or share count for company
            continue
        if perf.get('change_custom'):
            custom_price = perf.get('custom_price') or cur_price
            sector_perf['sector_value_custom'] += round(shares * custom_price / perf['change_custom'], 4)
            if custom_to:
                sector_perf['sector_value_custom_to'] += round(shares * custom_price, 4)
        sector_perf['sector_value_today'] += round(shares * cur_price, 4)
        for sector_field, change_field in zip(sector_fields, company_qs.changes):
            if not perf.get(change_field):
                continue
            sector_perf[sector_field] += round(shares * cur_price / perf[change_field], 4)

    # Calculate sector relative changes for periods
    for sector, perf in sectors_perf.items():
        if perf.get('sector_value_custom'):
            if 'sector_value_custom_to' in perf:
                perf['sector_change_custom'] = round(
                    (perf['sector_value_custom_to'] / perf['sector_value_custom'] - 1) * 100, 1)
            else:
                perf['sector_change_custom'] = round(
                    (perf['sector_value_today'] / perf['sector_value_custom'] - 1) * 100, 1)
        else:
            perf['sector_change_custom'] = None
        for change_field, sector_field in zip(sector_changes, sector_fields):
            if not perf[sector_field]:
                perf[change_field] = None
                continue
            perf[change_field] = round((perf['sector_value_today'] / perf[sector_field] - 1) * 100, 1)

    get_sector_outstanding(sectors_perf, companies_perf)

    sectors_perf = dict(sorted(sectors_perf.items(), key=lambda x: x[0]))

    return sectors_perf


def get_assets_dynamics(custom_since=None, custom_to=None):
    asset_qs = Asset.objects.all()
    most_recent_date = YahooAssetPrice.objects.first().date

    since = most_recent_date - timedelta(days=400)  # Query prices for 400 days by default
    custom_offset_since = 0
    custom_offset_to = 0
    if custom_since:
        since = custom_since if since > custom_since else since
        custom_offset_since = max(0, (most_recent_date - custom_since).days)
        if custom_to:
            custom_offset_to = min(max(0, (most_recent_date - custom_to).days), custom_offset_since)
    base_prices_qs = YahooAssetPrice.objects.filter(date__gte=since - timedelta(days=5))

    df = pandas.DataFrame(list(base_prices_qs.values('date', 'asset', 'close')))

    assets = list(asset_qs.values_list('pk', 'code', 'name'))

    res = dict()
    for pk, code, name in assets:
        asset_res = {'code': code}
        asset_df = df.loc[df['asset'] == pk]
        if asset_df.empty:  # No available prices found for an asset
            continue
        cur_price = asset_df['close'].iloc[0]
        asset_res['current_price'] = cur_price
        for period_name, period in CompanyQuerySet.changes.items():
            if period >= len(asset_df.index):  # Period longer than available price history
                continue
            prev_price = asset_df['close'].iloc[period]
            asset_res[period_name] = round((cur_price / prev_price - 1) * 100, 1)
        if custom_offset_since:
            if custom_offset_since < len(asset_df.index):
                custom_price = cur_price
                if custom_offset_to and custom_offset_to < len(asset_df.index):
                    custom_price = asset_df['close'].iloc[custom_offset_to]
                    asset_res['custom_price'] = custom_price
                asset_res['change_custom'] = round(
                    (custom_price / asset_df['close'].iloc[custom_offset_since] - 1) * 100, 1)
            else:
                asset_res['change_custom'] = None
        res[name] = asset_res
    return res
