import functools

from django.db.models import Q
from rest_framework import filters
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
    return Response([
        reverse('node', request=request, kwargs={'pk': 2}),
        reverse('nodes', request=request),
        reverse('random-node-pair', request=request),
        reverse('metapaths', request=request, kwargs={'source': 17054, 'target': 6602}),
        reverse('metapaths-random-nodes', request=request),
        reverse('paths', request=request, kwargs={'source': 17054, 'target': 6602, 'metapath': 'CbGeAlD'}),
    ])


class NodeViewSet(ReadOnlyModelViewSet):
    """
    Return nodes, sorted by similarity to the search term.
    Use `search=<str>` to search `identifier` for prefix match, and `name` for substring and trigram searches (similarity defaults to 0.3);
    Use `search=<str>&similarity=<value>` to set your own `similarity` value in the range of (0, 1.0].
    Set `similarity=1.0` to exclude trigram search.

    Set `other-node=node_id` to return non-null values for `metapath_count`.
    `metapath_counts` measures the number of metapaths stored in the database between the result node and other node.
    If `search` and `other-node` and both specified, results are sorted by search similarity and results with `metapath_count == 0` are returned.
    If `other-node` is specified but not `search`, results are sorted by `metapath_count` (descending) and only results with `metapath_count > 0` are returned.
    """
    http_method_names = ['get']
    serializer_class = NodeSerializer
    filter_backends = (filters.SearchFilter, )

    @functools.lru_cache()
    def get_serializer_context(self):
        """
        Add metapath_counts to context if "other-node" was specified.
        https://stackoverflow.com/a/52859696/4651668
        """
        context = super().get_serializer_context()
        search_against = context['request'].query_params.get('other-node')
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
        metanodes = get_metanodes(self.request)
        if metanodes is not None:
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
        elif 'other-node' in self.request.query_params:
            metapath_counts = self.get_serializer_context()['metapath_counts']
            queryset = queryset.filter(pk__in=set(metapath_counts))
            queryset = sorted(queryset, key=lambda node: metapath_counts[node.pk], reverse=True)

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
    Specify `complete` to also return metapaths of unknown significance whose path count information is not stored in the database.
    If not specified, `limit` defaults to returning all metapaths (i.e. without limit).

    The database only stores a single orientation of a metapath.
    For example, if GpPpGaD is stored between the given source and target node, DaGpPpG would not also be stored.
    Therefore, both orientations of a metapath are searched against the PathCount table.
    """
    http_method_names = ['get']

    def get(self, request, source, target):
        source_node = get_object_or_404(Node, pk=source)
        target_node = get_object_or_404(Node, pk=target)
        limit = get_limit(request, default=None)

        from .utils.paths import get_pathcount_queryset, get_metapath_queryset
        pathcounts = get_pathcount_queryset(source, target)
        pathcounts = PathCountDgpSerializer(pathcounts, many=True).data
        pathcounts.sort(key=lambda x: (x['adjusted_p_value'], x['p_value'], x['metapath_abbreviation']))
        if limit is not None:
            pathcounts = pathcounts[:limit]

        if 'complete' in request.query_params:
            metapaths_present = {x['metapath_id'] for x in pathcounts}
            metapath_qs = get_metapath_queryset(
                source_node.metanode,
                target_node.metanode,
                extra_filters=~Q(abbreviation__in=metapaths_present),
            )
            if limit is not None:
                metapath_qs = metapath_qs[:limit - len(pathcounts)]
            pathcounts += MetapathSerializer(metapath_qs, many=True).data

        # `metapath_qs = metapath_qs[:0]` doesn't filter to an empty query set`
        if limit is not None:
            pathcounts = pathcounts[:limit]

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


class QueryMetapathsRandomNodesView(QueryMetapathsView):
    """
    Return metapaths for a random source and target node for which at least one metapath with path count information exists in the database.
    """
    def get(self, request):
        info = RandomNodePairView().get(request=None).data
        response = super().get(
            request,
            source=info.pop('source_id'),
            target=info.pop('target_id'))
        response.data.update(info)
        return response


class QueryPathsView(APIView):
    """
    For a given source node, target node, and metapath, return the actual paths comprising the path count / DWPC.
    These paths have not been pre-computed and are extracted on-the-fly from the Hetionet Neo4j Browser.
    Therefore, it is advisable to avoid querying a source-target-metapath pair with a path count exceeding 10,000.
    Because results are ordered by PDP / percent_of_DWPC, reducing `limit` does not prevent neo4j from having to exhaustively traverse all paths.
    """
    http_method_names = ['get']

    def get(self, request, source, target, metapath):
        source_node = get_object_or_404(Node, pk=source)
        target_node = get_object_or_404(Node, pk=target)
        # TODO: validate "metapath" is a valid abbreviation
        limit = get_limit(request, default=100)

        from .utils.paths import get_paths
        output = get_paths(metapath, source_node.id, target_node.id, limit=limit)
        return Response(output)


def get_object_or_404(klass, *args, **kwargs):
    '''
    Similar to `django.shortcuts.get_object_or_404` but raises NotFound and produces a more verbose error message.
    '''
    from django.shortcuts import _get_queryset
    from rest_framework.exceptions import NotFound
    queryset = _get_queryset(klass)
    try:
        return queryset.get(*args, **kwargs)
    except queryset.model.DoesNotExist as e:
        error = e
    except queryset.model.MultipleObjectsReturned as e:
        error = e
    message = f"{error} Lookup parameters: args={args} kwargs={kwargs}"
    raise NotFound(message)


def get_metanodes(request):
    metanodes = request.query_params.get('metanodes')
    if metanodes is not None:
        assert isinstance(metanodes, str)
        metanodes = metanodes.split(',')
    return metanodes


def get_limit(request, default: int = 100):
    from rest_framework.exceptions import ParseError
    limit = request.query_params.get('limit', default)
    if limit is None:
        return None
    try:
        limit = int(limit)
    except Exception:
        raise ParseError("limit is not a valid number")
    if limit < 0:
        limit = None
    return limit
