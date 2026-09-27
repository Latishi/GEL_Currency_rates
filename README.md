# GEL Rate Explorer

GEL Rate Explorer is a Streamlit web application for viewing official Georgian lari exchange rates against selected foreign currencies. It retrieves data directly from the National Bank of Georgia, calculates summary values for a selected period, and displays the result as an interactive chart.

## Features

- Official National Bank of Georgia exchange-rate data
- Supported currencies: USD, EUR, GBP, TRY, and RUB
- Rates normalized to one unit of the selected currency in GEL
- Preset periods: 7 days, 14 days, 1 month, 3 months, 6 months, and 1 year
- Current rate, percentage change, highest, lowest, and average values
- Interactive Plotly chart with hover details and zoom controls
- Georgian and English interface
- Responsive layout for desktop and mobile screens

## How it works

The application requests currency observations from the NBG public endpoint for the selected currency and date range. The response is validated and converted to a Pandas DataFrame containing `date` and `rate` columns.

NBG can publish a rate for more than one currency unit. The application divides the published `rate` by `quantity`, so every displayed value consistently represents one unit of the selected currency.

The dashboard calculates its values from official observations only:

- **Current rate**: the latest available official observation.
- **Change**: percentage difference between the first and latest observation in the selected period.
- **Highest / Lowest / Average**: the maximum, minimum, and arithmetic mean of the returned observations.

The percentage-change annotation identifies the selected currency and clarifies that the comparison is against GEL for the selected period.

## Technology

- Python
- Streamlit
- Pandas
- Plotly
- Requests
- National Bank of Georgia public currency API

## Data source

Exchange-rate data is requested directly from the official [National Bank of Georgia currency service](https://nbg.gov.ge/en/monetary-policy/currency). The application does not use a local database or a separately maintained currency dataset.

Official observations may not be available for every calendar day. The displayed current rate is always based on the latest official observation returned by NBG.

## Run locally

1. Create and activate a virtual environment.

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies.

   ```bash
   pip install -r requirements.txt
   ```

3. Start the application.

   ```bash
   streamlit run app.py
   ```

4. Open the local URL printed by Streamlit, normally `http://localhost:8501`.

## Project structure

```text
.
├── app.py            Application interface, data retrieval, validation, calculations, and chart
├── requirements.txt  Python dependencies
└── README.md         Project documentation
```
