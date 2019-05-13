import logging

import hetio.neo4j

from dj_hetmech_app.utils import (
    get_hetionet_metagraph,
    get_neo4j_driver,
)


def get_paths(metapath, source_id, target_id, limit=None):
    """
    Return JSON-serializeable object with paths between two nodes for a given metapath.
    """
    metagraph = get_hetionet_metagraph()
    metapath = metagraph.get_metapath(metapath)

    from dj_hetmech_app.models import Node, PathCount
    from django.db.models import Q
    source_record = Node.objects.get(pk=source_id)
    target_record = Node.objects.get(pk=target_id)
    source_identifier = source_record.get_cast_identifier()
    target_identifier = target_record.get_cast_identifier()

    metapath_qs = PathCount.objects.filter(
        Q(metapath=metapath.abbrev, source=source_id, target=target_id) |
        Q(metapath=metapath.inverse.abbrev, source=target_id, target=source_id)
    )
    metapath_record = metapath_qs.first()
    metapath_qs_count = metapath_qs.count()
    if metapath_qs_count > 1:
        # see https://github.com/greenelab/hetmech-backend/issues/43
        import pandas
        qs_df = pandas.DataFrame.from_records(metapath_qs.all().values())
        logging.warning(
            f'get_paths returned {metapath_qs_count} results, '
            'but database should not have more than one row (including inverse orientation) for '
            f'{metapath.abbrev} from {source_id} to {target_id}.\n'
            + qs_df.to_string(index=False)
        )
    if metapath_record and metapath_record.p_value:
        import math
        metapath_score = -math.log10(metapath_record.get_adjusted_p_value())
    else:
        metapath_score = None

    query = hetio.neo4j.construct_pdp_query(metapath, property='identifier', path_style='id_lists')
    if limit is not None:
        query += f'\nLIMIT {limit}'
    driver = get_neo4j_driver()
    neo4j_params = {
        'source': source_identifier,
        'target': target_identifier,
        'w': 0.5,
    }
    with driver.session() as session:
        results = session.run(query, neo4j_params)
        results = [dict(record) for record in results]
    neo4j_node_ids = set()
    neo4j_rel_ids = set()
    paths_obj = []
    for row_ in results:
        row = {
            'metapath': metapath.abbrev,
        }
        row.update(row_)
        row['score'] = None if metapath_score is None else metapath_score * row['percent_of_DWPC']
        neo4j_node_ids.update(row['node_ids'])
        neo4j_rel_ids.update(row['rel_ids'])
        paths_obj.append(row)

    node_id_to_info = get_neo4j_node_info(neo4j_node_ids)
    rel_id_to_info = get_neo4j_rel_info(neo4j_rel_ids)
    json_obj = {
        'query': {
            'source_id': source_id,
            'target_id': target_id,
            'source_metanode': source_record.metanode.identifier,
            'target_metanode': target_record.metanode.identifier,
            'source_identifier': source_identifier,
            'target_identifier': target_identifier,
            'metapath': metapath.abbrev,
            'metapath_id': [edge.get_id() for edge in metapath],
            'metapath_score': metapath_score,
            'limit': limit,
        },
        'paths': paths_obj,
        'nodes': node_id_to_info,
        'relationships': rel_id_to_info,
    }
    return json_obj


cypher_node_query = '''\
MATCH (node)
WHERE id(node) IN $node_ids
RETURN
  id(node) AS neo4j_id,
  head(labels(node)) AS node_label,
  properties(node) AS properties
ORDER BY neo4j_id
'''


def get_neo4j_node_info(node_ids):
    """
    Return information on nodes corresponding to the input neo4j node ids.
    """
    node_ids = sorted(node_ids)
    driver = get_neo4j_driver()
    with driver.session() as session:
        results = session.run(cypher_node_query, node_ids=node_ids)
        results = [dict(record) for record in results]
    metagraph = get_hetionet_metagraph()
    for record in results:
        metanode = metagraph.get_metanode(record['node_label'])
        record['metanode'] = metanode.identifier
    id_to_info = {x['neo4j_id']: x for x in results}
    return id_to_info


cypher_rel_query = '''\
MATCH ()-[rel]-()
WHERE id(rel) in $rel_ids
RETURN
  id(rel) AS neo4j_id,
  type(rel) AS rel_type,
  id(startNode(rel)) AS source_neo4j_id,
  id(endNode(rel)) AS target_neo4j_id,
  properties(rel) AS properties
ORDER BY neo4j_id
'''


def get_neo4j_rel_info(rel_ids):
    """
    Return information on relationships corresponding to the
    input neo4j relationship ids.
    """
    rel_ids = sorted(rel_ids)
    driver = get_neo4j_driver()
    with driver.session() as session:
        results = session.run(cypher_rel_query, rel_ids=rel_ids)
        results = [dict(record) for record in results]
    metagraph = get_hetionet_metagraph()
    for record in results:
        metaedge = metagraph.get_metaedge(record['rel_type'])
        record['kind'] = metaedge.kind
        record['directed'] = metaedge.direction != 'both'
    id_to_info = {x['neo4j_id']: x for x in results}
    return id_to_info
