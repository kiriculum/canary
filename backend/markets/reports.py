from datetime import timedelta, date
from itertools import chain
from typing import Optional

import pandas

from markets.models import YahooStockPrice, CompanyQuerySet, Share, Company


def get_price_changes_per_company(companies_qs: CompanyQuerySet, custom_date: Optional[date]):
    since = date.today() - timedelta(days=400)
    custom_offset = 0
    if custom_date:
        since = custom_date if since > custom_date else since
        custom_offset = max(0, (date.today() - custom_date).days)
    base_prices_qs = YahooStockPrice.objects.filter(date__gte=since)

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
        if custom_offset and custom_offset < len(company_df.index):
            company_res['change_custom'] = round(cur_price / company_df['close'].iloc[custom_offset], 4)
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


def get_market_shares(custom_date=None):
    company_qs = Company.objects.last_top500()
    companies_perf = get_price_changes_per_company(company_qs, custom_date)
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
        if custom_date:
            sectors_perf[sector]['sector_value_custom'] = 0
        for sector_field in sector_fields:
            sectors_perf[sector][sector_field] = 0

    # Calculate sector performances
    for _, perf in companies_perf.items():
        sector_perf = sectors_perf[perf['sector']]
        shares = perf.get('shares')
        cur_price = perf.get('current_price')
        if not (shares and cur_price):  # No price or share count for company
            continue
        if 'change_custom' in perf:
            sector_perf['sector_value_custom'] += round(shares * cur_price / perf['change_custom'], 4)
        sector_perf['sector_value_today'] += round(shares * cur_price, 4)
        for sector_field, change_field in zip(sector_fields, company_qs.changes):
            if not perf.get(change_field):
                continue
            sector_perf[sector_field] += round(shares * cur_price / perf[change_field], 4)

    for sector, perf in sectors_perf.items():
        if 'sector_value_custom' in perf:
            perf['sector_change_custom'] = round(
                (perf['sector_value_today'] / perf['sector_value_custom'] - 1) * 100, 1)
        for change_field, sector_field in zip(sector_changes, sector_fields):
            if not perf[sector_field]:
                continue
            perf[change_field] = round((perf['sector_value_today'] / perf[sector_field] - 1) * 100, 1)

    get_sector_outstanding(sectors_perf, companies_perf)

    sectors_perf = dict(sorted(sectors_perf.items(), key=lambda x: x[0]))

    return sectors_perf
