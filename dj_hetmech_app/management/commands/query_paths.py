import json

import hetnetpy.readwrite
from django.core.management.base import BaseCommand

from dj_hetmech_app.utils.paths import (
    get_paths,
    get_metapath_queryset,
)
from dj_hetmech_app.models import Node


class Command(BaseCommand):

    help = 'Call dj_hetmech_app.utils.paths.get_paths for prototyping purposes.'

    def handle(self, *args, **options):
        # source_node = Node.objects.get(metanode='Compound', identifier='DB01156')  # Bupropion
        # target_node = Node.objects.get(metanode='Disease', identifier='DOID:0050742')  # nicotine dependency
        # json_obj = get_paths(
        #     #metapath='CbGiGaD',
        #     metapath='CbGiGaDrD',
        #     source_id=source_node.id, 
        #     target_id=target_node.id,  
        #     limit=100,
        # )
        qs = get_metapath_queryset(
            source_metanode='Gene',
            target_metanode='Disease',
        )
        qs = qs[:5]
        from dj_hetmech_app.serializers import MetapathSerializer, serialize_record
        #json_obj = [serialize_record(record, extra_fields=['reversed']) for record in qs]
        json_obj = [MetapathSerializer(record).data for record in qs]
        #json_obj = list(qs.values())
        json_str = json.dumps(json_obj, indent=2, ensure_ascii=False)
        print(json_str)
