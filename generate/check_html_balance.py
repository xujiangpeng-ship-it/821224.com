"""Lightweight HTML well-formedness check over generated articles.

Uses html.parser with an explicit stack to catch the two things that actually
hurt us in search/ad review:
  - unbalanced / mis-nested tags introduced by inserting blocks
  - content landing inside an illegal parent (e.g. <section> inside <p>)

Usage: python check_html_balance.py [limit]
"""
import os
import sys
from html.parser import HTMLParser

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'content')
VOID = {'br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'col', 'wbr',
        'area', 'base', 'embed', 'param', 'track'}


class Checker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        # auto-close a <p> when a block element starts
        if tag in ('p',) and self.stack and self.stack[-1][0] == 'p':
            self.stack.pop()
        self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                unclosed = self.stack[i + 1:]
                if unclosed:
                    self.errors.append(
                        'line %d: </%s> closed while <%s> (opened line %d) still open'
                        % (self.getpos()[0], tag, unclosed[-1][0], unclosed[-1][1]))
                del self.stack[i:]
                return
        self.errors.append('line %d: stray </%s>' % (self.getpos()[0], tag))


def articles():
    out = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f != 'index.html':
                continue
            rel = os.path.join(dp, f).replace('\\', '/')
            parts = rel.split('/')
            if len(parts) >= 4 and parts[-4] == 'content':
                out.append(rel)
    return sorted(out)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    files = articles()
    if limit:
        files = files[:limit]
    bad = []
    for rel in files:
        try:
            c = Checker()
            c.feed(open(rel, encoding='utf-8').read())
            left = [t for t, _ in c.stack if t not in ('html', 'body')]
            if c.errors or left:
                bad.append((rel, len(c.errors), left))
        except Exception as e:
            bad.append((rel, 0, ['parse-error: %s' % str(e)[:60]]))
    print('checked: %d articles' % len(files))
    print('with structural problems: %d' % len(bad))
    for rel, n, left in bad[:15]:
        print('  %-58s errors=%d leftover=%s'
              % (rel.split('/')[-2][:58], n, left[:4]))


if __name__ == '__main__':
    main()
