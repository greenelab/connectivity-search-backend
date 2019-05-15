from django.core.management.base import BaseCommand


class Command(BaseCommand):

    help = 'Call dj_hetmech_app.utils.paths.get_paths for prototyping purposes.'

    def handle(self, *args, **options):
        # source_node = Node.objects.get(metanode='Compound', identifier='DB01156')  # Bupropion
        # target_node = Node.objects.get(metanode='Disease', identifier='DOID:0050742')  # nicotine dependency
        search_against_id = 43315
        from dj_hetmech_app.utils.paths import get_metapath_counts_for_node
        counter = get_metapath_counts_for_node(search_against_id)
        print(counter.most_common(10))
