VeriKred adalah prototipe aplikasi berbasis blockchain untuk pencatatan dan verifikasi kredensial pendidikan. Smart contract menyimpan informasi jangkar kredensial dan statusnya, sedangkan data pribadi pemilik kredensial tidak disimpan secara langsung di blockchain.

Project ini mencakup perancangan solusi, implementasi smart contract, pengujian, deployment pada node lokal, dan integrasi frontend.

## 1. Teknologi

- Solidity 0.8.26
- Hardhat
- Node.js dan npm
- JavaScript
- ethers.js
- HTML, CSS, dan JavaScript
- Local Ethereum development network

## 2. Struktur Project

```text
VeriKred_Project1_Project2/
├── docs/
│   └── project1/
│       ├── architecture.svg
│       ├── DESAIN_PROJECT_1.md
│       └── STATUS_DAN_CHECKLIST.md
├── hardhat/
│   ├── contracts/
│   │   └── CredentialRegistry.sol
│   ├── test/
│   │   ├── CredentialRegistry.test.js
│   │   └── DebuggingEvidence.test.js
│   ├── scripts/
│   │   └── deploy.js
│   ├── frontend/
│   │   └── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── deployment-record.json
│   └── README.md
└── bukti_pengujian/
```

Catatan: sesuaikan struktur di atas apabila lokasi atau nama file pada folder pengumpulan berbeda. Folder `bukti_pengujian` digunakan untuk mengumpulkan log pengujian, deployment record, dan screenshot demonstrasi.

## 3. Persyaratan

Sebelum menjalankan project, siapkan:

- Node.js versi 18 atau lebih baru.
- npm.
- Browser modern.
- Terminal PowerShell atau terminal lain yang mendukung perintah npm.

Pastikan seluruh perintah dijalankan dari direktori `hardhat`, kecuali disebutkan lain.

## 4. Instalasi Dependensi

Buka terminal pada direktori `hardhat`, kemudian jalankan:

```bash
npm install
```

Perintah ini memasang dependensi yang dibutuhkan untuk kompilasi, pengujian, dan deployment lokal.

## 5. Kompilasi Smart Contract

Jalankan:

```bash
npm run compile
```

Kompilasi dinyatakan berhasil apabila Hardhat selesai tanpa error. Pesan `Nothing to compile` berarti tidak ada perubahan source yang memerlukan kompilasi ulang berdasarkan cache Hardhat.

Source contract utama berada di:

```text
contracts/CredentialRegistry.sol
```

## 6. Menjalankan Unit Test

Jalankan:

```bash
npm test
```

Pengujian mencakup skenario berikut:

- Deployment dan pengaturan governance.
- Penerbitan kredensial oleh issuer yang berwenang.
- Penolakan penerbit yang tidak terdaftar.
- Validasi root dan ID kredensial.
- Verifikasi kecocokan root.
- Kontrol akses untuk pencabutan kredensial.
- Suspend, reinstate, dan revoke.
- Validasi transisi status.
- Supersede kredensial.
- Perpindahan governance.
- Validasi expiry dan kondisi issuer.
- Pengikatan holder.

Hasil pengujian terakhir yang tercatat adalah **13 passing**. Jalankan kembali `npm test` pada lingkungan pengumpulan dan simpan output aktual sebagai bukti pengujian.

File test tersedia pada direktori `test/`.

## 7. Menjalankan Node Blockchain Lokal

Buka terminal pertama di direktori `hardhat`, lalu jalankan:

```bash
npm run node
```

Node Hardhat akan menyediakan RPC lokal, umumnya pada:

```text
http://127.0.0.1:8545
```

Chain ID yang digunakan adalah:

```text
31337
```

Biarkan terminal node tetap berjalan selama proses deployment dan demonstrasi.

Node lokal menyediakan akun pengujian beserta saldo ETH simulasi. Gunakan akun tersebut hanya untuk pengembangan dan pengujian lokal.

## 8. Deployment Smart Contract

Buka terminal kedua di direktori `hardhat`, kemudian jalankan:

```bash
npm run deploy:local
```

Script deployment akan menerbitkan `CredentialRegistry` ke node lokal dan menghasilkan file:

```text
deployment-record.json
```

Record tersebut berisi informasi deployment seperti jaringan, Chain ID, alamat deployer, alamat kontrak, transaction hash, nomor blok, dan waktu deployment.

**Penting:** alamat kontrak dan transaction hash harus berasal dari hasil eksekusi aktual. Deployment record hanya berlaku untuk deployment yang bersangkutan. Jika node lokal di-reset, riwayat blockchain dan kontrak sebelumnya mungkin tidak tersedia lagi.

## 9. Menjalankan Frontend

Pastikan node Hardhat sudah berjalan dan frontend menggunakan alamat kontrak yang benar untuk deployment aktif.

Dari direktori `hardhat`, buka terminal tambahan dan jalankan:

```powershell
py -m http.server 8080 --directory frontend
```

Kemudian buka browser pada:

```text
http://127.0.0.1:8080
```

Jika perintah `py` tidak tersedia, gunakan Python yang telah terpasang pada komputer.

Frontend menggunakan koneksi ke node Hardhat lokal. Pastikan RPC, Chain ID, alamat kontrak, dan akun yang dipilih sesuai dengan deployment serta hak akses yang diperlukan.

Untuk pengujian penerbitan, gunakan akun issuer yang terdaftar. Akun yang tidak memiliki role issuer seharusnya ditolak ketika memanggil fungsi penerbitan.

## 10. Skenario Demonstrasi

Lakukan pengujian menggunakan data dummy dan simpan bukti aktual.

1. **Issue credential:** terbitkan kredensial menggunakan issuer yang berwenang.
2. **Read record:** baca record berdasarkan Credential ID.
3. **Verify credential:** cocokkan Credential ID dan root, lalu periksa status kredensial.
4. **Suspend:** ubah status kredensial menjadi suspended.
5. **Reinstate:** aktifkan kembali kredensial yang memenuhi aturan kontrak.
6. **Revoke:** cabut kredensial sesuai aturan kontrak.
7. **Unauthorized access:** coba melakukan aksi yang membutuhkan izin menggunakan akun yang tidak berwenang dan pastikan transaksi ditolak.

Untuk setiap operasi yang berhasil, catat transaction hash jika tersedia. Simpan screenshot yang menunjukkan hasil operasi dan status kredensial.

Penolakan transaksi seperti `bukan penerbit` merupakan perilaku yang diharapkan apabila akun tidak memiliki izin issuer, bukan otomatis merupakan bug kontrak.

## 11. Bukti Pengujian dan Deployment

Kumpulkan bukti yang relevan dalam folder `bukti_pengujian/`, antara lain:

- Output instalasi dependensi.
- Output kompilasi.
- Output unit test.
- Bukti debugging dan hasil pengujian ulang.
- Output deployment lokal.
- `deployment-record.json`.
- Record deployment frontend jika menggunakan deployment terpisah.
- Transaction hash dari operasi perubahan state yang berhasil.
- Screenshot demonstrasi Issue, Verify, perubahan status, dan penolakan akses.

Pastikan bukti dari deployment berbeda tidak digabungkan seolah-olah berasal dari kontrak yang sama.

## 12. Keamanan dan Batasan

- Project ini merupakan prototipe dan pengujian lokal, bukan layanan produksi.
- Data kredensial yang digunakan untuk demonstrasi harus berupa data dummy.
- Jangan menyimpan data pribadi sensitif secara langsung pada blockchain.
- Jangan memasukkan private key atau seed phrase akun pribadi.
- Jangan menggunakan dana atau aset kripto nyata.
- Deployment lokal bukan bukti bahwa kontrak sudah berjalan pada public testnet atau mainnet.
- Pengujian unit bukan pengganti audit keamanan independen.

## 13. Ringkasan Luaran

### Project 1

- Diagram arsitektur dan alur transaksi.
- Source code smart contract Solidity.
- Dokumen desain model data, kontrol akses, dan keputusan on-chain/off-chain.

### Project 2

- Folder unit test dan hasil pengujian.
- Deployment record dan bukti transaksi dari jaringan lokal.
- Frontend/client atau script integrasi.
- README instalasi dan reproduksi.

## 14. Reproduksi Singkat

Urutan dasar untuk mengulang pengujian adalah:

1. Jalankan `npm install`.
2. Jalankan `npm run compile`.
3. Jalankan `npm test`.
4. Jalankan `npm run node` pada terminal pertama.
5. Jalankan `npm run deploy:local` pada terminal kedua.
6. Jalankan server frontend pada terminal ketiga.
7. Buka `http://127.0.0.1:8080`.
8. Uji operasi yang relevan dan simpan hasil aktual.
