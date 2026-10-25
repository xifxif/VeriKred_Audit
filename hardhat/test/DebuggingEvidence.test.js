const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Debugging evidence - VeriKred", function () {
  it("detects an incorrect expected governance address", async function () {
    const [gov] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("CredentialRegistry");
    const registry = await Factory.deploy(gov.address);
    await registry.waitForDeployment();

    // DEBUG EXPERIMENT: intentionally incorrect expectation.
    expect(await registry.governance()).to.equal(gov.address);
  });
});

