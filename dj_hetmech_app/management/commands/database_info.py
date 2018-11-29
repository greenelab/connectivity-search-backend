import collections

import django.apps
from django.core.management.base import BaseCommand
import pandas


class Command(BaseCommand):

    help = 'Print information on dj_hetmech_app database tables.'

    def handle(self, *args, **options):
        dj_hetmech_app = django.apps.apps.get_app_config('dj_hetmech_app')
        for model in dj_hetmech_app.models.values():
            print(
                f' {model.__name__} Table '.center(80, '#') + '\n' +
                f'{model.objects.all().count():,} rows\n'
            )
            rows = map(collections.OrderedDict, model.objects.all()[:5].values())
            head_df = pandas.DataFrame.from_records(rows)
            if not head_df.empty:
                print(head_df.to_string(index=False), '\n')
