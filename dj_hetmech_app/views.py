from django.db.models import Q
from rest_framework import filters, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import Node, PathCount
from .serializers import NodeSerializer, PathCountDgpSerializer


@api_view(['GET'])
def api_root(request):
    """
    Hetionet connectivity search API. This API is used to power <https://search.het.io>.
    The codebase for this API is available at <https://github.com/greenelab/hetmech-backend>.
    Please use GitHub Issues for any questions or feedback.
    """
    return Response({
        'nodes': reverse('node-list', request=request),
        'random-node-pair': reverse('random-node-pair', request=request),
        'count-metapaths-to': reverse('count-metapaths-to', request=request),
        'query-metapaths': reverse('query-metapaths', request=request),
        'query-paths': reverse('query-paths', request=request),
    })


class NodeViewSet(ReadOnlyModelViewSet):
    """
    Return nodes in the network that match the search term (sometimes partially).
    Use `count-metapaths-to=node_id` to return non-null values for metapath_counts.
    """
    http_method_names = ['get']
    serializer_class = NodeSerializer
    filter_backends = (filters.SearchFilter, )
    # See the following page for "search" implementation and other filter options:
    # https://www.django-rest-framework.org/api-guide/filtering/
    search_fields = ('identifier', 'metanode__identifier', 'name')

    def get_serializer_context(self):
        """
        Add metapath_counts to context if "count-metapaths-to" was specified.
        https://stackoverflow.com/a/52859696/4651668
        """
        context = super().get_serializer_context()
        search_against = context['request'].query_params.get('count-metapaths-to')
        if search_against is None:
            return context
        try:
            search_against = int(search_against)
        except ValueError:
            return context
        from dj_hetmech_app.utils.paths import get_metapath_counts_for_node
        context['metapath_counts'] = get_metapath_counts_for_node(search_against)
        return context

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


class RandomNodePairView(APIView):
    """
    Return a random source and target node for which at least one metapath with path count information exists in the database.
    The implementation chooses a random row from the PathCount table,
    such that source-target pairs with many metapaths are more likely to be selected than source-target pairs with few metapaths.
    """
    http_method_names = ['get']

    def get(self, request):
        import random
        # More info on random row lookup at https://stackoverflow.com/a/56119397/4651668
        max_id = PathCount.objects.last().id
        random_id = random.randint(0, max_id)
        pathcount_row = PathCount.objects.get(pk=random_id)
        n_metapaths = PathCount.objects.filter(source=pathcount_row.source, target=pathcount_row.target).count()

        data = {
            'source_id': pathcount_row.source.id,
            'target_id': pathcount_row.target.id,
            'n_metapaths': n_metapaths,
            'pathcount_table_random_id': random_id,
            'pathcount_table_max_id': max_id,
        }
        return Response(data)


class QueryMetapathsView(APIView):
    """
    Return metapaths between a given source and target node whose path count information is stored in the database.
    The database only stores a single orientation of a metapath.
    For example, if GpPpGaD is stored between the given source and target node, DaGpPpG would not also be stored.
    Therefore, both orientations of a metapath are searched against the PathCount table.
    """
    http_method_names = ['get']

    def polish_pathcounts(self, source_node, target_node, pathcounts_data):
        """
        This function polishes pathcounts_data. The polishment includes:
        * Add extra metapath-related fields;
        * Copy nested fields in 'dgp' to upper level;
        * Make source/target consistent with query parameters in the URL;
        * Remove redundant fields;
        * Sort pathcounts by certain fields.
        """
        from dj_hetmech_app.utils import metapath_from_abbrev
        from hetio.neo4j import construct_pdp_query

        for entry in pathcounts_data:
            # Retrieve hetio.hetnet.MetaPath object for metapath
            serialized_metapath = entry.pop('metapath')
            metapath = metapath_from_abbrev(serialized_metapath['abbreviation'])

            # Copy all key/values in entry['dgp'] and remove 'dgp' field:
            for key, value in entry.pop('dgp').items():
                entry[f'dgp_{key}'] = value

            for key, value in serialized_metapath.items():
                entry[f'metapath_{key}'] = value

            # If necessary, swap "source_degree" and "target_degree" values.
            entry['metapath_reversed'] = int(source_node.id) != entry['source']
            if entry['metapath_reversed']:
                metapath = metapath.inverse
                entry['dgp_source_degree'], entry['dgp_target_degree'] = (
                    entry['dgp_target_degree'], entry['dgp_source_degree']
                )

            entry['metapath_abbreviation'] = metapath.abbrev
            entry['metapath_name'] = metapath.get_unicode_str()
            entry['metapath_metaedges'] = [metaedge.get_id() for metaedge in metapath]
            entry['cypher_query'] = (
                construct_pdp_query(metapath, property='identifier', path_style='string')
                .replace('{ source }', f"{source_node.get_cast_identifier().__repr__()} // {source_node.name}")
                .replace('{ target }', f"{target_node.get_cast_identifier().__repr__()} // {target_node.name}")
                .replace('{ w }', '0.5')
                .replace('RETURN', 'RETURN\n  path AS neo4j_path,')
                + '\nLIMIT 10'
            )

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
        except Node.DoesNotExist:
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
        except Node.DoesNotExist:
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
            source_node,
            target_node,
            PathCountDgpSerializer(path_counts, many=True).data
        )

        return Response(data)


class QueryPathsView(APIView):
    """
    For a given source node, target node, and metapath, return the actual paths comprising the path count / DWPC.
    These paths have not been pre-computed and are extracted on-the-fly from the Hetionet Neo4j Browser.
    Therefore, it is advisable to avoid querying a source-target-metapath pair with a path count exceeding 10,000.
    Because results are ordered by PDP / percent_of_DWPC, reducing max_paths does not prevent neo4j from having to exhaustively traverse all paths.
    """
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
        except Node.DoesNotExist:
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
        except Node.DoesNotExist:
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


class CountMetapathsToView(APIView):
    """
    Given a node, find the other nodes with the highest number of metapaths in the database.
    """
    http_method_names = ['get']

    def get(self, request, query_node=None):
        if query_node is None:
            return Response(
                {'error': 'must specify a query node like `count-metapaths-to/50/`'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate "max-nodes" (default to 100 if not found in URL)
        max_nodes = request.query_params.get('max-nodes', '50')
        try:
            max_nodes = int(max_nodes)
        except Exception:
            return Response(
                {'error': 'max-nodes is not a valid number'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if max_nodes < 0:
            max_nodes = None

        from .utils.paths import get_metapath_counts_for_node
        node_counter = get_metapath_counts_for_node(query_node)
        output = {
            'query-node': query_node,
            'count': len(node_counter),
            'max-nodes': max_nodes,
            'results': [],
        }
        for other_node, count in node_counter.most_common(n=max_nodes):
            other_node = Node.objects.get(pk=other_node)
            other_node_obj = NodeSerializer(other_node).data
            other_node_obj['metapath_count'] = count
            output['results'].append(other_node_obj)
        return Response(output)
