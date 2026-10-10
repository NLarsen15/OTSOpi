"""
Plot the last 7 days of cut-off rigidities for each station.

Usage:
    python plot_cutoffs.py OUT_DIR

Writes one PNG per station, a combined small-multiples PNG and an index.html
into OUT_DIR, which the Plots workflow publishes to GitHub Pages. Headless: Agg backend.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from hourly_cutoff import OUTPUT_DIR as DATA_DIR, STATIONS

WINDOW = timedelta(days=7)

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES = "#2a78d6"

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


def load(name: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Hourly frame for [start, end]; missing hours are NaN so lines break at gaps."""
    path = os.path.join(DATA_DIR, f"{name}_cutoff.csv")
    hours = pd.date_range(start, end, freq="h")
    if not os.path.exists(path):
        return pd.DataFrame(index=hours, columns=["Ru_GV", "Rc_GV", "Rl_GV"], dtype=float)
    df = pd.read_csv(path, parse_dates=["datetime_utc"]).set_index("datetime_utc")
    df = df[~df.index.duplicated(keep="last")]
    return df[["Ru_GV", "Rc_GV", "Rl_GV"]].reindex(hours)


def draw(ax, name: str, df: pd.DataFrame, start: datetime, end: datetime) -> None:
    ax.fill_between(df.index, df["Rl_GV"], df["Ru_GV"], color=SERIES, alpha=0.18,
                    linewidth=0, label="Penumbra (Rl–Ru)")
    ax.plot(df.index, df["Rc_GV"], color=SERIES, linewidth=1.5, label="Effective cut-off Rc")
    # Hours with no neighbours draw no line segment; mark them so gaps stay honest.
    rc = df["Rc_GV"]
    lone = rc.notna() & rc.shift(1).isna() & rc.shift(-1).isna()
    if lone.any():
        ax.vlines(df.index[lone], df["Rl_GV"][lone], df["Ru_GV"][lone], color=SERIES, alpha=0.35, linewidth=2)
        ax.plot(df.index[lone], rc[lone], "o", color=SERIES, markersize=4)

    latest = df["Rc_GV"].dropna()
    subtitle = f"latest Rc {latest.iloc[-1]:.2f} GV" if len(latest) else "no data in window"
    ax.set_title(f"{name}  ·  {subtitle}", loc="left", fontsize=10, fontweight="bold")

    ax.set_xlim(start, end)
    ax.set_ylabel("Rigidity (GV)")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.tick_params(length=0)
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    # Flat series (e.g. Thule at 0 GV) still get a readable axis.
    lo, hi = ax.get_ylim()
    if hi - lo < 0.2:
        mid = (hi + lo) / 2
        ax.set_ylim(max(0, mid - 0.1), mid + 0.1 if mid > 0.1 else 0.2)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)

    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    start = end - WINDOW
    frames = {name: load(name, start, end) for name in STATIONS}
    footer = f"OTSO, TSY01 + IGRF, NOAA live inputs · window to {end:%Y-%m-%d %H:%M} UTC"

    # Small multiples: stations differ by several GV, so each gets its own y-scale.
    fig, axes = plt.subplots(len(STATIONS), 1, figsize=(10, 2.4 * len(STATIONS)), sharex=True)
    for ax, (name, df) in zip(axes, frames.items()):
        draw(ax, name, df, start, end)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=2, frameon=False)
    fig.suptitle("Vertical cut-off rigidity, last 7 days", x=0.01, ha="left", fontweight="bold")
    axes[-1].set_xlabel("Date (UTC)")
    fig.text(0.01, 0.005, footer, fontsize=8, color=TEXT_SECONDARY)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(os.path.join(out_dir, "all_stations_7d.png"), dpi=110, metadata=PNG_METADATA)
    plt.close(fig)

    for name, df in frames.items():
        fig, ax = plt.subplots(figsize=(10, 3.2))
        draw(ax, name, df, start, end)
        ax.legend(loc="lower right", bbox_to_anchor=(1, 1), ncol=2, frameon=False, fontsize=8)
        ax.set_xlabel("Date (UTC)")
        fig.text(0.01, 0.01, footer, fontsize=8, color=TEXT_SECONDARY)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        fig.savefig(os.path.join(out_dir, f"{name}_7d.png"), dpi=110, metadata=PNG_METADATA)
        plt.close(fig)

    images = "\n".join(f'<h2>{n}</h2>\n<img src="{n}_7d.png" alt="{n} cut-off rigidity, last 7 days">'
                       for n in STATIONS)
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
</style>
</head>
<body>
<h1>Neutron monitor vertical cut-off rigidity</h1>
<p>Last 7 days, hourly. Updated {end:%Y-%m-%d %H:%M} UTC. Data: <code>main</code> branch, <code>data/</code>.</p>
<img src="all_stations_7d.png" alt="Cut-off rigidity for all stations, last 7 days">
{images}
</body>
</html>
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
