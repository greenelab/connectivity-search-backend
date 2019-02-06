from rest_framework.viewsets import ModelViewSet
from rest_framework import filters

from .models import Node
from .serializers import NodeSerializer


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
