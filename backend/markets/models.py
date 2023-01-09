import logging
from typing import Iterable

from django.core.exceptions import EmptyResultSet
from django.core.validators import MinValueValidator, MinLengthValidator
from django.db.models import ForeignKey, FloatField, DateField, CharField, Model as dModel, Manager, \
    CASCADE, Index, UniqueConstraint, DateTimeField, BigIntegerField

logger = logging.getLogger('django')


class Model(dModel):
    """Abstract model with manager"""
    objects = Manager()

    class Meta:
        abstract = True


class ParYieldRate(Model):
    """Abstract model to store daily par yield rates"""
    created = DateField(auto_now_add=True)
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


class Company(Model):
    """Model for company names/codes"""
    name = CharField(max_length=255)
    code = CharField(max_length=16, unique=True, validators=[MinLengthValidator(2)])
    sector = CharField(max_length=255)

    class Meta:
        indexes = [
            Index(fields=['code'])
        ]


class Asset(Model):
    """Model for various assets: index, future, option"""
    name = CharField(max_length=255)
    code = CharField(max_length=16, unique=True, validators=[MinLengthValidator(2)])


class Price(Model):
    """Abstract model for prices of various assets"""
    modified = DateTimeField(auto_now=True)
    date = DateField()
    open = FloatField()
    high = FloatField()
    low = FloatField()
    close = FloatField()
    volume = BigIntegerField()

    class Meta:
        abstract = True,
        indexes = [
            Index(fields=['date']),
            Index(fields=['close']),
        ]


class StockPrice(Price):
    """Abstract model for stock prices"""
    company = ForeignKey(Company, on_delete=CASCADE)

    class Meta:
        abstract = True,
        constraints = [
            UniqueConstraint(fields=['date', 'company'], name='%(app_label)s_%(class)s_date_company'),
        ]


class AssetPrice(Price):
    """Abstract model for asset prices"""
    asset = ForeignKey(Asset, on_delete=CASCADE)

    class Meta:
        abstract = True,
        constraints = [
            UniqueConstraint(fields=['date', 'asset'], name='%(app_label)s_%(class)s_date_asset'),
        ]


class Top500Manager(Manager):
    """Query manager for top500 model"""

    def last_top500(self):
        one_of_last_top500 = self.order_by('-date').first()
        if not one_of_last_top500:
            raise EmptyResultSet('No available top500 companies available')
        return self.filter(date=one_of_last_top500.date)


class Top500(Model):
    """Model for top 500 companies per day"""
    date = DateField()
    company = ForeignKey(Company, on_delete=CASCADE, related_name='top500')

    objects = Top500Manager()

    class Meta:
        constraints = [
            UniqueConstraint(fields=['date', 'company'], name='%(app_label)s_%(class)s_date_company'),
        ]


class Share(Model):
    """Model for annual shares count per company"""
    company = ForeignKey(Company, on_delete=CASCADE)
    date = DateField()
    count = FloatField(validators=[MinValueValidator(0)])  # Stored in billions

    class Meta:
        indexes = [
            Index(fields=['date']),
            Index(fields=['count']),
        ]
        constraints = [
            UniqueConstraint(fields=['company', 'date'], name='%(app_label)s_%(class)s_date_company'),
        ]


class YahooStockPrice(StockPrice):
    """Model for Yahoo Finance stock prices"""


class YahooAssetPrice(AssetPrice):
    """Model for Yahoo Finance asset prices"""


class TreasuryRates(ParYieldRate):
    """Model for Daily par yield curve rates of U.S. Department of the Treasury"""
