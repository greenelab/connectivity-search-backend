from django.db.models import Q
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework import filters

from .models import Node, PathCount
from .serializers import (
    NodeSerializer,
    PathCountSerializer,
    PathCountDgpSerializer,
)

# Create your views here.

# The view that shows node information.
# See this page for "search" implementation and other filter options:
# https://www.django-rest-framework.org/api-guide/filtering/
class NodeView(ModelViewSet):
    http_method_names = ['get']

    queryset = Node.objects.all()
    serializer_class = NodeSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('identifier', 'metanode__identifier', 'name')


class PathCountView(ModelViewSet):
    http_method_names = ['get']
    serializer_class = PathCountSerializer

    def get_queryset(self):
        """Optionally restricts the returned PathCount results to a given
        user by filtering against the two query parameters in the URL.
        """
        queryset = PathCount.objects.all()
        node1 = self.request.query_params.get('qsource', None)
        node2 = self.request.query_params.get('qtarget', None)
        if node1 and node2:
            queryset = queryset.filter(
                Q(source=node1, target=node2) | Q(source=node2, target=node1)
            )

        return queryset


class QueryPairView(APIView):
    http_method_names = ['get']

    def get(self, request):
        qsource_id = request.query_params.get('qsource', None)
        qtarget_id = request.query_params.get('qtarget', None)
        try:
            qsource_node = Node.objects.get(pk=qsource_id)
            qtarget_node = Node.objects.get(pk=qtarget_id)
        except:
            raise Http404

        path_counts = PathCount.objects.filter(
            Q(source=qsource_id, target=qtarget_id) |
            Q(source=qtarget_id, target=qsource_id)
        )

        data = {}
        data['qsource'] = NodeSerializer(qsource_node).data
        data['qtarget'] = NodeSerializer(qtarget_node).data
        data['pathCounts'] = PathCountDgpSerializer(path_counts, many=True).data

        return Response(data)
