from django.db.models import F
from django.http.request import HttpRequest
from django.views.generic import TemplateView

from .helpers import parse_date
from .models import TreasuryRates
from .reports import get_market_dynamics, get_assets_dynamics


class IndexView(TemplateView):
    """View class for home page"""
    template_name = 'markets/index.html'


class YieldPerDayView(TemplateView):
    """View class for Yield per Day page"""
    template_name = 'markets/yield_per_day.html'

    def get(self, request, *args, **kwargs):
        kwargs['params'] = request.GET
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fields = TreasuryRates.get_fields_list()

        res = list(map(TreasuryRates.serialize_per_day,
                       TreasuryRates.objects.order_by('-date').values(*fields)))
        full_res = []

        when = parse_date(kwargs['params'].get('when'))
        if when:
            try:
                custom_res = TreasuryRates.objects.filter(date=when).values(*fields)
                if custom_res.count():
                    custom_res = custom_res.first()
                    custom_res = TreasuryRates.serialize_per_day(custom_res)
                    custom_res['label'] = custom_res['label'] + ' (Custom)'
                    full_res.append(custom_res)
            except ValueError:
                pass

        selections = {
            'Yesterday': 0,
            'Week': 5,
            'Month': 20,
            'Quarter': 60,
            'Half Year': 120,
            'Year': 250
        }
        for period, offset in selections.items():
            if len(res) < offset:
                break
            day_stat = res[offset]
            label = day_stat['label'] + f' ({period})'
            day_stat['label'] = label
            full_res.append(day_stat)

        context['rates'] = {'datasets': full_res}
        return context


class YieldPerMaturityView(TemplateView):
    """View class for Yield per Maturity page"""
    template_name = 'markets/yield_per_maturity.html'

    def get(self, request: HttpRequest, *args, **kwargs):
        kwargs['params'] = request.GET
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = kwargs['params']
        fields = TreasuryRates.get_fields_list()

        query = TreasuryRates.objects.order_by('-date')

        # Filter data for a period
        for filt_str, border_str in [('date__gte', 'since'), ('date__lte', 'to')]:
            border = params.get(border_str)
            if border_str == 'since' and not border:
                border = '01/01/2007'  # If no start period provided set default to 2007
            border = parse_date(border) if border else None
            if border:
                query = query.filter(**{filt_str: border})

        # Check if query has more than LIMIT of points, then take only Nth elements
        if 'limit' in params and params['limit']:
            limit = int(params['limit'])
        else:
            limit = 30  # Default LIMIT is 30 points
        excess = query.count() // limit
        if excess:
            offset = query.first().id % excess
            # query = query.annotate(row_id=Window(expression=RowNumber()))
            query = query.annotate(idmod=(F('id') - offset) % excess).filter(idmod=0)

        query = query.values(*fields)
        context['rates'] = TreasuryRates.serialize_per_maturity(sorted(list(query), key=lambda x: x['date']))
        return context


class SectorsView(TemplateView):
    """View class for Market Sectors page"""
    template_name = 'markets/sectors.html'

    def get(self, request: HttpRequest, *args, **kwargs):
        kwargs['params'] = request.GET
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = kwargs['params']
        custom_since = parse_date(params.get('since'))
        custom_to = None
        if custom_since:
            context['custom'] = True
            custom_to = parse_date(params.get('to'))

        assets = get_assets_dynamics(custom_since, custom_to)
        sp500 = assets.pop('S&P 500')
        context['assets'] = assets
        context['sp500'] = sp500
        context['sectors'] = get_market_dynamics(custom_since, custom_to)
        return context
