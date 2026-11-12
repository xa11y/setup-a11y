#!/usr/bin/env bash
# Grant and verify Accessibility permission on GitHub-hosted macOS runners.
set -euo pipefail

client="${1:-}"
if [ -z "$client" ]; then
  echo "::warning::setup-a11y: macOS accessibility tests need the test process granted kTCCServiceAccessibility, but no 'macos-tcc-client' was provided. Trees will come back empty until the permission is granted. See https://xa11y.dev/guides/ci/#macos"
  exit 0
fi

echo "Granting TCC kTCCServiceAccessibility to: $client"
tcc_db="/Library/Application Support/com.apple.TCC/TCC.db"
client_sql="$(printf '%s' "$client" | sed "s/'/''/g")"

# tccd can hold the database lock. Wait up to 10 seconds per statement and
# retry up to five times, backing off between attempts. Apply this to reads
# as well as writes; a successful INSERT alone does not confirm the grant.
tcc_out=""
tcc_sqlite_retry() {
  local operation="$1" sql="$2" attempt=1 out
  until out="$(sudo sqlite3 -cmd ".timeout 10000" "$tcc_db" "$sql" 2>&1)"; do
    echo "setup-a11y: TCC.db $operation attempt $attempt/5 failed: $out" >&2
    if [ "$attempt" -ge 5 ]; then
      echo "::error::setup-a11y: TCC.db $operation for $client failed after 5 attempts: $out" >&2
      exit 1
    fi
    sleep $((attempt * 2))
    attempt=$((attempt + 1))
  done
  tcc_out="$out"
}

# Named columns tolerate additional columns across macOS versions.
# auth_value=2 means allowed; client_type=1 means an absolute path.
tcc_sqlite_retry "write" \
  "INSERT OR REPLACE INTO access(service,client,client_type,auth_value,auth_reason,auth_version,csreq,policy_id,indirect_object_identifier_type,indirect_object_identifier,indirect_object_code_identity,flags,last_modified) \
   VALUES('kTCCServiceAccessibility','${client_sql}',1,2,4,1,NULL,NULL,0,'UNUSED',NULL,0,$(date +%s));"

# Match the entire primary key of the row written above.
tcc_sqlite_retry "read-back" \
  "SELECT auth_value FROM access WHERE service='kTCCServiceAccessibility' AND client='${client_sql}' AND client_type=1 AND indirect_object_identifier='UNUSED';"
if [ "$tcc_out" != "2" ]; then
  echo "::error::setup-a11y: TCC.db holds no allowed kTCCServiceAccessibility row for $client after the write (auth_value: '$tcc_out')" >&2
  exit 1
fi

# Restart tccd only after verification so it picks up the grant.
sudo launchctl stop com.apple.tccd 2>/dev/null || true
sleep 2
