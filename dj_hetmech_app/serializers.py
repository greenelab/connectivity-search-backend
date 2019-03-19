from rest_framework import serializers
from .models import Node, Metapath, PathCount, DegreeGroupedPermutation

class NodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Node
        fields = '__all__'


class DgpSerializer(serializers.ModelSerializer):
    class Meta:
        model = DegreeGroupedPermutation
        exclude = ('id', 'metapath', )


class CompactMetaPathSerilizer(serializers.ModelSerializer):
    """This serializer only includes two fields in Metapath model.
    It is defined specifically for PathCountDgpSerializer.
    """
    class Meta:
        model = Metapath
        fields = ('abbreviation', 'name', )


class PathCountDgpSerializer(serializers.ModelSerializer):
    dgp = DgpSerializer()
    metapath = CompactMetaPathSerilizer()

    class Meta:
        model = PathCount
        fields = '__all__'
