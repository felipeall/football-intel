# 17. Rumor resolution and reliability scoring (phase 2)

Status: Accepted — 2026-10-11

## Decision
Each Rumor is a long-running Temporal workflow that sleeps on a durable timer until its transfer window closes + 7 days, then checks Transfermarkt transfers and records a grade:
- wrong
- right club, wrong window
- right club and window
- exact (club, window and fee within ±25%)

Loans are graded separately from permanent transfers. Reliability is scored per journalist and per outlet, ranked only above a minimum sample size.
