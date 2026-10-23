# Encrypted backup, NAS pull and fresh-install restore

No owner NAS/VPS was accessed during implementation. Archive generation/rotation and empty-schema restore are tested locally; distinguish those from real transfer connectivity, public HTTPS and systemd boot evidence in [test results](../testing/RESULTS.md).

## Archive contract and keys

`stocklog-backup.timer` runs a bounded management command daily at 16:15 UTC plus at most five minutes jitter. The command serialises with installation/restore, holds the property's mutation guard during a supported `mariadb-dump --single-transaction --quick` export, and does not copy raw MariaDB files. It includes accounts/password hashes, settings/templates, identifiers/history, inventory, allocations, audit and migrations; an exact source-release archive, requirements/build locks, version/migration fingerprint and checksums accompany the SQL.

The temporary archive is encrypted using age to the public recipient in `/etc/stocklog/app.env`. Only validated complete files are atomically published under immutable archive IDs; authenticated discovery returns ID, byte length and SHA-256. A monotonic publication sequence handles multiple successful backups within one Unix second. Rotate only after successful publication to exactly the three latest unique versions (up to three during initial accumulation). A failed dump/encryption/download/hash/disk-space check retains previous good versions. Readers pin an immutable filename; an already open download remains stable through rotation, while a missing rotated file fails and must rediscover latest.

Private archives live outside the web root. The web backup endpoints require an administrator's authenticated session. There is no public backup URL and no backup token embedded in Git. Default delivery to NAS uses a separately restricted SSH key.

The installer creates `/etc/stocklog/recovery.key` with mode 0600 and retains it on reruns. Its public recipient is used for encryption. **Store a protected off-server copy of the private recovery key** and document who can recover it. Losing both the VPS and the only recovery key makes the encrypted archives unusable. The archive deliberately excludes deployment credentials and this decryption key. New-server credentials/paths are supplied by the new installer. New Django secrets may expire old sessions; password hashes/accounts remain restorable.

## First manual backup

```sh
systemctl start stocklog-backup.service
journalctl -u stocklog-backup -n 50 --no-pager
ls -l /var/lib/stocklog/backups
```

Do not print private configuration or key files to logs. The published `latest.json` contains non-secret archive metadata. Ensure disk-space monitoring covers three retained archives, the complete next candidate and export/workspace. Provider snapshots may supplement, not replace, the StockLOG restore test.

## Restricted NAS access

Create a dedicated Ed25519 key on the NAS under its scheduler account, protected by filesystem permissions; unattended scheduling needs a key or agent arrangement that does not require interactive entry. Keep the key restricted to backup retrieval.

On the VPS, install **only the public key** in `/var/lib/stocklog-backup/.ssh/authorized_keys` with this prefix:

```text
restrict,command="/usr/local/bin/stocklog-backup-read" ssh-ed25519 YOUR_NAS_PUBLIC_KEY_COMMENT_AND_DATA
```

Use the normal `ssh-ed25519 BASE64DATA comment` public-key format after the restriction prefix. Set the home/.ssh ownership to `stocklog-backup:stocklog-backup`, `.ssh` mode 0700 and `authorized_keys` mode 0600. Do not enable passwords, unrestricted shell commands, port forwarding, agent forwarding or a key for the main application/admin account. The forced command permits only `latest` and `get <32-hex immutable ID>`; the transfer account can read the encrypted archive group but not application secrets/recovery keys. Optionally restrict the public key's source address if the NAS has a stable address and connectivity has been verified.

Pin the VPS host key in a NAS-owned `known_hosts` file. Compare its fingerprint against the VPS host public key obtained through your trusted administrator/provider channel; never accept an unverified scan as proof of identity. The script requires strict host-key checking and batch-only authentication.

Copy `ops/nas_pull.py` to a private NAS tools directory. It requires Python 3 and OpenSSH only. Example Task Scheduler invocation (replace paths/host):

```sh
python3 /volume1/StockLOG-tools/nas_pull.py \
  --host YOUR_VPS_HOST --user stocklog-backup \
  --key /volume1/StockLOG-tools/ssh/id_ed25519 \
  --known-hosts /volume1/StockLOG-tools/ssh/known_hosts \
  --destination /volume1/StockLOG-backups
```

Schedule daily at **04:00 Australia/Sydney**, after the nominal server job in both daylight-saving seasons. A long server job may mean the latest completed archive is from the previous run; the pull never reads a changing candidate. Logs identify success/failure and immutable ID, not credentials. The script downloads to a temporary file, checks length/hash/completion, atomically publishes, deduplicates retries and retains three latest successful unique versions locally. A failed transfer does not remove good copies. No browser/cPanel automation, NAS write connection from the VPS, or full farm database sync is involved.

## Restore on a clean replacement installation

Install the matching StockLOG release on a clean Debian 13 target first, using the installer. Do not create a first-admin account for a restore: the backup includes accounts/property/settings. Transfer the encrypted archive, published manifest/checksum and protected private recovery key to a private local maintenance directory (mode 0700); verify the ciphertext hash through a trusted manifest before restore.

Run as root in maintenance:

```sh
bash /opt/stocklog/current/ops/restore-debian13.sh \
  --archive /root/recovery/ARCHIVE_ID.tar.gz.age \
  --identity /root/recovery/recovery.key \
  --sha256 EXPECTED_64_HEX_SHA256 \
  --target stocklog_restore_20261023
```

The command creates a **new** schema; an existing target name causes refusal, never DROP/overwrite. It checks ciphertext and internal checksums, safe archive paths/types/size, application/schema/migration compatibility, then imports through the supported MariaDB client in binary/batch mode and verifies migration state. Original installation data remains untouched. Inspect/reconcile accounts, property/settings/templates, identifier reservations, counts, balances, allocations and audit before use. On failure the new target stays isolated for diagnosis; do not point the application at it. Disk preflight must allow the isolated schema/export workspace; use an adequately sized separate test server if this cannot fit the small VPS.

To activate a restore in the same reviewed maintenance invocation, append **`--activate`**. This is an explicit request to stop the web service, switch the database configuration and restart it after restore validation. The old database and `/etc/stocklog/app.env.pre-restore` remain for recovery. Protect that file as a secret. If activation fails, restore that private configuration and restart only after confirming the prior database/release are compatible. Do not drop the old database as part of an automatic rollback.

Archives include exact release material to avoid relying on an unpublished Git SHA. Restore requires its matching application version/migration fingerprint; arbitrary future-version compatibility is not promised. Restore the matching release into isolation first, then follow reviewed forward migrations. Environment-specific DB credentials/private paths and keys are not imported blindly from the old server.

## Retention

Business/audit retention is indefinite by default. Backup rotation is independent of deliberate administrator retention redaction. An eligible off-property/dead animal can have details redacted only after ten calendar years from its most recent exit/death; repurchase resets eligibility. Permanent identifier reservations and shared-event accounting totals survive. Older encrypted backups may contain pre-redaction details until the three-version rotation replaces them. No nightly age-based animal purge exists.
