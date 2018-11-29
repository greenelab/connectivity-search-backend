"""
```
python manage.py makemigrations
python manage.py migrate
python manage.py flush --no-input
python manage.py populate_database
```
"""

import functools
import pathlib
import zipfile
from urllib.request import urlretrieve

import hetio.readwrite
import hetmatpy.hetmat
import hetmatpy.pipeline
import pandas
from django.core.management.base import BaseCommand
from hetmatpy.hetmat.archive import load_archive

import dj_hetmech_app.models as hetmech_models
from dj_hetmech_app.utils import timed


class Command(BaseCommand):

    help = 'Populate the database with Hetionet information'
    download_dir = pathlib.Path(__file__).parent.joinpath('downloads')
    hetmat_path = download_dir / 'hetionet-v1.0.hetmat'

    @timed
    def _download_hetionet_hetmat(self):
        repo = 'https://github.com/hetio/hetionet'
        commit = '6186d406ee63455babc4801e8f6e87ce89b0a719'
        path = 'hetnet/matrix/hetionet-v1.0.hetmat.zip'
        url = f'{repo}/raw/{commit}/{path}'
        load_archive(url, self.hetmat_path)
        return self.hetmat_path

    @property
    @functools.lru_cache()
    def _hetionet_hetmat(self):
        if not self.hetmat_path.exists():
            self._download_hetionet_hetmat()
        return hetmatpy.hetmat.HetMat(self.hetmat_path)

    @property
    @functools.lru_cache()
    @timed
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

    @functools.lru_cache(maxsize=10_000)
    def _get_node(self, metanode, identifier):
        """
        Return the Django node object.
        """
        return hetmech_models.Node.objects.get(
            metanode=self._get_metanode(metanode),
            identifier=str(identifier),
        )

    @functools.lru_cache(maxsize=10_000)
    def _get_metapath(self, abbreviation):
        """
        Return the Django metapath object.
        """
        return hetmech_models.Metapath.objects.get(abbreviation=abbreviation)

    @functools.lru_cache(maxsize=10_000)
    def _get_dgp(self, metapath, source_degree, target_degree):
        """
        Return the Django metapath object.
        """
        return hetmech_models.DegreeGroupedPermutation.objects.get(
            metapath=self._get_metapath(str(metapath)),
            source_degree=source_degree,
            target_degree=target_degree,
        )

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

    def _populate_degree_grouped_permutation_table(self, length):
        """
        Populate DGP table from https://zenodo.org/record/1435834
        """
        assert isinstance(length, int)
        filename = f'degree-grouped-perms_length-{length}_damping-0.5.zip'
        path = self.zenodo_download('1435834', filename)
        with zipfile.ZipFile(path) as zip_file:
            for zip_path in zip_file.namelist():
                metapath, _ = pathlib.Path(zip_path).name.split('.', 1)
                with zip_file.open(zip_path) as tsv_file:
                    dgp_df = pandas.read_table(tsv_file, compression='gzip')
                dgp_df['mean_nz'] = dgp_df['sum'] / dgp_df['nnz']
                dgp_df['sd_nz'] = (
                    (dgp_df['sum_of_squares'] - dgp_df['sum'] ** 2 / dgp_df['nnz']) / (dgp_df['nnz'] - 1)) ** 0.5
                objs = list()
                for row in dgp_df.itertuples():
                    objs.append(hetmech_models.DegreeGroupedPermutation(
                        metapath=self._get_metapath(metapath),
                        source_degree=row.source_degree,
                        target_degree=row.target_degree,
                        n_dwpcs=row.n,
                        n_nonzero_dwpcs=row.nnz,
                        nonzero_mean=row.mean_nz,
                        nonzero_sd=row.sd_nz,
                    ))
                hetmech_models.DegreeGroupedPermutation.objects.bulk_create(objs)

    def _download_path_counts(self, length):
        """
        Populate path count table from https://zenodo.org/record/1435834
        """
        archives = [
            f'degree-grouped-perms_length-{length}_damping-0.5.zip',
            f'dwpcs_length-{length}_damping-0.0.zip',
            f'dwpcs_length-{length}_damping-0.5.zip',
        ]
        for archive in archives:
            path = self.zenodo_download('1435834', archive)
            load_archive(path, self.hetmat_path)

    def _populate_path_count_table(self, length):
        """
        Populate path count table.
        """
        hetmat = self._hetionet_hetmat
        metapaths = hetmech_models.Metapath.objects.values_list('abbreviation', flat=True)
        for metapath in metapaths:
            metapath = self._hetionet_graph.metagraph.metapath_from_abbrev(metapath)
            rows = hetmatpy.pipeline.combine_dwpc_dgp(
                graph=hetmat,
                metapath=metapath,
                damping=0.5,
                ignore_zeros=True,
                max_p_value=0.1,
            )
            objs = list()
            for row in rows:
                objs.append(hetmech_models.PathCount(
                    metapath=self._get_metapath(metapath),
                    source=self._get_node(metapath.source().identifier, row['source_id']),
                    target=self._get_node(metapath.target().identifier, row['target_id']),
                    dgp_id=self._get_dgp(str(metapath), row['source_degree'], row['target_degree']),
                    path_count=row['path_count'],
                    dwpc=row['dwpc'],
                    p_value=row['p_value'],
                ))
            hetmech_models.PathCount.objects.bulk_create(objs)

    def handle(self, *args, **options):
        timed(self._populate_metanode_table)()
        timed(self._populate_metapath_table)()
        timed(self._populate_node_table)()
        timed(self._download_hetionet_hetmat)()
        for length in range(1, 2):
            timed(self._download_path_counts)(length)
            timed(self._populate_degree_grouped_permutation_table(length))
            timed(self._populate_path_count_table(length))

    def zenodo_download(self, record_id, filename):
        """
        Download a file from a Zenodo record and return the path to the
        download location. If a file already exists at the specified path,
        do not re-download.
        """
        record_id = str(record_id)
        storage = pathlib.Path(__file__).parent.joinpath('downloads')
        zenodo_dir = storage.joinpath('zenodo', record_id)
        zenodo_dir.mkdir(parents=True, exist_ok=True)
        path = zenodo_dir.joinpath(filename)
        if not path.exists():
            url = f'https://zenodo.org/record/{record_id}/files/{filename}'
            urlretrieve(url, path)
        return path
