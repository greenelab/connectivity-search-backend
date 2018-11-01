"""
Database schema.

See https://django-extensions.readthedocs.io/en/latest/graph_models.html for
exporting a schema visualization. Must install django-extensions and pygraphviz / pydotplus,
then run:

```
python manage.py graph_models --output=media/models-schema.svg dj_hetmech
python manage.py graph_models --output=media/models-schema.png dj_hetmech
```

References:
  https://docs.djangoproject.com/en/2.1/ref/models/fields/
  https://docs.djangoproject.com/en/2.1/ref/models/options/
"""

from django.contrib.postgres.fields import JSONField
from django.db import models


class Metanode(models.Model):
    identifier = models.CharField(primary_key=True, max_length=50)
    abbreviation = models.CharField(max_length=10)
    n_nodes = models.PositiveIntegerField()

class Node(models.Model):
    metanode = models.ForeignKey(to='Metanode', on_delete=models.PROTECT)
    identifier = models.CharField(max_length=50)
    identifier_type = models.CharField(max_length=50, choices=[
        ('str', 'string'),
        ('int', 'integer'),
    ])
    name = models.CharField(max_length=200)
    url = models.URLField(blank=True)
    data = JSONField()

    class Meta:
        unique_together = ('metanode', 'identifier')


class Metapath(models.Model):
    abbreviation = models.CharField(primary_key=True, max_length=20)
    verbose = models.CharField(max_length=200)
    verbose_pretty = models.CharField(max_length=200)
    source = models.ForeignKey(to='Metanode', on_delete=models.PROTECT, related_name='metapath_source')
    target = models.ForeignKey(to='Metanode', on_delete=models.PROTECT, related_name='metapath_target')
    length = models.PositiveSmallIntegerField()
    path_count_density = models.FloatField()
    path_count_mean = models.FloatField()
    path_count_max = models.PositiveIntegerField()
    dwpc_raw_mean = models.FloatField()


class DegreeGroupedPermutation(models.Model):
    metapath = models.ForeignKey(to='Metapath', on_delete=models.PROTECT)
    source_degree = models.PositiveIntegerField()
    target_degree = models.PositiveIntegerField()
    n_dwpcs = models.PositiveIntegerField()
    n_nonzero_dwpcs = models.PositiveIntegerField()
    nonzero_mean = models.FloatField()
    nonzero_sd = models.FloatField()

    class Meta:
        unique_together = ('metapath', 'source_degree', 'target_degree')


class PathCount(models.Model):
    metapath = models.ForeignKey(to='Metapath', on_delete=models.PROTECT)
    source = models.ForeignKey(to='Node', on_delete=models.PROTECT, related_name='path_source')
    target = models.ForeignKey(to='Node', on_delete=models.PROTECT, related_name='path_target')
    path_count = models.PositiveIntegerField()
    dwpc = models.FloatField(
        verbose_name='degree-weighted path count with damping exponent of 0.5'
    )
    p_value = models.FloatField()

    class Meta:
        unique_together = ('metapath', 'source', 'target')
