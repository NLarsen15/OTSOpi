"""
Station list for the OTSOpi pipeline, and a command-line tool to manage it.

stations.json is the single source of truth: hourly_cutoff.py computes these
stations and plot_cutoffs.py draws them. Use the ./station wrapper:

    ./station list                 configured stations
    ./station search TEXT          search OTSO's built-in station list
    ./station add CODE [NAME]      add an OTSO station, commit and push
    ./station remove NAME          stop computing a station (its data is kept), commit and push

add/remove take --no-push to only edit stations.json locally. They wait for any
running computation to finish, and pull before editing so machines stay in step.
"""

import argparse
import csv
import fcntl
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(REPO, "stations.json")
LOCK = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "nm-cutoffs", "lock")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")  # used in file names, so keep it simple


def load_stations() -> list:
    """[{"name", "code", "lat", "lon"}, ...] in configured order."""
    with open(CONFIG) as f:
        return json.load(f)["stations"]


def save_stations(stations: list) -> None:
    lines = ",\n".join("    " + json.dumps(s, ensure_ascii=False) for s in stations)
    with open(CONFIG, "w") as f:
        f.write('{\n  "stations": [\n' + lines + "\n  ]\n}\n")


def otso_station_list() -> list:
    """Rows (name, lat, lon) of OTSO's built-in station list. Needs OTSO installed."""
    try:
        from importlib.resources import files
        path = files("OTSO._core.custom_classes") / "StationList.csv"
        with open(path, newline="") as f:
            return [(r["Name"], float(r["Latitude"]), float(r["Longitude"])) for r in csv.DictReader(f)]
    except ModuleNotFoundError:
        sys.exit("OTSO is not installed in this Python; run via ./station (uses OTSOenv).")


def lon180(lon: float) -> float:
    return round(lon - 360 if lon > 180 else lon, 4)


def git(*args, check=True):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0",
               GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=20")
    return subprocess.run(["git", "-C", REPO, *args], check=check, env=env, text=True,
                          capture_output=True)


def locked_edit(change, message: str, push: bool) -> None:
    """Hold the pipeline lock, sync with GitHub, apply change(stations), commit and push."""
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    with open(LOCK, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("A computation is running; waiting for it to finish...", flush=True)
            fcntl.flock(lock, fcntl.LOCK_EX)
        if push:
            if git("diff", "--quiet", "HEAD", "--", "stations.json", check=False).returncode != 0:
                sys.exit("stations.json has uncommitted local edits (e.g. from --no-push). "
                         "Commit or discard them first:  git checkout -- stations.json")
            r = git("pull", "-q", "--rebase", "--autostash", "origin", "main", check=False)
            if r.returncode != 0:
                sys.exit("git pull failed, nothing changed:\n" + r.stderr)
        stations = load_stations()
        change(stations)
        save_stations(stations)
        if not push:
            print("stations.json updated (not committed: --no-push).")
            return
        git("add", "stations.json")
        git("commit", "-q", "-m", message)
        r = git("push", "-q", "origin", "HEAD:main", check=False)
        if r.returncode != 0:
            print("Committed locally but the push failed; the hourly run will push it:\n" + r.stderr)
        else:
            print(f"Committed and pushed: {message}")


def cmd_list(_args):
    for s in load_stations():
        print(f"{s['name']:14s} {s['code']:8s} lat {s['lat']:7.2f}  lon {s['lon']:8.2f}")


def cmd_search(args):
    text = args.text.lower()
    rows = [r for r in otso_station_list() if text in r[0].lower()]
    if not rows:
        print("No match. Run with a shorter search, e.g. the first few letters.")
    for name, lat, lon in rows:
        print(f"{name:20s} lat {lat:7.2f}  lon {lon180(lon):8.2f}")


def cmd_add(args):
    rows = otso_station_list()
    # Codes are the upper-case entries (e.g. KIEL); the full name (Kiel) is a separate row.
    match = ([r for r in rows if r[0] == args.code.upper()]
             or [r for r in rows if r[0].upper() == args.code.upper()])
    if not match:
        sys.exit(f"'{args.code}' is not in OTSO's station list. Try: ./station search {args.code[:3]}")
    code, lat, lon = match[0]
    name = args.name
    if not name:  # default: the full-name alias listed with the same coordinates
        aliases = [r[0] for r in rows if (r[1], r[2]) == (lat, lon) and r[0] != code and not r[0].isupper()]
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", aliases[0]) if aliases else code.title()
    if not NAME_RE.match(name):
        sys.exit(f"Name '{name}' must start with a letter and use only letters, digits, '-' or '_'.")

    def change(stations):
        if any(s["name"].lower() == name.lower() or s["code"] == code for s in stations):
            sys.exit(f"{name} ({code}) is already configured.")
        stations.append({"name": name, "code": code, "lat": lat, "lon": lon180(lon)})

    locked_edit(change, f"Add station {name} ({code})", push=not args.no_push)
    print(f"{name} ({code}) will be computed from the next run, including backfill of the last ~21 h.")


def cmd_remove(args):
    def change(stations):
        keep = [s for s in stations if s["name"].lower() != args.name.lower()]
        if len(keep) == len(stations):
            sys.exit(f"No configured station called '{args.name}'. See: ./station list")
        if not keep:
            sys.exit("Refusing to remove the last station.")
        stations[:] = keep

    locked_edit(change, f"Remove station {args.name}", push=not args.no_push)
    print(f"{args.name} is no longer computed; its existing data files are kept.")


def main() -> int:
    p = argparse.ArgumentParser(prog="station", description="Manage the OTSOpi station list.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show configured stations").set_defaults(func=cmd_list)
    s = sub.add_parser("search", help="search OTSO's built-in station list")
    s.add_argument("text")
    s.set_defaults(func=cmd_search)
    a = sub.add_parser("add", help="add an OTSO station by code, e.g. KIEL")
    a.add_argument("code")
    a.add_argument("name", nargs="?", help="display/file name (default: OTSO's full name)")
    a.add_argument("--no-push", action="store_true", help="only edit stations.json locally")
    a.set_defaults(func=cmd_add)
    r = sub.add_parser("remove", help="stop computing a station (data is kept)")
    r.add_argument("name")
    r.add_argument("--no-push", action="store_true", help="only edit stations.json locally")
    r.set_defaults(func=cmd_remove)
    args = p.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
