from django.db.models import Q
from rest_framework import filters, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from .models import Node, PathCount
from .serializers import NodeSerializer, PathCountDgpSerializer

# Create your views here.

# The view that shows node information.
# See the following page for "search" implementation and other filter options:
# https://www.django-rest-framework.org/api-guide/filtering/
class NodeView(ModelViewSet):
    http_method_names = ['get']
    serializer_class = NodeSerializer
    filter_backends = (filters.SearchFilter, )
    search_fields = ('identifier', 'metanode__identifier', 'name')

    def get_queryset(self):
        """Optionally restricts the returned nodes to a given list of
        metanode abbreviations by filtering against a comma-separated
        `matanodes` query parameter in the URL.
        """

        queryset = Node.objects.all()
        metanodes_str = self.request.query_params.get('metanodes', None)
        if metanodes_str is not None:
            metanodes = metanodes_str.split(',')
            queryset = queryset.filter(metanode__abbreviation__in=metanodes)

        return queryset


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
                from dj_hetmech_app.utils import reverse_metapath
                entry.update(reverse_metapath(entry['metapath_abbreviation']))

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
        # Validate "source" parameter
        source_id = request.query_params.get('source', None)
        if source_id is None:
            return Response(
                {'error': 'source parameter not found in URL'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            source_node = Node.objects.get(pk=source_id)
        except:
            return Response(
                {'error': 'source node not found in database'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate "target" parameter
        target_id = request.query_params.get('target', None)
        if target_id is None:
            return Response(
                {'error': 'target parameter not found in URL'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            target_node = Node.objects.get(pk=target_id)
        except:
            return Response(
                {'error': 'target node not found in database'},
                status=status.HTTP_404_NOT_FOUND
            )

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
