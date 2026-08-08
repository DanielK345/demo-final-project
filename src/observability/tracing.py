from contextlib import contextmanager


@contextmanager
def trace_span(name: str):
    _ = name
    yield
