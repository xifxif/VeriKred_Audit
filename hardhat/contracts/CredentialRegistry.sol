// SPDX-License-Identifier: MIT
pragma solidity 0.8.26; // [F-06] versi dikunci = versi yang diuji (hardhat.config.js)

/// @title CredentialRegistry - jangkar kredensial akademik (tanpa PII)
/// @notice Prototipe konsep. v2 = hasil perbaikan audit keamanan internal (lihat laporan audit, F-01..F-06).
///         BELUM di-deploy ke testnet/mainnet, BELUM diaudit independen, BELUM diuji fuzz/analisis statis formal.
/// @dev Format credId (F-03): 20 byte pertama WAJIB alamat penerbit, 12 byte sisanya ID lokal bebas.
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
    event GovernanceTransferStarted(address indexed current, address indexed pending); // [F-05]
    event GovernanceTransferred(address indexed previous, address indexed current);    // [F-05]

    error NotGovernance();
    error NotIssuerOf();
    error AlreadyExists();
    error InvalidTransition();
    error IssuerIsCompromised();   // [F-02] penerbit ditandai kompromi
    error InvalidCredentialId();   // [F-03] prefix credId != alamat penerbit
    error InvalidExpiry();         // [F-04] expiry non-nol harus di masa depan
    error InvalidBinding();        // [F-04] holderBinding tidak boleh nol

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
        require(a != address(0), "issuer=0"); // [F-04]
        isIssuer[a] = allowed;
        emit IssuerSet(a, allowed);
    }

    function markIssuerCompromised(address a, uint64 fromTime) external onlyGovernance {
        issuerCompromisedFrom[a] = fromTime;
        emit IssuerCompromised(a, fromTime);
    }

    /// @dev next = address(0) membatalkan alih governance yang tertunda.
    function transferGovernance(address next) external onlyGovernance {
        pendingGovernance = next;
        emit GovernanceTransferStarted(governance, next); // [F-05]
    }

    function acceptGovernance() external {
        require(msg.sender == pendingGovernance, "bukan pending");
        address previous = governance;
        governance = msg.sender;
        pendingGovernance = address(0);
        emit GovernanceTransferred(previous, msg.sender); // [F-05]
    }

    // ---- penerbitan & siklus status ----
    function issue(bytes32 id, bytes32 root, bytes32 binding, uint64 expiry) external {
        _requireActiveIssuer();
        _create(id, root, binding, expiry);
    }

    /// @dev Aksi "memperlemah" (suspend, revoke) sengaja TETAP diizinkan bagi penerbit pemilik record
    ///      walau sudah dicabut/terkompromi (fail-safe). Aksi "menguatkan/menulis" (reinstate, supersede,
    ///      rebind, issue) mensyaratkan penerbit aktif [F-01, F-02].
    function suspend(bytes32 id) external onlyIssuerOf(id) {
        if (creds[id].status != Status.ACTIVE) revert InvalidTransition();
        creds[id].status = Status.SUSPENDED;
        emit StatusChanged(id, Status.SUSPENDED);
    }

    function reinstate(bytes32 id) external onlyIssuerOf(id) {
        _requireActiveIssuer(); // [F-01][F-02]
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
        _requireActiveIssuer(); // [F-01][F-02] supersede = menerbitkan record baru
        Status s = creds[oldId].status;
        if (s != Status.ACTIVE && s != Status.SUSPENDED) revert InvalidTransition();
        creds[oldId].status = Status.SUPERSEDED; // effects sebelum interaksi (tidak ada external call)
        emit StatusChanged(oldId, Status.SUPERSEDED);
        _create(newId, root, binding, expiry);
    }

    /// @dev Pemulihan kunci holder. Maker-checker ditegakkan di smart-account penerbit (2 penanda tangan).
    function rebind(bytes32 id, bytes32 newBinding) external onlyIssuerOf(id) {
        _requireActiveIssuer(); // [F-01][F-02]
        if (newBinding == bytes32(0)) revert InvalidBinding(); // [F-04]
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

    /// @notice Bentuk credId yang sah untuk `issuer`: [20 byte alamat penerbit][12 byte ID lokal]. [F-03]
    function credentialId(address issuer, bytes12 localId) external pure returns (bytes32) {
        return bytes32(bytes.concat(bytes20(issuer), localId));
    }

    /// @dev Penerbit harus terdaftar DAN tidak ditandai kompromi.
    function _requireActiveIssuer() private view {
        require(isIssuer[msg.sender], "bukan penerbit");
        if (issuerCompromisedFrom[msg.sender] != 0) revert IssuerIsCompromised();
    }

    function _create(bytes32 id, bytes32 root, bytes32 binding, uint64 expiry) private {
        // [F-03] namespace per-penerbit: penerbit lain tidak dapat merebut/menyalin credId.
        if (address(bytes20(id)) != msg.sender) revert InvalidCredentialId();
        if (creds[id].status != Status.NONE) revert AlreadyExists();
        require(root != bytes32(0), "root=0");
        if (binding == bytes32(0)) revert InvalidBinding();                       // [F-04]
        if (expiry != 0 && expiry <= block.timestamp) revert InvalidExpiry();     // [F-04]
        creds[id] = Credential(msg.sender, root, binding, uint64(block.timestamp), expiry, Status.ACTIVE);
        emit Issued(id, msg.sender, root, expiry);
    }
}
