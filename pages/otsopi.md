<!--
  Source of the website's "The OTSOpi" page (otsopi.html), converted from Markdown when the
  site is built. The first "# " line becomes the page title next to the logo.
  Placeholders filled in at build time:
    {stations}  number of configured stations
    {levels}    number of asymptotic-direction rigidities
    {model}     external field model (e.g. TSY01S)
  The photo and the tables sit side by side inside the <div class="pi"> block; markdown="1"
  lets Markdown (headings, tables) be used inside it. The tables' header row is hidden.
-->

# The OTSOpi

All results on this site are computed by a Raspberry Pi 5 running
[OTSO](https://github.com/NLarsen15/OTSOpy) around the clock. Every hour it downloads the
latest space-weather data, traces cosmic-ray trajectories through the geomagnetic field for
each station, and pushes the results to [GitHub](https://github.com/NLarsen15/OTSOpi),
which rebuilds this website.

<div class="pi" markdown="1">
<figure><img src="otsopi.jpg" alt="The OTSOpi: a Raspberry Pi 5 in a black case with an OTSO polar-bear sticker">
<figcaption>The OTSOpi.</figcaption></figure>
<div class="specs" markdown="1">

## Hardware and software

| Component | Details |
|---|---|
| Board | Raspberry Pi 5 Model B (quad-core Arm Cortex-A76, 2.4 GHz) |
| Memory | 8 GB |
| Storage | 64 GB microSD |
| Operating system | Ubuntu Server 24.04.5 LTS (64-bit) |
| Software | Python 3.12, OTSO 1.3.8 |
| Parallelism | 1 process × 4 threads |
| Schedule | systemd timer at :05 past every hour (plus a :35 retry), and 3 min after boot |

## Computation

| Item | Details |
|---|---|
| Each hour | {stations} stations: vertical cut-off scan 20 → 0 GV in 0.01 GV steps, plus asymptotic directions at {levels} rigidities (1–100 GV) per station |
| Field model | IGRF + {model} (with its built-in magnetopause), driven by live inputs: NOAA SWPC solar wind and IMF, Kyoto WDC Dst, GFZ Kp |
| Integration model | Boris-Buneman, adaptive time step limited to 1 % of the gyro-period, with a 0.001 % energy (β) check. Trajectories start at 20 km altitude and end on re-entry below 20 km, escape through the magnetopause, or after 100 R<sub>E</sub> of path |
| Time per hour | **≈ 1 minute for 15 stations** (median 54 s, range 49–79 s) · ≈ 30 s for 4 stations · ≈ 2 s for the :35 check when nothing is missing |
| Backfill | After an outage, missed hours (up to ~21 h back) are caught up at the same rate: 19 hours for 15 stations took about 18 minutes |

<p class="muted">Timings measured on 11 October 2026; each extra station adds roughly 3 s per hour.</p>

</div>
</div>
