#!/usr/bin/env python3
import hashlib, json, os, statistics, time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

# ---------------------------------------------------------------- util kripto
def h(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

def pub_bytes(sk: Ed25519PrivateKey) -> bytes:
    return sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

def leaf(key: str, value: str, salt: bytes) -> bytes:
    return h(b"\x00" + salt + key.encode() + b"=" + value.encode())

def node(a: bytes, b: bytes) -> bytes:
    return h(b"\x01" + a + b)

def merkle_levels(leaves):
    levels = [leaves]
    while len(levels[-1]) > 1:
        cur, nxt = levels[-1], []
        for i in range(0, len(cur), 2):
            nxt.append(node(cur[i], cur[i + 1] if i + 1 < len(cur) else cur[i]))
        levels.append(nxt)
    return levels

def merkle_proof(levels, idx):
    proof = []
    for lvl in levels[:-1]:
        sib = idx ^ 1
        proof.append((lvl[sib] if sib < len(lvl) else lvl[idx], sib < idx))
        idx //= 2
    return proof

def verify_proof(leaf_hash, proof, root):
    cur = leaf_hash
    for sib, sib_is_left in proof:
        cur = node(sib, cur) if sib_is_left else node(cur, sib)
    return cur == root

# ------------------------------------------------ registry (cermin kontrak)
class Reject(Exception):
    pass

NONE, ACTIVE, SUSPENDED, REVOKED, SUPERSEDED = "NONE", "ACTIVE", "SUSPENDED", "REVOKED", "SUPERSEDED"

class Registry:
    def __init__(self, admins, quorum=2):
        self.admins, self.quorum = set(admins), quorum
        self.issuers = {}      # issuerId -> {"keys":[{pub, from, compromised_from}], "active":bool}
        self.creds = {}        # credId -> dict
        self.events = []       # log on-chain (tanpa PII)

    def _gov(self, approvers):
        if len(set(approvers) & self.admins) < self.quorum:
            raise Reject("kuorum multisig tidak terpenuhi")

    def register_issuer(self, issuer_id, pub, now, approvers):
        self._gov(approvers)
        self.issuers[issuer_id] = {"keys": [{"pub": pub, "from": now, "compromised_from": None}], "active": True}
        self.events.append(("IssuerSet", issuer_id))

    def rotate_issuer_key(self, issuer_id, new_pub, now, approvers):
        self._gov(approvers)
        self.issuers[issuer_id]["keys"].append({"pub": new_pub, "from": now, "compromised_from": None})
        self.events.append(("IssuerKeyRotated", issuer_id))

    def mark_key_compromised(self, issuer_id, key_index, from_time, approvers):
        self._gov(approvers)
        self.issuers[issuer_id]["keys"][key_index]["compromised_from"] = from_time
        self.events.append(("IssuerKeyCompromised", issuer_id, from_time))

    def _own(self, caller, cred_id):
        c = self.creds.get(cred_id)
        if not c:
            raise Reject("kredensial tidak ada")
        if c["issuer"] != caller:
            raise Reject("bukan penerbit kredensial ini")
        return c

    def issue(self, caller, cred_id, root, holder_binding, key_index, now, expiry=0):
        if caller not in self.issuers or not self.issuers[caller]["active"]:
            raise Reject("bukan penerbit terdaftar")
        if cred_id in self.creds:
            raise Reject("credId sudah dipakai (tidak boleh ditimpa)")
        self.creds[cred_id] = dict(issuer=caller, root=root, binding=holder_binding, issued_at=now,
                                   expiry=expiry, status=ACTIVE, key_index=key_index)
        self.events.append(("Issued", cred_id.hex()[:8], caller))

    def suspend(self, caller, cred_id):
        c = self._own(caller, cred_id)
        if c["status"] != ACTIVE: raise Reject("transisi tidak valid")
        c["status"] = SUSPENDED; self.events.append(("StatusChanged", SUSPENDED))

    def reinstate(self, caller, cred_id):
        c = self._own(caller, cred_id)
        if c["status"] != SUSPENDED: raise Reject("transisi tidak valid")
        c["status"] = ACTIVE; self.events.append(("StatusChanged", ACTIVE))

    def revoke(self, caller, cred_id):
        c = self._own(caller, cred_id)
        if c["status"] not in (ACTIVE, SUSPENDED): raise Reject("transisi tidak valid (REVOKED/SUPERSEDED final)")
        c["status"] = REVOKED; self.events.append(("StatusChanged", REVOKED))

    def supersede(self, caller, old_id, new_id, root, holder_binding, key_index, now, expiry=0):
        c = self._own(caller, old_id)
        if c["status"] not in (ACTIVE, SUSPENDED): raise Reject("transisi tidak valid")
        self.issue(caller, new_id, root, holder_binding, key_index, now, expiry)
        c["status"] = SUPERSEDED; self.events.append(("StatusChanged", SUPERSEDED))

    def rebind(self, caller, cred_id, new_binding, approvers):
        c = self._own(caller, cred_id)
        if len(set(approvers)) < 2: raise Reject("rebind wajib maker-checker (2 petugas)")
        if c["status"] != ACTIVE: raise Reject("transisi tidak valid")
        c["binding"] = new_binding; self.events.append(("HolderRebound", cred_id.hex()[:8]))

    def lookup(self, cred_id):
        c = self.creds.get(cred_id)
        return None if c is None else dict(c)

# ------------------------------------------------------------ penerbit/holder
class Issuer:
    def __init__(self, name):
        self.name, self.sk = name, Ed25519PrivateKey.generate()
    def pub(self): return pub_bytes(self.sk)

def build_credential(issuer, cred_id, attrs, holder_pub, expiry=0, key_index=0):
    keys = sorted(attrs)
    salts = {k: os.urandom(16) for k in keys}
    leaves = [leaf(k, str(attrs[k]), salts[k]) for k in keys]
    levels = merkle_levels(leaves)
    root = levels[-1][0]
    body = {"id": cred_id.hex(), "issuer": issuer.name, "root": root.hex(), "keys": keys, "expiry": expiry,
            "holderBinding": h(holder_pub).hex(), "keyIndex": key_index}
    vc = {"body": body, "sig": issuer.sk.sign(canon(body)).hex()}
    secret = {"attrs": attrs, "salts": salts, "levels": levels, "keys": keys}
    return vc, secret, root

def present(vc, secret, holder_sk, disclose, nonce, audience):
    disclosed = []
    for k in disclose:
        i = secret["keys"].index(k)
        disclosed.append({"key": k, "value": str(secret["attrs"][k]), "salt": secret["salts"][k].hex(),
                          "proof": [(s.hex(), left) for s, left in merkle_proof(secret["levels"], i)], "idx": i})
    msg = canon({"vc": vc["body"]["id"], "nonce": nonce, "aud": audience, "keys": sorted(disclose)})
    return {"vc": vc, "disclosed": disclosed, "nonce": nonce, "aud": audience, "holderPub": pub_bytes(holder_sk).hex(),
            "holderSig": holder_sk.sign(msg).hex()}

class Verifier:
    def __init__(self, name, registry):
        self.name, self.reg, self.nonces = name, registry, set()
    def challenge(self):
        n = os.urandom(12).hex(); self.nonces.add(n); return n
    def verify(self, pres, now):
        why = []
        vc, body = pres["vc"], pres["vc"]["body"]
        issuer = self.reg.issuers.get(body["issuer"])
        cred_id = bytes.fromhex(body["id"])
        rec = self.reg.lookup(cred_id)
        if not issuer or not issuer["active"]: why.append("PENERBIT_TIDAK_TERDAFTAR")
        else:
            key = issuer["keys"][body["keyIndex"]] if body["keyIndex"] < len(issuer["keys"]) else None
            if key is None: why.append("KUNCI_PENERBIT_TIDAK_DIKENAL")
            else:
                try: Ed25519PublicKey.from_public_bytes(key["pub"]).verify(bytes.fromhex(vc["sig"]), canon(body))
                except InvalidSignature: why.append("TANDA_TANGAN_PENERBIT_TIDAK_VALID")
        if rec is None: why.append("TIDAK_ADA_JANGKAR_ON_CHAIN")
        else:
            if rec["root"].hex() != body["root"]: why.append("ROOT_TIDAK_COCOK_DENGAN_JANGKAR")
            if rec["status"] != ACTIVE: why.append("STATUS_" + rec["status"])
            if rec["expiry"] and now > rec["expiry"]: why.append("KEDALUWARSA")
            if issuer:
                kk = issuer["keys"][rec["key_index"]] if rec["key_index"] < len(issuer["keys"]) else None
                if kk and kk["compromised_from"] is not None and rec["issued_at"] >= kk["compromised_from"]:
                    why.append("DITERBITKAN_SETELAH_KUNCI_PENERBIT_BOCOR")
            hp = bytes.fromhex(pres["holderPub"])
            if h(hp) != rec["binding"]: why.append("KUNCI_HOLDER_TIDAK_TERIKAT")
        if pres["nonce"] not in self.nonces: why.append("NONCE_TIDAK_VALID_ATAU_SUDAH_DIPAKAI")
        else: self.nonces.discard(pres["nonce"])
        if pres["aud"] != self.name: why.append("AUDIENCE_SALAH")
        try:
            msg = canon({"vc": body["id"], "nonce": pres["nonce"], "aud": pres["aud"],
                         "keys": sorted(d["key"] for d in pres["disclosed"])})
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(pres["holderPub"])).verify(bytes.fromhex(pres["holderSig"]), msg)
        except InvalidSignature: why.append("BUKTI_KEPEMILIKAN_HOLDER_GAGAL")
        for d in pres["disclosed"]:
            lh = leaf(d["key"], d["value"], bytes.fromhex(d["salt"]))
            if not verify_proof(lh, [(bytes.fromhex(s), l) for s, l in d["proof"]], bytes.fromhex(body["root"])):
                why.append("BUKTI_MERKLE_GAGAL:" + d["key"])
        return (len(why) == 0), why

# ----------------------------------------------------------------- harness uji
RESULTS = []
def case(cid, kategori, deskripsi, fn):
    try:
        ok, detail = fn()
    except Exception as e:  # kegagalan tak terduga = FAIL
        ok, detail = False, "EXCEPTION: %r" % e
    RESULTS.append({"id": cid, "kategori": kategori, "deskripsi": deskripsi, "hasil": "PASS" if ok else "FAIL", "detail": detail})

ATTRS = {"nama": "Siti Rahma", "nim": "207006001", "program_studi": "S1 Informatika", "gelar": "S.Kom.",
         "tanggal_lulus": "2026-08-20", "ipk": "3.72", "nomor_ijazah": "IJZ-2026-000123"}
T0 = 1_800_000_000

def setup():
    reg = Registry(admins={"rektor", "wr1", "kauptik"})
    univ = Issuer("univ-a")
    reg.register_issuer("univ-a", univ.pub(), T0, ["rektor", "wr1"])
    holder = Ed25519PrivateKey.generate()
    return reg, univ, holder, Verifier("hrd-pt-x", reg)

def issue_std(reg, univ, holder, attrs=ATTRS, expiry=0, now=T0 + 10, cid=None, key_index=0):
    cid = cid or os.urandom(16)
    vc, sec, root = build_credential(univ, cid, attrs, pub_bytes(holder), expiry, key_index)
    reg.issue("univ-a", cid, root, h(pub_bytes(holder)), key_index, now, expiry)
    return cid, vc, sec

def t_f1():
    reg, univ, holder, ver = setup(); cid, vc, sec = issue_std(reg, univ, holder)
    p = present(vc, sec, holder, ["gelar", "tanggal_lulus"], ver.challenge(), "hrd-pt-x")
    ok, why = ver.verify(p, T0 + 100)
    s = json.dumps(p)
    leak = [v for k, v in ATTRS.items() if k not in ("gelar", "tanggal_lulus") and v in s]
    return ok and not leak, "verifikasi=%s; atribut bocor=%s" % (ok, leak)

def t_f2():
    reg, univ, holder, ver = setup(); cid, vc, sec = issue_std(reg, univ, holder)
    p = present(vc, sec, holder, ["nomor_ijazah"], ver.challenge(), "hrd-pt-x")
    ok, why = ver.verify(p, T0 + 100); return ok, "ok=%s %s" % (ok, why)

def t_f3():
    reg, univ, holder, ver = setup(); cid, vc, sec = issue_std(reg, univ, holder)
    reg.revoke("univ-a", cid)
    ok, why = ver.verify(present(vc, sec, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 100)
    try: reg.reinstate("univ-a", cid); final = False
    except Reject: final = True
    return (not ok) and "STATUS_REVOKED" in why and final, "alasan=%s; REVOKED final=%s" % (why, final)

def t_f4():
    reg, univ, holder, ver = setup(); cid, vc, sec = issue_std(reg, univ, holder)
    reg.suspend("univ-a", cid)
    ok1, why1 = ver.verify(present(vc, sec, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 100)
    reg.reinstate("univ-a", cid)
    ok2, why2 = ver.verify(present(vc, sec, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 100)
    return (not ok1) and ok2, "saat SUSPENDED=%s; setelah reinstate=%s" % (why1, ok2)

def t_f5():
    reg, univ, holder, ver = setup(); old, vc1, s1 = issue_std(reg, univ, holder)
    attrs2 = dict(ATTRS, nama="Siti Rahma Putri")
    new = os.urandom(16); vc2, s2, r2 = build_credential(univ, new, attrs2, pub_bytes(holder))
    reg.supersede("univ-a", old, new, r2, h(pub_bytes(holder)), 0, T0 + 50)
    ok1, why1 = ver.verify(present(vc1, s1, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 100)
    ok2, why2 = ver.verify(present(vc2, s2, holder, ["nama"], ver.challenge(), "hrd-pt-x"), T0 + 100)
    return (not ok1) and ok2, "lama=%s; baru ok=%s" % (why1, ok2)

def t_f6():
    reg, univ, holder, ver = setup(); cid, vc, sec = issue_std(reg, univ, holder, expiry=T0 + 1000)
    ok1, _ = ver.verify(present(vc, sec, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 500)
    ok2, why2 = ver.verify(present(vc, sec, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 2000)
    return ok1 and (not ok2) and "KEDALUWARSA" in why2, "sebelum=%s; sesudah=%s" % (ok1, why2)

def t_f7():
    reg, univ, holder, ver = setup(); cid, vc, sec = issue_std(reg, univ, holder)
    new_holder = Ed25519PrivateKey.generate()
    reg.rebind("univ-a", cid, h(pub_bytes(new_holder)), ["petugas-1", "petugas-2"])
    ok_old, why_old = ver.verify(present(vc, sec, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 100)
    ok_new, why_new = ver.verify(present(vc, sec, new_holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 100)
    try: reg.rebind("univ-a", cid, h(b"x"), ["petugas-1"]); single = False
    except Reject: single = True
    return (not ok_old) and ok_new and single, "kunci lama=%s; kunci baru ok=%s; rebind 1 petugas ditolak=%s" % (why_old, ok_new, single)

def t_f8():
    reg, univ, holder, ver = setup(); cid, vc, sec = issue_std(reg, univ, holder)
    new_key = Issuer("univ-a"); reg.rotate_issuer_key("univ-a", new_key.pub(), T0 + 200, ["rektor", "kauptik"])
    ok_old, _ = ver.verify(present(vc, sec, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 300)
    cid2 = os.urandom(16); vc2, s2, r2 = build_credential(new_key, cid2, ATTRS, pub_bytes(holder), 0, 1)
    reg.issue("univ-a", cid2, r2, h(pub_bytes(holder)), 1, T0 + 250)
    ok_new, why = ver.verify(present(vc2, s2, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 300)
    return ok_old and ok_new, "lama ok=%s; baru ok=%s %s" % (ok_old, ok_new, why)

def t_s1():
    reg, univ, holder, ver = setup(); attacker = Issuer("univ-a")  # meniru nama penerbit
    cid = os.urandom(16); vc, sec, root = build_credential(attacker, cid, ATTRS, pub_bytes(holder))
    reg.issue("univ-a", cid, root, h(pub_bytes(holder)), 0, T0 + 10)  # anggap jangkar masuk (skenario terburuk)
    ok, why = ver.verify(present(vc, sec, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 100)
    try: reg.issue("penyerang", os.urandom(16), root, root, 0, T0); direct = False
    except Reject: direct = True
    return (not ok) and "TANDA_TANGAN_PENERBIT_TIDAK_VALID" in why and direct, "alasan=%s; jangkar langsung oleh non-penerbit ditolak=%s" % (why, direct)

def t_s2():
    reg, univ, holder, ver = setup(); cid, vc, sec = issue_std(reg, univ, holder)
    p = present(vc, sec, holder, ["ipk"], ver.challenge(), "hrd-pt-x"); p["disclosed"][0]["value"] = "4.00"
    ok, why = ver.verify(p, T0 + 100); return (not ok) and any("BUKTI_MERKLE_GAGAL" in w for w in why), "alasan=%s" % why

def t_s3():
    reg, univ, holder, ver = setup(); cid, vc, sec = issue_std(reg, univ, holder)
    n = ver.challenge(); p = present(vc, sec, holder, ["gelar"], n, "hrd-pt-x")
    ok1, _ = ver.verify(p, T0 + 100); ok2, why2 = ver.verify(p, T0 + 101)
    ver2 = Verifier("hrd-pt-y", reg); n2 = ver2.challenge()
    p2 = present(vc, sec, holder, ["gelar"], n2, "hrd-pt-x")  # dibuat untuk verifier lain
    ok3, why3 = ver2.verify(p2, T0 + 100)
    return ok1 and (not ok2) and (not ok3), "pertama=%s; replay=%s; audience salah=%s" % (ok1, why2, why3)

def t_s4():
    reg, univ, holder, ver = setup(); cid, vc, sec = issue_std(reg, univ, holder)
    thief = Ed25519PrivateKey.generate()
    ok, why = ver.verify(present(vc, sec, thief, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 100)
    return (not ok) and "KUNCI_HOLDER_TIDAK_TERIKAT" in why, "alasan=%s" % why

def t_s5():
    reg, univ, holder, ver = setup(); cid, vc, sec = issue_std(reg, univ, holder)
    other = Issuer("univ-b"); reg.register_issuer("univ-b", other.pub(), T0, ["rektor", "wr1"])
    rej = []
    for name, fn in [("revoke oleh penerbit lain", lambda: reg.revoke("univ-b", cid)),
                     ("revoke oleh non-penerbit", lambda: reg.revoke("penyerang", cid)),
                     ("timpa credId", lambda: reg.issue("univ-a", cid, b"\x00" * 32, b"\x00" * 32, 0, T0)),
                     ("daftar penerbit tanpa kuorum", lambda: reg.register_issuer("x", b"k", T0, ["rektor"]))]:
        try: fn(); rej.append((name, "DITERIMA"))
        except Reject: rej.append((name, "ditolak"))
    return all(r[1] == "ditolak" for r in rej), str(rej)

def t_s6():
    reg, univ, holder, ver = setup()
    c_before, vc1, s1 = issue_std(reg, univ, holder, now=T0 + 100)
    c_after, vc2, s2 = issue_std(reg, univ, holder, now=T0 + 500)
    reg.mark_key_compromised("univ-a", 0, T0 + 300, ["rektor", "wr1"])
    ok1, _ = ver.verify(present(vc1, s1, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 600)
    ok2, why2 = ver.verify(present(vc2, s2, holder, ["gelar"], ver.challenge(), "hrd-pt-x"), T0 + 600)
    return ok1 and (not ok2) and "DITERBITKAN_SETELAH_KUNCI_PENERBIT_BOCOR" in why2, "sebelum bocor ok=%s; sesudah=%s" % (ok1, why2)

def t_s7():
    reg = Registry(admins={"a", "b", "c"}); outs = []
    for name, appr in [("1 penyetuju", ["a"]), ("penyetuju ganda sama", ["a", "a"]), ("non-admin", ["x", "y"])]:
        try: reg.register_issuer("i", b"k", T0, appr); outs.append((name, "DITERIMA"))
        except Reject: outs.append((name, "ditolak"))
    try: reg.register_issuer("i", b"k", T0, ["a", "b"]); okq = True
    except Reject: okq = False
    return all(o[1] == "ditolak" for o in outs) and okq, "%s; 2-dari-3 valid diterima=%s" % (outs, okq)

def t_s8():
    reg, univ, holder, ver = setup()
    cid1, vc1, s1 = issue_std(reg, univ, holder); cid2, vc2, s2 = issue_std(reg, univ, holder)
    onchain = json.dumps([(k.hex(), {kk: (vv.hex() if isinstance(vv, bytes) else str(vv)) for kk, vv in v.items()})
                          for k, v in reg.creds.items()]) + json.dumps(reg.events)
    pii = [v for v in ATTRS.values() if v in onchain]
    return (not pii) and vc1["body"]["root"] != vc2["body"]["root"], \
        "PII di data on-chain=%s; root dua kredensial berdata sama berbeda=%s" % (pii, vc1["body"]["root"] != vc2["body"]["root"])

def perf():
    reg, univ, holder, ver = setup(); N = 1000
    t = time.perf_counter(); items = []
    for _ in range(N):
        cid = os.urandom(16); vc, sec, root = build_credential(univ, cid, ATTRS, pub_bytes(holder))
        reg.issue("univ-a", cid, root, h(pub_bytes(holder)), 0, T0 + 10); items.append((vc, sec))
    build_ms = (time.perf_counter() - t) * 1000 / N
    lat, size = [], 0
    for vc, sec in items:
        p = present(vc, sec, holder, ["gelar", "tanggal_lulus"], ver.challenge(), "hrd-pt-x")
        s = time.perf_counter(); ok, _ = ver.verify(p, T0 + 100); lat.append((time.perf_counter() - s) * 1000)
        assert ok; size = len(json.dumps(p).encode())
    lat.sort()
    return {"N": N, "build_issue_ms_mean": round(build_ms, 3), "verify_ms_mean": round(statistics.mean(lat), 3),
            "verify_ms_p95": round(lat[int(0.95 * N) - 1], 3), "verify_ms_max": round(lat[-1], 3),
            "verify_per_sec_single_thread": round(1000 / statistics.mean(lat)), "presentation_bytes": size}

if __name__ == "__main__":
    case("F1", "Fungsional", "Terbitkan lalu verifikasi dengan pengungkapan selektif (gelar, tanggal lulus); NIM/IPK/nama tidak muncul", t_f1)
    case("F2", "Fungsional", "Verifikasi hanya satu atribut (nomor ijazah)", t_f2)
    case("F3", "Fungsional", "Pencabutan: verifikasi gagal; REVOKED bersifat final", t_f3)
    case("F4", "Fungsional", "Suspend lalu reinstate: gagal saat suspend, berhasil setelah reinstate", t_f4)
    case("F5", "Fungsional", "Supersede (penerbitan ulang): versi lama gagal, versi baru valid", t_f5)
    case("F6", "Fungsional", "Kedaluwarsa sertifikat kompetensi", t_f6)
    case("F7", "Fungsional", "Pemulihan kunci holder via rebind maker-checker", t_f7)
    case("F8", "Fungsional", "Rotasi kunci penerbit: kredensial lama tetap valid, baru memakai kunci baru", t_f8)
    case("S1", "Keamanan", "Kredensial palsu (kunci penyerang) ditolak", t_s1)
    case("S2", "Keamanan", "Atribut dimanipulasi (IPK diubah) ditolak oleh bukti Merkle", t_s2)
    case("S3", "Keamanan", "Replay presentasi dan audience salah ditolak", t_s3)
    case("S4", "Keamanan", "VC curian tanpa kunci holder ditolak", t_s4)
    case("S5", "Keamanan", "Otorisasi: aksi oleh pihak tak berwenang ditolak", t_s5)
    case("S6", "Keamanan", "Kunci penerbit bocor: kredensial setelah waktu kebocoran ditolak, sebelumnya tetap valid", t_s6)
    case("S7", "Keamanan", "Kuorum multisig 2-dari-3 ditegakkan", t_s7)
    case("S8", "Keamanan/Privasi", "Tidak ada PII on-chain; garam membuat root tidak dapat ditautkan", t_s8)
    P = perf()
    out = {"cases": RESULTS, "performance": P, "pass": sum(r["hasil"] == "PASS" for r in RESULTS), "total": len(RESULTS)}
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json"), "w"), indent=2, ensure_ascii=False)
    for r in RESULTS: print(r["id"], r["hasil"], "-", r["detail"][:140])
    print("PASS %d/%d" % (out["pass"], out["total"])); print(P)
