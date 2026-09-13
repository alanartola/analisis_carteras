# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Portfolio-analysis project for the Argentine capital market (BYMA). Not a software package —
there is no build/lint/test tooling. The deliverable is a data file plus a notebook meant to be
run in Google Colab. See [docs/CONTEXTO_PROYECTO.md](docs/CONTEXTO_PROYECTO.md) for the full
narrative history of decisions made while building this (data sourcing, gotchas, environment
setup), and the root [README.md](README.md) for end-user usage instructions.

## Architecture

Three parts, in a one-way data flow:

1. **`scripts/` (run once, manually, to (re)build the universe file)**
   `fetch_market_caps.py` → `fetch_market_caps_retry.py` → `build_excel.py`, in that order.
   - `fetch_market_caps.py` holds the hardcoded list of all companies officially listed on BYMA
     (`COMPANIES`) and queries `yfinance` for each `<TICKER>.BA` to get market cap/price. Writes
     `scripts/market_caps_raw.json`.
   - `fetch_market_caps_retry.py` re-reads that JSON and retries entries with a missing market
     cap using `fast_info` / shares-outstanding, overwriting the same JSON file in place.
   - `build_excel.py` reads the JSON, sorts by market cap (unknown-cap rows go last, alphabetical,
     flagged `N/D` — never invented), and writes `empresas_byma.xlsx` at the repo root.
   - `YF_OVERRIDES` in `fetch_market_caps.py` maps a BYMA ticker to a different Yahoo Finance
     ticker when they don't match (currently only `CEPU2` → `CEPU.BA`). Check Yahoo Finance
     manually before adding more of these — don't guess.
   - `test_notebook_logic.py` is a smoke test that mimics the notebook's pipeline against the
     local xlsx (temporarily marking a few tickers with `x` in memory) to catch bugs before
     pushing changes to the notebook. Run it after editing `cartera_eficiente.ipynb`'s logic.

2. **`empresas_byma.xlsx`** — the only file the end user edits by hand. Sheet `Universo BYMA` has
   one row per company with a blank `Analizar (x)` column for the user to mark. Sheet `Notas`
   documents the data source/methodology in-file.

3. **`cartera_eficiente.ipynb`** — runs in Google Colab, launched via the "Open in Colab" badge
   in the README. It reads `empresas_byma.xlsx` **directly from
   `https://raw.githubusercontent.com/alanartola/analisis_carteras/main/empresas_byma.xlsx`**
   (hardcoded `EXCEL_URL` in the config cell) — not from a local file. This means:
   - Any edit to the Excel (marking/unmarking companies) only takes effect in Colab **after** it
     is pushed to the `main` branch.
   - If the file is ever renamed or the default branch changes, `EXCEL_URL` in the notebook and
     the Colab badge URLs in `README.md` must be updated together.
   - The notebook filters rows where `Analizar (x)` is `x`/`si`/`sí` (case-insensitive), downloads
     history via `yfinance` (plus the Merval index, `^MERV`, as a benchmark for Beta/Alpha and the
     backtest), then does a full analysis in 11 numbered sections: descriptive stats (skew,
     kurtosis, Jarque-Bera normality test, max drawdown per asset), a correlation heatmap +
     hierarchical clustering dendrogram, per-asset risk metrics (historical/parametric VaR, CVaR,
     Sortino, Calmar, CAPM Beta/Alpha), **six** portfolio-construction methods (min-variance,
     max-Sharpe, max-diversification and risk-parity via `scipy.optimize.minimize`; HRP via a
     hand-rolled hierarchical-bisection implementation — see `_orden_quasi_diagonal` /
     `_biparticion_recursiva` in the notebook; and 1/N as a naive baseline), a Monte Carlo
     efficient-frontier cloud marking all six, a full comparison table (return, vol, Sharpe,
     Sortino, Calmar, VaR/CVaR, max drawdown, diversification ratio, Beta) and per-asset risk
     contribution, a walk-forward backtest (rolling re-optimization on a trailing window, no
     look-ahead, benchmarked against 1/N and the Merval), and a bootstrap-resampling robustness
     check on the max-Sharpe weights. No short-selling by default; an optional
     `MAX_WEIGHT_PER_ASSET` concentration cap applies only to the four `scipy`-optimized
     portfolios, not to HRP or 1/N (documented in the notebook's own limitations section).
   - `scripts/test_notebook_logic.py` mirrors *all* of this (smaller Monte Carlo / bootstrap /
     backtest parameters, 1y of data) — run it after touching the notebook's logic, before
     regenerating the notebook cells by hand. There is no `nbformat`/`jupyter` in `.venv`; the
     notebook was originally generated with a throwaway builder script (list of markdown/code
     cell strings serialized to nbformat-4 JSON) rather than hand-edited JSON — if you need to
     regenerate it wholesale rather than tweak a cell, recreate that pattern instead of hand-writing
     `.ipynb` JSON.

## Environment

- Local Python env: `.venv/` (gitignored). Recreate with:
  ```
  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  ```
- Run any script from the repo root, e.g. `.\.venv\Scripts\python.exe scripts\build_excel.py`
  (scripts use relative paths like `"empresas_byma.xlsx"` and `"scripts/market_caps_raw.json"`).
- Git remote uses **SSH** (`git@github.com:alanartola/analisis_carteras.git`), not HTTPS. Pushing
  from a new machine needs its own SSH key registered at github.com/settings/keys — see
  [docs/CONTEXTO_PROYECTO.md](docs/CONTEXTO_PROYECTO.md) for the exact steps used last time.

## Key fact to not re-litigate

BYMA lists **82** companies total (verified against the official listing page, Sept 2026), of
which 2 have trading suspended. The universe file has **80** rows, not 100 — there is no way to
get 100 without inventing companies or including foreign-listed ADRs (MercadoLibre, Globant,
etc.) that are not part of the local capital market. Don't "fix" this by padding the list.
