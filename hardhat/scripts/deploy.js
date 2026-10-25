const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  const Factory = await hre.ethers.getContractFactory("CredentialRegistry");
  // [R-01] Produksi: set GOVERNANCE_ADDRESS ke multisig/timelock. Default (deployer) hanya untuk demo lokal.
  const governance = process.env.GOVERNANCE_ADDRESS || deployer.address;
  if (!hre.ethers.isAddress(governance)) throw new Error("GOVERNANCE_ADDRESS tidak valid");
  if (hre.network.name !== "localhost" && hre.network.name !== "hardhat" && governance === deployer.address) {
    throw new Error("Jaringan non-lokal: wajib set GOVERNANCE_ADDRESS (multisig/timelock), bukan EOA deployer.");
  }
  const contract = await Factory.deploy(governance);
  const tx = contract.deploymentTransaction();
  await contract.waitForDeployment();
  const address = await contract.getAddress();
  const network = await hre.ethers.provider.getNetwork();
  const receipt = await hre.ethers.provider.getTransactionReceipt(tx.hash);
  const record = {
    contractName: "CredentialRegistry",
    network: hre.network.name,
    chainId: network.chainId.toString(),
    rpcUrl: hre.network.name === "localhost" ? "http://127.0.0.1:8545" : "Hardhat in-process network",
    deployer: deployer.address,
    governance,
    contractAddress: address,
    deploymentTransactionHash: tx.hash,
    deploymentBlockNumber: receipt.blockNumber,
    compiler: "solc 0.8.26",
    contractVersion: "v2 (post-audit)",
    timestampUTC: new Date().toISOString(),
    note: "Local test deployment; replace this record only with values from an actual run. Never use real funds or production keys."
  };
  const out = path.join(__dirname, "..", "deployment-record.json");
  fs.writeFileSync(out, JSON.stringify(record, null, 2) + "\n");
  console.log(JSON.stringify(record, null, 2));
}
main().catch((e) => { console.error(e); process.exitCode = 1; });
