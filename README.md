# Digital Gardens North Tyne versus QTS Cambois and Stargate UK — reproducible model

Requires Python 3.10+, numpy, pandas, matplotlib and python-docx. Run from this directory, in order:

```bash
python power_247.py           # hourly dispatch and 7,560-portfolio fossil-free-first frontier (comparison case) (~1 min)
python power_247.py design    # design case: wind/solar -> battery -> grid -> block on grid failure; 1,625-portfolio search,
                              # 16-year and wind-yield replays, islanded outage autonomy (battery + block), raw-ERA5 re-optimisation (~2 min)
python trajectory.py          # GB decarbonisation path for the fossil-free-first and carbon-aware rules (~7 min)
python design_trajectory.py   # 25-year (2027-2051) emissions path of the design case and the grid campus
python heat_community.py      # node-by-node hourly heat (homes, greenhouses, aquaculture, seaweed, digesters, drying),
                              # rivers, food, circular feed, seaweed, community ledger with percentages, vehicles, jobs
python island_network.py      # islanded 33 kV network: load flow, N-1 circuit and turbine contingencies, cost
python export_scenarios.py    # surplus offtake terms and export caps (re-dispatch of the design)
python compare_econ.py        # cumulative emissions of the comparison operating rules
python design_econ.py         # design-case comparators, emissions tables, water, jobs, GPU economics and premium
python validate.py            # 149 assertions on balances and results
python figures.py             # FIGURES/
python build_manuscript.py    # HISTORICAL manuscript draft helper: DOES NOT recreate the curated submission documents; do not use for final submission
```

All assumptions are declared, with sources, in `params.py`.

## Input data
- `DATA/Digital_Gardens_UK_ERA5_historical/`: hourly ERA5 reanalysis 2010-2025 (Open-Meteo, model `era5`, UTC) for the eight nodes,
  four wind proxies and the two comparator sites, with provenance manifest. Re-download with `DATA/digital_gardens_uk_era5.py`.
  Copernicus licence and Open-Meteo terms apply.
- `DATA/Digital_Gardens_UK_GRID/`: half-hourly GB national and North East England carbon intensity (NESO Carbon Intensity API,
  CC BY 4.0) and Elexon market index prices (BSC open data licence), 2018-2025. Re-download with `DATA/digital_gardens_uk_grid.py`.
- `DATA/communities.csv`: populations and IT allocation of the eight communities (Digital Gardens website archive).

Coordinates are town-centre or area proxies, not surveyed generation or data-centre sites.
