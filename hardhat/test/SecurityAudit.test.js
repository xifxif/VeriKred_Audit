// Unit test verifikasi temuan audit keamanan VeriKred (CredentialRegistry).
// Setiap blok describe() memetakan satu ID temuan pada laporan audit.
// Pada kode SEBELUM perbaikan (tag git `audit-baseline`) tes bertanda "VULNERABLE" GAGAL
// karena transaksi berbahaya berhasil dieksekusi; pada kode SESUDAH perbaikan semuanya LULUS.
const { expect } = require("chai");
const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

describe("Security audit — CredentialRegistry", function () {
  let registry, gov, issuer, issuer2, outsider, addr;
  const hash = (s) => ethers.keccak256(ethers.toUtf8Bytes(s));
  const root = hash("merkle-root-demo");
  const root2 = hash("merkle-root-demo-2");
  const binding = hash("holder-binding-demo");

  // credId = [20 byte alamat penerbit][12 byte ID lokal]  (lihat F-03)
  const cid = (signer, label) =>
    ethers.hexlify(ethers.concat([signer.address, ethers.dataSlice(hash(label), 0, 12)]));

  // Pastikan pemanggilan (eth_call/staticCall) di-revert. Bila berhasil => celah terbukti.
  async function mustFail(fn, msg) {
    let succeeded = true;
    try { await fn(); } catch (e) { succeeded = false; }
    expect(succeeded, "VULNERABLE: " + msg).to.equal(false);
  }

  const now = async () => (await ethers.provider.getBlock("latest")).timestamp;

  beforeEach(async function () {
    [gov, issuer, issuer2, outsider] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("CredentialRegistry");
    registry = await Factory.deploy(gov.address);
    await registry.waitForDeployment();
    addr = await registry.getAddress();
    await registry.connect(gov).setIssuer(issuer.address, true);
    await registry.connect(gov).setIssuer(issuer2.address, true);
  });

  // ---------------------------------------------------------------------------
  describe("F-01 Access control: penerbit yang dicabut izinnya masih bisa menulis state", function () {
    it("VULNERABLE: penerbit non-aktif tidak boleh supersede (mencetak kredensial baru)", async () => {
      const oldId = cid(issuer, "old"), newId = cid(issuer, "new");
      await registry.connect(issuer).issue(oldId, root, binding, 0);
      await registry.connect(gov).setIssuer(issuer.address, false);

      const call = () => registry.connect(issuer).supersede.staticCall(oldId, newId, root2, binding, 0);
      await mustFail(call, "penerbit yang dicabut dapat mencetak kredensial baru lewat supersede()");
      await expect(call()).to.be.revertedWith("bukan penerbit");
    });

    it("VULNERABLE: penerbit non-aktif tidak boleh reinstate maupun rebind", async () => {
      const id = cid(issuer, "c1"), id2 = cid(issuer, "c2");
      await registry.connect(issuer).issue(id, root, binding, 0);
      await registry.connect(issuer).issue(id2, root, binding, 0);
      await registry.connect(issuer).suspend(id2);
      await registry.connect(gov).setIssuer(issuer.address, false);

      const re = () => registry.connect(issuer).reinstate.staticCall(id2);
      await mustFail(re, "penerbit yang dicabut dapat mengaktifkan kembali kredensial yang di-suspend");
      await expect(re()).to.be.revertedWith("bukan penerbit");

      const rb = () => registry.connect(issuer).rebind.staticCall(id, hash("attacker-key"));
      await mustFail(rb, "penerbit yang dicabut dapat memindahkan holderBinding");
      await expect(rb()).to.be.revertedWith("bukan penerbit");
    });

    it("fail-safe: penerbit non-aktif TETAP boleh suspend dan revoke kredensialnya sendiri", async () => {
      const id = cid(issuer, "c1"), id2 = cid(issuer, "c2");
      await registry.connect(issuer).issue(id, root, binding, 0);
      await registry.connect(issuer).issue(id2, root, binding, 0);
      await registry.connect(gov).setIssuer(issuer.address, false);
      await registry.connect(issuer).suspend(id);
      await registry.connect(issuer).revoke(id2);
      expect((await registry.check(id, root))[1]).to.equal(2n);
      expect((await registry.check(id2, root))[1]).to.equal(3n);
    });
  });

  // ---------------------------------------------------------------------------
  describe("F-02 Access control: penerbit yang ditandai kompromi masih bisa mengubah kredensial lama", function () {
    let preId, suspendedId;
    beforeEach(async () => {
      preId = cid(issuer, "pre-compromise");
      suspendedId = cid(issuer, "suspended");
      await registry.connect(issuer).issue(preId, root, binding, 0);
      await registry.connect(issuer).issue(suspendedId, root, binding, 0);
      await registry.connect(issuer).suspend(suspendedId);
      // kompromi dimulai SETELAH kedua kredensial diterbitkan => keduanya tidak "tainted"
      await registry.connect(gov).markIssuerCompromised(issuer.address, (await now()) + 1);
    });

    it("kredensial pra-kompromi tetap valid (itulah sebabnya kunci bocor berbahaya)", async () => {
      expect((await registry.check(preId, root))[0]).to.equal(true);
    });

    it("VULNERABLE: rebind() oleh kunci terkompromi harus ditolak (pengambilalihan holder)", async () => {
      const call = () => registry.connect(issuer).rebind.staticCall(preId, hash("attacker-key"));
      await mustFail(call, "kunci penerbit bocor dapat mengganti holderBinding kredensial yang masih valid");
      await expect(call()).to.be.revertedWithCustomError(registry, "IssuerIsCompromised");
    });

    it("VULNERABLE: reinstate() oleh kunci terkompromi harus ditolak", async () => {
      const call = () => registry.connect(issuer).reinstate.staticCall(suspendedId);
      await mustFail(call, "kunci bocor dapat mengaktifkan kembali kredensial yang di-suspend");
      await expect(call()).to.be.revertedWithCustomError(registry, "IssuerIsCompromised");
    });

    it("VULNERABLE: issue() dan supersede() oleh penerbit terkompromi harus ditolak", async () => {
      const i = () => registry.connect(issuer).issue.staticCall(cid(issuer, "x"), root, binding, 0);
      await mustFail(i, "penerbit terkompromi masih dapat menerbitkan");
      await expect(i()).to.be.revertedWithCustomError(registry, "IssuerIsCompromised");
      const s = () => registry.connect(issuer).supersede.staticCall(preId, cid(issuer, "y"), root2, binding, 0);
      await mustFail(s, "penerbit terkompromi masih dapat supersede");
      await expect(s()).to.be.revertedWithCustomError(registry, "IssuerIsCompromised");
    });

    it("fail-safe: penerbit terkompromi tetap dapat suspend/revoke (arah aman)", async () => {
      await registry.connect(issuer).suspend(preId);
      await registry.connect(issuer).revoke(preId);
      expect((await registry.check(preId, root))[1]).to.equal(3n);
    });
  });

  // ---------------------------------------------------------------------------
  describe("F-03 Front-running / transaction ordering: pembajakan kepemilikan credId", function () {
    it("VULNERABLE: penerbit lain tidak boleh menyalin (id, root, binding) dari mempool", async () => {
      const id = cid(issuer, "student-123");
      // Penyerang (penerbit terdaftar lain) menyalin parameter transaksi korban dan menang urutan.
      const frontrun = () => registry.connect(issuer2).issue.staticCall(id, root, binding, 0);
      await mustFail(frontrun, "penyerang dapat mengambil kepemilikan credId milik penerbit lain");
      await expect(frontrun()).to.be.revertedWithCustomError(registry, "InvalidCredentialId");

      // Transaksi sah milik korban tetap berhasil dan korban menjadi pemilik.
      await registry.connect(issuer).issue(id, root, binding, 0);
      expect((await registry.get(id)).issuer).to.equal(issuer.address);
    });

    it("credId tanpa prefix alamat penerbit ditolak", async () => {
      await expect(registry.connect(issuer).issue(hash("tanpa-prefix"), root, binding, 0))
        .to.be.revertedWithCustomError(registry, "InvalidCredentialId");
      await expect(registry.connect(issuer).issue(ethers.ZeroHash, root, binding, 0))
        .to.be.revertedWithCustomError(registry, "InvalidCredentialId");
    });

    it("supersede() juga mewajibkan newId berprefix penerbit", async () => {
      const oldId = cid(issuer, "a");
      await registry.connect(issuer).issue(oldId, root, binding, 0);
      await expect(registry.connect(issuer).supersede(oldId, cid(issuer2, "b"), root2, binding, 0))
        .to.be.revertedWithCustomError(registry, "InvalidCredentialId");
      // atomik: kredensial lama tidak berubah bila supersede gagal
      expect((await registry.check(oldId, root))[0]).to.equal(true);
    });

    it("helper credentialId() konsisten dengan format off-chain", async () => {
      const local = ethers.dataSlice(hash("student-123"), 0, 12);
      expect(await registry.credentialId(issuer.address, local)).to.equal(cid(issuer, "student-123"));
    });
  });

  // ---------------------------------------------------------------------------
  describe("F-04 Validasi input", function () {
    it("VULNERABLE: expiry yang sudah lewat ditolak pada issue()", async () => {
      const t = await now();
      for (const exp of [1, t - 10, t]) {
        const call = () => registry.connect(issuer).issue.staticCall(cid(issuer, "e" + exp), root, binding, exp);
        await mustFail(call, "kredensial dengan expiry di masa lalu diterima (mati sejak lahir): " + exp);
        await expect(call()).to.be.revertedWithCustomError(registry, "InvalidExpiry");
      }
      // 0 (tanpa kedaluwarsa) dan masa depan tetap diterima
      await registry.connect(issuer).issue(cid(issuer, "ok0"), root, binding, 0);
      await registry.connect(issuer).issue(cid(issuer, "ok1"), root, binding, t + 1000);
    });

    it("VULNERABLE: expiry masa lalu ditolak pada supersede()", async () => {
      const oldId = cid(issuer, "old");
      await registry.connect(issuer).issue(oldId, root, binding, 0);
      const call = () => registry.connect(issuer).supersede.staticCall(oldId, cid(issuer, "new"), root2, binding, 1);
      await mustFail(call, "supersede menerima expiry masa lalu");
      await expect(call()).to.be.revertedWithCustomError(registry, "InvalidExpiry");
    });

    it("VULNERABLE: holderBinding nol ditolak pada issue(), supersede() dan rebind()", async () => {
      const id = cid(issuer, "b0");
      const i = () => registry.connect(issuer).issue.staticCall(id, root, ethers.ZeroHash, 0);
      await mustFail(i, "binding nol diterima pada issue");
      await expect(i()).to.be.revertedWithCustomError(registry, "InvalidBinding");

      await registry.connect(issuer).issue(id, root, binding, 0);
      const s = () => registry.connect(issuer).supersede.staticCall(id, cid(issuer, "b1"), root2, ethers.ZeroHash, 0);
      await mustFail(s, "binding nol diterima pada supersede");
      await expect(s()).to.be.revertedWithCustomError(registry, "InvalidBinding");

      const r = () => registry.connect(issuer).rebind.staticCall(id, ethers.ZeroHash);
      await mustFail(r, "binding nol diterima pada rebind");
      await expect(r()).to.be.revertedWithCustomError(registry, "InvalidBinding");
    });

    it("VULNERABLE: setIssuer(address(0)) ditolak", async () => {
      const call = () => registry.connect(gov).setIssuer.staticCall(ethers.ZeroAddress, true);
      await mustFail(call, "alamat nol dapat didaftarkan sebagai penerbit");
      await expect(call()).to.be.revertedWith("issuer=0");
    });

    it("root nol tetap ditolak dan supersede ke id yang sama ditolak", async () => {
      await expect(registry.connect(issuer).issue(cid(issuer, "z"), ethers.ZeroHash, binding, 0))
        .to.be.revertedWith("root=0");
      const id = cid(issuer, "same");
      await registry.connect(issuer).issue(id, root, binding, 0);
      await expect(registry.connect(issuer).supersede(id, id, root2, binding, 0))
        .to.be.revertedWithCustomError(registry, "AlreadyExists");
      expect((await registry.check(id, root))[0]).to.equal(true); // rollback atomik
    });
  });

  // ---------------------------------------------------------------------------
  describe("F-05 Governance: event & transisi dua langkah", function () {
    it("VULNERABLE: alih governance memancarkan event dan membersihkan pending", async () => {
      await expect(registry.connect(gov).transferGovernance(outsider.address))
        .to.emit(registry, "GovernanceTransferStarted").withArgs(gov.address, outsider.address);
      await expect(registry.connect(outsider).acceptGovernance())
        .to.emit(registry, "GovernanceTransferred").withArgs(gov.address, outsider.address);
      expect(await registry.governance()).to.equal(outsider.address);
      expect(await registry.pendingGovernance()).to.equal(ethers.ZeroAddress);
      await expect(registry.connect(gov).setIssuer(gov.address, true))
        .to.be.revertedWithCustomError(registry, "NotGovernance");
    });

    it("pihak selain pending tidak dapat accept; transfer dapat dibatalkan dengan address(0)", async () => {
      await registry.connect(gov).transferGovernance(outsider.address);
      await expect(registry.connect(issuer).acceptGovernance()).to.be.revertedWith("bukan pending");
      await registry.connect(gov).transferGovernance(ethers.ZeroAddress);
      await expect(registry.connect(outsider).acceptGovernance()).to.be.revertedWith("bukan pending");
    });
  });

  // ---------------------------------------------------------------------------
  describe("F-06 Konfigurasi kompilator", function () {
    it("VULNERABLE: pragma dikunci ke 0.8.26 (bukan floating ^)", () => {
      const src = fs.readFileSync(path.join(__dirname, "..", "contracts", "CredentialRegistry.sol"), "utf8");
      expect(src).to.match(/pragma solidity 0\.8\.26;/);
      expect(src).to.not.match(/pragma solidity \^/);
    });
  });

  // ---------------------------------------------------------------------------
  describe("Pengujian properti: reentrancy, DoS, ETH (tidak ada temuan; bukti negatif)", function () {
    it("tidak ada permukaan reentrancy: tanpa call eksternal, payable, receive, fallback", async () => {
      const src = fs.readFileSync(path.join(__dirname, "..", "contracts", "CredentialRegistry.sol"), "utf8")
        .replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
      for (const forbidden of [/\.call\s*[({]/, /delegatecall/, /staticcall/, /selfdestruct/, /\.transfer\s*\(/, /\.send\s*\(/, /payable/]) {
        expect(src).to.not.match(forbidden);
      }
      expect(registry.interface.receive).to.equal(false);
      expect(registry.interface.fallback).to.equal(null);
      await expect(gov.sendTransaction({ to: addr, value: 1n })).to.be.reverted;
      await expect(gov.sendTransaction({ to: addr, data: "0x12345678" })).to.be.reverted;
    });

    it("tidak ada DoS state-growth: biaya gas operasi tidak bergantung jumlah kredensial", async () => {
      const first = cid(issuer, "first");
      await registry.connect(issuer).issue(first, root, binding, 0);
      const g1 = (await (await registry.connect(issuer).suspend(first)).wait()).gasUsed;
      for (let i = 0; i < 60; i++) await registry.connect(issuer).issue(cid(issuer, "bulk" + i), root, binding, 0);
      const last = cid(issuer, "last");
      await registry.connect(issuer).issue(last, root, binding, 0);
      const g2 = (await (await registry.connect(issuer).suspend(last)).wait()).gasUsed;
      expect(Number(g2)).to.be.closeTo(Number(g1), 300);
    });

    it("tidak ada ketergantungan oracle eksternal: check() hanya memakai state + block.timestamp", async () => {
      const t = await now();
      const id = cid(issuer, "ts");
      await registry.connect(issuer).issue(id, root, binding, t + 100);
      expect((await registry.check(id, root))[0]).to.equal(true);
      await ethers.provider.send("evm_setNextBlockTimestamp", [t + 200]);
      await ethers.provider.send("evm_mine", []);
      expect((await registry.check(id, root))[0]).to.equal(false);
    });
  });
});
