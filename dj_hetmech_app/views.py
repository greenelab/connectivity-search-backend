from rest_framework.viewsets import ModelViewSet
from rest_framework import filters

from .models import Node, PathCount
from .serializers import NodeSerializer, PathCountSerializer


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
        node1 = self.request.query_params.get('node1', None)
        node2 = self.request.query_params.get('node2', None)
        if node1 and node2:
            queryset = queryset.filter(
                Q(source=node1, target=node2) | Q(source=node2, target=node1)
            )

        return queryset
