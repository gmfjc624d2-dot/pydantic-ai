"""Run each REGRESSIONS pair through the CLI of the module in a fresh directory holding only it and LICENSE."""
import hashlib, json, platform, shutil, subprocess, sys, tempfile
from pathlib import Path
module_dir, fixtures = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(fixtures))
import cases
print(f'## Python {platform.python_version()}; module sha256 {hashlib.sha256((module_dir / "export_compare.py").read_bytes()).hexdigest()}')
for name, pair in cases.REGRESSIONS.items():
    with tempfile.TemporaryDirectory() as tmp:
        for f in ('export_compare.py', 'LICENSE'):
            shutil.copy(module_dir / f, tmp)
        Path(tmp, 'plain.txt').write_bytes(pair['plain'])
        Path(tmp, 'markdown.md').write_bytes(pair['markdown'])
        proc = subprocess.run([sys.executable, '-I', 'export_compare.py', '--plain', 'plain.txt', '--markdown', 'markdown.md'],
                              cwd=tmp, capture_output=True, timeout=60)
        r = json.loads(proc.stdout)
        res, counts = r['results'], r['normalization']['counts']
        bodies = {s: [(g['byte_start'], g['byte_end'], g['sha256'][:12]) for g in r['layouts'][s]['segments'] if g['name'] == 'body'] for s in ('plain', 'markdown')}
        print(f"{name}: version={r['tool']['version']} rc={proc.returncode} (1.0.1 expects {pair['expect']['exit']}) "
              f"raw_bodies_equal={res['raw_bodies_equal']} normalized_bodies_equal={res['normalized_bodies_equal']} "
              f"table_separator_rows={counts['plain']['table_separator_rows']}/{counts['markdown']['table_separator_rows']} "
              f"cited_ids={[e['id'] for e in res['citations']['url_map']]} body_segments={bodies} "
              f"inputs_sha256={hashlib.sha256(pair['plain']).hexdigest()[:12]}/{hashlib.sha256(pair['markdown']).hexdigest()[:12]} stderr_bytes={len(proc.stderr)}")
