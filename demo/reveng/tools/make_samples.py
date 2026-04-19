#!/usr/bin/env python3
"""make_samples.py – (re)generate all synthetic demo pcap files.

Each synthetic capture is a tiny hand-crafted binary file that contains
exactly the packets described in the corresponding expected.txt.  These
files are committed to the repository so the demo works out of the box
without any external downloads.

Usage:
    python tools/make_samples.py [--output-dir <demo/reveng dir>]

The script is idempotent: running it again overwrites the existing
sample.pcap files with identical content.
"""

import argparse
import struct
from pathlib import Path


# ---------------------------------------------------------------------------
# PCAP helpers (no third-party libraries required)
# ---------------------------------------------------------------------------

PCAP_MAGIC = 0xA1B2C3D4
PCAP_VERSION_MAJOR = 2
PCAP_VERSION_MINOR = 4
DLT_USER0 = 147  # "Private use" link type used for all demo frames


def pcap_global_header(link_type: int = DLT_USER0) -> bytes:
    """Return a 24-byte libpcap global header."""
    return struct.pack(
        "<IHHiIII",
        PCAP_MAGIC,
        PCAP_VERSION_MAJOR,
        PCAP_VERSION_MINOR,
        0,       # thiszone (UTC)
        0,       # sigfigs
        65535,   # snaplen
        link_type,
    )


def pcap_packet_record(ts_sec: int, data: bytes) -> bytes:
    """Return a pcap packet record (header + data)."""
    length = len(data)
    return struct.pack("<IIII", ts_sec, 0, length, length) + data


def write_pcap(path: Path, packets: list[bytes]) -> None:
    """Write a complete pcap file with DLT_USER0 link type."""
    with path.open("wb") as fh:
        fh.write(pcap_global_header())
        for i, pkt in enumerate(packets):
            fh.write(pcap_packet_record(i + 1, pkt))
    print(f"  written {path}  ({path.stat().st_size} bytes, {len(packets)} packet(s))")


# ---------------------------------------------------------------------------
# Case 1: ip_scoped
# Frame layout (11 bytes, big-endian):
#   version[1]  src_ip[4]  dst_ip[4]  payload_size[2]
# ---------------------------------------------------------------------------

def make_ip_scoped(out_dir: Path) -> None:
    """
    5 packets covering every combination of scope (LAN / NAT / inet):
      #1  src=192.168.1.1  dst=8.8.8.8      (LAN  -> inet)
      #2  src=100.64.0.1   dst=8.8.8.8      (NAT  -> inet)
      #3  src=8.8.8.8      dst=192.168.1.1  (inet -> LAN)
      #4  src=192.168.1.1  dst=10.0.0.1     (LAN  -> LAN)
      #5  src=8.8.8.8      dst=100.64.0.1   (inet -> NAT)
    """
    VERSION = 1
    packets = [
        struct.pack(">B II H", VERSION, 0xC0A80101, 0x08080808, 64),  # LAN->inet
        struct.pack(">B II H", VERSION, 0x64400001, 0x08080808, 64),  # NAT->inet
        struct.pack(">B II H", VERSION, 0x08080808, 0xC0A80101, 64),  # inet->LAN
        struct.pack(">B II H", VERSION, 0xC0A80101, 0x0A000001, 64),  # LAN->LAN
        struct.pack(">B II H", VERSION, 0x08080808, 0x64400001, 64),  # inet->NAT
    ]
    write_pcap(out_dir / "ip_scoped" / "sample.pcap", packets)


# ---------------------------------------------------------------------------
# Case 2: session_id  (meta.id: session_demo)
# Frame layout (10 bytes, big-endian):
#   src_ip[4]  dst_ip[4]  service_port[2]
# ---------------------------------------------------------------------------

def make_session_id(out_dir: Path) -> None:
    """
    4 packets forming two bidirectional flows:
      #1  src=192.168.1.1  dst=192.168.1.2  port=1234  (A -> B)
      #2  src=192.168.1.2  dst=192.168.1.1  port=1234  (B -> A)  ← same session
      #3  src=10.0.0.1     dst=10.0.0.2     port=80    (C -> D)
      #4  src=10.0.0.2     dst=10.0.0.1     port=80    (D -> C)  ← same session
    session_key = src_ip XOR dst_ip   (identical for both directions)
    """
    packets = [
        struct.pack(">II H", 0xC0A80101, 0xC0A80102, 1234),  # A->B
        struct.pack(">II H", 0xC0A80102, 0xC0A80101, 1234),  # B->A
        struct.pack(">II H", 0x0A000001, 0x0A000002, 80),    # C->D
        struct.pack(">II H", 0x0A000002, 0x0A000001, 80),    # D->C
    ]
    write_pcap(out_dir / "session_id" / "sample.pcap", packets)


# ---------------------------------------------------------------------------
# Case 3: tls_weak_cipher
# Frame layout (5 bytes, big-endian):
#   handshake_type[1]  tls_version[2]  cipher_suite[2]
# ---------------------------------------------------------------------------

def make_tls_weak_cipher(out_dir: Path) -> None:
    """
    2 packets:
      #1  type=0x01  version=0x0303  cipher=0x0005  (TLS 1.2, RC4-SHA → WEAK)
      #2  type=0x01  version=0x0303  cipher=0x002F  (TLS 1.2, AES-128-CBC-SHA → OK)
    """
    CLIENTHELLO = 0x01
    TLS12 = 0x0303
    WEAK_RC4_SHA = 0x0005
    SAFE_AES_CBC = 0x002F
    packets = [
        struct.pack(">B H H", CLIENTHELLO, TLS12, WEAK_RC4_SHA),
        struct.pack(">B H H", CLIENTHELLO, TLS12, SAFE_AES_CBC),
    ]
    write_pcap(out_dir / "tls_weak_cipher" / "sample.pcap", packets)


# ---------------------------------------------------------------------------
# Case 4: tls_sni_analysis
# Frame layout (36 bytes, big-endian):
#   handshake_type[1]  tls_version[2]  sni_length[1]  sni_name[32, null-padded]
# ---------------------------------------------------------------------------

def make_tls_sni_analysis(out_dir: Path) -> None:
    """
    3 packets with different SNI lengths:
      #1  sni_length=14  sni_name="cloudflare.com"   → Medium  (>10, ≤20)
      #2  sni_length=11  sni_name="netflix.com"       → Medium
            #3  sni_length=39  sni_name=<random 32-char>    → Long/Anomaly (>20)
    """
    CLIENTHELLO = 0x01
    TLS12 = 0x0303

    def frame(sni: str, sni_length_override: int | None = None) -> bytes:
        encoded = sni.encode("ascii")
        padded = encoded[:32].ljust(32, b"\x00")
        length = sni_length_override if sni_length_override is not None else len(sni)
        return struct.pack(">B H B", CLIENTHELLO, TLS12, length) + padded

    # Long anomalous SNI: sni_length=39 (> 20 → Long/Anomaly) while the
    # fixed 32-byte field stores the truncated name.  The mismatch is
    # intentional and demonstrates the anomaly-detection use-case.
    long_sni = "axmzxmzkzqwpqwpqwpq-anomaly.exam"  # 32 chars stored in field
    long_sni_claimed_length = 39  # reported length > field size → anomaly

    packets = [
        frame("cloudflare.com"),            # 14 chars – Medium
        frame("netflix.com"),               # 11 chars – Medium
        frame(long_sni, long_sni_claimed_length),  # 39 claimed – Long/Anomaly
    ]
    write_pcap(out_dir / "tls_sni_analysis" / "sample.pcap", packets)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate synthetic demo pcap files for demo/reveng."
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Root directory that contains the case sub-folders "
            "(default: parent of this script's directory, i.e. demo/reveng/)."
        ),
    )
    args = parser.parse_args()

    if args.output_dir:
        out_dir = Path(args.output_dir).resolve()
    else:
        # tools/make_samples.py → tools/ → demo/reveng/
        out_dir = Path(__file__).resolve().parent.parent

    print(f"Output directory: {out_dir}")
    print()

    make_ip_scoped(out_dir)
    make_session_id(out_dir)
    make_tls_weak_cipher(out_dir)
    make_tls_sni_analysis(out_dir)

    print()
    print("All synthetic sample.pcap files regenerated successfully.")


if __name__ == "__main__":
    main()
