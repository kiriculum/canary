from django.db import models


class Rate(models.Model):
    """Abstract model to store various rates"""
    created = models.DateField(auto_now_add=True)

    objects = models.Manager()

    class Meta:
        abstract = True


class ParYieldRate(Rate):
    """Abstract model to store daily par yield rates"""
    date = models.DateField(unique=True)
    month1 = models.FloatField(null=True, blank=True)
    month2 = models.FloatField(null=True, blank=True)
    month3 = models.FloatField(null=True, blank=True)
    month4 = models.FloatField(null=True, blank=True)
    month6 = models.FloatField(null=True, blank=True)
    year1 = models.FloatField(null=True, blank=True)
    year2 = models.FloatField(null=True, blank=True)
    year3 = models.FloatField(null=True, blank=True)
    year5 = models.FloatField(null=True, blank=True)
    year7 = models.FloatField(null=True, blank=True)
    year10 = models.FloatField(null=True, blank=True)
    year20 = models.FloatField(null=True, blank=True)
    year30 = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['date']),
        ]


class TreasuryRates(ParYieldRate):
    """Daily par yield curve rates of U.S. Department of the Treasury"""
