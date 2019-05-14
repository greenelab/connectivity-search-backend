from rest_framework import serializers
from .models import (
    Node,
    Metapath,
    PathCount,
    DegreeGroupedPermutation,
)


class NodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Node
        fields = '__all__'

    # search_against_n_metapaths = serializers.SerializerMethodField()

    # def get_search_against_n_metapaths(self, record):
    #     return None


class DgpSerializer(serializers.ModelSerializer):
    class Meta:
        model = DegreeGroupedPermutation
        exclude = ('id', 'metapath', )


class MetapathSerializer(serializers.ModelSerializer):

    # metapath_abbreviation = serializers.CharField(source='abbreviation')
    # metapath_name = serializers.CharField(source='name')
    metaedges = serializers.SerializerMethodField()

    class Meta:
        model = Metapath
        exclude = ('source', 'target', )

    def get_metaedges(self, record):
        from dj_hetmech_app.utils import metapath_from_abbrev
        metapath = metapath_from_abbrev(record.abbreviation)
        return [metaedge.get_id() for metaedge in metapath]


class PathCountDgpSerializer(serializers.ModelSerializer):
    dgp = DgpSerializer()
    metapath = MetapathSerializer()

    class Meta:
        model = PathCount
        fields = '__all__'

    adjusted_p_value = serializers.SerializerMethodField()

    def get_adjusted_p_value(self, record):
        return record.get_adjusted_p_value()
