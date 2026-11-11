"""Strict standalone family-orbit CLI, no adapter execution."""
import argparse
import json
import re
import sys
from .core import EvalForgeError
from .family import family_report


def loads(text):
    if len(text.encode('utf8')) > 131072:
        raise EvalForgeError('input exceeds 128 KiB')
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d:
                raise EvalForgeError('duplicate JSON key')
            d[k] = v
        return d
    def integer(token):
        if re.fullmatch('0|[1-9][0-9]*', token) is None:
            raise EvalForgeError('nonnegative integer JSON numeric tokens only')
        return int(token)
    def bad(_):
        raise EvalForgeError('decimal, exponent and nonfinite numeric tokens rejected')
    r = json.loads(text, object_pairs_hook=pairs, parse_int=integer, parse_float=bad, parse_constant=bad)
    def depth(x, k=0):
        if k > 8:
            raise EvalForgeError('nesting exceeds 8')
        if isinstance(x, dict):
            for v in x.values():depth(v, k+1)
        elif isinstance(x, list):
            for v in x:depth(v, k+1)
    depth(r)
    return r


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    args = p.parse_args(argv)
    try:
        if args.input == '-':text = sys.stdin.read(131073)
        else:
            with open(args.input, encoding='utf8') as f:text = f.read(131073)
        r = family_report(loads(text))
        print(json.dumps(r, allow_nan=False, separators=(',', ':')))
    except (EvalForgeError, ValueError, TypeError, OSError, KeyError, RecursionError, OverflowError) as e:
        print('family error: '+str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
