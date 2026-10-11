# 17. Rumor resolution and reliability scoring (backlog)

Status: Deferred — 2026-10-12 (backlog, see ADR 1)

## Decision
Each Rumor is a long-running Temporal workflow that sleeps on a durable timer until its transfer window closes + 7 days, then checks Transfermarkt transfers and records a grade:
- wrong
- right club, wrong window
- right club and window
- exact (club, window and fee within ±25%)

Loans are graded separately from permanent transfers. Reliability is scored per journalist and per outlet, ranked only above a minimum sample size.
