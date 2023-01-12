from datetime import date, timedelta

from django.test import TestCase

from markets.models import Top500, Company, YahooStockPrice, Share, CompanyQuerySet


class TestReports(TestCase):
    @classmethod
    def setUpTestData(cls):
        comps = [
            Company.objects.create(name='test1', code='test1', sector='sector1'),
            Company.objects.create(name='test2', code='test2', sector='sector1'),
            Company.objects.create(name='test3', code='test3', sector='sector2'),
            Company.objects.create(name='test4', code='test4', sector='sector1'),
            Company.objects.create(name='test5', code='test5', sector='sector1'),
            Company.objects.create(name='test6', code='test6', sector='sector1'),
        ]
        today = date.today()

        for i, comp in enumerate(comps, 1):
            Top500(company=comp, date=today).save()
            YahooStockPrice.objects.bulk_create(
                [YahooStockPrice(company=comp, date=today - timedelta(days=day), open=1.0, high=1.0, low=1.0,
                                 close=round(30 * (1 - i / 1000) ** day, 6), volume=100) for day in range(366)]
            )
            Share.objects.create(company=comp, date=today, count=10 * i)

    def test_company_report(self):
        company_qs: CompanyQuerySet = (Company.objects.last_top500()
                                       .annotate_prices()
                                       .annotate_price_changes()
                                       .annotate_shares())

        _changes = company_qs.get_sector_changes()
        sectors = company_qs.get_sector_outstanding()
        pass
