
def timed(func):
    """
    Decorator to print the execution time of a function. Partially based on
    https://gist.github.com/bradmontgomery/bd6288f09a24c06746bbe54afe4b8a82
    """
    import datetime
    import functools
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
