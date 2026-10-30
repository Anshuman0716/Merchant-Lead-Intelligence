# Merchant Lead Intelligence Engine

> It tells a payments SDR which merchants to call first, why, and what to say.

Takes 300–500 Indian online businesses (D2C, edtech, SaaS), detects their payment setup from
public website signals, scores them against 3 ICPs, and outputs a tiered, CRM-ready lead list
with personalised openers — plus a dashboard and a one-page insight note.

🚧 Work in progress.

## How to run

```bash
make setup      # install deps
make pipeline   # rebuild everything from data/seeds/
make app        # open the dashboard
make test
```
