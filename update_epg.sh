#!/usr/bin/env bash
set -Eeuo pipefail
TZ=${TZ:-America/New_York}
export TZ

# --- Determine writable log directory ---
LOG_DIR="/var/log/zap2py"
FALLBACK_DIR="$HOME/zap2py-logs"

if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
  LOG_DIR="$FALLBACK_DIR"
  mkdir -p "$LOG_DIR"
  INITIAL_MSG="[WARN] /var/log/zap2py not writable, using fallback: $LOG_DIR"
else
  INITIAL_MSG="[INFO] Using log directory: $LOG_DIR"
fi

LOG="$LOG_DIR/update_epg_$(date +%F).log"

# --- Combined console + timestamped log output ---
mkdir -p "$(dirname "$LOG")"
touch "$LOG"

# Send all stdout/stderr to both console and timestamped log
exec > >(tee >(awk '{ print strftime("[%Y-%m-%d %H:%M:%S]"), $0; fflush(); }' >>"$LOG")) 2>&1

echo "$INITIAL_MSG"
echo "[INFO] Logging initialized → $LOG"

# --- YAML path: /app/lineups.yaml by default; fallback to ./lineups.yaml if not present ---
CONFIG_YAML="${1:-/app/lineups.yaml}"
[[ ! -f "$CONFIG_YAML" && -f "./lineups.yaml" ]] && CONFIG_YAML="./lineups.yaml"

MAIL_TO="${MAIL_TO:-}"   # no default; silently skip if empty
HOST=$(hostname)
CRON_SCHEDULE="${CRON_SCHEDULE:-}"

send_mail() {
  local subject="$1"
  local body="$2"

  if [[ -z "${MAIL_TO:-}" ]]; then
    return 0
  fi

  if ! command -v mail >/dev/null 2>&1; then
    echo "[WARN] 'mail' command not available; skipping email to ${MAIL_TO}."
    return 0
  fi

  if echo -e "$body" | mail -s "$subject" "$MAIL_TO"; then
    echo "[INFO] Email sent to ${MAIL_TO}: $subject"
  else
    echo "[WARN] Failed to send email to ${MAIL_TO} (mail command returned non-zero)"
  fi
}

run_job() {
  SECONDS=0
  FAILED=0
  echo "[INFO] Logs will be written to: $LOG"
  echo "[INFO] Starting EPG update on $HOST at $(date)"
  echo "[INFO] Using config file: $CONFIG_YAML"
  echo

  if python3 -m zap2py "$CONFIG_YAML"; then
    FAILED=0
  else
    code=$?
    if (( code > 1 )); then
      FAILED=1
    else
      FAILED=0
    fi
  fi

  echo
  echo "[INFO] EPG update finished."
  echo "[INFO] Total time: $((SECONDS / 60))m $((SECONDS % 60))s"

  LINEUPS_TOTAL=$(grep -c "Running lineup" "$LOG" || echo 0)
  LINEUPS_FAILED=$(grep -c "\[ERROR\].*failed" "$LOG" || echo 0)
  LINEUPS_OK=$((LINEUPS_TOTAL - LINEUPS_FAILED))
  MIN=$((SECONDS / 60))
  SEC=$((SECONDS % 60))

  if ((FAILED == 0)); then
    SUBJECT="EPG Update SUCCESS <${HOST}>"
    BODY="Updating EPG complete!\n${MIN} minutes and ${SEC} seconds elapsed.\nLineups processed: ${LINEUPS_TOTAL} (${LINEUPS_OK} succeeded, ${LINEUPS_FAILED} failed)."
    send_mail "$SUBJECT" "$BODY"
  else
    SUBJECT="EPG Update FAILURE <${HOST}>"
    BODY="EPG update failed on ${HOST}.\nElapsed: ${MIN}m ${SEC}s.\n\n--- Last 200 lines of log ---\n"
    BODY+=$(tail -n 200 "$LOG" 2>/dev/null || echo "(no log)")
    send_mail "$SUBJECT" "$BODY"
  fi

  find "$LOG_DIR" -type f -name "update_epg_*.log" -mtime +7 -delete 2>/dev/null || true
  echo "[INFO] Log rotation complete (kept 7 days)."
  echo "[INFO] EPG job completed with status: ${FAILED}"
}

if [[ -n "$CRON_SCHEDULE" ]]; then
  echo "[INFO] Using cron schedule: $CRON_SCHEDULE"
  apt-get update -qq && apt-get install -y -qq cron >/dev/null 2>&1

  echo "$CRON_SCHEDULE root /usr/local/bin/update_epg.sh $CONFIG_YAML >> $LOG 2>&1" > /etc/cron.d/zap2py
  chmod 0644 /etc/cron.d/zap2py
  crontab /etc/cron.d/zap2py

  echo "[INFO] Cron job installed for schedule '$CRON_SCHEDULE'"
  echo "[INFO] Running initial update immediately..."
  run_job || true
  echo "[INFO] Starting cron daemon..."
  cron -f
else
  run_job
fi