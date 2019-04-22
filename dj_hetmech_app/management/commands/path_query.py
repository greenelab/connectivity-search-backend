import json

import hetio.readwrite
from django.core.management.base import BaseCommand

from dj_hetmech_app.utils.paths import (
    get_neo4j_node_info,
    get_neo4j_rel_info,
    get_paths,
)


class Command(BaseCommand):

    help = 'Call dj_hetmech_app.utils.paths.get_paths for prototyping purposes.'

    def handle(self, *args, **options):
        metagraph_url = 'https://github.com/hetio/hetionet/raw/727411d4796ba2858bc8e684ba407047c1615390/hetnet/json/hetionet-v1.0-metagraph.json'
        metagraph = hetio.readwrite.read_metagraph(metagraph_url)
        json_obj = get_paths(
            metagraph=metagraph,
            metapath='CbGiGaD',
            source_identifier='DB01156',  # Bupropion
            target_identifier='DOID:0050742',  # nicotine dependency
            limit=100,
        )
        json_str = json.dumps(json_obj, indent=2)
        print(json_str)
