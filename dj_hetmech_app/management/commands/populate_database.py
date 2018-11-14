"""
```
python manage.py makemigrations
python manage.py migrate
python manage.py flush --no-input
python manage.py populate_database
```
"""

import functools

from django.core.management.base import BaseCommand
import hetio.readwrite
import pandas

import dj_hetmech_app.models as hetmech_models


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

    @functools.lru_cache()
    def _get_metanode(self, identifier):
        """
        Return the Django metanode object.
        """
        return hetmech_models.Metanode.objects.get(identifier=identifier)

    def _populate_metanode_table(self):
        url = 'https://github.com/hetio/hetionet/raw/23f6117c24b9a3130d8050ee4354b0ccd6cd5b9a/describe/nodes/metanodes.tsv'
        metanode_df = pandas.read_table(url).sort_values('metanode')
        for row in metanode_df.itertuples():
            hetmech_models.Metanode.objects.create(
                identifier=row.metanode,
                abbreviation=row.abbreviation,
                n_nodes=row.nodes,
            )

    def _populate_metapath_table(self):
        repo = 'https://github.com/greenelab/hetmech'
        commit = '34e95b9f72f47cdeba3d51622bee31f79e9a4cb8'
        path = 'explore/bulk-pipeline/archives/metapath-dwpc-stats.tsv'
        url = f'{repo}/raw/{commit}/{path}'
        metapath_df = pandas.read_table(url).rename(columns={
            'dwpc-0.5_raw_mean': 'dwpc_raw_mean',
        })
        metagraph = self._hetionet_graph.metagraph
        objs = list()
        for row in metapath_df.itertuples():
            metapath = metagraph.metapath_from_abbrev(row.metapath)
            objs.append(hetmech_models.Metapath(
                abbreviation=metapath.abbrev,
                name=metapath.get_unicode_str(),
                source=self._get_metanode(metapath.source().identifier),
                target=self._get_metanode(metapath.target().identifier),
                length=len(metapath),
                path_count_density=row.pc_density,
                path_count_mean=row.pc_mean,
                path_count_max=row.pc_max,
                dwpc_raw_mean=row.dwpc_raw_mean,
            ))
        hetmech_models.Metapath.objects.bulk_create(objs)

    def _populate_node_table(self):
        nodes = sorted(self._hetionet_graph.get_nodes())
        objs = list()
        for node in nodes:
            objs.append(hetmech_models.Node(
                metanode=self._get_metanode(node.metanode.identifier),
                identifier=str(node.identifier),
                identifier_type=node.identifier.__class__.__name__,
                name=node.name,
                url=node.data.get('url', ''),
                data=node.data,
            ))
        hetmech_models.Node.objects.bulk_create(objs)

    def handle(self, *args, **options):
        self._populate_metanode_table()
        self._populate_metapath_table()
        self._populate_node_table()
