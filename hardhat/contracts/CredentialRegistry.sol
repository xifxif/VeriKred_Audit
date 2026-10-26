// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title CredentialRegistry - jangkar kredensial akademik (tanpa PII)
/// @notice Prototipe konsep. Terkompilasi (solc 0.8.26) dan lolos 15 uji di EVM lokal in-memory (evm/).
///         BELUM di-deploy ke testnet/mainnet, BELUM diaudit, BELUM diuji fuzz/analisis statis.
contract CredentialRegistry {
    enum Status { NONE, ACTIVE, SUSPENDED, REVOKED, SUPERSEDED }

    struct Credential {
        address issuer;        // akun penerbit (smart-account multisig institusi)
        bytes32 root;          // Merkle root atribut bergaram
        bytes32 holderBinding; // keccak256(kunci publik holder)
        uint64  issuedAt;
        uint64  expiry;        // 0 = tidak kedaluwarsa
        Status  status;
    }

    address public governance;        // TimelockController di belakang multisig konsorsium
    address public pendingGovernance; // alih governance dua langkah
    mapping(address => bool)   public isIssuer;
    mapping(address => uint64) public issuerCompromisedFrom; // 0 = tidak ada
    mapping(bytes32 => Credential) private creds;

    event IssuerSet(address indexed issuer, bool allowed);
    event IssuerCompromised(address indexed issuer, uint64 fromTime);
    event Issued(bytes32 indexed credId, address indexed issuer, bytes32 root, uint64 expiry);
    event StatusChanged(bytes32 indexed credId, Status newStatus);
    event HolderRebound(bytes32 indexed credId, bytes32 newBinding);

    error NotGovernance();
    error NotIssuerOf();
    error AlreadyExists();
    error InvalidTransition();

    modifier onlyGovernance() {
        if (msg.sender != governance) revert NotGovernance();
        _;
    }

    modifier onlyIssuerOf(bytes32 id) {
        if (creds[id].issuer != msg.sender || msg.sender == address(0)) revert NotIssuerOf();
        _;
    }

    constructor(address _governance) {
        require(_governance != address(0), "gov=0");
        governance = _governance;
    }

    // ---- governance (dipanggil lewat timelock + multisig) ----
    function setIssuer(address a, bool allowed) external onlyGovernance {
        isIssuer[a] = allowed;
        emit IssuerSet(a, allowed);
    }

    function markIssuerCompromised(address a, uint64 fromTime) external onlyGovernance {
        issuerCompromisedFrom[a] = fromTime;
        emit IssuerCompromised(a, fromTime);
    }

    function transferGovernance(address next) external onlyGovernance { pendingGovernance = next; }

    function acceptGovernance() external {
        require(msg.sender == pendingGovernance, "bukan pending");
        governance = msg.sender;
        pendingGovernance = address(0);
    }

    // ---- penerbitan & siklus status ----
    function issue(bytes32 id, bytes32 root, bytes32 binding, uint64 expiry) external {
        require(isIssuer[msg.sender], "bukan penerbit");
        _create(id, root, binding, expiry);
    }

    function suspend(bytes32 id) external onlyIssuerOf(id) {
        if (creds[id].status != Status.ACTIVE) revert InvalidTransition();
        creds[id].status = Status.SUSPENDED;
        emit StatusChanged(id, Status.SUSPENDED);
    }

    function reinstate(bytes32 id) external onlyIssuerOf(id) {
        if (creds[id].status != Status.SUSPENDED) revert InvalidTransition();
        creds[id].status = Status.ACTIVE;
        emit StatusChanged(id, Status.ACTIVE);
    }

    function revoke(bytes32 id) external onlyIssuerOf(id) {
        Status s = creds[id].status;
        if (s != Status.ACTIVE && s != Status.SUSPENDED) revert InvalidTransition();
        creds[id].status = Status.REVOKED; // final
        emit StatusChanged(id, Status.REVOKED);
    }

    function supersede(bytes32 oldId, bytes32 newId, bytes32 root, bytes32 binding, uint64 expiry)
        external onlyIssuerOf(oldId)
    {
        Status s = creds[oldId].status;
        if (s != Status.ACTIVE && s != Status.SUSPENDED) revert InvalidTransition();
        creds[oldId].status = Status.SUPERSEDED; // effects sebelum interaksi (tidak ada external call)
        emit StatusChanged(oldId, Status.SUPERSEDED);
        _create(newId, root, binding, expiry);
    }

    /// @dev Pemulihan kunci holder. Maker-checker ditegakkan di smart-account penerbit (2 penanda tangan).
    function rebind(bytes32 id, bytes32 newBinding) external onlyIssuerOf(id) {
        if (creds[id].status != Status.ACTIVE) revert InvalidTransition();
        creds[id].holderBinding = newBinding;
        emit HolderRebound(id, newBinding);
    }

    // ---- baca (gratis, dipanggil verifier) ----
    function check(bytes32 id, bytes32 root) external view returns (bool valid, Status status) {
        Credential storage c = creds[id];
        status = c.status;
        uint64 cf = issuerCompromisedFrom[c.issuer];
        bool tainted = cf != 0 && c.issuedAt >= cf;
        bool expired = c.expiry != 0 && block.timestamp > c.expiry;
        valid = (status == Status.ACTIVE) && c.root == root && !tainted && !expired;
    }

    function get(bytes32 id) external view returns (Credential memory) { return creds[id]; }

    function _create(bytes32 id, bytes32 root, bytes32 binding, uint64 expiry) private {
        if (creds[id].status != Status.NONE) revert AlreadyExists();
        require(root != bytes32(0), "root=0");
        creds[id] = Credential(msg.sender, root, binding, uint64(block.timestamp), expiry, Status.ACTIVE);
        emit Issued(id, msg.sender, root, expiry);
    }
}
