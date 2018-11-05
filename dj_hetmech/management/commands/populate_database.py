import functools

from django.core.management.base import BaseCommand
import hetio.readwrite
import pandas

import dj_hetmech.models as hetmech_models


class Command(BaseCommand):

    help = 'Populate the database with Hetionet information'

    @property
    @functools.lru_cache()
    def _hetionet_graph(self):
        repo = 'https://github.com/hetio/hetionet'
        commit = '23f6117c24b9a3130d8050ee4354b0ccd6cd5b9a'
        path = 'hetnet/json/hetionet-v1.0.json.bz2'
        url = f'{repo}/raw/{commit}/{path}'
        return hetio.readwrite.read_graph(url)

    def _populate_metanode_table(self):
        url = 'https://github.com/hetio/hetionet/raw/23f6117c24b9a3130d8050ee4354b0ccd6cd5b9a/describe/nodes/metanodes.tsv'
        metanode_df = pandas.read_table(url).sort_values('metanode')
        for row in metanode_df.itertuples():
            hetmech_models.Metanode.objects.create(
                identifier=row.metanode,
                abbreviation=row.abbreviation,
                n_nodes=row.nodes,
            )

    def _populate_node_table(self):
        nodes = sorted(self._hetionet_graph.get_nodes())
        for node in nodes:
            hetmech_models.Node.objects.create(
                metanode=node.kind.identifier,
                identifier=str(node.identifier),
                identifier_type=node.identifier.__class__.__name__,
                name=node.name,
                url=node.data.get('url', ''),
                data=node.data,
            )

    def handle(self, *args, **options):
        self._populate_metanode_table()
        self._populate_node_table()
