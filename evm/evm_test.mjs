import { VM } from '@ethereumjs/vm';
import { Common, Chain, Hardfork } from '@ethereumjs/common';
import { Address, hexToBytes, bytesToHex } from '@ethereumjs/util';
import { Block } from '@ethereumjs/block';
import { Interface, keccak256, toUtf8Bytes, ZeroHash } from 'ethers';
import fs from 'fs';

const abi = JSON.parse(fs.readFileSync('abi.json','utf8'));
const bytecode = JSON.parse(fs.readFileSync('bytecode.json','utf8'));
const iface = new Interface(abi);
const common = new Common({ chain: Chain.Mainnet, hardfork: Hardfork.Shanghai });
const vm = await VM.create({ common });
const A = n => new Address(hexToBytes('0x' + n.toString(16).padStart(40,'0')));
const GOV = A(0xA1), ISS1 = A(0xB1), ISS2 = A(0xB2), OUT = A(0xC1), NEWGOV = A(0xD1);
let NOW = 1_800_000_000n;
const mkBlock = () => Block.fromBlockData({ header: { timestamp: NOW, number: 1n } }, { common });

async function call(from, to, fn, args=[]) {
  const data = hexToBytes(iface.encodeFunctionData(fn, args));
  const r = await vm.evm.runCall({ caller: from, origin: from, to, data, gasLimit: 8_000_000n, block: mkBlock() });
  return { r, gas: r.execResult.executionGasUsed, reverted: !!r.execResult.exceptionError,
           ret: bytesToHex(r.execResult.returnValue) };
}
const sel = e => iface.getError(e).selector;
const revertsWith = (res, name) => res.reverted && res.ret.startsWith(sel(name));
const revertsAny  = res => res.reverted;

// deploy
const ctorData = hexToBytes('0x' + bytecode + iface.encodeDeploy([GOV.toString()]).slice(2));
const dep = await vm.evm.runCall({ caller: GOV, origin: GOV, data: ctorData, gasLimit: 8_000_000n, block: mkBlock() });
const C = dep.createdAddress;
const id = s => keccak256(toUtf8Bytes(s));
const root = id('root-A'), bind = id('holder-A');
const results = []; const gasInfo = {};
const rec = (idc, desc, ok, detail) => results.push({ id: idc, deskripsi: desc, hasil: ok ? 'PASS' : 'FAIL', detail });

rec('E1','Deploy kontrak; governance = alamat konstruktor', !dep.execResult.exceptionError &&
    (await call(GOV, C, 'governance')).ret.toLowerCase().endsWith(GOV.toString().slice(2).toLowerCase()), 'deploy gas=' + dep.execResult.executionGasUsed);
gasInfo.deploy = Number(dep.execResult.executionGasUsed);

let x = await call(OUT, C, 'setIssuer', [ISS1.toString(), true]);
rec('E2','setIssuer oleh non-governance ditolak (NotGovernance)', revertsWith(x,'NotGovernance'), 'revert=' + x.ret.slice(0,10));

x = await call(GOV, C, 'setIssuer', [ISS1.toString(), true]); gasInfo.setIssuer = Number(x.gas);
await call(GOV, C, 'setIssuer', [ISS2.toString(), true]);
x = await call(OUT, C, 'issue', [id('c0'), root, bind, 0]);
rec('E3','issue oleh non-penerbit ditolak', revertsAny(x), 'reverted=' + x.reverted);

const CID = id('cred-1');
x = await call(ISS1, C, 'issue', [CID, root, bind, 0]); gasInfo.issue = Number(x.gas);
let chk = await call(OUT, C, 'check', [CID, root]);
let [valid, status] = iface.decodeFunctionResult('check', chk.ret);
rec('E4','issue oleh penerbit terdaftar; check(root benar) valid=true, status=ACTIVE', !x.reverted && valid === true && Number(status) === 1, `valid=${valid}; status=${status}; gas issue=${x.gas}`);

chk = await call(OUT, C, 'check', [CID, id('root-salah')]);
[valid] = iface.decodeFunctionResult('check', chk.ret);
rec('E5','check dengan root salah → valid=false', valid === false, `valid=${valid}`);

x = await call(ISS1, C, 'issue', [CID, root, bind, 0]);
rec('E6','timpa credId yang sama ditolak (AlreadyExists)', revertsWith(x,'AlreadyExists'), 'revert=' + x.ret.slice(0,10));

x = await call(ISS2, C, 'revoke', [CID]);
rec('E7','revoke oleh penerbit lain ditolak (NotIssuerOf)', revertsWith(x,'NotIssuerOf'), 'revert=' + x.ret.slice(0,10));

x = await call(ISS1, C, 'suspend', [CID]); gasInfo.suspend = Number(x.gas);
chk = await call(OUT, C, 'check', [CID, root]); [valid, status] = iface.decodeFunctionResult('check', chk.ret);
const v1 = valid === false && Number(status) === 2;
x = await call(ISS1, C, 'reinstate', [CID]);
chk = await call(OUT, C, 'check', [CID, root]); [valid, status] = iface.decodeFunctionResult('check', chk.ret);
rec('E8','suspend → valid=false; reinstate → valid=true', v1 && valid === true && Number(status) === 1, `saat suspend ok=${v1}; setelah reinstate valid=${valid}`);

x = await call(ISS1, C, 'revoke', [CID]); gasInfo.revoke = Number(x.gas);
const y = await call(ISS1, C, 'reinstate', [CID]);
chk = await call(OUT, C, 'check', [CID, root]); [valid, status] = iface.decodeFunctionResult('check', chk.ret);
rec('E9','revoke bersifat final: reinstate setelah revoke ditolak (InvalidTransition)', !x.reverted && revertsWith(y,'InvalidTransition') && valid === false && Number(status) === 3, `status=${status}; reinstate revert=${y.ret.slice(0,10)}`);

const OLD = id('old'), NEW = id('new'), root2 = id('root-B');
await call(ISS1, C, 'issue', [OLD, root, bind, 0]);
x = await call(ISS1, C, 'supersede', [OLD, NEW, root2, bind, 0]); gasInfo.supersede = Number(x.gas);
const co = iface.decodeFunctionResult('check', (await call(OUT, C, 'check', [OLD, root])).ret);
const cn = iface.decodeFunctionResult('check', (await call(OUT, C, 'check', [NEW, root2])).ret);
rec('E10','supersede: versi lama SUPERSEDED (tidak valid), versi baru valid', !x.reverted && co[0] === false && Number(co[1]) === 4 && cn[0] === true, `lama status=${co[1]}; baru valid=${cn[0]}`);

const EXP = id('exp'); await call(ISS1, C, 'issue', [EXP, root, bind, NOW + 1000n]);
let a = iface.decodeFunctionResult('check', (await call(OUT, C, 'check', [EXP, root])).ret)[0];
NOW += 2000n;
let b = iface.decodeFunctionResult('check', (await call(OUT, C, 'check', [EXP, root])).ret)[0];
rec('E11','kedaluwarsa: valid sebelum expiry, tidak valid sesudah expiry', a === true && b === false, `sebelum=${a}; sesudah=${b}`);

// kunci bocor: ISS2 menerbitkan sebelum & sesudah waktu kebocoran
const PRE = id('pre'), POST = id('post');
await call(ISS2, C, 'issue', [PRE, root, bind, 0]);
NOW += 500n; const leakAt = NOW;
NOW += 500n; await call(ISS2, C, 'issue', [POST, root, bind, 0]);
const mk = await call(GOV, C, 'markIssuerCompromised', [ISS2.toString(), leakAt]);
const pre = iface.decodeFunctionResult('check', (await call(OUT, C, 'check', [PRE, root])).ret)[0];
const post = iface.decodeFunctionResult('check', (await call(OUT, C, 'check', [POST, root])).ret)[0];
rec('E12','kunci penerbit bocor: kredensial sebelum waktu bocor tetap valid, sesudahnya tidak', !mk.reverted && pre === true && post === false, `sebelum=${pre}; sesudah=${post}`);

const RB = id('rb'); await call(ISS1, C, 'issue', [RB, root, bind, 0]);
const nb = id('holder-baru');
const rbBad = await call(OUT, C, 'rebind', [RB, nb]);
const rbOk = await call(ISS1, C, 'rebind', [RB, nb]);
const got = iface.decodeFunctionResult('get', (await call(OUT, C, 'get', [RB])).ret)[0];
rec('E13','rebind: non-penerbit ditolak; penerbit berhasil mengganti holderBinding', revertsWith(rbBad,'NotIssuerOf') && !rbOk.reverted && got.holderBinding === nb, `binding baru tersimpan=${got.holderBinding === nb}`);

const t1 = await call(OUT, C, 'transferGovernance', [NEWGOV.toString()]);
const t2 = await call(GOV, C, 'transferGovernance', [NEWGOV.toString()]);
const ac1 = await call(OUT, C, 'acceptGovernance');
const ac2 = await call(NEWGOV, C, 'acceptGovernance');
const g = (await call(OUT, C, 'governance')).ret.toLowerCase();
rec('E14','alih governance dua langkah: pihak tak berwenang ditolak; pending dapat accept', t1.reverted && !t2.reverted && ac1.reverted && !ac2.reverted && g.endsWith(NEWGOV.toString().slice(2).toLowerCase()), `governance baru berlaku=${g.endsWith(NEWGOV.toString().slice(2).toLowerCase())}`);

const z = await call(NEWGOV, C, 'issue', [id('z'), ZeroHash, bind, 0]);
const z2 = await call(ISS1, C, 'issue', [id('z2'), ZeroHash, bind, 0]);
rec('E15','issue dengan root = 0 ditolak', z2.reverted, `reverted=${z2.reverted}`);

const pass = results.filter(r => r.hasil === 'PASS').length;
const out = { evm: 'ethereumjs/evm (in-memory, hardfork Shanghai)', solc: '0.8.26', cases: results, pass, total: results.length, gas: gasInfo };
fs.writeFileSync('../evm_results.json', JSON.stringify(out, null, 2));
results.forEach(r => console.log(r.id, r.hasil, '-', r.detail));
console.log(`PASS ${pass}/${results.length}`, gasInfo);
