<!--
  Source of the website's History page (history.html), converted from Markdown when the
  site is built. The first "# " line becomes the page title next to the logo.
  {stations} is replaced by the number of configured stations.
  The first bullet list is drawn as a timeline. Images live in assets/history/ and are
  referenced as history/<file>. Raw HTML (e.g. the gallery below) is allowed.
-->

# History

OTSOpi grew out of a simple question after the great geomagnetic storm of May 2024: could
cut-off rigidities be computed automatically, as conditions change, rather than after the
fact? This page records how the idea developed, from a first trial in 2024 to the current
OTSOpi.

- **October 2022 · OTSO**
  The first version of [OTSO](https://github.com/NLarsen15/OTSO), the Open-source
  geomagneToSphere prOpagation tool (Fortran and Python), for computing cut-off rigidities
  and asymptotic directions of neutron monitors.
- **May 2024 · The May 2024 storm**
  The geomagnetic storm of 10–11 May 2024, the strongest in two decades, together with my
  growing interest in automating programs, sparked the idea of a machine that computes
  cut-offs on its own.
- **September–October 2024 · The first OTSO-Pi**
  A Raspberry Pi in my office running the original OTSO, computing apparent cut-off
  rigidities from 20 to 0 GV in 0.01 GV steps with a rigidity scan, using IGRF13 and TSY01.
  Each computation took about 8 minutes for Oulu and about 2 minutes for Cornwall. It ran
  through the severe geomagnetic storm of 10–11 October 2024, when Oulu's effective cut-off
  fell to 0 GV and Cornwall's from about 3.2 to 2.2 GV (plots below).
- **October 2024 · Live data in OTSO**
  A live-data option was added to OTSO, fetching real-time solar-wind and geomagnetic
  indices directly.
- **2025 · OTSOpy**
  [OTSOpy](https://github.com/NLarsen15/OTSOpy), OTSO rebuilt as a pip-installable Python
  package, carried the live-data option forward.
- **October 2026 · OTSOpi**
  OTSOpi, revived on a Raspberry Pi 5 with OTSOpy: hourly vertical cut-offs and asymptotic
  directions for {stations} neutron monitors, published automatically to this website
  ([details](otsopi.html)).

## Legacy: the first OTSO-Pi (2024)

Effective cut-offs from the first OTSO-Pi, 14 September to 14 October 2024, including the
storm of 10–11 October 2024.

<div class="gallery">
<figure><img src="history/2024_oulu_cutoff.png" alt="2024 OTSO-Pi effective cut-off for Oulu, 14 September to 14 October 2024">
<figcaption>Oulu effective cut-off, September–October 2024.</figcaption></figure>
<figure><img src="history/2024_cornwall_cutoff.png" alt="2024 OTSO-Pi effective cut-off for Cornwall, 14 September to 14 October 2024">
<figcaption>Cornwall effective cut-off, September–October 2024.</figcaption></figure>
</div>
