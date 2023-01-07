from datetime import datetime

from django.db.models import F
from django.views.generic import TemplateView

from .models import TreasuryRates


class IndexView(TemplateView):
    template_name = 'markets/index.html'


class YieldPerDayView(TemplateView):
    template_name = 'markets/yield_per_day.html'

    def get(self, request, *args, **kwargs):
        kwargs['params'] = request.GET
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fields = TreasuryRates.get_fields_list()

        context['rates'] = list(map(TreasuryRates.serialize_per_day,
                                    TreasuryRates.objects.order_by('-date').values(*fields)))
        return context


class YieldPerMaturityView(TemplateView):
    template_name = 'markets/yield_per_maturity.html'

    def get(self, request, *args, **kwargs):
        kwargs['params'] = request.GET
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = kwargs['params']
        fields = TreasuryRates.get_fields_list()

        query = TreasuryRates.objects.order_by('-date')
        if 'since' in params and params['since']:
            since = datetime.strptime(params['since'], '%Y-%m').date()
            query = query.filter(date__gte=since)

        if 'to' in params and params['to']:
            to = datetime.strptime(params['to'], '%Y-%m').date()
            query = query.filter(date__lte=to)

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
