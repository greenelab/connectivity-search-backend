import collections

import django.apps
from django.core.management.base import BaseCommand
import pandas


class Command(BaseCommand):

    help = 'Print information on dj_consearch_app database tables.'

    def handle(self, *args, **options):
        dj_consearch_app = django.apps.apps.get_app_config('dj_consearch_app')
        for model in dj_consearch_app.models.values():
            print(
                f' {model.__name__} Table '.center(80, '#') + '\n' +
                f'{model.objects.count():,} rows\n'
            )
            rows = map(collections.OrderedDict, model.objects.all()[:5].values())
            head_df = pandas.DataFrame.from_records(rows)
            if not head_df.empty:
                print(head_df.to_string(index=False), '\n')
        # Output number of metapaths in PathCount table
        total_metapaths = dj_consearch_app.models['metapath'].objects.count()
        complete_metapaths = dj_consearch_app.models['pathcount'].objects.values('metapath').distinct()
        print(f'{len(complete_metapaths):,} completed metapaths of {total_metapaths:,} total metapaths')

