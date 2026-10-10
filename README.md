# OTSOpi

Repo for OTSO computations done on Raspberry Pi

![Vertical cut-off rigidity, last 7 days](https://nlarsen15.github.io/OTSOpi/all_stations_7d.png)

Daily averages over the past year: <https://nlarsen15.github.io/OTSOpi/>

Hourly geomagnetic vertical cut-off rigidities for neutron monitor stations,
computed with [OTSO](https://github.com/NLarsen15/OTSOpy) on a Raspberry Pi
using live NOAA/Kyoto/GFZ space-weather inputs.

| Station | OTSO code |
|---|---|
| Oulu | OULU |
| Thule | THUL |
| Lomnický štít | LMKS |
| Moscow (IZMIRAN) | MOSC |

## Data (`main` branch)

`data/<Station>_cutoff.csv`, one row per hour:

| Column | Meaning |
|---|---|
| `datetime_utc` | Time the cut-off is computed for (UTC, top of the hour) |
| `Ru_GV`, `Rc_GV`, `Rl_GV` | Upper, effective and lower cut-off rigidity (GV) |
| `external_model` | Tsyganenko external field model used |
| `computed_at_utc` | When the row was computed (UTC) |

Each hour is computed 3 hours after the fact so the live input datasets have
updated. Hours missed (e.g. while offline) are backfilled while live data still
covers them (~21 h). Live inputs are provisional and may differ from the final
OMNI values.

Model setup: IGRF + TSY01S (storm-time TSY01, optimised) with its built-in
magnetopause, Boris-Buneman
integration with 1 % gyro-step, rigidity scan 20 → 0 GV in 0.01 GV steps,
start altitude 20 km.

### Asymptotic viewing directions

`data/asymptotic/<Station>/<YYYY-MM>.csv`, one row per hour, one column per
rigidity level (`1GV` … `100GV`, 65 levels: 0.1 GV steps below 2 GV, widening
to 5 GV steps above 50 GV). Each cell is `filter;latitude;longitude` as output
by OTSO: the filter code for that trajectory, and the asymptotic direction in
GEO coordinates (degrees, 0.01° precision). Same hours and inputs as the
cut-off files.

## Plots

Two figures, one panel per station: the last 7 days hourly, and daily
averages (days with at least 12 hourly values) over up to the last year.
Below them, an interactive map per station shows the asymptotic viewing
directions (1–100 GV, coloured by rigidity) with a time slider and play
button covering the last 7 days, drawn in the browser from `asymptotic.json`.
They are drawn by a GitHub Action (`.github/workflows/plots.yml`)
each time new data is pushed, and published to GitHub Pages. No images are
committed, so the history stays small. One-time setup: Settings → Pages →
Source: **GitHub Actions**.

## Running

- `hourly_cutoff.py` computes and appends to `data/`.
- `plot_cutoffs.py OUT_DIR` writes the plots (run by the Action; needs only
  `requirements-plots.txt`, not OTSO).
- `run_hourly.sh` is the cron entry point: compute, commit and push.
  Logs go to `~/.local/state/nm-cutoffs/run.log`.
- `bench_cores.py` picks `corenum`/`threadnum` for the machine.

```
5 * * * * /path/to/OTSOpi/run_hourly.sh
```

## License

GPL-3.0, see [LICENSE](LICENSE).
