"""
Plot cut-off rigidities for all stations.

Usage:
    python plot_cutoffs.py OUT_DIR

Writes two small-multiples PNGs (last 7 days hourly, and daily averages over up to
a year), asymptotic.json (hourly asymptotic viewing directions for the last 7 days,
drawn in the browser as a map with a time slider) and an index.html into OUT_DIR,
which the Plots workflow publishes to GitHub Pages. Headless: Agg backend.
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from stations import load_stations
from hourly_cutoff import ASYM_LEVELS, DELIM, EXTERNAL_MODEL, OUTPUT_DIR as DATA_DIR, STATIONS

WINDOW = timedelta(days=7)
LONG_WINDOW = timedelta(days=365)
MIN_LONG_SPAN = timedelta(days=30)  # keep the long plot readable while data is young
MIN_HOURS_PER_DAY = 12              # days with fewer hourly values get no average

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES = "#2a78d6"

# Sequential blue ramp (steps 250-700) for rigidity on the asymptotic maps: light = low R.
ASYM_RAMP = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf",
             "#1c5cab", "#184f95", "#104281", "#0d366b"]
LAND = "#ecebe7"

# Geographic station locations (lat, lon in degrees), from stations.json.
STATION_COORDS = {s["name"]: (s["lat"], s["lon"]) for s in load_stations()}
PLOTLY_JS = "https://cdn.plot.ly/plotly-2.35.2.min.js"

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "axes.labelcolor": TEXT_SECONDARY,
    "axes.titlecolor": TEXT_PRIMARY,
    "xtick.color": TEXT_SECONDARY,
    "ytick.color": TEXT_SECONDARY,
    "text.color": TEXT_PRIMARY,
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
})
PNG_METADATA = {"Software": None}


def read_station(name: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{name}_cutoff.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=["Ru_GV", "Rc_GV", "Rl_GV"], index=pd.DatetimeIndex([]), dtype=float)
    df = pd.read_csv(path, parse_dates=["datetime_utc"]).set_index("datetime_utc")
    df = df[~df.index.duplicated(keep="last")]
    return df[["Ru_GV", "Rc_GV", "Rl_GV"]]


def hourly(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    """Hourly frame for [start, end]; missing hours are NaN so lines break at gaps."""
    return df.reindex(pd.date_range(start, end, freq="h"))


def daily(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    """Daily means for [start, end]; under-sampled days are NaN."""
    days = pd.date_range(start, end, freq="D")
    if df.empty:
        return pd.DataFrame(index=days, columns=df.columns, dtype=float)
    means = df.resample("D").mean()
    counts = df["Rc_GV"].resample("D").count()
    means[counts < MIN_HOURS_PER_DAY] = float("nan")
    return means.reindex(days)


def read_asymptotic(name: str, start: datetime, end: datetime) -> dict:
    """{timestamp: (lats, lons)} for [start, end]; non-allowed levels are None."""
    asym_dir = os.path.join(DATA_DIR, "asymptotic", name)
    months = sorted({f"{d:%Y-%m}" for d in pd.date_range(start, end, freq="D")} | {f"{end:%Y-%m}"})
    out = {}
    for month in months:
        path = os.path.join(asym_dir, f"{month}.csv")
        if not os.path.exists(path):
            continue
        with open(path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            if header[1:] != [f"{level:g}GV" for level in ASYM_LEVELS]:
                print(f"skipping {path}: levels differ from ASYM_LEVELS", file=sys.stderr)
                continue
            for row in reader:
                if not row or not (f"{start:%Y-%m-%d %H:%M:%S}" <= row[0] <= f"{end:%Y-%m-%d %H:%M:%S}"):
                    continue
                lats, lons = [], []
                for cell in row[1:]:
                    parts = cell.split(DELIM)
                    if len(parts) >= 3 and parts[0].strip() == "1":
                        lon = float(parts[2])
                        lats.append(round(float(parts[1]), 2))
                        lons.append(round(lon - 360 if lon > 180 else lon, 2))
                    else:
                        lats.append(None)
                        lons.append(None)
                out[row[0]] = (lats, lons)
    return out


def asymptotic_payload(start: datetime, end: datetime) -> dict:
    """Hourly directions per station, keeping only rigidities at or above that hour's Ru."""
    per_station = {name: read_asymptotic(name, start, end) for name in STATIONS}
    times = sorted(set().union(*per_station.values()))
    blank = [None] * len(ASYM_LEVELS)
    stations = {}
    for name, rows in per_station.items():
        ru = read_station(name)["Ru_GV"]
        lats, lons = [], []
        for t in times:
            lat, lon = rows.get(t, (blank, blank))
            ru_t = ru.get(pd.Timestamp(t))
            if ru_t is not None and ru_t == ru_t:  # skip NaN; without Ru keep the allowed levels only
                keep = [level >= ru_t for level in ASYM_LEVELS]
                lat = [v if k else None for v, k in zip(lat, keep)]
                lon = [v if k else None for v, k in zip(lon, keep)]
            lats.append(lat)
            lons.append(lon)
        stations[name] = {"loc": STATION_COORDS[name], "lat": lats, "lon": lons}
    return {"levels": ASYM_LEVELS, "times": times, "stations": stations}


def draw(ax, name: str, df: pd.DataFrame, start: datetime, end: datetime, latest_label: str) -> None:
    ax.fill_between(df.index, df["Rl_GV"], df["Ru_GV"], color=SERIES, alpha=0.18,
                    linewidth=0, label="Penumbra (Rl–Ru)")
    ax.plot(df.index, df["Rc_GV"], color=SERIES, linewidth=1.5, label="Effective cut-off Rc")
    # Points with no neighbours draw no line segment; mark them so gaps stay honest.
    rc = df["Rc_GV"]
    lone = rc.notna() & rc.shift(1).isna() & rc.shift(-1).isna()
    if lone.any():
        ax.vlines(df.index[lone], df["Rl_GV"][lone], df["Ru_GV"][lone], color=SERIES, alpha=0.35, linewidth=2)
        ax.plot(df.index[lone], rc[lone], "o", color=SERIES, markersize=4)

    latest = df["Rc_GV"].dropna()
    subtitle = f"{latest_label} {latest.iloc[-1]:.2f} GV" if len(latest) else "no data in window"
    ax.set_title(f"{name}  ·  {subtitle}", loc="left", fontsize=10, fontweight="bold")

    ax.set_xlim(start, end)
    ax.set_ylabel("Rigidity (GV)")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.tick_params(length=0)
    if end - start <= timedelta(days=14):
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    else:
        locator = mdates.AutoDateLocator(maxticks=10)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    # Flat series (e.g. Thule at 0 GV) still get a readable axis.
    lo, hi = ax.get_ylim()
    if hi - lo < 0.2:
        mid = (hi + lo) / 2
        ax.set_ylim(max(0, mid - 0.1), mid + 0.1 if mid > 0.1 else 0.2)


def small_multiples(frames: dict, start: datetime, end: datetime, title: str,
                    latest_label: str, footer: str, path: str) -> None:
    # Stations differ by several GV, so each gets its own y-scale.
    fig, axes = plt.subplots(len(frames), 1, figsize=(10, 2.4 * len(frames)), sharex=True)
    for ax, (name, df) in zip(axes, frames.items()):
        draw(ax, name, df, start, end, latest_label)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=2, frameon=False)
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold")
    axes[-1].set_xlabel("Date (UTC)")
    fig.text(0.01, 0.005, footer, fontsize=8, color=TEXT_SECONDARY)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(path, dpi=110, metadata=PNG_METADATA)
    plt.close(fig)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)

    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    data = {name: read_station(name) for name in STATIONS}
    footer = f"OTSO, {EXTERNAL_MODEL} + IGRF, NOAA live inputs · updated {end:%Y-%m-%d %H:%M} UTC"

    start = end - WINDOW
    small_multiples({n: hourly(df, start, end) for n, df in data.items()}, start, end,
                    "Vertical cut-off rigidity, last 7 days (hourly)", "latest Rc", footer,
                    os.path.join(out_dir, "all_stations_7d.png"))

    # Long window grows with the record until it reaches a year.
    today = end.replace(hour=0)
    first = pd.Timestamp(min((df.index.min() for df in data.values() if not df.empty), default=today))
    long_start = max(today - LONG_WINDOW, first.normalize().to_pydatetime())
    long_start = min(long_start, today - MIN_LONG_SPAN)
    span_days = (today - long_start).days
    small_multiples({n: daily(df, long_start, today) for n, df in data.items()}, long_start, today,
                    f"Vertical cut-off rigidity, daily averages, last {span_days} days",
                    "latest daily mean Rc", footer + f" · days with ≥{MIN_HOURS_PER_DAY} h of data",
                    os.path.join(out_dir, "all_stations_daily.png"))

    payload = asymptotic_payload(end - WINDOW, end)
    with open(os.path.join(out_dir, "asymptotic.json"), "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    ramp = json.dumps([[i / (len(ASYM_RAMP) - 1), c] for i, c in enumerate(ASYM_RAMP)])
    station_order = json.dumps(list(STATIONS))

    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Neutron monitor cut-offs</title>
<style>
  body {{ background: {SURFACE}; color: {TEXT_PRIMARY}; font-family: system-ui, sans-serif;
         max-width: 1100px; margin: 0 auto; padding: 16px; }}
  img {{ max-width: 100%; height: auto; }}
  p {{ color: {TEXT_SECONDARY}; }}
  .slider-row {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: 8px 0 4px; }}
  .slider-row input[type=range] {{ flex: 1 1 320px; accent-color: {SERIES}; }}
  .slider-row button {{ font: inherit; padding: 4px 14px; border: 1px solid {GRID}; border-radius: 6px;
                        background: #fff; color: {TEXT_PRIMARY}; cursor: pointer; min-width: 72px; }}
  .slider-row output {{ font-variant-numeric: tabular-nums; color: {TEXT_PRIMARY}; min-width: 15ch; }}
  .station-toggle {{ display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }}
  .station-toggle input {{ accent-color: {SERIES}; width: 16px; height: 16px; }}
  #asym {{ width: 100%; height: 600px; }}
  @media (max-width: 700px) {{ #asym {{ height: 420px; }} }}
</style>
</head>
<body>
<h1>Neutron monitor vertical cut-off rigidity</h1>
<p>Updated {end:%Y-%m-%d %H:%M} UTC. Data: <code>main</code> branch, <code>data/</code>.</p>
<h2>Last 7 days, hourly</h2>
<img src="all_stations_7d.png" alt="Hourly cut-off rigidity for all stations, last 7 days">
<h2>Daily averages, last {span_days} days</h2>
<img src="all_stations_daily.png" alt="Daily mean cut-off rigidity for all stations, last {span_days} days">
<h2>Asymptotic viewing directions, last 7 days</h2>
<p>Direction (geographic coordinates) from which particles arriving vertically at each station come
from outside the magnetosphere, for rigidities from the station's upper cut-off Ru up to 100 GV;
colour shows rigidity and marker shape the station (its location is the black marker of the same shape).
Tick stations on or off, drag the slider (or use the arrow keys) or press Play; hover a point for details.</p>
<div class="slider-row" id="asym-stations" role="group" aria-label="Stations shown"></div>
<div class="slider-row">
  <button id="asym-play" type="button">Play</button>
  <input id="asym-time" type="range" min="0" max="0" value="0" step="1" aria-label="Hour shown">
  <output id="asym-label" for="asym-time">loading…</output>
</div>
<div id="asym"></div>
<script src="{PLOTLY_JS}"></script>
<script>
(async function () {{
  const el = document.getElementById("asym");
  const slider = document.getElementById("asym-time");
  const label = document.getElementById("asym-label");
  const play = document.getElementById("asym-play");
  const boxes = document.getElementById("asym-stations");
  let data;
  try {{
    data = await (await fetch("asymptotic.json", {{cache: "no-store"}})).json();
  }} catch (e) {{ label.textContent = "No asymptotic data available"; return; }}
  if (!data.times.length) {{ label.textContent = "No asymptotic data in the last 7 days"; play.disabled = true; return; }}

  const names = {station_order};
  // Shape identifies the station (colour is rigidity); cycles if there are more stations than shapes.
  const shapes = [["circle", "●"], ["square", "■"], ["diamond", "◆"], ["triangle-up", "▲"],
                  ["triangle-down", "▼"], ["star", "★"], ["cross", "✚"], ["x", "✖"],
                  ["pentagon", "⬟"], ["hexagon", "⬢"], ["hourglass", "⧗"], ["star-triangle-up", "⟁"]];
  const symbols = names.map((_, i) => shapes[i % shapes.length][0]);
  const glyphs = names.map((_, i) => shapes[i % shapes.length][1]);
  const ramp = {ramp};
  const logR = data.levels.map(Math.log10);
  const hoverR = data.levels.map(r => r + " GV");
  const narrow = window.matchMedia("(max-width: 700px)").matches;
  const shown = Object.fromEntries(names.map(n => [n, true]));

  names.forEach((name, i) => {{
    const lab = document.createElement("label");
    lab.className = "station-toggle";
    lab.innerHTML = '<input type="checkbox" checked> <span aria-hidden="true">' + glyphs[i] + '</span> ' + name;
    lab.querySelector("input").addEventListener("change", ev => {{ shown[name] = ev.target.checked; show(+slider.value); }});
    boxes.appendChild(lab);
  }});

  const colorbar = Object.assign({{tickvals: [0, 0.5, 1, 1.5, 2], ticktext: ["1", "3", "10", "30", "100"],
                                  outlinewidth: 0, tickcolor: "{TEXT_SECONDARY}"}},
    narrow ? {{orientation: "h", x: 0.5, xanchor: "center", y: -0.02, yanchor: "top", len: 0.8, thickness: 10,
               title: {{text: "Rigidity (GV)", side: "top"}}}}
           : {{thickness: 12, len: 0.7, title: {{text: "Rigidity (GV)", side: "right"}}}});

  function traces(t) {{
    const out = [];
    names.forEach((name, i) => {{
      const st = data.stations[name], visible = shown[name];
      out.push({{type: "scattergeo", mode: "markers", lat: st.lat[t], lon: st.lon[t], text: hoverR, visible,
                 marker: {{symbol: symbols[i], size: 8, color: logR, colorscale: ramp, cmin: 0, cmax: 2,
                          line: {{width: 0}}, showscale: i === 0, colorbar}},
                 hovertemplate: "<b>" + name + "</b> %{{text}}<br>%{{lat:.2f}}°, %{{lon:.2f}}°<extra></extra>",
                 showlegend: false}});
      out.push({{type: "scattergeo", mode: "markers", lat: [st.loc[0]], lon: [st.loc[1]], visible,
                 marker: {{symbol: symbols[i], size: 13, color: "{TEXT_PRIMARY}", line: {{width: 0}}}},
                 hovertemplate: "<b>" + name + "</b> station<br>%{{lat:.2f}}°, %{{lon:.2f}}°<extra></extra>",
                 showlegend: false}});
    }});
    // Keep the colour bar even when the first station is hidden.
    const firstShown = names.findIndex(n => shown[n]);
    out.forEach((tr, k) => {{ if (k % 2 === 0) tr.marker.showscale = (k / 2 === firstShown); }});
    return out;
  }}

  const layout = {{
    paper_bgcolor: "{SURFACE}", margin: {{l: 8, r: 8, t: 8, b: narrow ? 70 : 8}},
    font: {{family: "system-ui, sans-serif", color: "{TEXT_PRIMARY}", size: 12}},
    hoverlabel: {{bgcolor: "#fff", bordercolor: "{GRID}", font: {{color: "{TEXT_PRIMARY}"}}}},
    uirevision: "keep",  // keep the user's zoom/pan while the slider moves
    geo: {{projection: {{type: "natural earth"}}, showland: true, landcolor: "{LAND}", showocean: true,
           oceancolor: "{SURFACE}", showcountries: false, coastlinecolor: "#c9c7c0", coastlinewidth: 0.6,
           bgcolor: "{SURFACE}", showframe: false,
           lataxis: {{showgrid: true, gridcolor: "{GRID}", dtick: 30}}, lonaxis: {{showgrid: true, gridcolor: "{GRID}", dtick: 60}}}}
  }};

  slider.max = data.times.length - 1;
  slider.value = data.times.length - 1;
  function show(t) {{
    label.textContent = data.times[t].slice(0, 16) + " UTC";
    Plotly.react(el, traces(t), layout, {{responsive: true, displaylogo: false}});
  }}
  show(+slider.value);
  slider.addEventListener("input", () => show(+slider.value));

  let timer = null;
  play.addEventListener("click", () => {{
    if (timer) {{ clearInterval(timer); timer = null; play.textContent = "Play"; return; }}
    if (+slider.value >= +slider.max) slider.value = 0;
    play.textContent = "Pause";
    timer = setInterval(() => {{
      if (+slider.value >= +slider.max) {{ clearInterval(timer); timer = null; play.textContent = "Play"; return; }}
      slider.value = +slider.value + 1;
      show(+slider.value);
    }}, 200);
  }});
}})();
</script>
</body>
</html>
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
