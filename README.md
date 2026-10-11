# OTSOpi

Repo for OTSO computations done on Raspberry Pi

![Vertical cut-off rigidity, last 7 days](https://nlarsen15.github.io/OTSOpi/all_stations_7d.png)

Daily averages over the past year: <https://nlarsen15.github.io/OTSOpi/>

Hourly geomagnetic vertical cut-off rigidities for neutron monitor stations,
computed with [OTSO](https://github.com/NLarsen15/OTSOpy) on a Raspberry Pi
using live NOAA/Kyoto/GFZ space-weather inputs.

The stations are listed in [`stations.json`](stations.json). The initial set is:

| Station | OTSO code |
|---|---|
| Oulu | OULU |
| Thule | THUL |
| Lomnický štít | LMKS |
| Moscow (IZMIRAN) | MOSC |

These stations were selected following Mertens et al. (2025):

> Mertens, C. J., Gronoff, G. P., & Phoenix, D. B. (2025). NAIRAS Version 3
> atmospheric ionizing radiation validation: Comparisons to RaD‐X measurements.
> *Space Weather*, 23(4), e2024SW004296.
> [doi:10.1029/2024SW004296](https://doi.org/10.1029/2024SW004296)

### Adding or removing stations

Any station in OTSO's built-in list can be added from the terminal. The command
commits and pushes `stations.json`, and the next hourly run computes the new
station, backfilling the last ~21 h:

```
./station search kiel        # find the OTSO code
./station add KIEL           # add it (name defaults to OTSO's full name: Kiel)
./station remove Kiel        # stop computing it; existing data is kept
./station list
```

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

### Model inputs

`data/inputs.csv`, one row per hour (shared by all stations): the inputs OTSO
used, as reported by OTSO after its own processing of the live data.

| Column | Meaning |
|---|---|
| `Kp`, `IOPT` | Kp index and the Tsyganenko IOPT derived from it |
| `Vx_kms`, `Vy_kms`, `Vz_kms` | Solar wind velocity (km/s) |
| `Bx_nT`, `By_nT`, `Bz_nT` | IMF components (nT; Bx is the 30-min average OTSO passes on) |
| `By_avg30_nT`, `Bz_avg30_nT` | 30-min averaged IMF By, Bz (nT) |
| `density_cm3`, `Pdyn_nPa` | Solar wind density (cm⁻³) and dynamic pressure (nPa) |
| `Dst_nT` | Dst index (nT) |
| `G1`, `G2`, `G3` | Tsyganenko G parameters |
| `W1`–`W6`, `N_index`, `B_index`, `SYMH_nT` | Inputs for other Tsyganenko models (0 when not used) |
| `data_source`, `external_model`, `otso_version`, `computed_at_utc` | Provenance |

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
- `run_hourly.sh` is the cron/systemd entry point: compute, commit and push.
  Logs go to `~/.local/state/nm-cutoffs/run.log`.
- `./station` manages the station list (`stations.py`, `stations.json`).
- `bench_cores.py` picks `corenum`/`threadnum` for the machine.

```
5 * * * * /path/to/OTSOpi/run_hourly.sh
```

## License

GPL-3.0, see [LICENSE](LICENSE).
