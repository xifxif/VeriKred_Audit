# Status Project 1 dan Project 2

## Project 1 — Desain solusi, smart contract, arsitektur DApp
- [x] Use case VeriKred dan aktor utama dijelaskan.
- [x] Aset/data on-chain dan off-chain dipisahkan.
- [x] Role, aturan bisnis, siklus status, serta trade-off dijelaskan.
- [x] Diagram arsitektur tersedia di `architecture.svg`.
- [x] Source contract Solidity tersedia pada `CredentialRegistry.sol` dan salinan di `hardhat/contracts/`.
- [ ] Mahasiswa perlu menyesuaikan identitas/kelas pada dokumen pengumpulan bila diperlukan.

## Project 2 — Testing, debugging, deployment, integrasi
- [x] Unit test Hardhat ditulis untuk skenario positif, negatif, status/batas, dan kontrol akses.
- [x] Script deployment local node ditulis; menghasilkan record dari transaksi aktual.
- [x] Client MetaMask dapat membaca record, memverifikasi root/status, dan mengirim issue/suspend/reinstate/revoke jika akun memiliki role yang tepat.
- [ ] Jalankan `npm install`, `npm run compile`, `npm test` dan simpan output aktual.
- [ ] Jalankan node lokal dan `npm run deploy:local`; simpan `deployment-record.json` yang benar-benar dihasilkan.
- [ ] Jalankan demo client, catat minimal satu transaction hash dari perubahan state, serta ambil screenshot/log nyata.

**Penting:** paket ini menyiapkan kode dan dokumen. Deployment record, transaction hash, dan hasil test Hardhat belum diklaim sebagai hasil eksekusi karena perlu dijalankan di lingkungan pengguna. Hasil EVM in-memory yang ada di paket lama bukan pengganti deployment node lokal.
