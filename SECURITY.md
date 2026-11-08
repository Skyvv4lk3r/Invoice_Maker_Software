# Security and data handling

This is a local development starter, not a hardened production release. It does
not yet encrypt the database or exports, implement recovery-key management, or
provide a complete access-control model.

Do not post real invoice data, GST identifiers, customer addresses, credentials,
database files or backup archives in public issues. Report a vulnerability through
GitHub's private vulnerability reporting feature if the repository owner enables
it; otherwise contact the repository owner through an established private channel.

Keep dependency updates reviewed and tested. The application has no telemetry,
automatic messaging, cloud-sync integration or runtime HTTP listener. OS access to
the data directory still controls who can read local records.
