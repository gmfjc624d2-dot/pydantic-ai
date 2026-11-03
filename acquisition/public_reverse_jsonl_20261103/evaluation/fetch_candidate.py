"""Download the file_read_backwards 3.2.0 sdist from PyPI, check its SHA-256 and unpack it (standard library only).

Run: python3 -I evaluation/fetch_candidate.py DEST_DIR   (DEST_DIR must not exist yet)

Nothing from the archive is executed or installed. Only regular files and directories with relative paths inside
the archive's single top-level directory are extracted; anything else stops the extraction.
"""

from __future__ import annotations

import hashlib
import io
import sys
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

URL = (
    'https://files.pythonhosted.org/packages/5e/53/804f4321dd72e2953c6d5875e9d07d79415a1f8055d5197b92d6d97da19a/'
    'file_read_backwards-3.2.0.tar.gz'
)
SHA256 = '5478d305ebaeaae8fe3c6585a24dfc3262170224450acc9321398f0d26cdd109'  # PyPI's digest, uploaded 2025-04-21
TOP = 'file_read_backwards-3.2.0'


def main() -> int:
    dest = Path(sys.argv[1])
    dest.mkdir(parents=True, exist_ok=False)
    with urllib.request.urlopen(URL, timeout=60) as response:  # noqa: S310 (fixed https URL)
        data = response.read(1 << 22)
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        print(f'sha256 mismatch: got {digest}, expected {SHA256}')
        return 1
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        members = archive.getmembers()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if member.name.startswith('/') or '..' in parts or not parts or parts[0] != TOP:
                print(f'refusing archive member {member.name!r}')
                return 1
            if not (member.isfile() or member.isdir()):
                print(f'refusing non-regular archive member {member.name!r}')
                return 1
        archive.extractall(dest, members=members)  # noqa: S202 (members checked above)
    print(f'{URL}\nsha256 {digest} verified; unpacked {len(members)} members into {dest / TOP}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
