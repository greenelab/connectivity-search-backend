"""
```
python manage.py makemigrations
python manage.py migrate
python manage.py flush --no-input
python manage.py populate_database --max-metapath-length=3  --reduced-metapaths --batch-size=12000
python manage.py database_info
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
from dj_hetmech_app.utils import (
    get_neo4j_driver,
    timed,
)


class Command(BaseCommand):

    help = 'Populate the database with Hetionet information'
    download_dir = pathlib.Path(__file__).parent.joinpath('downloads')
    hetmat_path = download_dir / 'hetionet-v1.0.hetmat'

    @timed
    def _download_hetionet_hetmat(self):
        path = self.github_download(
            repo='hetio/hetionet',
            commit='6186d406ee63455babc4801e8f6e87ce89b0a719',
            path='hetnet/matrix/hetionet-v1.0.hetmat.zip',
        )
        load_archive(path, self.hetmat_path)

    @property
    def _hetionet_metagraph(self):
        return self._hetionet_hetmat.metagraph

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
        path = self.github_download(
            repo='hetio/hetionet',
            commit='23f6117c24b9a3130d8050ee4354b0ccd6cd5b9a',
            path='hetnet/json/hetionet-v1.0.json.bz2',
        )
        return hetio.readwrite.read_graph(path)

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
        path = self.github_download(
            repo='hetio/hetionet',
            commit='23f6117c24b9a3130d8050ee4354b0ccd6cd5b9a',
            path='describe/nodes/metanodes.tsv',
        )
        metanode_df = pandas.read_csv(path, sep='\t').sort_values('metanode')
        for row in metanode_df.itertuples():
            hetmech_models.Metanode.objects.create(
                identifier=row.metanode,
                abbreviation=row.abbreviation,
                n_nodes=row.nodes,
            )

    @functools.lru_cache(maxsize=20_000)
    def _keep_metapath(self, metapath):
        """
        Return a boolean to indicate whether to load the specified metapath into the database.
        """
        metagraph = self._hetionet_metagraph
        metapath = metagraph.get_metapath(metapath)
        if len(metapath) > self.options['max_metapath_length']:
            return False
        if self.options['reduced_metapaths']:
            keep = {
                ('Compound', 'Disease'),
            }
            for pair in list(keep):
                keep.add((pair[1], pair[0]))
            endpoints = metapath.source().identifier, metapath.target().identifier
            if endpoints not in keep:
                return False
            metaedge_GcG = metagraph.get_metaedge('GcG')
            if {metaedge_GcG, metaedge_GcG.inverse} & set(metapath):
                return False
        return True

    def _get_metapath_p_threshold(self, row):
        """
        Return p-value threshold for a metapath
        """
        if row.length == 1:
            return 1.0
        p_threshold = 5 * row.n_pairs ** -0.3 / row.n_similar
        return p_threshold

    def _populate_metapath_table(self):
        path = self.github_download(
            repo='greenelab/hetmech',
            commit='34e95b9f72f47cdeba3d51622bee31f79e9a4cb8',
            path='explore/bulk-pipeline/archives/metapath-dwpc-stats.tsv',
        )
        metapath_df = pandas.read_csv(path, sep='\t').rename(columns={
            'dwpc-0.5_raw_mean': 'dwpc_raw_mean',
        })
        metagraph = self._hetionet_metagraph
        metapath_df['metapath_obj'] = metapath_df.metapath.map(metagraph.get_metapath)
        metapath_df = metapath_df[metapath_df.metapath_obj.map(self._keep_metapath)]
        metapath_df['source'] = metapath_df.metapath_obj.map(lambda x: x.source().identifier)
        metapath_df['target'] = metapath_df.metapath_obj.map(lambda x: x.target().identifier)
        # Add n_similar column with the number of other metapaths with the
        # same source and target metanodes and length.
        metapath_df = metapath_df.merge(
            metapath_df
            .groupby(['source', 'target', 'length'])
            .apply(len).rename('n_similar').reset_index()
        )
        metapath_df['p_threshold'] = [self._get_metapath_p_threshold(x) for x in metapath_df.itertuples()]
        objs = list()
        for row in metapath_df.itertuples():
            metapath = row.metapath_obj
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
                n_similar=row.n_similar,
                p_threshold=row.p_threshold,
            ))
        hetmech_models.Metapath.objects.bulk_create(objs)

    def _populate_node_table(self):
        """
        Pulls nodes from neo4j as per https://github.com/greenelab/hetmech-backend/issues/36
        """
        metagraph = self._hetionet_metagraph
        query = '''
        MATCH (node)
        RETURN
          id(node) AS neo4j_id,
          head(labels(node)) AS node_label,
          properties(node) AS data
        ORDER BY neo4j_id
        '''
        driver = get_neo4j_driver()
        with driver.session() as session:
            results = session.run(query)
            results = [dict(result) for result in results]
            objs = list()
            for result in results:
                data = result['data']
                identifier = data.pop('identifier')
                metanode = metagraph.get_metanode(result['node_label'])
                objs.append(hetmech_models.Node(
                    id=result['neo4j_id'],
                    metanode=self._get_metanode(metanode.identifier),
                    identifier=str(identifier),
                    identifier_type=identifier.__class__.__name__,
                    name=data.pop('name'),
                    data=data,
                ))
                if len(objs) >= self.options['batch_size']:
                    hetmech_models.Node.objects.bulk_create(objs)
                    objs = list()
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
                if not self._keep_metapath(metapath):
                    continue
                metapath_key = self._get_metapath(metapath)
                with zip_file.open(zip_path) as tsv_file:
                    dgp_df = pandas.read_csv(tsv_file, sep='\t', compression='gzip')
                dgp_df = hetmatpy.pipeline.add_gamma_hurdle_to_dgp_df(dgp_df)
                objs = list()
                for row in dgp_df.itertuples():
                    objs.append(hetmech_models.DegreeGroupedPermutation(
                        metapath=metapath_key,
                        source_degree=row.source_degree,
                        target_degree=row.target_degree,
                        n_dwpcs=row.n,
                        n_nonzero_dwpcs=row.nnz,
                        nonzero_mean=row.mean_nz,
                        nonzero_sd=row.sd_nz,
                    ))
                    if len(objs) >= self.options['batch_size']:
                        hetmech_models.DegreeGroupedPermutation.objects.bulk_create(objs)
                        objs = list()
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
            with zipfile.ZipFile(path) as zip_file:
                members = zip_file.namelist()
            source_paths = list()
            for member in members:
                metapath, _ = pathlib.Path(member).name.split('.', 1)
                if self._keep_metapath(metapath):
                    source_paths.append(member)
            load_archive(path, self.hetmat_path, source_paths=source_paths)

    def _populate_path_count_table(self):
        """
        Populate path count table.
        """
        hetmat = self._hetionet_hetmat
        metapaths = (
            hetmech_models
            .DegreeGroupedPermutation
            .objects
            .values_list('metapath', flat=True)
            .distinct()
            .order_by()
        )
        for metapath in metapaths:
            metapath = self._hetionet_metagraph.metapath_from_abbrev(metapath)
            metapath_record = self._get_metapath(metapath)
            rows = hetmatpy.pipeline.combine_dwpc_dgp(
                graph=hetmat,
                metapath=metapath,
                damping=0.5,
                ignore_zeros=True,
                max_p_value=metapath_record.p_threshold,
            )
            objs = list()
            for row in rows:
                objs.append(hetmech_models.PathCount(
                    metapath=metapath_record,
                    source=self._get_node(metapath.source().identifier, row['source_id']),
                    target=self._get_node(metapath.target().identifier, row['target_id']),
                    dgp=self._get_dgp(str(metapath), row['source_degree'], row['target_degree']),
                    path_count=row['path_count'],
                    dwpc=row['dwpc'],
                    p_value=row['p_value'],
                ))
                if len(objs) >= self.options['batch_size']:
                    hetmech_models.PathCount.objects.bulk_create(objs)
                    objs = list()
            hetmech_models.PathCount.objects.bulk_create(objs)

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-metapath-length', type=int, default=1,
            help='max metapath length for which to populate the database with path counts '
                 '(default 1). For example, 3 imports path counts for metapaths with length 1, 2, or 3.'
        )
        parser.add_argument(
            '--reduced-metapaths', action='store_true',
            help='only load a reduced set of metapaths into the database for efficient prototyping.'
        )
        parser.add_argument(
            '--batch-size', type=int, default=5_000,
            help='max number of objects to write to the database at a time '
                 '(default 5000)',
        )

    def handle(self, *args, **options):
        # Load configuration
        self.options = options
        # Download hetmat
        self._download_hetionet_hetmat()
        self._hetionet_metagraph
        # Populate tables
        timed(self._populate_metanode_table)()
        timed(self._populate_node_table)()
        timed(self._populate_metapath_table)()
        for length in range(1, 1 + options['max_metapath_length']):
            timed(self._download_path_counts)(length)
            timed(self._populate_degree_grouped_permutation_table)(length)
        timed(self._populate_path_count_table)()

    def zenodo_download(self, record_id, filename):
        """
        Download a file from a Zenodo record and return the path to the
        download location. If a file already exists at the specified path,
        do not re-download.
        """
        record_id = str(record_id)
        path = self.download_dir.joinpath('zenodo', record_id, filename)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            url = f'https://zenodo.org/record/{record_id}/files/{filename}'
            urlretrieve(url, path)
        return path

    def github_download(self, repo, commit, path):
        """
        Download a file from a GitHub repository and return the path to the
        download location. If a file already exists at the specified path,
        do not re-download.
        """
        repo_user, repo_name = repo.split('/')
        local_path = self.download_dir.joinpath(
            'github',
            repo_user,
            repo_name,
            commit,
            *path.split('/'),
        )
        if not local_path.exists():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            url = f'https://github.com/{repo}/raw/{commit}/{path}'
            urlretrieve(url, local_path)
        return local_path
