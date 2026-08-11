"""Generate the required CAPM tables, charts, and regression summaries."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import statsmodels.api as sm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "capm_daily_data.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
ROLLING_WINDOW = 252

STOCK_TICKERS = [
    "AAPL",
    "JPM",
    "JNJ",
    "XOM",
    "PG",
    "CAT",
    "NEE",
    "AMZN",
    "LIN",
    "PLD",
]


def load_data() -> pd.DataFrame:
    """Load the already processed daily CAPM dataset."""
    data = pd.read_csv(DATA_PATH, parse_dates=["Date"], index_col="Date")
    required = ["market_excess"] + [f"{ticker}_excess" for ticker in STOCK_TICKERS]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required CAPM columns: {missing}")
    return data.sort_index()


def fit_models(data: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Fit one in-sample CAPM regression for each stock."""
    x = sm.add_constant(data[["market_excess"]])
    models = {}
    rows = []

    for ticker in STOCK_TICKERS:
        model = sm.OLS(data[f"{ticker}_excess"], x).fit()
        models[ticker] = model
        rows.append(
            {
                "ticker": ticker,
                "alpha_daily": model.params["const"],
                "beta": model.params["market_excess"],
                "alpha_pvalue": model.pvalues["const"],
                "beta_pvalue": model.pvalues["market_excess"],
                "r_squared": model.rsquared,
                "adjusted_r_squared": model.rsquared_adj,
                "observations": int(model.nobs),
            }
        )

    results = pd.DataFrame(rows).sort_values("beta", ascending=False)
    return models, results


def save_regression_table(results: pd.DataFrame) -> None:
    """Save the cross-stock regression comparison table."""
    results.to_csv(OUTPUT_DIR / "capm_regression_results.csv", index=False)


def save_regression_summaries(models: dict) -> None:
    """Save the full in-sample statsmodels summary for every stock."""
    sections = []
    for ticker in STOCK_TICKERS:
        sections.append(f"{'=' * 30} {ticker} {'=' * 30}\n")
        sections.append(models[ticker].summary().as_text())
        sections.append("\n\n")
    (OUTPUT_DIR / "in_sample_regression_summaries.txt").write_text(
        "".join(sections), encoding="utf-8"
    )


def save_beta_chart(results: pd.DataFrame) -> None:
    """Save a bar chart comparing estimated betas."""
    fig, ax = plt.subplots(figsize=(11, 6))
    sns.barplot(data=results, x="ticker", y="beta", color="steelblue", ax=ax)
    ax.axhline(1, color="red", linestyle="--", linewidth=1.5, label="Market beta = 1")
    ax.set_title("CAPM Beta Comparison")
    ax.set_xlabel("Stock")
    ax.set_ylabel("Estimated Beta")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "beta_comparison.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_scatter_regression_chart(data: pd.DataFrame, models: dict) -> None:
    """Save stock-vs-market excess-return scatter plots and fitted lines."""
    fig, axes = plt.subplots(2, 5, figsize=(20, 9), sharex=True, sharey=True)
    market_grid = pd.Series(
        [data["market_excess"].min(), data["market_excess"].max()],
        dtype="float64",
    )

    for ax, ticker in zip(axes.flat, STOCK_TICKERS):
        model = models[ticker]
        ax.scatter(
            data["market_excess"],
            data[f"{ticker}_excess"],
            s=7,
            alpha=0.25,
            color="steelblue",
        )
        fitted_line = model.params["const"] + model.params["market_excess"] * market_grid
        ax.plot(market_grid, fitted_line, color="darkred", linewidth=2)
        ax.set_title(
            f"{ticker}: beta={model.params['market_excess']:.2f}, "
            f"R-squared={model.rsquared:.2f}"
        )
        ax.set_xlabel("Market excess return")
        ax.set_ylabel("Stock excess return")

    fig.suptitle("Stock Excess Returns vs Market Excess Returns", fontsize=16, y=1.01)
    fig.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "scatter_regression_lines.png",
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig)


def save_residual_charts(data: pd.DataFrame, models: dict) -> None:
    """Save residual time-series and residual-vs-fitted diagnostic plots."""
    fig_time, axes_time = plt.subplots(2, 5, figsize=(20, 9), sharex=True, sharey=True)
    fig_fit, axes_fit = plt.subplots(2, 5, figsize=(20, 9), sharex=True, sharey=True)

    for time_ax, fit_ax, ticker in zip(axes_time.flat, axes_fit.flat, STOCK_TICKERS):
        model = models[ticker]
        time_ax.plot(data.index, model.resid, color="steelblue", linewidth=0.7)
        time_ax.axhline(0, color="black", linestyle="--", linewidth=1)
        time_ax.set_title(ticker)
        time_ax.set_xlabel("Date")
        time_ax.set_ylabel("Residual")

        fit_ax.scatter(model.fittedvalues, model.resid, s=8, alpha=0.3, color="steelblue")
        fit_ax.axhline(0, color="darkred", linestyle="--", linewidth=1)
        fit_ax.set_title(ticker)
        fit_ax.set_xlabel("Fitted excess return")
        fit_ax.set_ylabel("Residual")

    fig_time.suptitle("CAPM Residuals over Time", fontsize=16, y=1.01)
    fig_time.tight_layout()
    fig_time.savefig(
        OUTPUT_DIR / "residuals_over_time.png",
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig_time)

    fig_fit.suptitle("CAPM Residuals vs Fitted Values", fontsize=16, y=1.01)
    fig_fit.tight_layout()
    fig_fit.savefig(
        OUTPUT_DIR / "residuals_vs_fitted.png",
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig_fit)


def save_rolling_beta_chart(data: pd.DataFrame) -> None:
    """Save 252-trading-day rolling betas for all stocks."""
    market_variance = data["market_excess"].rolling(ROLLING_WINDOW).var()
    rolling_betas = pd.DataFrame(index=data.index)

    for ticker in STOCK_TICKERS:
        rolling_covariance = data[f"{ticker}_excess"].rolling(ROLLING_WINDOW).cov(
            data["market_excess"]
        )
        rolling_betas[ticker] = rolling_covariance / market_variance

    rolling_betas.to_csv(OUTPUT_DIR / "rolling_beta_252d.csv")

    fig, ax = plt.subplots(figsize=(14, 8))
    rolling_betas.plot(ax=ax, linewidth=1.2)
    ax.axhline(1, color="black", linestyle="--", linewidth=1, label="Market beta = 1")
    ax.set_title("252-Day Rolling CAPM Beta")
    ax.set_xlabel("Date")
    ax.set_ylabel("Rolling Beta")
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "rolling_beta_252d.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_time_window_comparison(data: pd.DataFrame) -> None:
    """Optionally compare CAPM estimates across two five-year subperiods."""
    windows = {
        "2016-2020": data.loc["2016":"2020"],
        "2021-2025": data.loc["2021":"2025"],
    }
    rows = []

    for window_name, window_data in windows.items():
        x = sm.add_constant(window_data[["market_excess"]])
        for ticker in STOCK_TICKERS:
            model = sm.OLS(window_data[f"{ticker}_excess"], x).fit()
            rows.append(
                {
                    "window": window_name,
                    "ticker": ticker,
                    "alpha_daily": model.params["const"],
                    "beta": model.params["market_excess"],
                    "alpha_pvalue": model.pvalues["const"],
                    "r_squared": model.rsquared,
                    "observations": int(model.nobs),
                }
            )

    pd.DataFrame(rows).to_csv(OUTPUT_DIR / "time_window_comparison.csv", index=False)


def write_manifest() -> None:
    """Document the generated deliverables."""
    manifest = """# CAPM outputs

- `capm_regression_results.csv`: alpha, beta, p-values, R-squared, and sample size.
- `scatter_regression_lines.png`: excess-return scatter plots with fitted CAPM lines.
- `residuals_over_time.png`: regression residuals through time.
- `residuals_vs_fitted.png`: residual-versus-fitted diagnostics.
- `rolling_beta_252d.csv`: underlying 252-day rolling beta series.
- `rolling_beta_252d.png`: 252-day rolling beta chart.
- `beta_comparison.png`: cross-stock beta bar chart.
- `in_sample_regression_summaries.txt`: full in-sample OLS summaries.
- `time_window_comparison.csv`: optional 2016-2020 versus 2021-2025 comparison.
"""
    (OUTPUT_DIR / "README.md").write_text(manifest, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    data = load_data()
    models, results = fit_models(data)

    save_regression_table(results)
    save_regression_summaries(models)
    save_beta_chart(results)
    save_scatter_regression_chart(data, models)
    save_residual_charts(data, models)
    save_rolling_beta_chart(data)
    save_time_window_comparison(data)
    write_manifest()

    print(f"Generated CAPM outputs in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
