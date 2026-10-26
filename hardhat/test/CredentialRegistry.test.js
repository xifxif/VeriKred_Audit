const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("CredentialRegistry — Project 2 tests", function () {
  let registry, gov, issuer, issuer2, verifier, outsider;
  const hash = (s) => ethers.keccak256(ethers.toUtf8Bytes(s));
  const root = hash("merkle-root-demo");
  const binding = hash("holder-binding-demo");

  beforeEach(async function () {
    [gov, issuer, issuer2, verifier, outsider] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("CredentialRegistry");
    registry = await Factory.deploy(gov.address);
    await registry.waitForDeployment();
    await registry.connect(gov).setIssuer(issuer.address, true);
    await registry.connect(gov).setIssuer(issuer2.address, true);
  });

  it("deploys with governance set to deployer", async () => {
    expect(await registry.governance()).to.equal(gov.address);
  });

  it("allows registered issuer to issue and emits Issued", async () => {
    const id = hash("credential-1");
    await expect(registry.connect(issuer).issue(id, root, binding, 0))
      .to.emit(registry, "Issued").withArgs(id, issuer.address, root, 0);
    const [valid, status] = await registry.connect(verifier).check(id, root);
    expect(valid).to.equal(true);
    expect(status).to.equal(1); // ACTIVE
  });

  it("rejects issue from unregistered account", async () => {
    await expect(registry.connect(outsider).issue(hash("fake"), root, binding, 0))
      .to.be.revertedWith("bukan penerbit");
  });

  it("rejects zero root and duplicate credential ID", async () => {
    await expect(registry.connect(issuer).issue(hash("zero"), ethers.ZeroHash, binding, 0))
      .to.be.revertedWith("root=0");
    const id = hash("duplicate");
    await registry.connect(issuer).issue(id, root, binding, 0);
    await expect(registry.connect(issuer).issue(id, root, binding, 0))
      .to.be.revertedWithCustomError(registry, "AlreadyExists");
  });

  it("returns invalid for a mismatched root", async () => {
    const id = hash("wrong-root");
    await registry.connect(issuer).issue(id, root, binding, 0);
    const [valid] = await registry.check(id, hash("different-root"));
    expect(valid).to.equal(false);
  });

  it("enforces issuer ownership for revoke", async () => {
    const id = hash("ownership");
    await registry.connect(issuer).issue(id, root, binding, 0);
    await expect(registry.connect(issuer2).revoke(id))
      .to.be.revertedWithCustomError(registry, "NotIssuerOf");
  });

  it("supports suspend and reinstate, then revoke is final", async () => {
    const id = hash("lifecycle");
    await registry.connect(issuer).issue(id, root, binding, 0);
    await registry.connect(issuer).suspend(id);
    expect((await registry.check(id, root))[0]).to.equal(false);
    await registry.connect(issuer).reinstate(id);
    expect((await registry.check(id, root))[0]).to.equal(true);
    await registry.connect(issuer).revoke(id);
    await expect(registry.connect(issuer).reinstate(id))
      .to.be.revertedWithCustomError(registry, "InvalidTransition");
  });

  it("rejects invalid state transition", async () => {
    const id = hash("transition");
    await registry.connect(issuer).issue(id, root, binding, 0);
    await expect(registry.connect(issuer).reinstate(id))
      .to.be.revertedWithCustomError(registry, "InvalidTransition");
  });

  it("supports superseding an old credential", async () => {
    const oldId = hash("old-version"), newId = hash("new-version"), newRoot = hash("new-root");
    await registry.connect(issuer).issue(oldId, root, binding, 0);
    await expect(registry.connect(issuer).supersede(oldId, newId, newRoot, binding, 0))
      .to.emit(registry, "StatusChanged").withArgs(oldId, 4);
    expect((await registry.check(oldId, root))[0]).to.equal(false);
    expect((await registry.check(newId, newRoot))[0]).to.equal(true);
  });

  it("rejects governance action from outsider and permits two-step transfer", async () => {
    await expect(registry.connect(outsider).setIssuer(outsider.address, true))
      .to.be.revertedWithCustomError(registry, "NotGovernance");
    await registry.connect(gov).transferGovernance(outsider.address);
    await expect(registry.connect(gov).acceptGovernance()).to.be.revertedWith("bukan pending");
    await registry.connect(outsider).acceptGovernance();
    expect(await registry.governance()).to.equal(outsider.address);
  });

  it("checks expiry and compromised issuer time", async function () {
    const latest = await ethers.provider.getBlock("latest");
    const expiry = BigInt(latest.timestamp + 3600);
    const expId = hash("expires");
    await registry.connect(issuer).issue(expId, root, binding, expiry);
    expect((await registry.check(expId, root))[0]).to.equal(true);
    await ethers.provider.send("evm_setNextBlockTimestamp", [Number(expiry + 1n)]);
    await ethers.provider.send("evm_mine", []);
    expect((await registry.check(expId, root))[0]).to.equal(false);

    const compromisedId = hash("compromised");
    const nowBlock = await ethers.provider.getBlock("latest");
    await registry.connect(issuer).issue(compromisedId, root, binding, 0);
    const issued = await registry.get(compromisedId);
    await registry.connect(gov).markIssuerCompromised(issuer.address, issued.issuedAt);
    expect((await registry.check(compromisedId, root))[0]).to.equal(false);
  });

  it("rebinds holder binding only through credential issuer", async function () {
    const id = hash("rebind"); const nextBinding = hash("new-holder");
    await registry.connect(issuer).issue(id, root, binding, 0);
    await expect(registry.connect(outsider).rebind(id, nextBinding))
      .to.be.revertedWithCustomError(registry, "NotIssuerOf");
    await expect(registry.connect(issuer).rebind(id, nextBinding))
      .to.emit(registry, "HolderRebound").withArgs(id, nextBinding);
    expect((await registry.get(id)).holderBinding).to.equal(nextBinding);
  });
});
