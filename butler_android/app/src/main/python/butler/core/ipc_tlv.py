import struct
import socket
import logging

logger = logging.getLogger("IPC_TLV")

class TLVFrame:
    """
    Type-Length-Value (TLV) frame for high-performance IPC.
    Structure: [Type: 1B] [Length: 4B, Big-Endian] [Value: NB]
    """
    HEADER_FORMAT = "!BI" # Big-endian, 1 byte Unsigned Char, 4 bytes Unsigned Int
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self, t: int, v: bytes):
        self.t = t
        self.v = v

    @classmethod
    def from_bytes(cls, data: bytes):
        if len(data) < cls.HEADER_SIZE:
            return None
        t, l = struct.unpack(cls.HEADER_FORMAT, data[:cls.HEADER_SIZE])
        v = data[cls.HEADER_SIZE : cls.HEADER_SIZE + l]
        return cls(t, v)

    def to_bytes(self) -> bytes:
        l = len(self.v)
        header = struct.pack(self.HEADER_FORMAT, self.t, l)
        return header + self.v

def send_tlv(sock: socket.socket, t: int, v: bytes):
    """Sends a TLV frame over a socket."""
    frame = TLVFrame(t, v)
    sock.sendall(frame.to_bytes())

def recv_tlv(sock: socket.socket) -> (int, bytes):
    """Receives a TLV frame from a socket."""
    header_data = _recv_all(sock, TLVFrame.HEADER_SIZE)
    if not header_data:
        return None, None

    t, l = struct.unpack(TLVFrame.HEADER_FORMAT, header_data)
    value_data = _recv_all(sock, l)
    return t, value_data

def _recv_all(sock: socket.socket, n: int) -> bytes:
    """Helper to receive exactly n bytes."""
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return bytes(data)
