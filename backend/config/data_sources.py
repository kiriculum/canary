# Link templates for CSV achieves of US treasury rates
us_treasury_monthly_rates = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/' \
                            'daily-treasury-rates.csv/all/{}?type={}&_format=csv'

us_treasury_yearly_rates = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/' \
                           'daily-treasury-rates.csv/{}/all?type={}&_format=csv'

# Xlsx file with company details, must be present in root folder (defaults to sector_ticker_fortune.xlsx)
company_asset_filename = 'sector_ticker_fortune.xlsx'
assets_filename = ''

# Link to current top 500 companies
top500_url = 'https://www.slickcharts.com/sp500'
# Template link for a company details to fetch share count
company_details_url = 'https://www.macrotrends.net/stocks/charts/{}/filler/shares-outstanding'
# Template link for Yahoo stock prices
yahoo_finance_url = 'https://query1.finance.yahoo.com/v7/finance/download' \
                    '/{}?period1={}&period2={}&interval=1d&events=history'

# Yahoo code(ticker) of a company/asset might differ from general one.
# So we keep dictionary for transforming in format {local_code: yahoo_code}
local_codes_to_yahoo = {
    'BRK.B': 'BRK-B',
}
