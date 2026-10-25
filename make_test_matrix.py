#!/usr/bin/env python3
"""Membangun docs/TEST_MATRIX.md dan docs/test_matrix.csv (format Template 12 tugas)
dari results.json, evm_results.json. Tidak menjalankan ulang uji; hanya menautkan
requirement -> test case -> hasil aktual -> bukti. Jalankan: python3 -I make_test_matrix.py"""
import csv, hashlib, json, os

BASE = os.path.dirname(os.path.abspath(__file__))
rd = lambda f: json.load(open(os.path.join(BASE, f), encoding="utf-8"))
sim, evm = rd("results.json"), rd("evm_results.json")

REQ = {
 "REQ-01": "Penerbitan kredensial: hanya jangkar (root Merkle + status) yang dicatat on-chain, tanpa PII",
 "REQ-02": "Verifikasi dengan pengungkapan selektif (hanya atribut yang diminta)",
 "REQ-03": "Siklus status kredensial: suspend, reinstate, revoke (final), supersede",
 "REQ-04": "Kedaluwarsa kredensial ditegakkan saat verifikasi",
 "REQ-05": "Otorisasi: hanya penerbit terdaftar/pemilik kredensial yang dapat menulis; tidak ada overwrite",
 "REQ-06": "Integritas & autentisitas: kredensial palsu dan atribut yang dimanipulasi ditolak",
 "REQ-07": "Anti-replay dan pengikatan ke kunci holder (VC curian tidak berguna)",
 "REQ-08": "Manajemen kunci penerbit: rotasi dan penanganan kunci bocor",
 "REQ-09": "Pemulihan kunci holder (rebind) dengan kontrol maker-checker",
 "REQ-10": "Governance: kuorum multisig dan alih governance dua langkah",
 "REQ-11": "Privasi: tidak ada PII on-chain dan root tidak dapat ditautkan (unlinkability)",
 "REQ-12": "Performa verifikasi memadai untuk penggunaan interaktif (asumsi: rata-rata < 50 ms)",
}

# id: (tipe, req, kondisi awal, langkah uji, hasil harapan)
CAT = {
 "F1": ("Happy path","REQ-01,REQ-02,REQ-11","Penerbit terdaftar; holder punya kunci; atribut fiktif lengkap","Terbitkan VC; holder menyajikan hanya gelar & tanggal lulus; verifier memverifikasi","Verifikasi berhasil; nama/NIM/IPK tidak terungkap"),
 "F2": ("Happy path","REQ-02","VC aktif","Sajikan hanya nomor ijazah","Verifikasi berhasil dengan satu atribut"),
 "F3": ("Negatif","REQ-03","VC aktif","Penerbit mencabut VC; verifier memverifikasi; coba reinstate","Verifikasi gagal STATUS_REVOKED; REVOKED final"),
 "F4": ("Happy path","REQ-03","VC aktif","Suspend, verifikasi, reinstate, verifikasi","Gagal saat SUSPENDED; berhasil setelah reinstate"),
 "F5": ("Happy path","REQ-03","VC aktif versi 1","Supersede dengan versi baru","Versi lama SUPERSEDED (gagal); versi baru valid"),
 "F6": ("Negatif","REQ-04","VC dengan expiry","Verifikasi sebelum dan sesudah expiry","Valid sebelum; KEDALUWARSA sesudah"),
 "F7": ("Recovery","REQ-09","Holder kehilangan kunci","Rebind ke kunci baru dengan 2 petugas; coba dengan 1 petugas","Kunci lama ditolak; kunci baru valid; 1 petugas ditolak"),
 "F8": ("Recovery","REQ-08","Penerbit punya kunci aktif","Rotasi kunci penerbit; terbitkan VC baru","VC lama tetap valid; VC baru valid dengan kunci baru"),
 "S1": ("Keamanan","REQ-05,REQ-06","Penyerang meniru nama penerbit dengan kunci sendiri","Buat VC palsu; coba jangkar langsung oleh non-penerbit","TANDA_TANGAN_PENERBIT_TIDAK_VALID; jangkar ditolak"),
 "S2": ("Keamanan","REQ-06","VC aktif","Ubah nilai IPK pada presentasi","BUKTI_MERKLE_GAGAL"),
 "S3": ("Keamanan","REQ-07","Presentasi sah sudah dipakai","Putar ulang presentasi; ubah audience","Nonce sudah dipakai ditolak; AUDIENCE_SALAH"),
 "S4": ("Keamanan","REQ-07","VC dicuri tanpa kunci holder","Penyerang menyajikan VC","KUNCI_HOLDER_TIDAK_TERIKAT"),
 "S5": ("Tidak berwenang","REQ-05","Penerbit lain / non-penerbit","Revoke VC milik penerbit lain; timpa credId; daftar penerbit tanpa kuorum","Seluruh aksi ditolak"),
 "S6": ("Recovery","REQ-08","Kunci penerbit dinyatakan bocor pada waktu T","Verifikasi VC sebelum dan sesudah T","Sebelum T valid; sesudah T ditolak"),
 "S7": ("Tidak berwenang","REQ-10","Admin 3, kuorum 2","Setujui oleh 1 admin, admin ganda, non-admin, lalu 2 admin sah","Tiga pertama ditolak; 2-dari-3 diterima"),
 "S8": ("Keamanan","REQ-01,REQ-11","Dua VC dengan data identik","Periksa data on-chain; bandingkan root","Tidak ada PII on-chain; root berbeda (bergaram)"),
 "E1": ("Happy path","REQ-10","EVM lokal bersih","Deploy kontrak dengan alamat governance","Deploy berhasil; governance sesuai konstruktor"),
 "E2": ("Tidak berwenang","REQ-05,REQ-10","Kontrak ter-deploy","setIssuer dipanggil non-governance","Revert NotGovernance"),
 "E3": ("Tidak berwenang","REQ-05","Akun belum terdaftar sebagai penerbit","issue() oleh non-penerbit","Revert"),
 "E4": ("Happy path","REQ-01","Penerbit terdaftar","issue(); check(root benar)","valid=true, status=ACTIVE"),
 "E5": ("Negatif","REQ-06","VC aktif on-chain","check() dengan root salah","valid=false"),
 "E6": ("Negatif","REQ-05","credId sudah terpakai","issue() ulang dengan credId sama","Revert AlreadyExists"),
 "E7": ("Tidak berwenang","REQ-05","VC milik penerbit A","revoke() oleh penerbit B","Revert NotIssuerOf"),
 "E8": ("Happy path","REQ-03","VC ACTIVE","suspend lalu reinstate","valid=false saat suspend; true setelah reinstate"),
 "E9": ("Negatif","REQ-03","VC REVOKED","reinstate() setelah revoke","Revert InvalidTransition"),
 "E10": ("Happy path","REQ-03","VC ACTIVE","supersede() ke credId baru","Lama SUPERSEDED; baru valid"),
 "E11": ("Negatif","REQ-04","VC dengan expiry","check() sebelum/sesudah expiry (waktu blok dimajukan)","valid sebelum; tidak valid sesudah"),
 "E12": ("Recovery","REQ-08","Penerbit ditandai bocor mulai T","check() VC sebelum/sesudah T","Sebelum T valid; sesudah T tidak valid"),
 "E13": ("Recovery","REQ-09,REQ-05","VC ACTIVE","rebind() oleh non-penerbit lalu oleh penerbit","Non-penerbit ditolak; binding diganti oleh penerbit"),
 "E14": ("Tidak berwenang","REQ-10","Kontrak ter-deploy","transferGovernance lalu acceptGovernance (pihak tak berwenang dan pending)","Pihak tak berwenang ditolak; pending berhasil"),
 "E15": ("Negatif","REQ-01","Penerbit terdaftar","issue() dengan root = 0","Revert (root=0)"),
}

rows = []
for src, data, fname in (("Simulasi Python", sim, "results.json"), ("EVM lokal", evm, "evm_results.json")):
    for c in data["cases"]:
        t, req, kon, lang, harap = CAT[c["id"]]
        rows.append(dict(id=c["id"], tipe=t, req=req, kondisi=kon, langkah=lang, harapan=harap,
                         aktual=c["detail"], status=c["hasil"], bukti=f"{fname}#{c['id']}", sumber=src))

p = sim["performance"]
perf_ok = p["verify_ms_mean"] < 50
rows.append(dict(id="P1", tipe="Performa", req="REQ-12", kondisi=f"N={p['N']} verifikasi berurutan, 1 thread, mesin pengembangan",
    langkah="Ukur waktu verifikasi presentasi", harapan="Rata-rata < 50 ms (asumsi acceptance criterion)",
    aktual=f"rata-rata {p['verify_ms_mean']} ms; p95 {p['verify_ms_p95']} ms; {p['presentation_bytes']} byte/presentasi",
    status="PASS" if perf_ok else "FAIL", bukti="results.json#performance", sumber="Simulasi Python"))

# validasi keterlacakan
assert {r for row in rows for r in row["req"].split(",")} <= set(REQ)
covered = {r for row in rows for r in row["req"].split(",")}
assert covered == set(REQ), set(REQ) - covered
for r in rows: assert r["id"] == "P1" or r["id"] in CAT

os.makedirs(os.path.join(BASE, "docs"), exist_ok=True)
cols = ["id","req","kondisi","langkah","harapan","aktual","status","bukti"]
heads = ["ID","Req","Kondisi Awal","Langkah Uji","Hasil Harapan","Hasil Aktual","Status","Bukti"]
with open(os.path.join(BASE,"docs","test_matrix.csv"),"w",newline="",encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(heads + ["Tipe","Sumber"])
    for r in rows: w.writerow([r[c] for c in cols] + [r["tipe"], r["sumber"]])

def sha(fn): return hashlib.sha256(open(os.path.join(BASE,fn),"rb").read()).hexdigest()
n_pass = sum(r["status"]=="PASS" for r in rows)
cnt = {}
for r in rows: cnt[r["tipe"]] = cnt.get(r["tipe"],0)+1
md = ["# Matriks Uji dan Keterlacakan Requirement","",
 "Dibangkitkan oleh `make_test_matrix.py` dari `results.json` dan `evm_results.json` (format Template 12 tugas).","",
 f"**Ringkasan:** {n_pass}/{len(rows)} PASS ({len(sim['cases'])} uji simulasi Python + {len(evm['cases'])} uji EVM + 1 uji performa). Syarat tugas minimal 10 uji.","",
 "**Cakupan jenis uji:** " + ", ".join(f"{k}: {v}" for k,v in sorted(cnt.items())) + ".","",
 "## Daftar requirement","","| Req | Deskripsi |","|---|---|"]
md += [f"| {k} | {v} |" for k,v in REQ.items()]
md += ["","## Matriks uji","","| "+" | ".join(heads)+" |","|"+"---|"*len(heads)]
esc = lambda s: str(s).replace("|","\\|")
md += ["| "+" | ".join(esc(r[c]) for c in cols)+" |" for r in rows]
md += ["","## Keterlacakan requirement ke uji","","| Req | Uji |","|---|---|"]
for k in REQ: md.append(f"| {k} | " + ", ".join(r["id"] for r in rows if k in r["req"].split(",")) + " |")
md += ["","## Integritas bukti (SHA-256)","",
 f"- results.json: `{sha('results.json')}`", f"- evm_results.json: `{sha('evm_results.json')}`",
 "","Catatan: hasil EVM berasal dari eksekusi `evm/evm_test.mjs` (lihat README); hash di atas mengikat tabel ini ke berkas bukti.",
 "Hasil PASS pada uji simulasi mencerminkan logika kontrak, bukan kontrak itu sendiri (lihat Batasan di README)."]
open(os.path.join(BASE,"docs","TEST_MATRIX.md"),"w",encoding="utf-8").write("\n".join(md)+"\n")
print(f"OK: {n_pass}/{len(rows)} PASS; semua {len(REQ)} requirement tertaut ke uji; jenis: {cnt}")
