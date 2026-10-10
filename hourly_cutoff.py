"""
Hourly neutron monitor cut-off rigidity computation using OTSO with live data.

Computes the vertical effective cut-off rigidity (Ru, Rc, Rl) for a set of
neutron monitor stations at the top of the UTC hour LAG_HOURS ago, using NOAA
real-time solar wind / geomagnetic data (livedata="ON"), and appends one row
per hour to a CSV per station in OUTPUT_DIR, backfilling any missed hours
still covered by the live data.

Intended to be run hourly from cron (see run_hourly.sh).
"""

import csv
import os
import sys
from datetime import datetime, timedelta, timezone

# Station display name -> OTSO station code
STATIONS = {
    "Oulu": "OULU",
    "Thule": "THUL",
    "Lomnicky": "LMKS",
    "Moscow": "MOSC",
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# TSY01 makes use of most of the live inputs (Dst, Pdyn, By, Bz, G1, G2).
# Live data is not supported for TSY04 or TA16_RBF.
EXTERNAL_MODEL = "TSY01"
OPTIMISE_TSY = True

# Parallelism, sized for a 4-core Raspberry Pi (corenum * threadnum <= 4).
# Benchmarked with bench_cores.py: 1 process x 4 threads was fastest.
CORENUM = 1
THREADNUM = 4

# Compute for this many hours in the past, so the online Dst/Kp/solar wind
# datasets have had time to update. Must stay well under OTSO's 24 h live-data limit.
LAG_HOURS = 3

# Each run also fills in any hours missing from the CSVs (e.g. machine was off)
# back to this many hours ago. NOAA real-time data only covers the last 24 h and
# OTSO averages the 30 min before each time, so hours older than MAX_AGE_HOURS
# at the moment of computation are skipped.
BACKFILL_HOURS = 21
MAX_AGE_HOURS = 23

CSV_HEADER = ["datetime_utc", "Ru_GV", "Rc_GV", "Rl_GV", "external_model", "computed_at_utc"]


def compute(event_time: datetime, corenum: int = CORENUM, threadnum: int = THREADNUM):
    # Imported here so plot_cutoffs.py (run in CI) can use STATIONS without OTSO installed.
    from OTSO import cutoff

    date_inputs = {"year": event_time.year, "month": event_time.month, "day": event_time.day,
                   "hour": event_time.hour, "minute": 0, "second": 0}

    magfield_inputs = {"internalmag": "IGRF", "externalmag": EXTERNAL_MODEL,
                       "boberg": False, "bobergtype": "EXTENSION",
                       "magnetopause": "Kobel", "AdaptiveExternalModel": False,
                       "optimise_tsy": OPTIMISE_TSY}

    rigidity_inputs = {"startrigidity": 20, "endrigidity": 0,
                       "rigiditystep": 0.01, "rigidityscan": "ON"}

    integration_inputs = {"intmodel": "Boris-Buneman", "gyropercent": 1, "minaltitude": 20,
                          "maxdistance": 100, "maxtime": 0, "mintrapdist": 6.6,
                          "startaltitude": 20, "betaerror": 0.001,
                          "totalbetacheck": True, "adaptivestep": True}

    computation_inputs = {"corenum": corenum, "threadnum": threadnum, "Verbose": False, "delim": ";"}

    data_retrieval_inputs = {"serverdata": "OFF", "livedata": "ON"}

    results = cutoff(
        Stations=list(STATIONS.values()),
        cutoff_comp="Vertical",
        datetime_params=date_inputs,
        magfield_params=magfield_inputs,
        rigidity_params=rigidity_inputs,
        integration_params=integration_inputs,
        computation_params=computation_inputs,
        coordinate_params={"coordsystem": "GEO", "inputcoord": "GDZ"},
        data_retrieval_params=data_retrieval_inputs,
    )
    return results[0]


def recorded_times(csv_path: str) -> set:
    if not os.path.exists(csv_path):
        return set()
    with open(csv_path, newline="") as f:
        return {row[0] for row in csv.reader(f) if row and row[0] != CSV_HEADER[0]}


def append_row(csv_path: str, row: list) -> None:
    new_file = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(CSV_HEADER)
        writer.writerow(row)


def sort_csv(csv_path: str) -> None:
    # Backfilled hours are appended out of order; keep each file chronological.
    if not os.path.exists(csv_path):
        return
    with open(csv_path, newline="") as f:
        rows = [row for row in csv.reader(f) if row and row[0] != CSV_HEADER[0]]
    rows.sort(key=lambda row: row[0])
    tmp_path = csv_path + ".tmp"
    with open(tmp_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)
    os.replace(tmp_path, csv_path)


def compute_hour(event_time: datetime, csv_paths: dict) -> None:
    timestamp = event_time.strftime("%Y-%m-%d %H:%M:%S")
    df = compute(event_time)
    computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for name, code in STATIONS.items():
        if timestamp in recorded_times(csv_paths[name]):
            continue
        if code not in df.columns:
            print(f"{timestamp}: no result for {name} ({code})", file=sys.stderr)
            continue
        col = df[code]
        append_row(csv_paths[name], [timestamp, col["Ru"], col["Rc"], col["Rl"],
                                     EXTERNAL_MODEL, computed_at])
        print(f"{timestamp}: {name} Ru={col['Ru']} Rc={col['Rc']} Rl={col['Rl']}", flush=True)


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    csv_paths = {name: os.path.join(OUTPUT_DIR, f"{name}_cutoff.csv") for name in STATIONS}
    recorded = {name: recorded_times(p) for name, p in csv_paths.items()}

    latest = (datetime.now(timezone.utc) - timedelta(hours=LAG_HOURS)).replace(
        minute=0, second=0, microsecond=0, tzinfo=None)
    candidates = [latest - timedelta(hours=h) for h in range(BACKFILL_HOURS - LAG_HOURS, -1, -1)]
    missing = [t for t in candidates
               if any(t.strftime("%Y-%m-%d %H:%M:%S") not in times for times in recorded.values())]

    if not missing:
        print(f"{latest}: nothing to compute, all hours recorded.")
        return 0
    if len(missing) > 1:
        print(f"{len(missing)} hours to compute ({missing[0]} to {missing[-1]}).", flush=True)

    failures = 0
    for event_time in missing:  # oldest first, since those are closest to expiring
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if now - event_time > timedelta(hours=MAX_AGE_HOURS):
            print(f"{event_time}: too old for live data, skipping.", file=sys.stderr)
            continue
        try:
            compute_hour(event_time, csv_paths)
        except (Exception, SystemExit) as e:  # OTSO calls exit() on some input errors
            failures += 1
            print(f"{event_time}: computation failed ({e!r})", file=sys.stderr)

    for p in csv_paths.values():
        sort_csv(p)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
