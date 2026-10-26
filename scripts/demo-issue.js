const { ethers } = require("hardhat");

async function main() {
  const [gov, issuer, issuer2, verifier, outsider] = await ethers.getSigners();

  const Factory = await ethers.getContractFactory("CredentialRegistry");
  const registry = await Factory.deploy(gov.address);
  await registry.waitForDeployment();

  await (await registry.connect(gov).setIssuer(issuer.address, true)).wait();

  const hash = (s) => ethers.keccak256(ethers.toUtf8Bytes(s));
  const id = hash("VeriKred-UAS-Demo-001");
  const root = hash("VeriKred-Merkle-Root-Demo-001");
  const binding = hash("VeriKred-Holder-Binding-Demo-001");

  const tx = await registry.connect(issuer).issue(id, root, binding, 0);
  const receipt = await tx.wait();

  const [valid, status] = await registry.connect(verifier).check(id, root);
  const credential = await registry.get(id);

  console.log("\n=== VERIKRED ISSUE DEMO ===");
  console.log("Network:", (await ethers.provider.getNetwork()).name);
  console.log("Chain ID:", (await ethers.provider.getNetwork()).chainId.toString());
  console.log("Contract address:", await registry.getAddress());
  console.log("Issuer:", issuer.address);
  console.log("Credential ID:", id);
  console.log("Root:", root);
  console.log("Transaction hash:", receipt.hash);
  console.log("Block number:", receipt.blockNumber);
  console.log("Transaction status:", receipt.status === 1 ? "SUCCESS" : "FAILED");
  console.log("Issued event:", receipt.logs.some((log) => {
    try {
      return registry.interface.parseLog(log)?.name === "Issued";
    } catch {
      return false;
    }
  }));
  console.log("Verification valid:", valid);
  console.log("Credential status:", status.toString());
  console.log("Stored issuer:", credential.issuer);
  console.log("Stored root:", credential.root);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
