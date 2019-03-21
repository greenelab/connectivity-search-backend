import functools


def timed(func):
    """
    Decorator to print the execution time of a function. Partially based on
    https://gist.github.com/bradmontgomery/bd6288f09a24c06746bbe54afe4b8a82
    """
    import datetime
    import inspect
    import time

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        timedelta = datetime.timedelta(seconds=round(end - start))
        bound_args = inspect.signature(func).bind(*args, **kwargs)
        bound_args.apply_defaults()
        arg_str = ', '.join(f'{k}={v}' for k, v in bound_args.arguments.items())
        print(f'{func.__name__}({arg_str}) ran in {timedelta}')
        return result
    return wrapper


@functools.lru_cache()
def get_hetionet_metagraph():
    """
    https://github.com/hetio/hetionet/blob/b7c144da0dd428def9e3c262d0bc48c050cf631d/hetnet/json/hetionet-v1.0-metagraph.json
    """
    import json
    from hetio.readwrite import metagraph_from_writable
    hetionet_metagraph_json = '''
    {
    "metanode_kinds": [
        "Anatomy",
        "Biological Process",
        "Cellular Component",
        "Compound",
        "Disease",
        "Gene",
        "Molecular Function",
        "Pathway",
        "Pharmacologic Class",
        "Side Effect",
        "Symptom"
    ],
    "metaedge_tuples": [
        [
        "Anatomy",
        "Gene",
        "downregulates",
        "both"
        ],
        [
        "Anatomy",
        "Gene",
        "expresses",
        "both"
        ],
        [
        "Anatomy",
        "Gene",
        "upregulates",
        "both"
        ],
        [
        "Compound",
        "Compound",
        "resembles",
        "both"
        ],
        [
        "Compound",
        "Disease",
        "palliates",
        "both"
        ],
        [
        "Compound",
        "Disease",
        "treats",
        "both"
        ],
        [
        "Compound",
        "Gene",
        "binds",
        "both"
        ],
        [
        "Compound",
        "Gene",
        "downregulates",
        "both"
        ],
        [
        "Compound",
        "Gene",
        "upregulates",
        "both"
        ],
        [
        "Compound",
        "Side Effect",
        "causes",
        "both"
        ],
        [
        "Disease",
        "Anatomy",
        "localizes",
        "both"
        ],
        [
        "Disease",
        "Disease",
        "resembles",
        "both"
        ],
        [
        "Disease",
        "Gene",
        "associates",
        "both"
        ],
        [
        "Disease",
        "Gene",
        "downregulates",
        "both"
        ],
        [
        "Disease",
        "Gene",
        "upregulates",
        "both"
        ],
        [
        "Disease",
        "Symptom",
        "presents",
        "both"
        ],
        [
        "Gene",
        "Biological Process",
        "participates",
        "both"
        ],
        [
        "Gene",
        "Cellular Component",
        "participates",
        "both"
        ],
        [
        "Gene",
        "Gene",
        "covaries",
        "both"
        ],
        [
        "Gene",
        "Gene",
        "interacts",
        "both"
        ],
        [
        "Gene",
        "Gene",
        "regulates",
        "forward"
        ],
        [
        "Gene",
        "Molecular Function",
        "participates",
        "both"
        ],
        [
        "Gene",
        "Pathway",
        "participates",
        "both"
        ],
        [
        "Pharmacologic Class",
        "Compound",
        "includes",
        "both"
        ]
    ],
    "kind_to_abbrev": {
        "Biological Process": "BP",
        "Cellular Component": "CC",
        "causes": "c",
        "Pharmacologic Class": "PC",
        "Molecular Function": "MF",
        "palliates": "p",
        "downregulates": "d",
        "expresses": "e",
        "Gene": "G",
        "covaries": "c",
        "upregulates": "u",
        "presents": "p",
        "Anatomy": "A",
        "Symptom": "S",
        "Pathway": "PW",
        "treats": "t",
        "localizes": "l",
        "Disease": "D",
        "participates": "p",
        "binds": "b",
        "includes": "i",
        "associates": "a",
        "Compound": "C",
        "interacts": "i",
        "resembles": "r",
        "regulates": "r",
        "Side Effect": "SE"
    }
    }
    '''
    metagraph = metagraph_from_writable(json.loads(hetionet_metagraph_json))
    return metagraph


@functools.lru_cache(maxsize=10_000)
def metapath_from_abbrev(abbreviation):
    metagraph = get_hetionet_metagraph()
    return metagraph.metapath_from_abbrev(abbreviation)
