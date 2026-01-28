# Backtesting

Backtesting is the process of testing a trade idea against historical data to see if it would have worked in the recent past.

---

## How It Works

When the bot considers a trade, it asks: "If I had made this same type of trade over the last 90 days, how would it have turned out?"

1. The bot looks at the last 90 days of real price data for the stock
2. It finds moments where the same signal conditions occurred (similar indicator readings)
3. It simulates entering the trade at those moments and holding for 5 days
4. It applies the same stop-loss and take-profit rules it would use in a real trade
5. It tallies up the results

---

## What Gets Measured

### Win Rate
The percentage of simulated trades that made money.

| Win Rate | Points |
|----------|--------|
| 60%+ | 30 |
| 50-59% | 20 |
| 40-49% | 10 |
| Below 40% | 0 |

### Average Return
The average profit (or loss) across all simulated trades.

| Avg Return | Points |
|------------|--------|
| 2%+ | 30 |
| 1-2% | 20 |
| 0-1% | 10 |
| Negative | 0 |

### Max Drawdown
The worst peak-to-trough drop during any simulated trade. Smaller is better.

| Max Drawdown | Points |
|-------------|--------|
| 5% or less | 20 |
| More than 5% | Reduced score |

### Sharpe Ratio
A measure of how consistent the returns were relative to the risk taken. Higher is better.

| Sharpe Ratio | Points |
|-------------|--------|
| 2.0+ | 20 |
| Below 2.0 | Reduced score |

**Analogy:** Imagine two restaurants both averaging 4-star reviews. One has all 4-star reviews (high Sharpe -- consistent). The other has a mix of 1-star and 5-star reviews (low Sharpe -- volatile). The consistent one is a safer bet.

---

## Why It Matters

Backtesting contributes **20%** of the final trade score. A trade idea might look good on paper, but if similar setups have lost money recently, the bot will downgrade or skip it entirely.

Backtesting is not a guarantee -- past performance doesn't predict the future -- but it filters out ideas that have been consistently failing in the current market environment.
