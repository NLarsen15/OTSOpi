"""
Hourly neutron monitor cut-off rigidity computation using OTSO with live data.

Computes the vertical effective cut-off rigidity (Ru, Rc, Rl) for a set of
neutron monitor stations at the top of the UTC hour LAG_HOURS ago, using NOAA
real-time solar wind / geomagnetic data (livedata="ON"), and appends one row
per hour to a CSV per station in OUTPUT_DIR, plus asymptotic viewing directions
at ASYM_LEVELS to monthly files in data/asymptotic/<Station>/, and the model inputs
OTSO used (solar wind, indices, G values) to data/inputs.csv. Missed hours still
covered by the live data are backfilled.

Intended to be run hourly from cron (see run_hourly.sh).
"""

import csv
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from stations import load_stations

# Station display name -> OTSO station code, from stations.json (managed with ./station).
# Custom stations (not in OTSO's list) are passed to OTSO as customlocations under their code.
STATIONS = {s["name"]: s["code"] for s in load_stations()}
CUSTOM_LOCATIONS = [[s["code"], s["lat"], s["lon"]] for s in load_stations() if s.get("custom")]
OTSO_STATIONS = [s["code"] for s in load_stations() if not s.get("custom")]

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# TSY01S (storm-time TSY01) uses the live Pdyn, Dst, By, Bz, G2 and G3, and its own
# built-in magnetopause (overriding "magnetopause" below). Live data is not supported
# for TSY04 or TA16_RBF.
EXTERNAL_MODEL = "TSY01S"
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


def _steps(start: float, stop: float, step: float) -> list:
    return [round(start + i * step, 2) for i in range(round((stop - start) / step))]


# Asymptotic viewing directions are computed at these rigidities (GV), finer at low
# rigidity where directions change fastest. Changing this list changes the columns
# of data/asymptotic files, so only do it at the start of a month.
ASYM_LEVELS = (_steps(1, 2, 0.1) + _steps(2, 5, 0.25) + _steps(5, 10, 0.5) + _steps(10, 20, 1)
               + _steps(20, 50, 2.5) + _steps(50, 100, 5) + [100])
ASYM_DIR = os.path.join(OUTPUT_DIR, "asymptotic")
ASYM_HEADER = ["datetime_utc"] + [f"{level:g}GV" for level in ASYM_LEVELS]
DELIM = ";"

# Model inputs OTSO actually used for each hour, parsed from its input summary:
# (label in OTSO's summary, column name). One row per hour in data/inputs.csv.
INPUT_FIELDS = [
    ("Kp", "Kp"), ("IOPT", "IOPT"),
    ("Vx", "Vx_kms"), ("Vy", "Vy_kms"), ("Vz", "Vz_kms"),
    ("Bx", "Bx_nT"), ("By", "By_nT"), ("Bz", "Bz_nT"),
    ("By Average (30mins)", "By_avg30_nT"), ("Bz Average (30mins)", "Bz_avg30_nT"),
    ("Density", "density_cm3"), ("Pdyn", "Pdyn_nPa"), ("Dst", "Dst_nT"),
    ("G1", "G1"), ("G2", "G2"), ("G3", "G3"),
    ("W1", "W1"), ("W2", "W2"), ("W3", "W3"), ("W4", "W4"), ("W5", "W5"), ("W6", "W6"),
    ("N", "N_index"), ("B", "B_index"), ("SYM-H", "SYMH_nT"),
]
# OTSO's summary reports "User Inputted Data Used" even with livedata on, so the source is
# recorded from this script's own setting instead.
DATA_SOURCE = "live (NOAA SWPC RTSW; Kyoto WDC Dst; GFZ Kp)"
INPUTS_HEADER = (["datetime_utc"] + [col for _, col in INPUT_FIELDS]
                 + ["data_source", "external_model", "otso_version", "computed_at_utc"])


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

    asymptotic_inputs = {"asymptotic": "YES", "asymlevels": ASYM_LEVELS, "unit": "GV"}

    computation_inputs = {"corenum": corenum, "threadnum": threadnum, "Verbose": False, "delim": DELIM}

    data_retrieval_inputs = {"serverdata": "OFF", "livedata": "ON"}

    results = cutoff(
        Stations=OTSO_STATIONS,
        customlocations=CUSTOM_LOCATIONS or None,
        cutoff_comp="Vertical",
        datetime_params=date_inputs,
        magfield_params=magfield_inputs,
        rigidity_params=rigidity_inputs,
        integration_params=integration_inputs,
        asymptotic_params=asymptotic_inputs,
        computation_params=computation_inputs,
        coordinate_params={"coordsystem": "GEO", "inputcoord": "GDZ"},
        data_retrieval_params=data_retrieval_inputs,
    )
    # results[0]: Ru/Rc/Rl per station (columns); results[1]: one row per station,
    # one "filter;lat;lon" cell per asymptotic level; results[-1]: OTSO's text summary
    # of the inputs it used.
    return results[0], results[1], results[-1]


def inputs_path() -> str:
    return os.path.join(OUTPUT_DIR, "inputs.csv")


def parse_inputs(summary: str) -> dict:
    """Pull the input values out of OTSO's summary text ("Label = value" lines)."""
    values = {}
    for label, col in INPUT_FIELDS:
        m = re.search(rf"^\s*{re.escape(label)}\s*=\s*([-+0-9.eE]+)", summary, re.M)
        values[col] = m.group(1) if m else ""
    m = re.search(r"^OTSO Version:\s*(\S+)", summary, re.M)
    values["otso_version"] = m.group(1) if m else ""
    return values


def cutoff_path(name: str) -> str:
    return os.path.join(OUTPUT_DIR, f"{name}_cutoff.csv")


def asym_path(name: str, event_time: datetime) -> str:
    return os.path.join(ASYM_DIR, name, f"{event_time:%Y-%m}.csv")


def recorded_times(csv_path: str) -> set:
    if not os.path.exists(csv_path):
        return set()
    with open(csv_path, newline="") as f:
        return {row[0] for row in csv.reader(f) if row and row[0] != "datetime_utc"}


def append_row(csv_path: str, header: list, row: list) -> None:
    new_file = not os.path.exists(csv_path)
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(header)
        writer.writerow(row)


def sort_csv(csv_path: str) -> None:
    # Backfilled hours are appended out of order; keep each file chronological.
    if not os.path.exists(csv_path):
        return
    with open(csv_path, newline="") as f:
        header, *rows = [row for row in csv.reader(f) if row]
    rows.sort(key=lambda row: row[0])
    tmp_path = csv_path + ".tmp"
    with open(tmp_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    os.replace(tmp_path, csv_path)


def asym_cells(asym_df, code: str) -> list:
    """The station's "filter;lat;lon" cells in ASYM_LEVELS order, lat/lon to 0.01 deg."""
    row = asym_df[asym_df["Station"] == code]
    if row.empty:
        return None
    raw = [str(v) for v in row.drop(columns="Station").iloc[0].tolist()]
    if len(raw) != len(ASYM_LEVELS):
        raise ValueError(f"expected {len(ASYM_LEVELS)} asymptotic levels for {code}, got {len(raw)}")
    cells = []
    for cell in raw:
        try:
            flag, lat, lon = cell.split(DELIM)[:3]
            cells.append(f"{int(float(flag))}{DELIM}{float(lat):.2f}{DELIM}{float(lon):.2f}")
        except ValueError:
            cells.append(cell)
    return cells


def compute_hour(event_time: datetime) -> None:
    timestamp = event_time.strftime("%Y-%m-%d %H:%M:%S")
    cut_df, asym_df, summary = compute(event_time)
    computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    if timestamp not in recorded_times(inputs_path()):
        v = parse_inputs(summary)
        missing = [col for _, col in INPUT_FIELDS if v[col] == ""]
        if missing:
            print(f"{timestamp}: inputs not found in OTSO summary: {', '.join(missing)}", file=sys.stderr)
        append_row(inputs_path(), INPUTS_HEADER,
                   [timestamp] + [v[col] for _, col in INPUT_FIELDS]
                   + [DATA_SOURCE, EXTERNAL_MODEL, v["otso_version"], computed_at])

    for name, code in STATIONS.items():
        if timestamp not in recorded_times(cutoff_path(name)):
            if code in cut_df.columns:
                col = cut_df[code]
                append_row(cutoff_path(name), CSV_HEADER,
                           [timestamp, col["Ru"], col["Rc"], col["Rl"], EXTERNAL_MODEL, computed_at])
                print(f"{timestamp}: {name} Ru={col['Ru']} Rc={col['Rc']} Rl={col['Rl']}", flush=True)
            else:
                print(f"{timestamp}: no cut-off result for {name} ({code})", file=sys.stderr)

        if timestamp not in recorded_times(asym_path(name, event_time)):
            cells = asym_cells(asym_df, code)
            if cells is None:
                print(f"{timestamp}: no asymptotic result for {name} ({code})", file=sys.stderr)
            else:
                append_row(asym_path(name, event_time), ASYM_HEADER, [timestamp] + cells)


def live_data_unavailable(e: BaseException) -> bool:
    """True when OTSO could not download the live inputs (network or source down)."""
    return isinstance(e, RuntimeError) and "could not be downloaded" in str(e)


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    latest = (datetime.now(timezone.utc) - timedelta(hours=LAG_HOURS)).replace(
        minute=0, second=0, microsecond=0, tzinfo=None)
    candidates = [latest - timedelta(hours=h) for h in range(BACKFILL_HOURS - LAG_HOURS, -1, -1)]

    # An hour is done only when its inputs and every station's cut-off and asymptotic rows are recorded.
    files = ({inputs_path()} | {cutoff_path(n) for n in STATIONS}
             | {asym_path(n, t) for n in STATIONS for t in candidates})
    recorded = {p: recorded_times(p) for p in files}

    def complete(t: datetime) -> bool:
        ts = t.strftime("%Y-%m-%d %H:%M:%S")
        return ts in recorded[inputs_path()] and all(
            ts in recorded[cutoff_path(n)] and ts in recorded[asym_path(n, t)] for n in STATIONS)

    missing = [t for t in candidates if not complete(t)]

    if not missing:
        print(f"{latest}: nothing to compute, all hours recorded.")
        return 0
    if len(missing) > 1:
        print(f"{len(missing)} hours to compute ({missing[0]} to {missing[-1]}).", flush=True)

    failures = 0
    for k, event_time in enumerate(missing):  # oldest first, since those are closest to expiring
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if now - event_time > timedelta(hours=MAX_AGE_HOURS):
            print(f"{event_time}: too old for live data, skipping.", file=sys.stderr)
            continue
        try:
            compute_hour(event_time)
        except (Exception, SystemExit) as e:  # OTSO calls exit() on some input errors
            failures += 1
            print(f"{event_time}: computation failed ({e!r})", file=sys.stderr)
            if live_data_unavailable(e):
                # Every remaining hour needs the same downloads; stop instead of retrying
                # each one. These hours stay missing and the next run tries them again.
                left = len(missing) - k - 1
                if left:
                    print(f"Live data unavailable (network?); leaving the remaining {left} hour(s) "
                          "for the next run.", file=sys.stderr)
                break

    for p in files:
        sort_csv(p)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
