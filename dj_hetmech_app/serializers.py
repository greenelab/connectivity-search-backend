from rest_framework import serializers
from .models import Node, PathCount

class NodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Node
        fields = '__all__'


class PathCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PathCount
        fields = '__all__'
