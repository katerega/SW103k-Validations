#!/usr/bin/env python3
import argparse
import ctypes
import hashlib
import os
import socket
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "bin/libsw103k_codec.so"
DATA = ROOT / "test-data"
ARCHIVES = ROOT / "evidence/two-vps/received"
OUTPUTS = ROOT / "evidence/two-vps/reconstructed"

FILES = [
    "01_repetitive_text.bin",
    "02_mixed_application.bin",
    "03_random_binary.bin",
]

CHUNK = 4096
MAGIC = b"SWR1"
END = b"SWEN"
PERSISTED = b"PERSISTED"
TRIGGER = b"DECOMPRESS"

# Wire header:
# magic, dataset, sequence, original length, compressed length,
# compression type, final-chunk flag, original file SHA256.
HEADER = struct.Struct("!4sIIIIBB32s")


def load_codec():
    if not LIB.exists():
        raise RuntimeError(f"Codec library missing: {LIB}")

    lib = ctypes.CDLL(str(LIB))
    byte_ptr = ctypes.POINTER(ctypes.c_ubyte)

    lib.sw103k_compress.argtypes = [
        byte_ptr,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_ubyte),
    ]
    lib.sw103k_compress.restype = byte_ptr

    lib.decompress_payload.argtypes = [
        byte_ptr,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    lib.decompress_payload.restype = byte_ptr

    libc = ctypes.CDLL(None)
    libc.free.argtypes = [ctypes.c_void_p]
    libc.free.restype = None

    return lib, libc


def compress_chunk(lib, libc, raw):
    source = ctypes.create_string_buffer(raw)
    out_len = ctypes.c_size_t(0)
    proto = ctypes.c_int(0)
    comp_type = ctypes.c_ubyte(0)

    result = lib.sw103k_compress(
        ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)),
        len(raw),
        ctypes.byref(out_len),
        ctypes.byref(proto),
        ctypes.byref(comp_type),
    )

    if not result:
        return raw, 0

    try:
        encoded = ctypes.string_at(result, out_len.value)
    finally:
        libc.free(result)

    if comp_type.value != 3:
        raise RuntimeError(
            f"Unexpected codec type returned: {comp_type.value}"
        )

    if len(encoded) >= len(raw):
        raise RuntimeError("Codec reported compression without size reduction")

    return encoded, 3


def decompress_chunk(lib, libc, encoded, comp_type):
    if comp_type == 0:
        return encoded

    if comp_type != 3:
        raise RuntimeError(f"Unsupported compression type: {comp_type}")

    source = ctypes.create_string_buffer(encoded)
    out_len = ctypes.c_size_t(0)

    result = lib.decompress_payload(
        ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)),
        len(encoded),
        ctypes.byref(out_len),
    )

    if not result:
        raise RuntimeError("SW103K TREE decompression failed")

    try:
        return ctypes.string_at(result, out_len.value)
    finally:
        libc.free(result)


def recv_exact(sock, length):
    chunks = []
    remaining = length

    while remaining:
        part = sock.recv(remaining)
        if not part:
            raise ConnectionError("Peer closed connection unexpectedly")
        chunks.append(part)
        remaining -= len(part)

    return b"".join(chunks)


def sender(host, port):
    lib, libc = load_codec()

    print(f"Connecting to VPS2 {host}:{port}")
    sock = socket.create_connection((host, port), timeout=30)
    sock.settimeout(120)

    total_original = 0
    total_payload = 0
    total_tree = 0
    total_raw = 0

    try:
        for dataset, filename in enumerate(FILES, start=1):
            path = DATA / filename
            raw_file = path.read_bytes()
            digest = hashlib.sha256(raw_file).digest()
            chunks = [
                raw_file[i:i + CHUNK]
                for i in range(0, len(raw_file), CHUNK)
            ]

            print(f"\nDATASET {dataset}: {filename}")
            print(f"Original bytes: {len(raw_file)}")
            print(f"Original SHA256: {digest.hex()}")

            for sequence, raw in enumerate(chunks):
                encoded, comp_type = compress_chunk(lib, libc, raw)
                last = int(sequence == len(chunks) - 1)

                header = HEADER.pack(
                    MAGIC,
                    dataset,
                    sequence,
                    len(raw),
                    len(encoded),
                    comp_type,
                    last,
                    digest,
                )

                sock.sendall(header + encoded)

                total_original += len(raw)
                total_payload += len(encoded)

                if comp_type == 3:
                    total_tree += len(encoded)
                else:
                    total_raw += len(encoded)

            print(f"Chunks sent: {len(chunks)}")

        sock.sendall(END)

        acknowledgement = recv_exact(sock, len(PERSISTED))
        if acknowledgement != PERSISTED:
            raise RuntimeError("Receiver did not acknowledge persistence")

        print("\nVPS2 confirms compressed archives were persisted.")
        print("Sending application-level DECOMPRESS trigger.")

        sock.sendall(TRIGGER)

        result = recv_exact(sock, 2)
        if result != b"OK":
            raise RuntimeError("Receiver reported validation failure")

        print("\nTRANSFER AND REMOTE VALIDATION COMPLETE")
        print(f"Original bytes:       {total_original}")
        print(f"Transmitted payload:  {total_payload}")
        print(f"TREE-compressed:      {total_tree}")
        print(f"RAW fallback:         {total_raw}")

        if total_original:
            saved = 100 * (1 - total_payload / total_original)
            print(f"Payload reduction:    {saved:.2f}%")

    finally:
        sock.close()


def receiver(bind, port):
    lib, libc = load_codec()
    ARCHIVES.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((bind, port))
    server.listen(1)

    print(f"SW103K validation receiver listening on {bind}:{port}")
    conn, address = server.accept()
    conn.settimeout(120)

    print(f"Connected from {address}")

    archive_paths = {
        i: ARCHIVES / f"{i:02d}.sw103k"
        for i in range(1, len(FILES) + 1)
    }

    archive_files = {
        i: open(path, "wb")
        for i, path in archive_paths.items()
    }

    seen = {i: 0 for i in archive_paths}
    finished = set()
    hashes = {}

    try:
        # PHASE 1: receive and persist only. No decompression here.
        while True:
            magic = recv_exact(conn, 4)

            if magic == END:
                break

            if magic != MAGIC:
                raise RuntimeError(f"Invalid record magic: {magic!r}")

            rest = recv_exact(conn, HEADER.size - 4)
            header = magic + rest

            (
                _,
                dataset,
                sequence,
                original_len,
                compressed_len,
                comp_type,
                last,
                digest,
            ) = HEADER.unpack(header)

            if dataset not in archive_files:
                raise RuntimeError(f"Unknown dataset ID: {dataset}")

            if dataset in finished:
                raise RuntimeError("Received data after final chunk")

            if sequence != seen[dataset]:
                raise RuntimeError(
                    f"Sequence error in dataset {dataset}: "
                    f"expected {seen[dataset]}, got {sequence}"
                )

            if original_len == 0 or original_len > CHUNK:
                raise RuntimeError("Invalid original chunk length")

            if compressed_len == 0 or compressed_len > CHUNK:
                raise RuntimeError("Invalid encoded chunk length")

            if comp_type not in (0, 3):
                raise RuntimeError(f"Unknown compression type: {comp_type}")

            payload = recv_exact(conn, compressed_len)

            # Store exact wire record and encoded payload to disk.
            archive_files[dataset].write(header)
            archive_files[dataset].write(payload)

            seen[dataset] += 1
            hashes[dataset] = digest

            if last:
                finished.add(dataset)

        # Force all archive bytes to persistent storage before decoding.
        for f in archive_files.values():
            f.flush()
            os.fsync(f.fileno())
            f.close()

        print("\nPERSISTENCE PHASE COMPLETE")
        stored_total = 0

        for dataset, path in archive_paths.items():
            size = path.stat().st_size
            stored_total += size
            print(f"{path.name}: {size} bytes on disk")

        print(f"Total archive bytes on disk: {stored_total}")
        print("All compressed archives flushed and fsynced.")

        conn.sendall(PERSISTED)

        # Wait for a distinct application-level decompression request.
        trigger = recv_exact(conn, len(TRIGGER))
        if trigger != TRIGGER:
            raise RuntimeError("Invalid application trigger")

        print("\nAPPLICATION DECOMPRESSION TRIGGER RECEIVED")

        # PHASE 2: read persisted archives and reconstruct files.
        for dataset, filename in enumerate(FILES, start=1):
            archive = archive_paths[dataset]
            output = OUTPUTS / filename

            reconstructed = 0
            expected_sequence = 0
            last_seen = False
            digest = None

            with open(archive, "rb") as source, open(output, "wb") as target:
                while True:
                    magic = source.read(4)
                    if not magic:
                        break

                    if len(magic) != 4 or magic != MAGIC:
                        raise RuntimeError("Corrupt archive record")

                    rest = source.read(HEADER.size - 4)
                    if len(rest) != HEADER.size - 4:
                        raise RuntimeError("Truncated archive header")

                    header = magic + rest
                    (
                        _,
                        record_dataset,
                        sequence,
                        original_len,
                        compressed_len,
                        comp_type,
                        last,
                        record_digest,
                    ) = HEADER.unpack(header)

                    if record_dataset != dataset:
                        raise RuntimeError("Dataset ID mismatch")

                    if sequence != expected_sequence:
                        raise RuntimeError("Persisted sequence mismatch")

                    payload = source.read(compressed_len)
                    if len(payload) != compressed_len:
                        raise RuntimeError("Truncated persisted payload")

                    restored = decompress_chunk(lib, libc, payload, comp_type)

                    if len(restored) != original_len:
                        raise RuntimeError("Reconstructed chunk length mismatch")

                    target.write(restored)
                    reconstructed += len(restored)
                    expected_sequence += 1
                    digest = record_digest

                    if last:
                        last_seen = True

            actual_hash = hashlib.sha256(output.read_bytes()).digest()

            if not last_seen:
                raise RuntimeError(f"Missing final chunk: {filename}")

            if actual_hash != hashes[dataset]:
                raise RuntimeError(f"SHA256 mismatch: {filename}")

            if digest != hashes[dataset]:
                raise RuntimeError(f"Archive digest mismatch: {filename}")

            print(f"\nPASS: {filename}")
            print(f"Reconstructed bytes: {reconstructed}")
            print(f"SHA256: {actual_hash.hex()}")

        print("\nALL THREE DATASETS PASSED SHA256 VERIFICATION")
        conn.sendall(b"OK")

    except Exception as exc:
        print(f"\nVALIDATION FAILED: {exc}", file=sys.stderr)
        try:
            conn.sendall(b"NO")
        except OSError:
            pass
        raise

    finally:
        for f in archive_files.values():
            if not f.closed:
                f.close()
        conn.close()
        server.close()


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    rx = sub.add_parser("receive")
    rx.add_argument("--bind", default="0.0.0.0")
    rx.add_argument("--port", type=int, default=10300)

    tx = sub.add_parser("send")
    tx.add_argument("--host", required=True)
    tx.add_argument("--port", type=int, default=10300)

    args = parser.parse_args()

    if args.mode == "receive":
        receiver(args.bind, args.port)
    else:
        sender(args.host, args.port)


if __name__ == "__main__":
    main()
