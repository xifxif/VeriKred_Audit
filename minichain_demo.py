#!/usr/bin/env python3
"""minichain_demo.py - demo mini-blockchain, pohon Merkle, serangan kamus, dan Ed25519 untuk VeriKred.
Ilustrasi konsep (BUKAN blockchain nyata): tanpa konsensus/jaringan. Hasil ditulis ke minichain_results.json.
Format hash blok: SHA-256 dari teks UTF-8 'indeks|previous hash|payload'; genesis memakai previous hash 64 nol."""
import hashlib, json, os
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

H = lambda b: hashlib.sha256(b).digest()
HX = lambda b: hashlib.sha256(b).hexdigest()
PAYLOADS = [
    "ISSUE|cred=A1|issuer=univa|root=ab12|2026-08-20",
    "ISSUE|cred=A2|issuer=univa|root=cd34|2026-08-20",
    "SUSPEND|cred=A1|issuer=univa|2026-09-02",
    "REINSTATE|cred=A1|issuer=univa|2026-09-05",
    "REVOKE|cred=A2|issuer=univa|2026-09-30",
]
GENESIS_PREV = "0" * 64

def block_hash(i, prev, payload): return HX(f"{i}|{prev}|{payload}".encode())

def build_chain(payloads):
    chain, prev = [], GENESIS_PREV
    for i, p in enumerate(payloads):
        h = block_hash(i, prev, p); chain.append({"i": i, "prev": prev, "payload": p, "hash": h}); prev = h
    return chain

def validate(chain):
    """Status per blok: VALID | GAGAL (hash) | GAGAL (tautan)."""
    out = []
    for k, b in enumerate(chain):
        if b["hash"] != block_hash(b["i"], b["prev"], b["payload"]): out.append("GAGAL (hash)")
        elif k > 0 and b["prev"] != chain[k - 1]["hash"]: out.append("GAGAL (tautan)")
        else: out.append("VALID")
    return out

def merkle(payloads):
    lvl = [H(b"\x00" + p.encode()) for p in payloads]; levels = [lvl]
    while len(lvl) > 1:
        lvl = [H(b"\x01" + lvl[i] + (lvl[i + 1] if i + 1 < len(lvl) else lvl[i])) for i in range(0, len(lvl), 2)]
        levels.append(lvl)
    return levels

def main():
    out = {}
    chain = build_chain(PAYLOADS)
    out["rantai"] = [{"record": "R-%02d" % (b["i"] + 1), "blok": b["i"], "prev12": b["prev"][:12], "hash12": b["hash"][:12]} for b in chain]
    out["rantai_asli"] = validate(chain)
    # Uji 1: payload R-03 diubah, hash tidak dihitung ulang
    c1 = [dict(b) for b in chain]; c1[2]["payload"] = "NOOP|cred=A1|issuer=univa|2026-09-02"
    out["uji1_ubah_payload"] = validate(c1)
    # Uji 2: penyerang menghitung ulang hash R-03 saja
    c2 = [dict(b) for b in c1]; c2[2]["hash"] = block_hash(2, c2[2]["prev"], c2[2]["payload"])
    out["uji2_hitung_ulang_R03"] = validate(c2)
    # Merkle
    lv = merkle(PAYLOADS); lv2 = merkle([PAYLOADS[0], PAYLOADS[1], c1[2]["payload"], PAYLOADS[3], PAYLOADS[4]])
    out["merkle"] = {"daun": [x.hex()[:8] for x in lv[0]], "tingkat1": [x.hex()[:8] for x in lv[1]], "tingkat2": [x.hex()[:8] for x in lv[2]],
                     "root": lv[-1][0].hex(), "root_setelah_R03_diubah": lv2[-1][0].hex(), "root_berubah": lv[-1][0] != lv2[-1][0]}
    # Serangan kamus pada hash IPK
    cands = ["3.10", "3.35", "3.50", "3.72", "3.85", "4.00"]
    plain = HX(b"ipk=3.72"); rec_plain = [c for c in cands if HX(("ipk=" + c).encode()) == plain]
    salt = os.urandom(16); salted = HX(b"\x00" + salt + b"ipk=3.72")
    rec_salt = [c for c in cands if HX(("ipk=" + c).encode()) == salted or HX(b"\x00" + ("ipk=" + c).encode()) == salted]
    out["serangan_kamus"] = {"kandidat": len(cands), "tanpa_garam_pulih": rec_plain, "dengan_garam_pulih": rec_salt}
    # Ed25519 (kunci sekali pakai; kunci privat tidak disimpan)
    sk = Ed25519PrivateKey.generate(); pub = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    msg = b"ISSUE|cred=A1|issuer=univa"; sig = sk.sign(msg)
    pk = sk.public_key(); ok = True; bad = False
    try: pk.verify(sig, msg)
    except InvalidSignature: ok = False
    try: pk.verify(sig, b"ISSUE|cred=A9|issuer=univa")
    except InvalidSignature: bad = True
    out["ed25519"] = {"kunci_publik": pub.hex(), "address_40hex(sha256, 20 byte terakhir)": HX(pub)[-40:],
                      "pesan_asli_terverifikasi": ok, "pesan_diubah_ditolak": bad}
    out["lulus"] = (all(s == "VALID" for s in out["rantai_asli"])
                    and out["uji1_ubah_payload"] == ["VALID", "VALID", "GAGAL (hash)", "VALID", "VALID"]
                    and out["uji2_hitung_ulang_R03"] == ["VALID", "VALID", "VALID", "GAGAL (tautan)", "VALID"]
                    and out["merkle"]["root_berubah"] and out["serangan_kamus"]["tanpa_garam_pulih"] == ["3.72"]
                    and out["serangan_kamus"]["dengan_garam_pulih"] == [] and ok and bad)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "minichain_results.json"), "w"), indent=2, ensure_ascii=False)
    for k in ("rantai_asli", "uji1_ubah_payload", "uji2_hitung_ulang_R03"): print(k, out[k])
    print("merkle root", out["merkle"]["root"][:16], "->", out["merkle"]["root_setelah_R03_diubah"][:16])
    print("kamus", out["serangan_kamus"]); print("ed25519", out["ed25519"]["pesan_asli_terverifikasi"], out["ed25519"]["pesan_diubah_ditolak"])
    print("PASS" if out["lulus"] else "FAIL")

if __name__ == "__main__": main()
