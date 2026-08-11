# CAPM Analysis of 10 U.S. Stocks

An end-to-end quantitative-finance project estimating and comparing CAPM alpha, beta, explanatory power, residual behaviour, and beta stability for ten U.S. stocks from different sectors.

## Project overview

- **Assets:** AAPL, JPM, JNJ, XOM, PG, CAT, NEE, AMZN, LIN, and PLD
- **Market proxy:** S&P 500 (`^GSPC`)
- **Risk-free rate:** FRED 3-month U.S. Treasury rate (`DGS3MO`)
- **Frequency:** Daily
- **Sample:** 2016-2025 (2,513 aligned trading-day observations)
- **Model:** OLS estimation of the Capital Asset Pricing Model

The project includes a reproducible data pipeline, exploratory notebook, cross-stock regression comparison, residual diagnostics, 252-day rolling beta analysis, subperiod analysis, and a written report.

## Key findings

- AAPL has the highest full-sample beta (1.208), followed by AMZN (1.175).
- JNJ (0.467) and PG (0.494) have the lowest betas, consistent with defensive-sector intuition.
- AAPL has the highest R-squared (0.568); the market explains about 21%-23% of variation in JNJ, NEE, and PG.
- Most estimated alphas are not statistically significant. AAPL's positive alpha is only marginally significant under conventional OLS inference.
- Rolling and five-year subperiod estimates show that beta changes materially through time.

![CAPM beta comparison](outputs/beta_comparison.png)

## CAPM specification

For each stock, the project estimates:

$$
R_{i,t}-R_{f,t}
=
\alpha_i
+
\beta_i(R_{m,t}-R_{f,t})
+
\epsilon_{i,t}.
$$

Daily stock and market excess returns are constructed using adjusted prices and a frequency-matched daily risk-free rate.

## Repository structure

```text
CAPM/
├── data/               # Generated raw and processed datasets (not committed)
├── notebooks/          # Exploratory analysis and CAPM modelling notebook
├── outputs/            # Tables, charts, rolling betas, and OLS summaries
├── reports/            # Written project report
├── src/
│   ├── download_data.py
│   └── generate_outputs.py
├── requirements.txt
└── README.md
```

## Reproduce the project

Create and activate a virtual environment, then install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Download and process the data:

```powershell
python .\src\download_data.py
```

Generate all result tables, diagnostic charts, rolling-beta outputs, and subperiod comparisons:

```powershell
python .\src\generate_outputs.py
```

## Main deliverables

- [Analysis notebook](notebooks/capm_analysis.ipynb)
- [Full written report](reports/CAPM_Report.md)
- [Regression comparison table](outputs/capm_regression_results.csv)
- [Stock excess returns and fitted regression lines](outputs/scatter_regression_lines.png)
- [Residual diagnostics](outputs/residuals_over_time.png)
- [252-day rolling beta chart](outputs/rolling_beta_252d.png)
- [Full in-sample OLS summaries](outputs/in_sample_regression_summaries.txt)

## Limitations

The S&P 500 is only a proxy for the theoretical market portfolio, CAPM omits other systematic factors, conventional OLS inference may be affected by heteroskedasticity and outliers, and all estimates depend on the chosen sample and frequency. Historical alpha and beta estimates should not be interpreted as forecasts.
