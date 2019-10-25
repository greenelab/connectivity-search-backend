from django.db.models import Q
from rest_framework import filters, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import Node, PathCount
from .serializers import NodeSerializer, MetapathSerializer, PathCountDgpSerializer


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
    Use `count-metapaths-to=node_id` to return non-null values for metapath_counts;
    Use `search=<str>` to search `identifier` for prefix match, and `name` for substring and trigram searches (similarity defaults to 0.3);
    Use `search=<str>&similarity=<value>` to set your own `similarity` value in the range of (0, 1.0]. (Set the value to 1.0 to exclude trigram search.)
    """
    http_method_names = ['get']
    serializer_class = NodeSerializer
    filter_backends = (filters.SearchFilter, )

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
        """Optionally restricts the returned nodes based on `metanodes` and
        `search` parameters in the URL.
        """

        queryset = Node.objects.all()

        # 'metanodes' parameter for exact match on metanode abbreviation
        metanodes_str = self.request.query_params.get('metanodes', None)
        if metanodes_str is not None:
            metanodes = metanodes_str.split(',')
            queryset = queryset.filter(metanode__abbreviation__in=metanodes)

        # 'search' parameter to search 'identifier' and 'name' fields
        search_str = self.request.query_params.get('search', None)
        if search_str is not None:
            from django.contrib.postgres.search import TrigramSimilarity
            from django.db.models import Case, When, Value, IntegerField

            # 'similarity' defaults to 0.3
            similarity = self.request.query_params.get('similarity', "0.3")
            try:
                similarity = float(similarity)
                if similarity <= 0 or similarity > 1.0:
                    raise ValueError
            except ValueError:
                from rest_framework.exceptions import ParseError
                raise ParseError(
                    {'error': 'Value of similarity must be in (0, 1.0]'}
                )

            queryset = queryset.annotate(
                similarity=TrigramSimilarity('name', search_str)
            ).filter(
                Q(identifier__istartswith=search_str) |  # prefix match of "identifier
                Q(name__icontains=search_str) |          # substring match of "name"
                Q(similarity__gt=similarity)             # trigram search of "name"
            ).annotate(
                identifier_prefix_match=Case(
                    When(identifier__istartswith=search_str, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
                name_substr_match=Case(
                    When(name__icontains=search_str, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ).order_by(
                '-identifier_prefix_match', '-name_substr_match', '-similarity', 'name'
            )

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

        from .utils.paths import get_pathcount_queryset, get_metapath_queryset
        pathcounts = get_pathcount_queryset(source_id, target_id)
        pathcounts = PathCountDgpSerializer(pathcounts, many=True).data
        pathcounts.sort(key=lambda x: (x['adjusted_p_value'], x['p_value'], x['metapath_abbreviation']))

        if 'complete' in request.query_params:
            metapaths_present = {x['metapath_id'] for x in pathcounts}
            metapath_qs = get_metapath_queryset(
                source_node.metanode,
                target_node.metanode,
                extra_filters=~Q(abbreviation__in=metapaths_present),
            )
            pathcounts += MetapathSerializer(metapath_qs, many=True).data

        remove_keys = {'source', 'target', 'metapath_source', 'metapath_target'}
        for dictionary in pathcounts:
            for key in remove_keys & set(dictionary):
                del dictionary[key]

        data = {
            'source': NodeSerializer(source_node).data,
            'target': NodeSerializer(target_node).data,
            'path_counts': pathcounts,
        }
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

        # 'metanodes' parameter for exact match on metanode abbreviation
        metanodes = self.request.query_params.get('metanodes', None)
        if metanodes is not None:
            metanodes = metanodes.split(',')

        from .utils.paths import get_metapath_counts_for_node
        node_counter = get_metapath_counts_for_node(query_node, metanodes)
        output = {
            'query-node': query_node,
            'metanodes': metanodes,
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
