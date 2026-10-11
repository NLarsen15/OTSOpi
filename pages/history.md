<!--
  Source of the website's History page (history.html), converted from Markdown when the
  site is built. The first "# " line becomes the page title next to the logo.
  {stations} is replaced by the number of configured stations.
  The first bullet list is drawn as a timeline. Images live in assets/history/ and are
  referenced as history/<file>. Raw HTML (e.g. the gallery below) is allowed.
-->

# History

The idea for OTSOpi came soon after the great geomagnetic storm of May 2024. I wanted to test
whether near-real-time cut-off rigidities could be computed for neutron monitors as
geomagnetic conditions changed, capturing the strong suppression of geomagnetic shielding
during extreme events. Such computations are usually done after the fact, which is of little
help when assessing space-weather impacts as they happen. Near-real-time values could be
useful to space-weather monitoring agencies.

This page records, for posterity, how the idea developed, from a first trial in 2024 to the
current OTSOpi.

- **October 2022 · OTSO**
  The first version of [OTSO](https://github.com/NLarsen15/OTSO), the Open-source
  geomagneToSphere prOpagation tool for computing cut-off rigidities and asymptotic
  directions of neutron monitors, was released. This coincided with the submission of the
  OTSO paper: Larsen, Mishev &amp; Usoskin, "[A new open-source geomagnetosphere propagation
  tool (OTSO) and its applications](https://doi.org/10.1029/2022JA031061)", *Journal of
  Geophysical Research: Space Physics*, 2023.
- **May 2024 · The May 2024 storm**
  The geomagnetic storm of 10–11 May 2024, the strongest in two decades, together with my
  growing interest in automating programs, sparked the idea of a machine that computes
  cut-offs on its own. I had bought two Raspberry Pi 5s for fun, to try out programming,
  self-hosting, homelabbing and task automation, and one of them became the OTSO-Pi.
- **September–October 2024 · The first OTSO-Pi**
  After choosing a logo for OTSO and printing several stickers (some of which can still be
  found in the corridors of the cosmic-ray department in Oulu), I set the Raspberry Pi 5 up
  in my office at the time, running the original OTSO. It computed apparent cut-off
  rigidities from 20 to 0 GV in 0.01 GV steps with a rigidity scan, using IGRF13 and TSY01.
  Each computation took about 8 minutes for Oulu and about 2 minutes for Cornwall. It
  captured the severe geomagnetic storm of 10–11 October 2024, when Oulu's effective cut-off
  fell to 0 GV and Cornwall's dropped from about 3.2 to 2.2 GV (very rough plots from the
  time are below). It also served as a test bed for a data-retrieval option in OTSO that
  pulled live data from NOAA and other online sources.
- **October 2024 · Presented at CCROS**
  The first OTSO-Pi results, including the storm of 10–11 October 2024, were presented at the
  [Coordinated Cosmic-Ray Observation System (CCROS)](https://snr.unl.edu/research/projects/CCROS)
  conference, held on 14–16 October 2024 at the University of Nebraska–Lincoln in Lincoln,
  Nebraska.
- **October 2024 · Live data in OTSO**
  The tested live-data option was added to OTSO, fetching real-time solar-wind data and
  geomagnetic indices directly.
- **2025 · OTSOpy**
  OTSO was refactored and rebuilt as [OTSOpy](https://github.com/NLarsen15/OTSOpy), a
  pip-installable Python package that makes the tool easier to use, and the live-data option
  was carried forward.
- **October 2026 · OTSOpi**
  OTSOpi was revived using the latest version of OTSOpy: hourly vertical cut-offs and
  asymptotic directions for {stations} neutron monitors, published automatically to this
  website ([details](otsopi.html)). Apparent cut-offs were not used this time, in favour of
  covering more stations and adding asymptotic cones.

## Legacy: the first OTSO-Pi (2024)

Effective cut-offs from the first OTSO-Pi, 14 September to 14 October 2024, including the
storm of 10–11 October 2024, as presented at CCROS.

<div class="gallery">
<figure><img src="history/2024_oulu_cutoff.png" alt="2024 OTSO-Pi effective cut-off for Oulu, 14 September to 14 October 2024">
<figcaption>Oulu effective cut-off, September–October 2024.</figcaption></figure>
<figure><img src="history/2024_cornwall_cutoff.png" alt="2024 OTSO-Pi effective cut-off for Cornwall, 14 September to 14 October 2024">
<figcaption>Cornwall effective cut-off, September–October 2024.</figcaption></figure>
</div>
