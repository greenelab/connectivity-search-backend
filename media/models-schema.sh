#!/usr/bin/env bash

# Uses the [graph_models](https://django-extensions.readthedocs.io/en/latest/graph_models.html) management command
# from django-extensions.
# See graph_models source code for usage at
# https://github.com/django-extensions/django-extensions/blob/a7e86ec0a8708b5e0555f4a52f9be250a55c2012/django_extensions/management/commands/graph_models.py#L47
# The original graphviz theme is [defined here](https://github.com/django-extensions/django-extensions/blob/2.2.9/django_extensions/templates/django_extensions/graph_models/original/digraph.dot).
# Must install django-extensions and graphviz/

# Export first to .dot for more control over graphviz command
python manage.py graph_models \
  --dot \
  --disable-sort-fields \
  --theme=original \
  --arrow-shape=inv \
  --output=media/models-schema.dot \
  dj_hetmech_app

dot_options="\
  -Gsplines=curved \
  -Ecolor=#08519c \
  -Gdpi=300 \
  -Gmargin=0 \
  media/models-schema.dot \
"

# SVG doesn't handle bold letters properly, so use PDF for vectors
# https://www.graphviz.org/doc/info/command.html
circo -Tpdf -o media/models-schema.pdf $dot_options

# Export to high-resolution PNG
circo -Tpng -o media/models-schema.png $dot_options
