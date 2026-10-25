const solc = require('solc'); const fs = require('fs');
const src = fs.readFileSync('../CredentialRegistry.sol','utf8');
const input = {language:'Solidity',sources:{'CredentialRegistry.sol':{content:src}},
 settings:{outputSelection:{'*':{'*':['abi','evm.bytecode.object']}}}};
const out = JSON.parse(solc.compile(JSON.stringify(input)));
const errs = (out.errors||[]);
console.log('solc', solc.version());
errs.forEach(e=>console.log(e.severity.toUpperCase()+':', e.formattedMessage.split('\n')[0]));
const c = out.contracts && out.contracts['CredentialRegistry.sol'] && out.contracts['CredentialRegistry.sol'].CredentialRegistry;
if (c) { console.log('COMPILED OK; abi entries:', c.abi.length, '; bytecode bytes:', c.evm.bytecode.object.length/2);
  fs.writeFileSync('abi.json', JSON.stringify(c.abi,null,1)); fs.writeFileSync('bytecode.json', JSON.stringify(c.evm.bytecode.object)); }
else console.log('COMPILE FAILED');
