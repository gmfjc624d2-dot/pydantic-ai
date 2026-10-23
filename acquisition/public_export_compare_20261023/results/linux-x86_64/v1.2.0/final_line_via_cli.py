"""Public bracketed_html fixtures with suffixes appended to the Markdown, through a module's CLI in fresh directories."""
import hashlib, json, platform, shutil, subprocess, sys, tempfile
from pathlib import Path
module_dir, fixtures = Path(sys.argv[1]), Path(sys.argv[2])
plain = (fixtures / 'bracketed_html_plain.txt').read_bytes()
markdown = (fixtures / 'bracketed_html_markdown.md').read_bytes()
question = (fixtures / 'bracketed_html_question.txt').read_bytes()
print(f'## Python {platform.python_version()}; module sha256 {hashlib.sha256((module_dir / "export_compare.py").read_bytes()).hexdigest()}')
for suffix in (b'', b'\n', b'\n\n', b' \n', b'\t\n', b'\nEnd.\n'):
    with tempfile.TemporaryDirectory() as tmp:
        for f in ('export_compare.py', 'LICENSE'):
            shutil.copy(module_dir / f, tmp)
        Path(tmp, 'plain.txt').write_bytes(plain)
        Path(tmp, 'markdown.md').write_bytes(markdown + suffix)
        Path(tmp, 'question.txt').write_bytes(question)
        proc = subprocess.run([sys.executable, '-I', 'export_compare.py', '--layout', 'bracketed-html', '--plain', 'plain.txt',
                               '--markdown', 'markdown.md', '--question-file', 'question.txt', '--markdown-body-start', '7',
                               '--request-id', 'public-layout-2'], cwd=tmp, capture_output=True, timeout=60)
        r = json.loads(proc.stdout)
        head = f'suffix {suffix!r}: markdown sha256 {hashlib.sha256(markdown + suffix).hexdigest()[:12]} rc={proc.returncode} stderr_bytes={len(proc.stderr)}'
        if 'error' in r:
            print(f'{head} REJECTED {r["error"]["code"]}: {r["error"]["message"]}')
            continue
        x, c, o = r['results'], r['results']['citations'], r['results']['request_id']['occurrences']
        tail = [(s['name'], s['first_line'], s['last_line'], s['byte_start'], s['byte_end']) for s in r['layouts']['markdown']['segments'][-2:]]
        print(f'{head} version={r["tool"]["version"]} raw={x["raw_bodies_equal"]} normalized={x["normalized_bodies_equal"]} '
              f'cited={[e["id"] for e in c["url_map"]]} entries={[(e["id"], e["equal"]) for e in c["entries_url_map"]]} hidden={c["hidden_markers"]["ids"]} '
              f'ids(plain body, md question, md body, md document)=({o["plain_body"]}, {o["markdown_question"]}, {o["markdown_body"]}, {o["markdown_document"]}) '
              f'{x["semantic_judgment"]}/{x["producer_authenticity"]} last_segments={tail}')
