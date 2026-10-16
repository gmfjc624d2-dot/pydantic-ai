"""Bring up the loopback interface inside a fresh network namespace (no `ip` binary needed)."""

import fcntl
import socket
import struct

SIOCGIFFLAGS = 0x8913
SIOCSIFFLAGS = 0x8914
IFF_UP = 0x1

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    ifreq = struct.pack('16sh', b'lo', 0)
    flags = struct.unpack('16sh', fcntl.ioctl(s, SIOCGIFFLAGS, ifreq))[1]
    fcntl.ioctl(s, SIOCSIFFLAGS, struct.pack('16sh', b'lo', flags | IFF_UP))
