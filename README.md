# FinOpsMap — AWS & Azure Cloud Pricing Comparator

> Compare AWS EC2, RDS and Azure VM, Database pricing in real time. Free, open-source FinOps tool.

🌐 **[finopsmap.com](https://finopsmap.com)**

---

## What is FinOpsMap?

FinOpsMap is a Python tool that fetches live pricing from AWS and Azure APIs and generates a self-contained interactive `index.html` dashboard — no server, no dependencies, just open the file.

Built for FinOps engineers and cloud architects who need to compare instance pricing across regions without opening a dozen browser tabs.

## Features

- **EC2 / RDS / Azure VM / Azure DB** pricing across multiple regions
- **Interactive heatmap** — world map with per-region cost coloring
- **GreenOps** — carbon intensity per region (gCO2eq/kWh)
- **Reserved pricing** — 1yr / 3yr with No Upfront / All Upfront
- **FinOps Score** — composite score based on cost, generation and ARM architecture
- **EUR/USD** conversion via FRED API (Federal Reserve)
- **FinOps Blog** — curated articles from AWS, Azure and FinOps Foundation

## Usage

```bash
# Install dependencies (none — uses Python stdlib only)
python3 fetch_prices.py
```

Open `index.html` in your browser.

### Optional: live EUR/USD rate

Get a free API key at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) and run:

```bash
FRED_API_KEY=your_key python3 fetch_prices.py
```

### Cache

Pricing data is cached in `data/aws/` and `data/azure/` for 7 days. Delete the cache to force a refresh:

```bash
rm -rf data/aws/ data/azure/
```

## Data Sources

| Source | Data |
|--------|------|
| [AWS Price List API](https://pricing.us-east-1.amazonaws.com) | EC2, RDS On-Demand & Reserved |
| [Azure Retail Prices API](https://prices.azure.com/api/retail/prices) | VM, Database On-Demand & Reserved |
| [Electricity Maps](https://www.electricitymaps.com) | Carbon intensity (static, open-source) |
| [FRED API](https://fred.stlouisfed.org) | EUR/USD exchange rate |

## Regions covered

**AWS** — Paris, Ireland, Frankfurt, London, Stockholm, Virginia

**Azure** — France Central, North Europe, West Europe, Germany West Central, UK South, Sweden Central, East US

## Contributing

PRs welcome. Open an issue for bugs or feature requests.

## Support

If FinOpsMap saves you time or money, consider supporting it:

☕ [buymeacoffee.com/finopsmap](https://buymeacoffee.com/finopsmap)

## License

MIT
