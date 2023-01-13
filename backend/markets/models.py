from __future__ import annotations

import logging
from typing import Iterable, Union

import pandas
from django.core.exceptions import EmptyResultSet
from django.core.validators import MinValueValidator, MinLengthValidator
from django.db.models import ForeignKey, FloatField, DateField, CharField, Model as dModel, Manager, \
    CASCADE, Index, UniqueConstraint, DateTimeField, BigIntegerField, Subquery, F, Window, OuterRef, Sum, QuerySet
from django.db.models.functions import Round, Lead

from markets.helpers import separate_capitalize

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
            'date', 'month1', 'month2', 'month3', 'month6', 'year1', 'year2', 'year3', 'year5',
            'year7', 'year10', 'year20', 'year30',
        ]

    @staticmethod
    def serialize_per_day(obj: dict) -> dict[str, Union[str, dict]]:
        """Return a row with just setting date as a label"""

        label = obj.pop('date').strftime('%d/%m/%y')
        for key, value in list(obj.items()):
            obj[separate_capitalize(key)] = obj.pop(key)

        return {'label': label, 'data': obj}

    @classmethod
    def serialize_per_maturity(cls, query: Iterable) -> dict[str, list]:
        """Transpose and return data with maturity field as a label"""
        fields = cls.get_fields_list()
        fields.pop(fields.index('date'))
        # Setup initial empty data
        datasets = {field: {'data': [], 'label': separate_capitalize(field)} for field in fields}
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
        ordering = ['-date']


class CompanyQuerySet(QuerySet):
    """Manager for Company model"""

    changes = {  # field_name: number of days to offset
        'change_day': 1,
        'change_week': 7,
        'change_month': 30,
        'change_quart': 90,
        'change_halfyear': 182,
        'change_year': 365
    }

    sector_changes = [
        'sector_change_day', 'sector_change_week', 'sector_change_month',
        'sector_change_quart', 'sector_change_halfyear', 'sector_change_year'
    ]

    alias_fields = [
        'company_value_day_ago',
        'company_value_week_ago',
        'company_value_month_ago',
        'company_value_quart_ago',
        'company_value_halfyear_ago',
        'company_value_year_ago',
    ]

    def last_top500(self) -> CompanyQuerySet:
        last_top500 = Top500.objects.last_top500()
        return self.filter(top500__in=last_top500)

    def annotate_price_changes(self) -> CompanyQuerySet:
        """Annotate companies with current price changes"""
        # Here is the difficult part. It's a complex single SQL Query that runs several Database functions on
        # YahooStockPrice table to get relative price changes for last available price in day, week, month and so on
        base_price_qs = YahooStockPrice.objects.filter(close__isnull=False, company=OuterRef('id'))
        changes_annotations = {
            f'{period}': Subquery(base_price_qs.annotate(
                **{f'{period}': Round(F('close') / Window(Lead('close', offset=number)), precision=4)})
                                  .values(period)[:1]) for period, number in self.changes.items()
        }
        return self.annotate(**changes_annotations)

    def annotate_prices(self) -> CompanyQuerySet:
        """Annotate companies with current price and price's date"""
        base_price_qs = YahooStockPrice.objects.filter(close__isnull=False, company=OuterRef('id'))
        current_price_annotations = {
            'current_price': Subquery(base_price_qs.values('close')[:1]),
            'price_date': Subquery(base_price_qs.values('date')[:1])
        }
        return self.annotate(**current_price_annotations)

    def annotate_shares(self) -> CompanyQuerySet:
        """Annotate companies with most recent share count"""
        shares_qs = Share.objects.filter(count__isnull=False, company=OuterRef('id'))
        shares_count_annotations = {
            'shares_count': Subquery(shares_qs.values('count')[:1])
        }
        return self.annotate(**shares_count_annotations)

    def get_sector_changes(self) -> CompanyQuerySet:
        """Get whole market sector changes"""

        alias_annotations = {
            new_field: F('shares_count') * F('current_price') / F(field)
            for new_field, field in zip(self.alias_fields, self.changes)
        }

        return self.alias(
            company_value_now=F('shares_count') * F('current_price'), **alias_annotations
        ).values('sector').annotate(
            sector_value_now=Sum('company_value_now'),
            **{new_field: Round((Sum('company_value_now') / Sum(field) - 1) * 100, precision=2)
               for new_field, field in zip(self.sector_changes, self.alias_fields)}
        )

    def get_sector_outstanding(self) -> pandas.DataFrame:
        """Get top 3 and bottom 3 companies per sector"""
        return pandas.DataFrame(list(self.values('sector', 'code', 'current_price', *self.changes)))


class Company(Model):
    """Model for company names/codes"""
    name = CharField(max_length=255)
    code = CharField(max_length=16, unique=True, validators=[MinLengthValidator(2)])
    sector = CharField(max_length=255)

    objects = CompanyQuerySet.as_manager()

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
        ordering = ['-date']
        indexes = [
            Index(fields=['date']),
            Index(fields=['close']),
        ]


class StockPrice(Price):
    """Abstract model for stock prices"""
    company = ForeignKey(Company, on_delete=CASCADE)

    class Meta:
        abstract = True,
        ordering = ['-date', 'company']
        constraints = [
            UniqueConstraint(fields=['date', 'company'], name='%(app_label)s_%(class)s_date_company'),
        ]


class AssetPrice(Price):
    """Abstract model for asset prices"""
    asset = ForeignKey(Asset, on_delete=CASCADE)

    class Meta:
        abstract = True,
        ordering = ['-date', 'asset']
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
        ordering = ['-date']
        constraints = [
            UniqueConstraint(fields=['date', 'company'], name='%(app_label)s_%(class)s_date_company'),
        ]


class Share(Model):
    """Model for shares count per company per date"""
    company = ForeignKey(Company, on_delete=CASCADE)
    date = DateField()
    count = FloatField(validators=[MinValueValidator(0)])  # Stored in billions

    class Meta:
        ordering = ['-date']
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
