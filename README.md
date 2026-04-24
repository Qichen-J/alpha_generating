# Alpha Generating — WorldQuant Brain Research

A personal research codebase for developing, testing, and submitting quantitative alpha factors on the [WorldQuant Brain](https://platform.worldquantbrain.com/) platform, with a focus on options-implied volatility signals.

---

## Repository Structure

```
brain/
├── Course1_/                          # Batch simulation framework
│   ├── Alpha_模板展开与批量回测.ipynb  # Template expansion & batch backtest notebook
│   ├── simulate_5000_alphas.py        # Bulk alpha simulation script
│   ├── outputs/                       # Simulation results
│   ├── Course1_模板合集/              # Alpha template library
│   └── Course1_经验合集/              # Competition experience notes
│
└── Course2/
    ├── Course2_code/                  # Alpha research scripts (main)
    │   ├── option8_alpha_r*.py        # Options data alpha iterations (R1–R14)
    │   ├── improve_target4_r*.py      # Target4 alpha improvement iterations
    │   ├── improve_target5_r*.py      # Target5 alpha improvement iterations
    │   ├── improve_mv_r*.py           # Momentum-volatility alpha iterations
    │   ├── improve_term_twist_alpha_r*.py  # IV term structure alpha iterations
    │   ├── outputs/                   # JSON/CSV simulation results
    │   └── *.ipynb                    # Interactive research notebooks
    │
    └── brain-alpha-judge/             # AI-powered alpha quality evaluator
        ├── scripts/judge_alpha.py     # Main judge script
        ├── data/                      # Candidate alphas & rubrics
        ├── references/                # Evaluation standards & roadmap
        └── outputs/                   # Judge reports (JSON + Markdown)
```

---

## Core Signal

The strongest discovered signal is a **3-factor implied volatility reversal** alpha:

```python
my_group = bucket(rank(cap), range='0,1,0.1')

iv_corr  = ts_corr(-implied_volatility_mean_30, returns, 126)  # IV-return correlation (126d)
hv_corr  = ts_corr(historical_volatility_30, -returns, 126)    # HV-return correlation (126d)
intra    = ts_rank(-(close - open) / open, 63)                 # Intraday reversal

alpha = group_rank(iv_corr,  my_group) \
      * group_rank(hv_corr,  my_group) \
      * group_rank(intra,    my_group)

group_neutralize(alpha, my_group)
```

**Key findings:**
- 126-day correlation window is critical (63d gives Fitness ~0.9, 126d gives ~1.1–1.3)
- `decay=5` raises Sharpe from ~1.6 to ~1.84; `decay=3` to ~1.93–2.05
- `implied_volatility_put_60` with 126d window is a novel low-correlation signal
- `SUBINDUSTRY` neutralization combined with `decay=5` achieves Sharpe ~1.95

---

## Simulation Settings

| Parameter | Value |
|---|---|
| Region | USA |
| Universe | TOP3000 |
| Instrument | EQUITY |
| Delay | 1 |
| Neutralization | INDUSTRY (default) |
| Truncation | 0.08 |
| Language | FASTEXPR |
| Pasteurization | ON |

**Pass thresholds:** Sharpe ≥ 1.25, Fitness ≥ 1.0, Turnover 1%–70%, Sub-universe Sharpe ≥ ~0.5

---

## Research Progress

| Round | Key Change | Best Result |
|---|---|---|
| R1–R8 | Baseline IV signals, parameter sweep | Sharpe ~1.6, Fitness < 1.0 |
| R9 | Parkinson volatility | All failed |
| R10–R11 | 3-factor combination | Fitness reaches 1.05–1.19 |
| R12 | **126d correlation window** | 🎉 First ALL PASS (`wpJv80bQ`, Sha=1.84) |
| R13 | decay=3/5, SUBINDUSTRY | Sha up to 1.95 |
| R14 | `ivput126` full family | Sha up to 2.05, Fit up to 1.38 |

---

## Usage

All scripts use the WorldQuant Brain REST API. Set your credentials before running:

```python
EMAIL    = "your_email@example.com"
PASSWORD = "your_password"
```

Run any iteration script directly:

```bash
python3 Course2/Course2_code/option8_alpha_r14.py
```

Results are saved to `Course2/Course2_code/outputs/` as JSON files.

---

## Data Source

Signals are derived from the **option8** dataset on WorldQuant Brain, including:
- `implied_volatility_mean_{10/20/30/60/90/120/...}` — mean IV at various tenors
- `implied_volatility_put_{30/60/90/...}` — put IV
- `implied_volatility_call_{30/60/90/...}` — call IV
- `historical_volatility_{10/20/30/60/...}` — realized volatility
- `implied_volatility_mean_skew_{30/60/...}` — IV skew

---

## Notes

- Credentials are **not** stored in this repository. Replace `xxxxxx` placeholders with your own credentials before running scripts.
- `.venv/`, `cache/`, and large data directories are excluded via `.gitignore`.
