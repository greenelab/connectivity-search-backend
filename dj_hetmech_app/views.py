from django.db.models import Q
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework import filters

from .models import Node, PathCount
from .serializers import NodeSerializer, PathCountDgpSerializer

# Create your views here.

# The view that shows node information.
# See the following page for "search" implementation and other filter options:
# https://www.django-rest-framework.org/api-guide/filtering/
class NodeView(ModelViewSet):
    http_method_names = ['get']

    queryset = Node.objects.all()
    serializer_class = NodeSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('identifier', 'metanode__identifier', 'name')


class QueryPairView(APIView):
    http_method_names = ['get']

    def polish_pathcounts(self, source_id, target_id, pathcounts_data):
        """This function polishes pathcounts_data. The polishment includes:
        * Copy nested fields in 'metapath' and 'dgp' to upper level;
        * Make source/target consistent with query parameters in the URL;
        * Remove redundant fields;
        * Sort pathcounts by certain fields.
        """

        for entry in pathcounts_data:
            # Copy the two key/value pairs in entry['metapath'] to entry:
            entry['metapath_abbreviation'] = entry['metapath']['abbreviation']
            entry['metapath_name'] = entry['metapath']['name']

            # Copy all key/values in entry['dgp'] and remove 'dgp' field:
            entry.update(entry.pop('dgp'))

            # If necessary, swap "source_degree" and "target_degree" values.
            reversed = int(source_id) != entry['source']
            entry['reversed'] = reversed
            if reversed:
                entry['source_degree'], entry['target_degree'] = (
                    entry['target_degree'], entry['source_degree']
                )

            # Delete 'metapath', 'source' and 'target' fields
            del entry['metapath']
            del entry['source']
            del entry['target']

        # Sort pathcounts_data by 'p_value' and 'metapath_abbreviation' fields:
        pathcounts_data.sort(
            key=lambda i: (i['p_value'], i['metapath_abbreviation'])
        )

        return pathcounts_data

    def get(self, request):
        source_id = request.query_params.get('source', None)
        target_id = request.query_params.get('target', None)
        try:
            source_node = Node.objects.get(pk=source_id)
            target_node = Node.objects.get(pk=target_id)
        except:
            raise Http404

        path_counts = PathCount.objects.filter(
            Q(source=source_id, target=target_id) |
            Q(source=target_id, target=source_id)
        )

        data = dict()
        data['source'] = NodeSerializer(source_node).data
        data['target'] = NodeSerializer(target_node).data
        data['path_counts'] = self.polish_pathcounts(
            source_id,
            target_id,
            PathCountDgpSerializer(path_counts, many=True).data
        )

        return Response(data)
