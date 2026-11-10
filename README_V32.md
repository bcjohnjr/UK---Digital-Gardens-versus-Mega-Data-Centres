# North Tyne Digital Gardens — V32 Research Reproducibility Notes

**Companion:** `SUBMIT/` at the archive root contains the Energy & Environmental Science Word/PDF files and figures; `RESEARCH/` contains prepared weather and price data, full numerical code, outputs and methods. The complete archive is **one ZIP** with these directories directly at its root, not a research ZIP nested inside it. No UK-study DOI has been minted or claimed. The submitting author must provide the research materials to editors/reviewers or deposit them at a persistent repository before external review.

## Reproduction
From `RESEARCH/` using Python and the dependencies described in `README_V31.md`:

```sh
python power_247.py design
python design_trajectory.py
python heat_community.py
python island_network.py
python export_scenarios.py
python design_econ.py
python revised_sensitivities.py
python pv_lca_screen.py
python turbine_trip_screen.py
python validate.py
```

`validate.py` passes **149 numerical assertions**, including the 25 MW output limit of the four-hour, 100 MWh battery. V32 makes **no change to the underlying numerical models or original output data** from V31: manuscript economic/emissions labelling, source statements, AI review attribution and release packaging are corrected.

## Reconciled community accounting
* Modelled adoption-weighted avoided community emissions are **58.2 kt CO2e/year before new-vehicle manufacturing** (gross scenario).
* Subtracting the specified weighted vehicle-manufacturing allowance gives **51.7–53.8 kt CO2e/year**. These are different, bounded metrics and are never carbon-removal credits.
* The separate **63–112 kt/year** figures are the limited-to-full deployment **gross** cases.
* The matched-IT supply lifecycle difference is approximately **136 kt/year** between the comparison campus and the Digital Gardens design, on the paper’s partial stated boundary.

## Source validation and transparency
* Dolphin Safe paper: Fang, Wang & Bronnmann (2025), *Fisheries Research* **292**, 107591, DOI `10.1016/j.fishres.2025.107591`; published abstract reports a **25.4%** hedonic tuna retail premium, **not** a measured AI-compute premium.
* AI-assisted authoring: Artificial Inventor/Synthetic Scientist V63, OpenAI ChatGPT GPT-6, and author-supplied referee-style critique attributed to Anthropic Claude (version not recorded). Exact Claude model version should be verified by the author before submitting.
* Affiliation remains **Independent Researcher, Zaragoza, Spain** as printed in the source manuscript; the author should confirm that this is the desired scholarly affiliation.
* No pending patent applications on the project, as confirmed by the author. Potential commercial interest is disclosed.
* The historic “Zero Carbon” badge is not part of the V32 public-facing research release, because the study does not establish zero lifecycle carbon emissions. Certification methodology and proposed customer-facing branding are retained in the article and supplement.
