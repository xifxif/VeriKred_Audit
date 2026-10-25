# Matriks Uji dan Keterlacakan Requirement

Dibangkitkan oleh `make_test_matrix.py` dari `results.json` dan `evm_results.json` (format Template 12 tugas).

**Ringkasan:** 32/32 PASS (16 uji simulasi Python + 15 uji EVM + 1 uji performa). Syarat tugas minimal 10 uji.

**Cakupan jenis uji:** Happy path: 8, Keamanan: 5, Negatif: 7, Performa: 1, Recovery: 5, Tidak berwenang: 6.

## Daftar requirement

| Req | Deskripsi |
|---|---|
| REQ-01 | Penerbitan kredensial: hanya jangkar (root Merkle + status) yang dicatat on-chain, tanpa PII |
| REQ-02 | Verifikasi dengan pengungkapan selektif (hanya atribut yang diminta) |
| REQ-03 | Siklus status kredensial: suspend, reinstate, revoke (final), supersede |
| REQ-04 | Kedaluwarsa kredensial ditegakkan saat verifikasi |
| REQ-05 | Otorisasi: hanya penerbit terdaftar/pemilik kredensial yang dapat menulis; tidak ada overwrite |
| REQ-06 | Integritas & autentisitas: kredensial palsu dan atribut yang dimanipulasi ditolak |
| REQ-07 | Anti-replay dan pengikatan ke kunci holder (VC curian tidak berguna) |
| REQ-08 | Manajemen kunci penerbit: rotasi dan penanganan kunci bocor |
| REQ-09 | Pemulihan kunci holder (rebind) dengan kontrol maker-checker |
| REQ-10 | Governance: kuorum multisig dan alih governance dua langkah |
| REQ-11 | Privasi: tidak ada PII on-chain dan root tidak dapat ditautkan (unlinkability) |
| REQ-12 | Performa verifikasi memadai untuk penggunaan interaktif (asumsi: rata-rata < 50 ms) |

## Matriks uji

| ID | Req | Kondisi Awal | Langkah Uji | Hasil Harapan | Hasil Aktual | Status | Bukti |
|---|---|---|---|---|---|---|---|
| F1 | REQ-01,REQ-02,REQ-11 | Penerbit terdaftar; holder punya kunci; atribut fiktif lengkap | Terbitkan VC; holder menyajikan hanya gelar & tanggal lulus; verifier memverifikasi | Verifikasi berhasil; nama/NIM/IPK tidak terungkap | verifikasi=True; atribut bocor=[] | PASS | results.json#F1 |
| F2 | REQ-02 | VC aktif | Sajikan hanya nomor ijazah | Verifikasi berhasil dengan satu atribut | ok=True [] | PASS | results.json#F2 |
| F3 | REQ-03 | VC aktif | Penerbit mencabut VC; verifier memverifikasi; coba reinstate | Verifikasi gagal STATUS_REVOKED; REVOKED final | alasan=['STATUS_REVOKED']; REVOKED final=True | PASS | results.json#F3 |
| F4 | REQ-03 | VC aktif | Suspend, verifikasi, reinstate, verifikasi | Gagal saat SUSPENDED; berhasil setelah reinstate | saat SUSPENDED=['STATUS_SUSPENDED']; setelah reinstate=True | PASS | results.json#F4 |
| F5 | REQ-03 | VC aktif versi 1 | Supersede dengan versi baru | Versi lama SUPERSEDED (gagal); versi baru valid | lama=['STATUS_SUPERSEDED']; baru ok=True | PASS | results.json#F5 |
| F6 | REQ-04 | VC dengan expiry | Verifikasi sebelum dan sesudah expiry | Valid sebelum; KEDALUWARSA sesudah | sebelum=True; sesudah=['KEDALUWARSA'] | PASS | results.json#F6 |
| F7 | REQ-09 | Holder kehilangan kunci | Rebind ke kunci baru dengan 2 petugas; coba dengan 1 petugas | Kunci lama ditolak; kunci baru valid; 1 petugas ditolak | kunci lama=['KUNCI_HOLDER_TIDAK_TERIKAT']; kunci baru ok=True; rebind 1 petugas ditolak=True | PASS | results.json#F7 |
| F8 | REQ-08 | Penerbit punya kunci aktif | Rotasi kunci penerbit; terbitkan VC baru | VC lama tetap valid; VC baru valid dengan kunci baru | lama ok=True; baru ok=True [] | PASS | results.json#F8 |
| S1 | REQ-05,REQ-06 | Penyerang meniru nama penerbit dengan kunci sendiri | Buat VC palsu; coba jangkar langsung oleh non-penerbit | TANDA_TANGAN_PENERBIT_TIDAK_VALID; jangkar ditolak | alasan=['TANDA_TANGAN_PENERBIT_TIDAK_VALID']; jangkar langsung oleh non-penerbit ditolak=True | PASS | results.json#S1 |
| S2 | REQ-06 | VC aktif | Ubah nilai IPK pada presentasi | BUKTI_MERKLE_GAGAL | alasan=['BUKTI_MERKLE_GAGAL:ipk'] | PASS | results.json#S2 |
| S3 | REQ-07 | Presentasi sah sudah dipakai | Putar ulang presentasi; ubah audience | Nonce sudah dipakai ditolak; AUDIENCE_SALAH | pertama=True; replay=['NONCE_TIDAK_VALID_ATAU_SUDAH_DIPAKAI']; audience salah=['AUDIENCE_SALAH'] | PASS | results.json#S3 |
| S4 | REQ-07 | VC dicuri tanpa kunci holder | Penyerang menyajikan VC | KUNCI_HOLDER_TIDAK_TERIKAT | alasan=['KUNCI_HOLDER_TIDAK_TERIKAT'] | PASS | results.json#S4 |
| S5 | REQ-05 | Penerbit lain / non-penerbit | Revoke VC milik penerbit lain; timpa credId; daftar penerbit tanpa kuorum | Seluruh aksi ditolak | [('revoke oleh penerbit lain', 'ditolak'), ('revoke oleh non-penerbit', 'ditolak'), ('timpa credId', 'ditolak'), ('daftar penerbit tanpa kuorum', 'ditolak')] | PASS | results.json#S5 |
| S6 | REQ-08 | Kunci penerbit dinyatakan bocor pada waktu T | Verifikasi VC sebelum dan sesudah T | Sebelum T valid; sesudah T ditolak | sebelum bocor ok=True; sesudah=['DITERBITKAN_SETELAH_KUNCI_PENERBIT_BOCOR'] | PASS | results.json#S6 |
| S7 | REQ-10 | Admin 3, kuorum 2 | Setujui oleh 1 admin, admin ganda, non-admin, lalu 2 admin sah | Tiga pertama ditolak; 2-dari-3 diterima | [('1 penyetuju', 'ditolak'), ('penyetuju ganda sama', 'ditolak'), ('non-admin', 'ditolak')]; 2-dari-3 valid diterima=True | PASS | results.json#S7 |
| S8 | REQ-01,REQ-11 | Dua VC dengan data identik | Periksa data on-chain; bandingkan root | Tidak ada PII on-chain; root berbeda (bergaram) | PII di data on-chain=[]; root dua kredensial berdata sama berbeda=True | PASS | results.json#S8 |
| E1 | REQ-10 | EVM lokal bersih | Deploy kontrak dengan alamat governance | Deploy berhasil; governance sesuai konstruktor | deploy gas=1563959 | PASS | evm_results.json#E1 |
| E2 | REQ-05,REQ-10 | Kontrak ter-deploy | setIssuer dipanggil non-governance | Revert NotGovernance | revert=0xb56f932c | PASS | evm_results.json#E2 |
| E3 | REQ-05 | Akun belum terdaftar sebagai penerbit | issue() oleh non-penerbit | Revert | reverted=true | PASS | evm_results.json#E3 |
| E4 | REQ-01 | Penerbit terdaftar | issue(); check(root benar) | valid=true, status=ACTIVE | valid=true; status=1; gas issue=93472 | PASS | evm_results.json#E4 |
| E5 | REQ-06 | VC aktif on-chain | check() dengan root salah | valid=false | valid=false | PASS | evm_results.json#E5 |
| E6 | REQ-05 | credId sudah terpakai | issue() ulang dengan credId sama | Revert AlreadyExists | revert=0x23369fa6 | PASS | evm_results.json#E6 |
| E7 | REQ-05 | VC milik penerbit A | revoke() oleh penerbit B | Revert NotIssuerOf | revert=0xc677a12e | PASS | evm_results.json#E7 |
| E8 | REQ-03 | VC ACTIVE | suspend lalu reinstate | valid=false saat suspend; true setelah reinstate | saat suspend ok=true; setelah reinstate valid=true | PASS | evm_results.json#E8 |
| E9 | REQ-03 | VC REVOKED | reinstate() setelah revoke | Revert InvalidTransition | status=3; reinstate revert=0xa6532e5d | PASS | evm_results.json#E9 |
| E10 | REQ-03 | VC ACTIVE | supersede() ke credId baru | Lama SUPERSEDED; baru valid | lama status=4; baru valid=true | PASS | evm_results.json#E10 |
| E11 | REQ-04 | VC dengan expiry | check() sebelum/sesudah expiry (waktu blok dimajukan) | valid sebelum; tidak valid sesudah | sebelum=true; sesudah=false | PASS | evm_results.json#E11 |
| E12 | REQ-08 | Penerbit ditandai bocor mulai T | check() VC sebelum/sesudah T | Sebelum T valid; sesudah T tidak valid | sebelum=true; sesudah=false | PASS | evm_results.json#E12 |
| E13 | REQ-09,REQ-05 | VC ACTIVE | rebind() oleh non-penerbit lalu oleh penerbit | Non-penerbit ditolak; binding diganti oleh penerbit | binding baru tersimpan=true | PASS | evm_results.json#E13 |
| E14 | REQ-10 | Kontrak ter-deploy | transferGovernance lalu acceptGovernance (pihak tak berwenang dan pending) | Pihak tak berwenang ditolak; pending berhasil | governance baru berlaku=true | PASS | evm_results.json#E14 |
| E15 | REQ-01 | Penerbit terdaftar | issue() dengan root = 0 | Revert (root=0) | reverted=true | PASS | evm_results.json#E15 |
| P1 | REQ-12 | N=1000 verifikasi berurutan, 1 thread, mesin pengembangan | Ukur waktu verifikasi presentasi | Rata-rata < 50 ms (asumsi acceptance criterion) | rata-rata 0.253 ms; p95 0.292 ms; 1472 byte/presentasi | PASS | results.json#performance |

## Keterlacakan requirement ke uji

| Req | Uji |
|---|---|
| REQ-01 | F1, S8, E4, E15 |
| REQ-02 | F1, F2 |
| REQ-03 | F3, F4, F5, E8, E9, E10 |
| REQ-04 | F6, E11 |
| REQ-05 | S1, S5, E2, E3, E6, E7, E13 |
| REQ-06 | S1, S2, E5 |
| REQ-07 | S3, S4 |
| REQ-08 | F8, S6, E12 |
| REQ-09 | F7, E13 |
| REQ-10 | S7, E1, E2, E14 |
| REQ-11 | F1, S8 |
| REQ-12 | P1 |

## Integritas bukti (SHA-256)

- results.json: `c5bac298a3a066427330df87e64707f9646227cca229c2dc02eb8f2509dbdd23`
- evm_results.json: `74615ee172038819c4103e24468427afef5d065cac89932fe778ffcb1926e76e`

Catatan: hasil EVM berasal dari eksekusi `evm/evm_test.mjs` (lihat README); hash di atas mengikat tabel ini ke berkas bukti.
Hasil PASS pada uji simulasi mencerminkan logika kontrak, bukan kontrak itu sendiri (lihat Batasan di README).
