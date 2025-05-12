import fnmatch

_subs: dict[str, list] = {}


def on(topic_pat, fn):
    _subs.setdefault(topic_pat, []).append(fn)


def emit(topic, payload, session=None):
    for pat, fns in _subs.items():
        if fnmatch.fnmatch(topic, pat):
            for fn in fns:
                fn(topic, payload, session)
