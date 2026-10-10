# OTSOpi

Repo for OTSO computations done on Raspberry Pi

![Vertical cut-off rigidity, last 7 days](https://nlarsen15.github.io/OTSOpi/all_stations_7d.png)

Per-station plots: <https://nlarsen15.github.io/OTSOpi/>

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

Model setup: IGRF + TSY01 (optimised), Kobel magnetopause, Boris-Buneman
integration with 1 % gyro-step, rigidity scan 20 → 0 GV in 0.01 GV steps,
start altitude 20 km.

## Plots

The 7-day plots are drawn by a GitHub Action (`.github/workflows/plots.yml`)
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
