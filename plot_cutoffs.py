"""
Plot cut-off rigidities for all stations.

Usage:
    python plot_cutoffs.py OUT_DIR

Writes into OUT_DIR, which the Plots workflow publishes to GitHub Pages:
  index.html     landing page: the featured (key) stations - 7-day hourly and daily-average
                 PNGs, and the asymptotic-direction map
  stations.html  all stations - overview table, interactive cut-off chart per station, and
                 the asymptotic-direction map
  asymptotic.json, cutoffs.json   data for the interactive charts
Headless: Agg backend.
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


def label(name: str) -> str:
    """Display form of a station name (names use '_' instead of spaces for file names)."""
    return name.replace("_", " ")


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
    ax.set_title(f"{label(name)}  ·  {subtitle}", loc="left", fontsize=10, fontweight="bold")

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
    # Shorter panels when there are many stations, so the image stays a sensible size.
    panel_h = 2.4 if len(frames) <= 6 else 1.7
    fig, axes = plt.subplots(len(frames), 1, figsize=(10, panel_h * len(frames) + 0.6), sharex=True)
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


# Stations shown on the landing page: those marked "featured" in stations.json
# (the four key stations of Mertens et al. 2025); everything is on stations.html.
FEATURED = [s["name"] for s in load_stations() if s.get("featured")] or list(STATIONS)[:4]

MERTENS = ('Mertens, Gronoff &amp; Phoenix (2025), <i>Space Weather</i> 23, e2024SW004296, '
           '<a href="https://doi.org/10.1029/2024SW004296">doi:10.1029/2024SW004296</a>')

CSS = """
  body { background: SURFACE; color: TEXT; font-family: system-ui, sans-serif;
         max-width: 1100px; margin: 0 auto; padding: 16px; }
  img { max-width: 100%; height: auto; }
  p, .muted { color: TEXT2; }
  a { color: #256abf; }
  nav { display: flex; gap: 18px; flex-wrap: wrap; border-bottom: 1px solid GRID; padding-bottom: 8px; }
  nav a { text-decoration: none; font-weight: 600; color: TEXT2; }
  nav a[aria-current] { color: TEXT; border-bottom: 2px solid SERIES; }
  .slider-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: 8px 0 4px; }
  .slider-row input[type=range] { flex: 1 1 320px; accent-color: SERIES; }
  button, select { font: inherit; padding: 4px 12px; border: 1px solid GRID; border-radius: 6px;
                   background: #fff; color: TEXT; cursor: pointer; }
  button[aria-pressed=true] { background: SERIES; border-color: SERIES; color: #fff; }
  .slider-row output { font-variant-numeric: tabular-nums; color: TEXT; min-width: 15ch; }
  .station-toggle { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
  .station-toggle input { accent-color: SERIES; width: 16px; height: 16px; }
  #asym { width: 100%; height: 600px; }
  #cut { width: 100%; height: 420px; }
  @media (max-width: 700px) { #asym { height: 420px; } #cut { height: 340px; } }
  .table-wrap { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; font-size: 14px; }
  th, td { padding: 6px 10px; border-bottom: 1px solid GRID; text-align: right; white-space: nowrap; }
  th { color: TEXT2; font-weight: 600; }
  th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) { text-align: left; }
  td.key::after { content: " ★"; color: SERIES; }
"""


def css() -> str:
    return (CSS.replace("SURFACE", SURFACE).replace("TEXT2", TEXT_SECONDARY)
               .replace("TEXT", TEXT_PRIMARY).replace("GRID", GRID).replace("SERIES", SERIES))


def page(path: str, title: str, current: str, body: str) -> None:
    links = [("index.html", "Key stations"), ("stations.html", "All stations")]
    nav = " ".join(f'<a href="{href}"' + (' aria-current="page"' if href == current else "") + f">{text}</a>"
                   for href, text in links)
    with open(path, "w") as f:
        f.write(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css()}</style>
</head>
<body>
<nav>{nav}</nav>
{body}
</body>
</html>
""")


# Interactive asymptotic-direction map. Plain text with __TOKENS__ (no f-string braces).
ASYM_JS = r"""
<div class="slider-row" id="asym-stations" role="group" aria-label="Stations shown"></div>
<div class="slider-row">
  <button id="asym-play" type="button">Play</button>
  <input id="asym-time" type="range" min="0" max="0" value="0" step="1" aria-label="Hour shown">
  <output id="asym-label" for="asym-time">loading…</output>
</div>
<div id="asym"></div>
<script>
(async function () {
  const el = document.getElementById("asym");
  const slider = document.getElementById("asym-time");
  const label = document.getElementById("asym-label");
  const play = document.getElementById("asym-play");
  const boxes = document.getElementById("asym-stations");
  let data;
  try {
    data = await (await fetch("asymptotic.json", {cache: "no-store"})).json();
  } catch (e) { label.textContent = "No asymptotic data available"; return; }
  if (!data.times.length) { label.textContent = "No asymptotic data in the last 7 days"; play.disabled = true; return; }

  const allNames = __ALL_NAMES__;        // global order: a station keeps its shape on every page
  const names = __NAMES__.filter(n => n in data.stations);
  // Shape identifies the station (colour is rigidity); cycles if there are more stations than shapes.
  const shapes = [["circle", "●"], ["square", "■"], ["diamond", "◆"], ["triangle-up", "▲"],
                  ["triangle-down", "▼"], ["star", "★"], ["cross", "✚"], ["x", "✖"],
                  ["pentagon", "⬟"], ["hexagon", "⬢"], ["hourglass", "⧗"], ["star-triangle-up", "⟁"],
                  ["triangle-left", "◀"], ["triangle-right", "▶"], ["star-square", "✦"],
                  ["diamond-tall", "⧫"], ["octagon", "⯃"], ["star-diamond", "✧"],
                  ["bowtie", "⋈"], ["hexagram", "✡"]];
  const shapeOf = n => shapes[Math.max(0, allNames.indexOf(n)) % shapes.length];
  const ramp = __RAMP__;
  const logR = data.levels.map(Math.log10);
  const hoverR = data.levels.map(r => r + " GV");
  const narrow = window.matchMedia("(max-width: 700px)").matches;
  const shown = Object.fromEntries(names.map(n => [n, true]));
  const label = n => n.replace(/_/g, " ");

  names.forEach(name => {
    const lab = document.createElement("label");
    lab.className = "station-toggle";
    lab.innerHTML = '<input type="checkbox" checked> <span aria-hidden="true">' + shapeOf(name)[1] + '</span> ' + label(name);
    lab.querySelector("input").addEventListener("change", ev => { shown[name] = ev.target.checked; show(+slider.value); });
    boxes.appendChild(lab);
  });

  const colorbar = Object.assign({tickvals: [0, 0.5, 1, 1.5, 2], ticktext: ["1", "3", "10", "30", "100"],
                                  outlinewidth: 0, tickcolor: "__TEXT2__"},
    narrow ? {orientation: "h", x: 0.5, xanchor: "center", y: -0.02, yanchor: "top", len: 0.8, thickness: 10,
              title: {text: "Rigidity (GV)", side: "top"}}
           : {thickness: 12, len: 0.7, title: {text: "Rigidity (GV)", side: "right"}});

  function traces(t) {
    const out = [];
    names.forEach(name => {
      const st = data.stations[name], visible = shown[name], sym = shapeOf(name)[0];
      out.push({type: "scattergeo", mode: "markers", lat: st.lat[t], lon: st.lon[t], text: hoverR, visible,
                marker: {symbol: sym, size: 8, color: logR, colorscale: ramp, cmin: 0, cmax: 2,
                         line: {width: 0}, showscale: false, colorbar},
                hovertemplate: "<b>" + label(name) + "</b> %{text}<br>%{lat:.2f}°, %{lon:.2f}°<extra></extra>",
                showlegend: false});
      out.push({type: "scattergeo", mode: "markers", lat: [st.loc[0]], lon: [st.loc[1]], visible,
                marker: {symbol: sym, size: 13, color: "__TEXT__", line: {width: 0}},
                hovertemplate: "<b>" + label(name) + "</b> station<br>%{lat:.2f}°, %{lon:.2f}°<extra></extra>",
                showlegend: false});
    });
    // One colour bar, on the first visible station.
    const firstShown = names.findIndex(n => shown[n]);
    out.forEach((tr, k) => { if (k % 2 === 0) tr.marker.showscale = (k / 2 === firstShown); });
    return out;
  }

  const layout = {
    paper_bgcolor: "__SURFACE__", margin: {l: 8, r: 8, t: 8, b: narrow ? 70 : 8},
    font: {family: "system-ui, sans-serif", color: "__TEXT__", size: 12},
    hoverlabel: {bgcolor: "#fff", bordercolor: "__GRID__", font: {color: "__TEXT__"}},
    uirevision: "keep",  // keep the user's zoom/pan while the slider moves
    geo: {projection: {type: "natural earth"}, showland: true, landcolor: "__LAND__", showocean: true,
          oceancolor: "__SURFACE__", showcountries: false, coastlinecolor: "#c9c7c0", coastlinewidth: 0.6,
          bgcolor: "__SURFACE__", showframe: false,
          lataxis: {showgrid: true, gridcolor: "__GRID__", dtick: 30}, lonaxis: {showgrid: true, gridcolor: "__GRID__", dtick: 60}}
  };

  slider.max = data.times.length - 1;
  slider.value = data.times.length - 1;
  function show(t) {
    label.textContent = data.times[t].slice(0, 16) + " UTC";
    Plotly.react(el, traces(t), layout, {responsive: true, displaylogo: false});
  }
  show(+slider.value);
  slider.addEventListener("input", () => show(+slider.value));

  let timer = null;
  play.addEventListener("click", () => {
    if (timer) { clearInterval(timer); timer = null; play.textContent = "Play"; return; }
    if (+slider.value >= +slider.max) slider.value = 0;
    play.textContent = "Pause";
    timer = setInterval(() => {
      if (+slider.value >= +slider.max) { clearInterval(timer); timer = null; play.textContent = "Play"; return; }
      slider.value = +slider.value + 1;
      show(+slider.value);
    }, 200);
  });
})();
</script>
"""

# Interactive cut-off chart for one chosen station (all-stations page).
CUT_JS = r"""
<div class="slider-row">
  <label for="cut-station">Station</label>
  <select id="cut-station"></select>
  <span role="group" aria-label="Time range">
    <button type="button" id="cut-hourly" aria-pressed="true">Last 7 days, hourly</button>
    <button type="button" id="cut-daily" aria-pressed="false">Daily averages</button>
  </span>
</div>
<div id="cut"></div>
<script>
(async function () {
  const el = document.getElementById("cut");
  const sel = document.getElementById("cut-station");
  const bH = document.getElementById("cut-hourly"), bD = document.getElementById("cut-daily");
  let data;
  try { data = await (await fetch("cutoffs.json", {cache: "no-store"})).json(); }
  catch (e) { el.textContent = "No cut-off data available"; return; }
  const label = n => n.replace(/_/g, " ");
  data.names.forEach(n => { const o = document.createElement("option"); o.value = n; o.textContent = label(n); sel.appendChild(o); });
  const fromHash = decodeURIComponent(location.hash.slice(1));
  if (data.names.includes(fromHash)) sel.value = fromHash;
  let mode = "hourly";

  function draw() {
    const d = data[mode], st = d.stations[sel.value], x = d.times;
    const band = "rgba(42,120,214,0.18)";
    const traces = [
      {x, y: st.Ru, mode: "lines", line: {width: 0}, hoverinfo: "skip", showlegend: false},
      {x, y: st.Rl, mode: "lines", line: {width: 0}, fill: "tonexty", fillcolor: band,
       name: "Penumbra (Rl–Ru)", hoverinfo: "skip"},
      {x, y: st.Rc, mode: mode === "hourly" ? "lines+markers" : "lines", marker: {size: 3},
       line: {color: "__SERIES__", width: 2}, name: "Effective cut-off Rc",
       customdata: st.Ru.map((u, i) => [u, st.Rl[i]]),
       hovertemplate: "%{x|%Y-%m-%d %H:%M} UTC<br>Rc %{y:.2f} GV<br>Ru %{customdata[0]:.2f} · Rl %{customdata[1]:.2f} GV<extra></extra>"}
    ];
    const layout = {
      paper_bgcolor: "__SURFACE__", plot_bgcolor: "__SURFACE__", margin: {l: 56, r: 12, t: 36, b: 84},
      font: {family: "system-ui, sans-serif", color: "__TEXT__", size: 12},
      title: {text: "<b>" + label(sel.value) + "</b>  " + (mode === "hourly" ? "last 7 days, hourly" : "daily averages"),
              x: 0, xanchor: "left", font: {size: 14}},
      legend: {orientation: "h", x: 0, xanchor: "left", y: -0.22, yanchor: "top"},
      xaxis: {gridcolor: "__GRID__", title: {text: "Date (UTC)"}},
      yaxis: {gridcolor: "__GRID__", title: {text: "Rigidity (GV)"}, rangemode: "tozero"},
      hovermode: "x unified", hoverlabel: {bgcolor: "#fff", bordercolor: "__GRID__"}
    };
    Plotly.react(el, traces, layout, {responsive: true, displaylogo: false});
  }
  sel.addEventListener("change", () => { history.replaceState(null, "", "#" + encodeURIComponent(sel.value)); draw(); });
  [[bH, "hourly"], [bD, "daily"]].forEach(([b, m]) => b.addEventListener("click", () => {
    mode = m; bH.setAttribute("aria-pressed", m === "hourly"); bD.setAttribute("aria-pressed", m === "daily"); draw();
  }));
  window.addEventListener("hashchange", () => {
    const n = decodeURIComponent(location.hash.slice(1)); if (data.names.includes(n)) { sel.value = n; draw(); }
  });
  draw();
})();
</script>
"""


def fill(template: str, **tokens) -> str:
    out = template
    for k, v in tokens.items():
        out = out.replace(f"__{k}__", v)
    return out


def colour_tokens() -> dict:
    return dict(SURFACE=SURFACE, TEXT2=TEXT_SECONDARY, TEXT=TEXT_PRIMARY, GRID=GRID, LAND=LAND, SERIES=SERIES)


def asym_section(names: list) -> str:
    ramp = json.dumps([[i / (len(ASYM_RAMP) - 1), c] for i, c in enumerate(ASYM_RAMP)])
    return fill(ASYM_JS, ALL_NAMES=json.dumps(list(STATIONS)), NAMES=json.dumps(names), RAMP=ramp,
                **colour_tokens())


def series(df: pd.DataFrame, col: str) -> list:
    return [None if v != v else round(float(v), 3) for v in df[col]]


def cutoffs_payload(hourly_frames: dict, daily_frames: dict) -> dict:
    def block(frames, fmt):
        times = next(iter(frames.values())).index
        return {"times": [t.strftime(fmt) for t in times],
                "stations": {n: {k: series(df, f"{k}_GV") for k in ("Ru", "Rc", "Rl")} for n, df in frames.items()}}
    return {"names": list(hourly_frames), "hourly": block(hourly_frames, "%Y-%m-%d %H:%M"),
            "daily": block(daily_frames, "%Y-%m-%d")}


def overview_table(data: dict, end: datetime) -> str:
    rows = []
    for s in sorted(load_stations(), key=lambda s: (data[s["name"]]["Rc_GV"].dropna().iloc[-1]
                                                   if not data[s["name"]]["Rc_GV"].dropna().empty else 99)):
        df = data[s["name"]].sort_index()
        last = df.dropna(subset=["Rc_GV"])
        if last.empty:
            vals = ["–"] * 6
        else:
            t, row = last.index[-1], last.iloc[-1]
            prev = last[last.index <= t - pd.Timedelta(hours=24)]
            week = last[last.index > t - pd.Timedelta(days=7)]["Rc_GV"]
            change = f"{row['Rc_GV'] - prev['Rc_GV'].iloc[-1]:+.2f}" if not prev.empty else "–"
            vals = [f"{row['Ru_GV']:.2f}", f"{row['Rc_GV']:.2f}", f"{row['Rl_GV']:.2f}", change,
                    f"{week.min():.2f}–{week.max():.2f}", f"{t:%m-%d %H:%M}"]
        key = ' class="key"' if s["name"] in FEATURED else ""
        where = f"{abs(s['lat']):.2f}°{'N' if s['lat'] >= 0 else 'S'}, {abs(s['lon']):.2f}°{'E' if s['lon'] >= 0 else 'W'}"
        code = s["code"] + (" (custom)" if s.get("custom") else "")
        rows.append(f'<tr><td{key}><a href="#{s["name"]}" onclick="document.getElementById(\'cut-station\').scrollIntoView()">'
                    f'{label(s["name"])}</a></td><td>{code}</td><td>{where}</td>' + "".join(f"<td>{v}</td>" for v in vals) + "</tr>")
    return ("""<div class="table-wrap"><table>
<thead><tr><th>Station</th><th>Code</th><th>Location</th><th>Ru</th><th>Rc</th><th>Rl</th>
<th>ΔRc 24 h</th><th>Rc 7-day range</th><th>Latest (UTC)</th></tr></thead>
<tbody>""" + "\n".join(rows) + "</tbody></table></div>")


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
    hourly_frames = {n: hourly(df, start, end) for n, df in data.items()}

    # Long window grows with the record until it reaches a year.
    today = end.replace(hour=0)
    first = pd.Timestamp(min((df.index.min() for df in data.values() if not df.empty), default=today))
    long_start = max(today - LONG_WINDOW, first.normalize().to_pydatetime())
    long_start = min(long_start, today - MIN_LONG_SPAN)
    span_days = (today - long_start).days
    daily_frames = {n: daily(df, long_start, today) for n, df in data.items()}

    # Landing-page figures: the featured (key) stations only.
    small_multiples({n: hourly_frames[n] for n in FEATURED}, start, end,
                    "Vertical cut-off rigidity, last 7 days (hourly)", "latest Rc", footer,
                    os.path.join(out_dir, "all_stations_7d.png"))
    small_multiples({n: daily_frames[n] for n in FEATURED}, long_start, today,
                    f"Vertical cut-off rigidity, daily averages, last {span_days} days",
                    "latest daily mean Rc", footer + f" · days with ≥{MIN_HOURS_PER_DAY} h of data",
                    os.path.join(out_dir, "all_stations_daily.png"))

    with open(os.path.join(out_dir, "asymptotic.json"), "w") as f:
        json.dump(asymptotic_payload(end - WINDOW, end), f, separators=(",", ":"))
    with open(os.path.join(out_dir, "cutoffs.json"), "w") as f:
        json.dump(cutoffs_payload(hourly_frames, daily_frames), f, separators=(",", ":"))

    asym_intro = """<p>Direction (geographic coordinates) from which particles arriving vertically at each station come
from outside the magnetosphere, for rigidities from the station's upper cut-off Ru up to 100 GV;
colour shows rigidity and marker shape the station (its location is the black marker of the same shape).
Tick stations on or off, drag the slider (or use the arrow keys) or press Play; hover a point for details.</p>"""
    plotly = f'<script src="{PLOTLY_JS}"></script>'

    page(os.path.join(out_dir, "index.html"), "Neutron monitor cut-offs", "index.html", f"""
<h1>Neutron monitor vertical cut-off rigidity</h1>
<p>Hourly geomagnetic cut-off rigidities computed with OTSO ({EXTERNAL_MODEL} + IGRF, live space-weather
inputs) for the four key stations of {MERTENS}: {", ".join(label(n) for n in FEATURED)}.
<a href="stations.html">All {len(STATIONS)} stations →</a></p>
<p class="muted">Updated {end:%Y-%m-%d %H:%M} UTC. Data: <code>main</code> branch, <code>data/</code>.</p>
<h2>Last 7 days, hourly</h2>
<img src="all_stations_7d.png" alt="Hourly cut-off rigidity for the key stations, last 7 days">
<h2>Daily averages, last {span_days} days</h2>
<img src="all_stations_daily.png" alt="Daily mean cut-off rigidity for the key stations, last {span_days} days">
<h2>Asymptotic viewing directions, last 7 days</h2>
{asym_intro}
{plotly}
{asym_section(FEATURED)}
""")

    page(os.path.join(out_dir, "stations.html"), "All neutron monitor stations", "stations.html", f"""
<h1>All stations</h1>
<p>{len(STATIONS)} neutron monitor stations, sorted by effective cut-off Rc. ★ marks the key stations
shown on the <a href="index.html">landing page</a>. Values are for the latest computed hour; click a
station to plot it. Custom stations are computed at their geographic coordinates.</p>
<p class="muted">Updated {end:%Y-%m-%d %H:%M} UTC. Rigidities in GV.</p>
{overview_table(data, end)}
<h2>Cut-off rigidity by station</h2>
<p>Effective cut-off Rc with the penumbra (Rl–Ru) shaded. Daily averages use days with at least
{MIN_HOURS_PER_DAY} hourly values, over up to the last year.</p>
{plotly}
{fill(CUT_JS, **colour_tokens())}
<h2>Asymptotic viewing directions, last 7 days</h2>
{asym_intro}
{asym_section(list(STATIONS))}
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
