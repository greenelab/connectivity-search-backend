from rest_framework import serializers
from .models import (
    Node,
    Metapath,
    PathCount,
    DegreeGroupedPermutation,
)


class NodeSerializer(serializers.ModelSerializer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request or 'count-metapaths-to' not in request.query_params:
            del self.fields['metapath_count']

    class Meta:
        model = Node
        fields = '__all__'

    metapath_count = serializers.SerializerMethodField()

    def get_metapath_count(self, record):
        """
        Get the number of metapaths in the PathCounts database table from
        this node to the node specified by the count_metapaths_to request parameter.
        """
        if "metapath_counts" not in self.context:
            return None
        return self.context['metapath_counts'][record.id]


class DgpSerializer(serializers.ModelSerializer):

    class Meta:
        model = DegreeGroupedPermutation
        exclude = ('metapath', )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Replace nan with None. https://github.com/greenelab/hetmech-backend/issues/63
        from pandas import isna
        for key in 'nonzero_mean', 'nonzero_sd':
            if isna(data[key]):
                data[key] = None
        data['reversed'] = vars(instance).get('reversed')
        if data['reversed']:
            data['source_degree'], data['target_degree'] = (
                data['target_degree'], data['source_degree']
            )
        data = format_dictionary_keys(data, "dgp_{}".format)
        return data


class MetapathSerializer(serializers.ModelSerializer):

    class Meta:
        model = Metapath
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['id'] = instance.pk
        data['reversed'] = vars(instance).get('reversed')
        from dj_hetmech_app.utils import metapath_from_abbrev
        metapath = metapath_from_abbrev(data['abbreviation']).inverse
        instance.metapath_object = metapath
        if data['reversed']:
            data['abbreviation'] = metapath.abbrev
            data['name'] = metapath.get_unicode_str()
            data['source'], data['target'] = data['target'], data['source']
        data['metaedges'] = [metaedge.get_id() for metaedge in metapath]
        data = format_dictionary_keys(data, "metapath_{}".format)
        return data


class PathCountDgpSerializer(serializers.ModelSerializer):

    class Meta:
        model = PathCount
        fields = '__all__'

    dgp = DgpSerializer()
    metapath = MetapathSerializer()
    adjusted_p_value = serializers.SerializerMethodField()

    def get_adjusted_p_value(self, record):
        return record.get_adjusted_p_value()

    def to_representation(self, instance):
        reversed_ = vars(instance).get('reversed')
        instance.metapath.reversed = reversed_
        instance.dgp.reversed = reversed_
        data = super().to_representation(instance)
        data['reversed'] = reversed_
        data.update(data.pop('metapath'))
        data.update(data.pop('dgp'))
        data['cypher_query'] = self.get_cypher(instance)
        return data

    def get_cypher(self, instance):
        metapath = instance.metapath.metapath_object
        source = instance.source
        target = instance.target
        from hetnetpy.neo4j import construct_pdp_query
        cypher_query = (
            construct_pdp_query(metapath, property='identifier', path_style='string')
            .replace('{ source }', f"{source.get_cast_identifier().__repr__()} // {source.name}")
            .replace('{ target }', f"{target.get_cast_identifier().__repr__()} // {target.name}")
            .replace('{ w }', '0.5')
            .replace('RETURN', 'RETURN\n  path AS neo4j_path,')
            + '\nLIMIT 10'
        )
        return cypher_query


def serialize_record(record, include=[], exclude=[], key_formatter=None):
    """
    Serialize a django model instance (called `record`) to a dictionary.
    The `include` argument allows specifying record attributes that
    are not part of the model, such as annotated fields. `exclude` allows
    suppressing the addition of fields. `key_formatter` is a function that
    is called on key names to modify their formatting. For example,
    `key_formatter='prefix_{}'.format`.

    Based on code by Zagaran posted to StackOverflow under a CC BY-SA 3.0
    License at https://stackoverflow.com/a/29088221/4651668.
    """
    data = {}
    set_key_kwargs = {
        'data': data,
        'exclude': exclude,
        'key_formatter': key_formatter,
    }
    for field in record._meta.concrete_fields:
        __set_key(field.name, field.value_from_object(record), **set_key_kwargs)
    for field in record._meta.many_to_many:
        value = list(
            [] if record.pk is None else
            field.value_from_object(record).values_list('pk', flat=True)
        )
        __set_key(field.name, value, **set_key_kwargs)
    for key in include:
        __set_key(key, vars(record).get(key), **set_key_kwargs)
    return data


def __set_key(key, value, data, exclude, key_formatter=None):
    """
    Set key for serialize_record
    """
    if key in exclude:
        return
    if key_formatter:
        key = key_formatter(key)
    data[key] = value


def format_dictionary_keys(dictionary, formatter):
    """
    Returns a new dictionaries whose keys have been passed through
    `formatter`, which should be a function that formats strings.
    """
    new = {}
    for key, value in dictionary.items():
        assert isinstance(key, str)
        new[formatter(key)] = value
    return new
