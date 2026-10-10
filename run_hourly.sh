#!/usr/bin/env bash
# Hourly job: compute cut-offs, commit the CSVs to `main` and push. Plots are drawn
# and published to GitHub Pages by .github/workflows/plots.yml, not here.
#
# Deliberately no `set -e`: a failed compute or push is logged and the run
# carries on, so the next hour still runs and unpushed commits go up later.
set -uo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-$REPO/OTSOenv/bin/python}"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/nm-cutoffs"   # log and lock: never in the repo
LOG="$STATE/run.log"
NET_TIMEOUT=120

export TZ=UTC LC_ALL=C GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=20"

mkdir -p "$STATE"
# Keep the log bounded.
if [[ -f "$LOG" ]] && (( $(wc -l < "$LOG") > 5000 )); then
    tail -n 2500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
exec >>"$LOG" 2>&1

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S') UTC  $*"; }

exec 9>"$STATE/lock"
if ! flock -n 9; then
    log "previous run still active, exiting"
    exit 0
fi

cd "$REPO" || exit 1
log "---- run start"

# 1. Compute, only with a trustworthy clock (the Pi has no RTC).
ntp="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || echo unknown)"
if [[ "$ntp" == "no" ]]; then
    log "clock not NTP-synchronised, skipping computation"
else
    [[ "$ntp" == "yes" ]] || log "warning: could not check NTP sync, continuing"
    "$PY" hourly_cutoff.py || log "compute finished with errors (exit $?)"
fi

# 2. Commit data to main, only if it changed.
git add -- data/
if git diff --cached --quiet -- data/; then
    log "data unchanged, no commit"
else
    latest="$(tail -n 1 data/Oulu_cutoff.csv | cut -d, -f1)"
    git commit -q -m "Cut-offs up to ${latest} UTC" -- data/ && log "committed data up to ${latest} UTC"
fi

# 3. Push main (fetch + rebase == git pull --rebase; tolerates an empty remote).
if timeout "$NET_TIMEOUT" git fetch -q origin; then
    if git rev-parse -q --verify refs/remotes/origin/main >/dev/null \
       && ! git rebase -q --autostash origin/main; then
        git rebase --abort 2>/dev/null
        log "rebase onto origin/main failed (conflict?), main not pushed - needs manual attention"
    elif [[ "$(git rev-parse HEAD)" != "$(git rev-parse -q --verify refs/remotes/origin/main)" ]]; then
        timeout "$NET_TIMEOUT" git push -q origin HEAD:main \
            && log "pushed main" || log "push main failed, will retry next hour"
    fi
else
    log "fetch failed (offline?), will retry next hour"
fi

log "---- run end"
