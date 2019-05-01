from django.db.models import Q
from rest_framework import filters, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from .models import Node, PathCount
from .serializers import NodeSerializer, PathCountDgpSerializer


@api_view(['GET'])
def api_root(request):
    return Response({
        'nodes': reverse('node-list', request=request),
        'query-metapaths': reverse('query-metapaths', request=request),
        'query-paths': reverse('query-paths', request=request),
    })


# The view that shows node information.
# See the following page for "search" implementation and other filter options:
# https://www.django-rest-framework.org/api-guide/filtering/
class NodeViewSet(ModelViewSet):
    http_method_names = ['get']
    serializer_class = NodeSerializer
    filter_backends = (filters.SearchFilter, )
    search_fields = ('identifier', 'metanode__identifier', 'name')

    def get_queryset(self):
        """Optionally restricts the returned nodes to a given list of
        metanode abbreviations by filtering against a comma-separated
        `metanodes` query parameter in the URL.
        """

        queryset = Node.objects.all()
        metanodes_str = self.request.query_params.get('metanodes', None)
        if metanodes_str is not None:
            metanodes = metanodes_str.split(',')
            queryset = queryset.filter(metanode__abbreviation__in=metanodes)

        return queryset


class QueryMetapathsView(APIView):
    http_method_names = ['get']

    def polish_pathcounts(self, source_id, target_id, pathcounts_data):
        """This function polishes pathcounts_data. The polishment includes:
        * Add extra metapath-related fields;
        * Copy nested fields in 'dgp' to upper level;
        * Make source/target consistent with query parameters in the URL;
        * Remove redundant fields;
        * Sort pathcounts by certain fields.
        """

        for entry in pathcounts_data:
            # Retrieve hetio.hetnet.MetaPath object for metapath
            from dj_hetmech_app.utils import metapath_from_abbrev
            serialized_metapath = entry.pop('metapath')
            metapath = metapath_from_abbrev(serialized_metapath['abbreviation'])

            # Copy all key/values in entry['dgp'] and remove 'dgp' field:
            for key, value in entry.pop('dgp').items():
                entry[f'dgp_{key}'] = value

            for key, value in serialized_metapath.items():
                entry[f'metapath_{key}'] = value

            # If necessary, swap "source_degree" and "target_degree" values.
            entry['metapath_reversed'] = int(source_id) != entry['source']
            if entry['metapath_reversed']:
                metapath = metapath.inverse
                entry['dgp_source_degree'], entry['dgp_target_degree'] = (
                    entry['dgp_target_degree'], entry['dgp_source_degree']
                )

            entry['metapath_abbreviation'] = metapath.abbrev
            entry['metapath_name'] = metapath.get_unicode_str()
            entry['metapath_metaedges'] = [metaedge.get_id() for metaedge in metapath]

            # Remove fields
            for key in 'source', 'target':
                del entry[key]

        # Sort pathcounts_data by 'p_value' and 'metapath_abbreviation' fields:
        pathcounts_data.sort(
            key=lambda x: (x['p_value'], x['metapath_abbreviation'])
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


class QueryPathsView(APIView):
    http_method_names = ['get']

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

        metapath = request.query_params.get('metapath', None)
        if metapath is None:
            return Response(
                {'error': 'metapath parameter not found in URL'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # TODO: validate "metapath" is a valid abbreviation

        # Validate "max-paths" (default to 100 if not found in URL)
        max_paths = request.query_params.get('max-paths', '100')
        try:
            max_paths = int(max_paths)
        except Exception:
            return Response(
                {'error': 'max-paths is not a valid number'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if max_paths < 0:
            max_paths = None

        from .utils.paths import get_paths
        output = get_paths(metapath, source_node.id, target_node.id, limit=max_paths)
        return Response(output)
