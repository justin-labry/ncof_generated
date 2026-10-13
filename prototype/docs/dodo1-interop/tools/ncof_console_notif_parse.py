"""NCOF 콘솔 로그(pydantic repr 덤프)를 통지 블록 단위로 JSON lines 로 바꾼다 — eval 없이 ast.parse.
No eval: uses ast.parse and a literal walker that maps Call nodes to dicts.
Usage: python3 -I ncof_console_notif_parse.py <log> [<log> ...]  -> writes JSON lines to stdout
Each record: {file, hdr_line, ts, src, items:[...]}
"""
import ast, json, re, sys

ANSI = re.compile(r'\x1b\[[0-9;]*m')
HDR = re.compile(r'^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+)\] \[INFO\] \[[\w.]+\] - \[(\w+)\] --- \[NOTIFICATION\] ---> \[NCOF\]')
TAIL = re.compile(r'\s*\[[\w_]+\.py:\d+\]\s*$')


def conv(n):
    if isinstance(n, ast.Constant):
        return n.value
    if isinstance(n, ast.List) or isinstance(n, ast.Tuple):
        return [conv(e) for e in n.elts]
    if isinstance(n, ast.Dict):
        return {conv(k): conv(v) for k, v in zip(n.keys, n.values)}
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
        return -conv(n.operand)
    if isinstance(n, ast.Call):
        fn = n.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, 'id', '?')
        d = {'__t': name}
        if n.args:
            d['__args'] = [conv(a) for a in n.args]
        for kw in n.keywords:
            d[kw.arg] = conv(kw.value)
        return d
    if isinstance(n, ast.Name):
        return {'__name': n.id}
    if isinstance(n, ast.Attribute):
        return {'__attr': n.attr}
    raise ValueError('unsupported node %r' % type(n))


def blocks(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = [ANSI.sub('', l.rstrip('\n')) for l in f]
    i = 0
    n = len(lines)
    while i < n:
        m = HDR.match(lines[i])
        if not m:
            i += 1
            continue
        hdr = i + 1
        ts, src = m.group(1), m.group(2)
        # next line: "[ts] [INFO] [...] - " then repr starts on following line
        j = i + 1
        body = []
        # skip the "- " line
        j += 1
        ok = False
        while j < n:
            l = lines[j]
            if TAIL.search(l) and l.strip().startswith(')'):
                body.append(TAIL.sub('', l))
                ok = True
                break
            if HDR.match(l):
                break
            body.append(l)
            j += 1
        rec = {'file': path.rsplit('/', 1)[-1], 'hdr_line': hdr, 'ts': ts, 'src': src}
        if ok:
            txt = '\n'.join(body)
            try:
                rec['obj'] = conv(ast.parse(txt, mode='eval').body)
            except Exception as e:
                rec['err'] = 'parse: %s' % e
        else:
            rec['err'] = 'unterminated'
        yield rec
        i = j + 1 if ok else j


if __name__ == '__main__':
    for p in sys.argv[1:]:
        for r in blocks(p):
            sys.stdout.write(json.dumps(r, ensure_ascii=False) + '\n')
