from rest_framework import serializers
from .models import Node, PathCount, DegreeGroupedPermutation

class NodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Node
        fields = '__all__'


class DgpSerializer(serializers.ModelSerializer):
    class Meta:
        model = DegreeGroupedPermutation
        exclude = ('id', 'metapath', )


class PathCountDgpSerializer(serializers.ModelSerializer):
    dgp = DgpSerializer()
    class Meta:
        model = PathCount
        fields = '__all__'
