# Data Licenses

## Karnataka Destinations

The destination records in `data/destinations.json` are sourced from official Karnataka government
sources, including the Archaeological Survey of India (ASI), Karnataka Forest Department, and
Karnataka State Tourism Development Corporation (KSTDC). Each record includes a `source_url` field
pointing to the authoritative source. All entry fees, distances, and visit durations are tagged
with a `basis` field (`sourced`, `estimated`, or `unknown`); no data is fabricated.

## OpenStreetMap Data

The files `data/transit_hubs.json`, `data/food.json`, and `data/stays.json` contain data derived
from **OpenStreetMap**.

- **License**: [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- **Attribution**: © OpenStreetMap contributors
- **Full attribution**: © OpenStreetMap contributors, ODbL 1.0 — https://www.openstreetmap.org/copyright

This data is pre-fetched offline by `scripts/build_osm_data.py` using the Overpass API and
committed to the repository. The application never contacts Overpass or any OpenStreetMap service
at request time. If the Overpass API was unreachable during the build, stub files with `count: 0`
are committed instead.

Any use or redistribution of these data files must comply with the ODbL 1.0 license terms and
include the attribution above.
