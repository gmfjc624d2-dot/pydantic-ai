import sys, os, tempfile, re
cases = [b'', b'\n', b'\r', b'\r\n', b'a', b'a\n', b'\nb', b'a\r\rb', b'a\r\r\nb\n',
         ('x' + chr(0x2028) + 'y').encode('utf-8'),
         ('p' + chr(0x2029) + 'q\x0br\x0cs\x1ct' + chr(0x85) + 'u').encode('utf-8'),
         b'\xe2\x82\nX', b'\xe2\x82\rX', b'\xf0\x9f\x98\r\n', b'\xed\xa0\x80\n', b'\xc0\xaf\n',
         b'\xef\xbb\xbfbom\n', b'\xff\xfe\n', b'a\x00b\r', b'\n\n\r\r\n\r', b'\xe2\x82\xac\r\n\xe2']
ok = True
for data in cases:
    fd, p = tempfile.mkstemp(); os.write(fd, data); os.close(fd)
    with open(p, encoding='utf-8', errors='replace', newline=None) as f:
        forward = list(f)
    os.unlink(p)
    pieces = re.split(rb'(\r\n|\r|\n)', data)
    cand = [pieces[i].decode('utf-8', 'replace') + '\n' for i in range(0, len(pieces) - 1, 2)]
    if pieces[-1]:
        cand.append(pieces[-1].decode('utf-8', 'replace'))
    same = cand == forward
    ok &= same
    print(sys.version.split()[0], 'same' if same else 'DIFF', repr(data), ascii(forward))
print('ALL SAME' if ok else 'SOME DIFFER')
