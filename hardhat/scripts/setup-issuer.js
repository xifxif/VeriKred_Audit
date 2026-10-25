// Mendaftarkan akun penerbit demo (signer index 1) ke kontrak yang SUDAH di-deploy.
// Membaca alamat dari deployment-record.json (hasil `npm run deploy:local`).
// Governance = signer index 0 (harus sama dengan governance saat deploy).
// Hanya untuk node lokal Hardhat: akun uji publik, JANGAN dipakai di jaringan nyata.
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  if (hre.network.name !== "localhost" && hre.network.name !== "hardhat") {
    throw new Error("Script ini hanya untuk jaringan lokal.");
  }
  const recPath = path.join(__dirname, "..", "deployment-record.json");
  const rec = JSON.parse(fs.readFileSync(recPath, "utf8"));
  const [gov, issuer] = await hre.ethers.getSigners();
  const registry = await hre.ethers.getContractAt("CredentialRegistry", rec.contractAddress);
  if ((await registry.governance()).toLowerCase() !== gov.address.toLowerCase()) {
    throw new Error("Signer index 0 bukan governance kontrak ini.");
  }
  const tx = await registry.connect(gov).setIssuer(issuer.address, true);
  const receipt = await tx.wait();
  const out = {
    action: "setIssuer(true)",
    contractAddress: rec.contractAddress,
    governance: gov.address,
    issuer: issuer.address,
    transactionHash: receipt.hash,
    blockNumber: receipt.blockNumber,
    status: receipt.status === 1 ? "SUCCESS" : "FAILED",
    isIssuerNow: await registry.isIssuer(issuer.address),
    timestampUTC: new Date().toISOString()
  };
  fs.writeFileSync(path.join(__dirname, "..", "setup-issuer-record.json"), JSON.stringify(out, null, 2) + "\n");
  console.log(JSON.stringify(out, null, 2));
}
main().catch((e) => { console.error(e); process.exitCode = 1; });
