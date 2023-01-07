from typing import Iterable

from django.db.models import ForeignKey, IntegerField, FloatField, DateField, CharField, Model, Manager, CASCADE, Index


class Rate(Model):
    """Abstract model to store various rates"""
    created = DateField(auto_now_add=True)

    objects = Manager()

    class Meta:
        abstract = True


class ParYieldRate(Rate):
    """Abstract model to store daily par yield rates"""
    date = DateField(unique=True)
    month1 = FloatField(null=True, blank=True)
    month2 = FloatField(null=True, blank=True)
    month3 = FloatField(null=True, blank=True)
    month4 = FloatField(null=True, blank=True)
    month6 = FloatField(null=True, blank=True)
    year1 = FloatField(null=True, blank=True)
    year2 = FloatField(null=True, blank=True)
    year3 = FloatField(null=True, blank=True)
    year5 = FloatField(null=True, blank=True)
    year7 = FloatField(null=True, blank=True)
    year10 = FloatField(null=True, blank=True)
    year20 = FloatField(null=True, blank=True)
    year30 = FloatField(null=True, blank=True)

    @staticmethod
    def get_fields_list() -> list:
        return [
            'date', 'month1', 'month2', 'month3', 'month4', 'month6', 'year1', 'year2', 'year3', 'year5',
            'year7', 'year10', 'year20', 'year30',
        ]

    @staticmethod
    def serialize_per_day(obj: dict):
        """Return a row with just setting date as a label"""
        return {'label': obj.pop('date'), 'data': obj}

    @classmethod
    def serialize_per_maturity(cls, query: Iterable):
        """Transpose and return data with maturity field as a label"""
        fields = cls.get_fields_list()
        fields.pop(fields.index('date'))
        # Setup initial empty data
        datasets = {field: {'data': [], 'label': field} for field in fields}
        labels = []

        for obj in query:
            for field in fields:
                datasets[field]['data'].append(obj.get(field, None))
            labels.append(obj['date'])
        return {'datasets': list(datasets.values()), 'labels': labels}

    class Meta:
        abstract = True
        indexes = [
            Index(fields=['date']),
        ]


class TreasuryRates(ParYieldRate):
    """Model for Daily par yield curve rates of U.S. Department of the Treasury"""


class Company(Model):
    """Model for company names/codes"""
    name = CharField(max_length=256)
    code = CharField(max_length=16)


class Date(Model):
    """Model for dates"""
    date = DateField()


class StockPrice(Model):
    """Abstract model for stock prices"""
    date = ForeignKey(Date, on_delete=CASCADE)
    company = ForeignKey(Company, on_delete=CASCADE)
    open = FloatField()
    high = FloatField()
    low = FloatField()
    close = FloatField()
    volume = IntegerField()

    class Meta:
        abstract = True


class YahooStockPrice(StockPrice):
    """Model for Yahoo Finance stock prices"""
