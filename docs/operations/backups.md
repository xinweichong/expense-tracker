# Encrypted backup and restoration

The trust foundation adds `python -m scripts.backup`. Run from the repository root using Python 3.12. Install `requirements-backup.txt` in the operator environment. No cloud resources or credentials are created automatically.

Snapshots include `data/app.db`, every user database, per-user `token.json`, and the explicitly supplied `config.yaml` and `credentials.json`. Each database is captured through SQLite's backup API, checked for integrity, and packaged with SHA-256 checksums. The complete archive is authenticated and encrypted with Fernet. Snapshot creation is bounded to 128 MiB of uncompressed input; exceeding this stops the operation rather than creating an incomplete backup. Databases are individually consistent, not a global transaction across all user databases; avoid account creation/deletion during a snapshot.

## Configure once

Generate the key in a protected directory **outside the repository and data directory**. Keep an additional copy in an off-host password manager; losing it makes snapshots unrecoverable.

```sh
python -m scripts.backup keygen --key-file /secure/cashe-backup.key
```

For R2 uploads, configure a private, dedicated Standard bucket and bucket-scoped credentials using the operator's protected environment:

- `R2_ENDPOINT_URL`: `https://<account-id>.r2.cloudflarestorage.com`
- `R2_BACKUP_BUCKET`: dedicated backup bucket
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: R2 access credentials

The client configuration follows [Cloudflare's boto3 example](https://developers.cloudflare.com/r2/examples/aws/boto3/). Verify the account's actual storage allocation and other R2 usage before enabling the job. Never add real keys to these docs or commit them.

## Create or upload

```sh
python -m scripts.backup create --key-file /secure/cashe-backup.key --data-dir /path/to/data --config /path/to/config.yaml --credentials /path/to/credentials.json --snapshot /secure/cashe-snapshot.fernet
python -m scripts.backup upload --key-file /secure/cashe-backup.key --data-dir /path/to/data --config /path/to/config.yaml --credentials /path/to/credentials.json
```

Local output is created exclusively with mode 0600; an existing file is not overwritten. Only encrypted archives leave the machine. Run one upload job at a time, daily, from the OCI host scheduler. Check the exit status and alert externally on failure or an overdue snapshot; host scheduling and an external heartbeat still require deployment configuration.

Uploads stop if existing bucket bytes plus the new archive exceed `--max-remote-bytes` (default 8,000,000,000). The ceiling counts the entire bucket, but not unrelated buckets in the account. Successful uploads are downloaded and verified before retention removes older objects under `cashe/`. Retention keeps the newest snapshot for 30 distinct days plus 12 distinct months. Other object prefixes are never pruned. A failed verification retains prior snapshots. Do not run overlapping upload jobs against the same bucket.

## Restore drill

Download a selected encrypted archive from R2, then restore into a **new, isolated** directory:

```sh
python -m scripts.backup restore --key-file /secure/cashe-backup.key --snapshot /secure/cashe-snapshot.fernet --destination /secure/cashe-restore-drill
```

Restoration authenticates the archive, verifies every checksum and database, and rejects unsafe archive paths before publishing the directory. Restored files appear under `data/` and `protected/`. The test suite verifies restoration of committed WAL data and reopening through the current production migrations.

Before a production cutover, boot the restored copy in an isolated environment with pollers, Telegram, webhooks, and external AI disabled. Check users, transaction counts, source-event links, and key reports. Preserve the current production data directory and post-snapshot source evidence for replay. Do not point production services at the restored directory until those checks pass.

Automated tests use synthetic fixtures. A real OCI/R2 restore drill has not yet been performed by this implementation.
