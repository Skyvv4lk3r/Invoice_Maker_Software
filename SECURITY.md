# Security scope

This is a local single-owner desktop application. Report security concerns privately
to the repository owner; do not include business records, passwords or recovery codes
in public issues.

## Implemented controls

- No default account or password. First-run creation is atomic and cannot replace an owner.
- Argon2id password/recovery hashing: 19 MiB memory, two iterations, one lane.
- Five failed sign-in/recovery attempts cause a persisted five-minute lockout.
- Process-local sessions, 15-minute idle timeout and credential epoch invalidation.
- Capability guards protect backend data operations as well as screens.
- Plaintext credentials and recovery codes are excluded from credential DTO reprs.
- Backup archive: Scrypt-derived key, random salt and nonce, AES-256-GCM authenticated
  encryption. The backup passphrase is independent of the login password.
- Restore verifies archive paths, sizes, hashes, schema and SQLite integrity. It
  stages a separate empty directory; it does not overwrite the active workspace.
- Logo re-encoding, bounded template data, escaped document text and CSV formula defence.

## Limitations

The live SQLite database and exports are **not encrypted**. Application login cannot
stop someone with OS/file access from reading data, modifying hashes or editing the
program. Audit history is not cryptographically tamper-proof. Protect the OS account
and storage; do not share a live database through a network/cloud folder.

A backup contains credential hashes and exports. Keep its passphrase separately.
Restoring brings back the owner credentials and invoice counter from that point in
time. Reconcile later invoices before issuing again. A restore is not a merge or
multi-device synchronisation operation. The application cannot recover a lost
password without the recovery code, or decrypt a backup without its passphrase.

A shared PDF cannot be revoked after cancellation. Word exports are editable.
The application does not provide digital signatures or access-controlled external
sharing links. Windows builds are unsigned development artifacts.

Reference for password hashing: [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
