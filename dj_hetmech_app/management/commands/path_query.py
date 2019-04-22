from django.core.management.base import BaseCommand

from dj_hetmech_app.utils.paths import (
    get_neo4j_node_info,
    get_neo4j_rel_info,
    get_paths,
)


class Command(BaseCommand):

    help = 'Run a test.'

    def handle(self, *args, **options):
        import hetio.readwrite
        import json
        metagraph = hetio.readwrite.read_metagraph('https://github.com/hetio/hetionet/raw/master/hetnet/json/hetionet-v1.0-metagraph.json')
        # id_to_info = get_neo4j_node_info(node_ids=[0, 1])
        # print(id_to_info)

        # id_to_info = get_neo4j_rel_info(rel_ids=[2029636, 1638425])
        # print(id_to_info)
        json_obj = get_paths(
            metagraph=metagraph,
            metapath='CbGiGaD',
            source_identifier='DB01156',  # Bupropion
            target_identifier='DOID:0050742',  # nicotine dependency
            limit=100,
        )
        print(json.dumps(json_obj, indent=2))
