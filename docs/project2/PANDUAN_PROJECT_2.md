# PROJECT 2 — Testing, Debugging, Deployment, dan Integrasi

## Status artefak saat ini

Paket awal memiliki 16 uji simulasi Python dan 15 uji kontrak melalui `@ethereumjs/vm` in-memory. Pengujian in-memory bukan deployment node blockchain yang persisten. Karena itu Project 2 dilengkapi dengan proyek Hardhat yang menyediakan compile, unit test pada EVM Hardhat, node lokal, script deployment, catatan deployment yang dihasilkan dari run nyata, dan frontend/client berbasis MetaMask.

## A. Instalasi

Prasyarat: Node.js 18 atau lebih baru dan npm.

```bash
cd hardhat
npm install
```

## B. Compile

```bash
npm run compile
```

Kriteria: kontrak `CredentialRegistry.sol` berhasil dikompilasi menggunakan solc 0.8.26. Jika gagal, simpan terminal output, periksa versi Node/npm, lalu jalankan `npm install` ulang.

## C. Unit test

```bash
npm test
```

Suite menguji deployment/governance, penerbitan sah, penerbit tak terdaftar, root nol, duplikasi ID, root tidak cocok, akses penerbit, siklus status, transisi tidak valid, supersede, alih governance, expiry/kompromi penerbit, dan rebind. Catat hasil aktual dari terminal; jangan mengubah FAIL menjadi PASS di laporan.

## D. Jalankan node lokal dan deploy

Terminal 1:

```bash
cd hardhat
npm run node
```

Terminal 2:

```bash
cd hardhat
npm run deploy:local
```

Script menghasilkan `hardhat/deployment-record.json` berisi network, chain ID, deployer, contract address, transaction hash, block number, compiler, dan timestamp dari eksekusi aktual. Alamat/hash tidak boleh diisi manual atau direka. Catatan ini hanya berlaku untuk sesi node lokal tersebut; setelah node dimulai ulang, deployment lama bisa hilang.

## E. Integrasi client

1. Pastikan node Hardhat berjalan di `http://127.0.0.1:8545`.
2. Tambahkan network lokal di MetaMask: RPC `http://127.0.0.1:8545`, chain ID `31337`, mata uang `ETH`.
3. Impor akun pengujian Hardhat hanya untuk pengembangan lokal. Jangan gunakan akun pribadi, seed phrase utama, atau dana nyata.
4. Buka `hardhat/frontend/index.html` melalui server lokal sederhana, misalnya `npx http-server frontend -p 8080` dari folder `hardhat` (atau ekstensi Live Server).
5. Masukkan alamat kontrak dari `deployment-record.json`, lalu Connect MetaMask.
6. Untuk uji baca, gunakan `credId` dan `root` bytes32 yang dibuat dengan data dummy. Verifier client menunjukkan status dan validitas jangkar. Client demo ini belum menyediakan form penerbitan; transaksi penerbitan/status diuji lewat unit test dan dapat ditambahkan sebagai tahap lanjutan.

Contoh membuat hash bytes32 di console Node dari folder `hardhat`:

```bash
node -e "const {keccak256,toUtf8Bytes}=require('ethers'); console.log('credId:',keccak256(toUtf8Bytes('demo-credential-1'))); console.log('root:',keccak256(toUtf8Bytes('demo-merkle-root-1')))"
```

## F. Bukti event dan perubahan state

Unit test memeriksa event `Issued`, `StatusChanged`, dan `HolderRebound`. Untuk demo langsung, terbitkan kredensial pada akun penerbit yang terdaftar, simpan transaction hash dari receipt, kemudian panggil `check` dengan ID/root yang sama. Catat hasil sebelum dan sesudah `suspend` atau `revoke`. Event yang diuji pada unit test merupakan bukti test; transaction hash dari local node harus direkam terpisah untuk bukti deployment/demonstrasi.

## G. Debugging yang perlu didokumentasikan

Gunakan kasus negatif `issue()` oleh akun yang belum terdaftar atau root nol. Expected result adalah revert (`bukan penerbit` atau `root=0`). Simpan:
- command yang dijalankan;
- pesan revert dari terminal;
- fungsi/require yang menyebabkan revert;
- perbaikan jika ada;
- hasil pengujian ulang.

Jangan menyebutnya sebagai bug kontrak bila revert merupakan perilaku yang memang diharapkan oleh aturan bisnis. Ini adalah demonstrasi debugging/penanganan kondisi tidak valid.

## H. Template deployment record

`deployment-record.json` dibuat otomatis saat script deployment dijalankan. Jika belum ada file tersebut, deployment belum dibuktikan. Sertakan file itu, log terminal, dan minimal satu transaction hash dari operasi state-changing yang berhasil. Jangan mengisi data contoh seolah-olah berasal dari deployment nyata.

## I. Batasan dan checklist sebelum dikumpulkan

- [ ] `npm run compile` sukses pada komputer yang digunakan.
- [ ] `npm test` sukses; jumlah pass/fail dicatat dari output aktual.
- [ ] Node lokal berjalan dan `deployment-record.json` dibuat.
- [ ] Contract address dan transaction hash cocok dengan node yang aktif.
- [ ] Frontend tersambung melalui MetaMask dan membaca status.
- [ ] Ada satu event dan perubahan state yang didemonstrasikan.
- [ ] Screenshot/log terminal menunjukkan bukti aktual, bukan gambar rekayasa.
- [ ] `deployment-record.json`, akun uji, dan chain ID dijelaskan di README final.
- [ ] Private key/seed phrase tidak di-commit dan tidak menggunakan dana nyata.
