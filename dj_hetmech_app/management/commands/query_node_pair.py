"""
# Obesity to FTO query
python manage.py query_node_pair \
  --source Disease DOID:9970 \
  --target Gene 79068

# hematologic cancer to multiple sclerosis query
python manage.py query_node_pair \
  --source Disease DOID:2531 \
  --target Disease DOID:2377

# multiple sclerosis to myelination query
python manage.py query_node_pair \
  --source Disease DOID:2531 \
  --target "Biological Process" "GO:0042552"
"""
import collections
import functools
import pathlib

from django.core.management.base import BaseCommand
# from django.db.models import F
from django.db.models import Q
import pandas

import dj_hetmech_app.models as hetmech_models


class Command(BaseCommand):

    help = 'Return metapath scores for a node pair.'

    @functools.lru_cache()
    def _get_metanode(self, identifier):
        """
        Return the Django metanode object.
        """
        return hetmech_models.Metanode.objects.get(identifier=identifier)

    @functools.lru_cache(maxsize=10_000)
    def _get_node(self, metanode, identifier):
        """
        Return the Django node object.
        """
        return hetmech_models.Node.objects.get(
            metanode=self._get_metanode(metanode),
            identifier=str(identifier),
        )

    def add_arguments(self, parser):
        parser.add_argument(
            '--source', required=True, nargs=2,
            help='The source node as its metanode and identifier'
        )
        parser.add_argument(
            '--target', required=True, nargs=2,
            help='The target node as its metanode and identifier'
        )
        parser.add_argument(
            '--output', type=pathlib.Path,
            help='Path to write output TSV to (otherwise uses stdout)'
        )

    def handle(self, *args, **options):
        source_kind, source_id = options['source']
        target_kind, target_id = options['target']
        source = self._get_node(source_kind, source_id)
        target = self._get_node(target_kind, target_id)
        # print(source)
        # print(target)
        qs = (
            hetmech_models.PathCount.objects
            .filter(Q(source=source, target=target) | Q(source=target, target=source))
            # .select_related('dgp')
            # .annotate(source_degree=F('dpg__source_degree'))
            .order_by('p_value')
        )
        rows = map(collections.OrderedDict, qs.values())
        dwpc_df = pandas.DataFrame.from_records(rows)
        if dwpc_df.empty:
            print('no results')
            return
        qs = (
            hetmech_models.DegreeGroupedPermutation.objects
            .filter(id__in=set(dwpc_df.dgp_id))
        )
        rows = map(collections.OrderedDict, qs.values())
        dgp_df = pandas.DataFrame.from_records(rows).rename(
            columns={'id': 'dgp_id'}
        )
        dwpc_df = dwpc_df.merge(dgp_df).drop(
            columns=['id', 'source_id', 'target_id', 'dgp_id']
        )
        if not dwpc_df.empty:
            if options['output']:
                dwpc_df.to_csv(options['output'], index=False, sep='\t')
            else:
                print(dwpc_df.to_string(index=False), '\n')
