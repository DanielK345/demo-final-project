# Maps Evaluation Datasets

This directory contains evaluation datasets for the Maps geocoding/routing subsystem.

## Structure

- `sample_template.csv` — Template with example rows; owner fills 500 real/anonymised queries
- `golden_500.csv` — **(EXTERNAL_BLOCKED)** Business/Product must provide and approve

## CSV Format

```csv
query,expected_name,expected_lat,expected_lon,type,slice
"Bưu điện Hà Nội","Bưu điện Hà Nội",21.0285,105.8542,POI,normal
"132 ngõ Thổ Quan","132 Ngõ Thổ Quan",21.0185,105.8325,address,alley
"buu dien ha noi","Bưu điện Hà Nội",21.0285,105.8542,POI,no-accent
```

## Slices

| Slice | Description |
|---|---|
| `normal` | Standard Vietnamese text with diacritics |
| `house-number` | Street address with house number |
| `alley` | Ngõ/ngách/hẻm addresses |
| `POI` | Named points of interest |
| `no-accent` | No Vietnamese diacritics |
| `ASR-like` | Common speech-to-text spelling variants |
| `old-new` | Old/new place names (e.g. renamed streets) |
| `reverse` | Reverse geocoding (lat/lon → place) |
| `boundary` | Service area boundary cases |

## Important

- Do NOT use synthetic/AI-generated addresses as production benchmarks
- All queries must be public/common POIs or anonymised
- Owner must approve the golden dataset before it can be used for quality gates
- No PII in any evaluation dataset
