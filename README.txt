
1. STRUKTUR
  CredentialRegistry.sol      Smart contract: jangkar kredensial + siklus status (tanpa PII).
  verikred_sim.py             Simulasi end-to-end (penerbit, holder, verifier, registry) + 16 uji + performa.
  results.json                Keluaran verikred_sim.py (F1-F8, S1-S8, performa).
  minichain_demo.py           Ilustrasi hash-chain + Merkle. Keluaran: minichain_results.json.
  evm/                        Kompilasi kontrak (solc 0.8.26) dan 15 uji di EVM lokal.
  evm_results.json            Keluaran evm/evm_test.mjs (E1-E15 + estimasi gas).
  make_test_matrix.py         Membangun matriks keterlacakan requirement -> uji -> bukti.
  docs/TEST_MATRIX.md, docs/test_matrix.csv
                              Matriks 32 uji dalam format Template 12 tugas (ID, Req, Kondisi Awal,
                              Langkah Uji, Hasil Harapan, Hasil Aktual, Status, Bukti) + REQ-01..REQ-12.
  docs/AI_DECLARATION.md      Template deklarasi penggunaan AI (bagian 9 tugas) - WAJIB DIISI mahasiswa.
  docs/PROCESS_LOG.md         Template log pengerjaan (lampiran proses) - WAJIB DIISI mahasiswa.

2. VERSI DAN DEPENDENCY
  Solidity compiler : solc 0.8.26 (pragma ^0.8.24), via npm paket "solc" 0.8.26
  EVM uji           : @ethereumjs/vm 8.1.1, @ethereumjs/common 4.4.0, @ethereumjs/block 5.3.0,
                      @ethereumjs/util 9.1.0, ethers 6.17.0 (hardfork Shanghai, in-memory)
                      Versi terkunci di evm/package.json dan evm/package-lock.json.
  Python            : 3.10+ dan pustaka 'cryptography' (pip install cryptography); diuji dengan 50.0.1
  Node.js           : 18+ (diuji dengan v22.22.0)

3. LANGKAH MENJALANKAN
  python3 -I verikred_sim.py        -> menulis results.json, mencetak PASS 16/16
  python3 -I minichain_demo.py      -> menulis minichain_results.json, mencetak PASS
  cd evm && npm install && npm run compile && npm test
                                    -> menulis ../evm_results.json, mencetak PASS 15/15
                                       (npm install butuh internet satu kali)
  python3 -I make_test_matrix.py    -> menulis docs/TEST_MATRIX.md dan docs/test_matrix.csv
                                       (jalankan SETELAH kedua uji di atas)

4. HASIL UJI (lihat docs/TEST_MATRIX.md)
  Simulasi Python 16/16 PASS; EVM 15/15 PASS; performa 1 uji PASS; total 32/32.
  Jenis uji: happy path 8, negatif 7, recovery 5, keamanan 5, tidak berwenang 6, performa 1.
  Seluruh 12 requirement tertaut ke minimal satu uji. Angka performa dan gas bersifat indikatif
  (bergantung mesin), bukan klaim kinerja jaringan nyata. Kriteria performa (< 50 ms) adalah asumsi.

5. DATA DUMMY
  Semua nama, NIM, IPK, nomor ijazah, alamat, dan kunci pada artefak adalah fiktif/dummy.
  Kunci Ed25519 dan garam dibangkitkan acak tiap eksekusi dan tidak disimpan. Tidak ada private key
  pribadi, credential, dana nyata, mainnet, atau data pribadi nyata. Hasil PASS/FAIL deterministik.

6. BATASAN
  - Kontrak belum di-deploy ke testnet, belum diaudit, belum diuji fuzz/analisis statis (mis. Slither).
  - Simulasi Python mencerminkan logika kontrak, tetapi tidak identik: kuorum multisig, maker-checker
    rebind, pelacakan kunci bocor per-kunci, verifikasi tanda tangan, dan bukti Merkle hanya ada di
    simulasi/off-chain; kontrak menganggap kuorum dijalankan oleh multisig/timelock di luar kontrak.
  - Laporan PDF, diagram arsitektur, suitability matrix, threat model/risk register, dan video
    presentasi adalah keluaran terpisah; paket ini hanya artefak teknis dan bukti uji.
