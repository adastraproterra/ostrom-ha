# Ostrom Integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%3E%3D2023.1-blue.svg)](https://www.home-assistant.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A custom Home Assistant integration for the German energy provider **Ostrom**. Provides real-time spot prices, consumption data, and cost tracking directly in your Home Assistant dashboard.

---

## Features

| Feature | Description |
|---|---|
|  **Working Price** | Static contracted rate in ct/kWh always visible as a sensor |
|  **Current Spot Price** | Live hourly electricity price in ct/kWh, updated every hour |
|  **24h Price Forecast** | All upcoming hourly prices as a sensor attribute  perfect for ApexCharts |
|  **Daily Consumption** | Energy used today in kWh |
|  **Monthly Consumption** | Energy used this month in kWh |
|  **Monthly Cost** | Gross electricity cost for the current month in € |

---

## Requirements

- Home Assistant **2023.1** or newer
- [HACS](https://hacs.xyz/) installed
- An active Ostrom customer account
- API credentials (Client ID & Client Secret) from the [Ostrom Developer Portal](https://developer.ostrom-api.io/)

---

## Installation via HACS

1. Open **HACS > Integrations**
2. Click **(top right) Custom repositories**
3. Enter the URL: `https://github.com/adastraproterra/ostrom-ha`
4. Category: **Integration** â†’ click **Add**
5. Search for **Ostrom** in HACS and click **Download**
6. **Restart Home Assistant**

---

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Ostrom**
3. Fill in the form:

| Field | Description |
|---|---|
| **Client ID** | From the Ostrom Developer Portal |
| **Client Secret** | From the Ostrom Developer Portal |
| **Postal Code** | Your ZIP code (used for regional grid fees) |
| **Working Price (ct/kWh)** | Your static contracted working price |

---

## Available Sensors

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ostrom_working_price` | ct/kWh | Static working price (manually configured) |
| `sensor.ostrom_current_electricity_price` | ct/kWh | Live spot price, updated hourly |
| `sensor.ostrom_daily_consumption` | kWh | Consumption today |
| `sensor.ostrom_monthly_consumption` | kWh | Consumption this month |
| `sensor.ostrom_monthly_cost` | € | Gross cost this month |

> **Tip:** The `current_electricity_price` sensor includes a `preisprognose_24h` attribute containing all hourly forecast prices as a list â€” ideal for use with the ApexCharts card.

---

## Example: ApexCharts Price Chart

```yaml
type: custom:apexcharts-card
graph_span: 24h
header:
  title: Ostrom Electricity Prices
  show: true
apex_config:
  plotOptions:
    bar:
      colors:
        ranges:
          - from: 0
            to: 0.15
            color: "#2ecc71"
          - from: 0.15
            to: 0.25
            color: "#f39c12"
          - from: 0.25
            to: 1
            color: "#e74c3c"
series:
  - entity: sensor.ostrom_current_electricity_price
    type: column
    name: Price (ct/kWh)
    float_precision: 4
    group_by:
      duration: 1h
      func: avg
```

---

## Update Interval

Data is fetched **once per hour** (on the full hour). The Ostrom API provides prices up to 23:00 of the current day, and after 14:00 also the prices for the following day.

---

## Troubleshooting

**Integration not found after install?** Make sure you restarted Home Assistant after installing via HACS.

**Authentication error?** Double-check your Client ID and Client Secret. Make sure you created a *Production* client, not a Sandbox client.

**No consumption data?**  Consumption data requires an active contract with a smart meter. Sensors will show `unavailable` if the API returns no data yet.

---

## Contributing

Pull requests and issues are welcome! Please open an issue before submitting large changes.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

*This integration is not affiliated with or endorsed by Ostrom GmbH.*
