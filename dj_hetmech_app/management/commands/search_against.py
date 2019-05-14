import collections

import pandas
import hetio.readwrite
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum, F

from dj_hetmech_app.utils.paths import (
    get_neo4j_node_info,
    get_neo4j_rel_info,
    get_paths,
)
from dj_hetmech_app.models import Node, PathCount


class Command(BaseCommand):

    help = 'Call dj_hetmech_app.utils.paths.get_paths for prototyping purposes.'

    def handle(self, *args, **options):
        # source_node = Node.objects.get(metanode='Compound', identifier='DB01156')  # Bupropion
        # target_node = Node.objects.get(metanode='Disease', identifier='DOID:0050742')  # nicotine dependency
        search_against_id = 43315
        query_set = (
            PathCount.objects
            .annotate(search_against=F('source'), node=F('target'))
            .filter(search_against=search_against_id)
            .values('node')
            .annotate(n_metapaths=Count('node'))
            .order_by('-n_metapaths')
        ).union((
            PathCount.objects
            .annotate(search_against=F('target'), node=F('source'))
            .filter(search_against=search_against_id)
            .values('node')
            .annotate(n_metapaths=Count('node'))
            .order_by('-n_metapaths')
        ), all=True)

        head_df = pandas.DataFrame(list(query_set)).head()
        if not head_df.empty:
            print(head_df.to_string(index=False), '\n')

        counter = collections.Counter()
        for result in query_set:
            counter[result['node']] += result['n_metapaths']
        print(counter.most_common(n=10))

        # # Reverse
        # query_set_b = (
        #     PathCount.objects
        #     .annotate(search_against=F('target'), node=F('source'))
        #     .filter(search_against=search_against_id)
        #     .values('node')
        #     .annotate(n_metapaths=Count('node'))
        #     .order_by('-n_metapaths')
        # )
        # head_df = pandas.DataFrame(list(query_set_b)).head()
        # if not head_df.empty:
        #     print(head_df.to_string(index=False), '\n')
        # query_set = query_set_a.union(query_set_b, all=True)
        # for result in query_set:
        #     counter[result['node']] += result['n_metapaths']

        # Reverse

        # metapath_qs = PathCount.objects.filter(
        #     Q(source=source_id, target=target_id) |
        #     Q(source=target_id, target=source_id)
        # )
