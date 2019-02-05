from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework import filters

from .models import Node
from .serializers import NodeSerializer


# Create your views here.
class NodeView(ModelViewSet):
    http_method_names = ['get']

    queryset = Node.objects.all()
    serializer_class = NodeSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('identifier', 'metanode__identifier', 'name')
