"""GEL Rate Explorer: official GEL exchange-rate dashboard."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


NBG_RATES_URL = "https://nbg.gov.ge/gw/api/ct/monetarypolicy/currencies"
NBG_CURRENCY_PAGE_URL = "https://nbg.gov.ge/en/monetary-policy/currency"
CURRENCIES = ["USD", "EUR", "GBP", "TRY", "RUB"]
PERIODS = {
    "7d": {"days": 7, "months": 0},
    "14d": {"days": 14, "months": 0},
    "1m": {"days": 0, "months": 1},
    "3m": {"days": 0, "months": 3},
    "6m": {"days": 0, "months": 6},
    "1y": {"days": 0, "months": 12},
}

TEXT = {
    "ka": {
        "app_name": "GEL Rate Explorer",
        "subtitle": "საქართველოს ლარის ოფიციალური გაცვლითი კურსების ანალიზი (ეროვნული ბანკის კურსი)",
        "language": "ენა",
        "currency": "ვალუტა",
        "period": "პერიოდი",
        "current_rate": "მიმდინარე კურსი",
        "change": "ცვლილება",
        "change_help": "{currency}-ის კურსის ცვლილება ლართან მიმართებით არჩეულ პერიოდში",
        "highest": "მაქსიმუმი",
        "lowest": "მინიმუმი",
        "average": "საშუალო",
        "history": "კურსის ისტორია",
        "chart_title": "ოფიციალური გაცვლითი კურსი: {period}",
        "rate_axis": "კურსი (GEL)",
        "date_axis": "თარიღი",
        "source": "მონაცემების წყარო",
        "source_name": "საქართველოს ეროვნული ბანკი",
        "error": "ბოდიშს გიხდით, მონაცემების მიღებისას ეროვნული ბანკის მხარეს დაფიქსირდა შეცდომა. გთხოვთ, მოგვიანებით სცადოთ თავიდან.",
        "no_data": "არჩეული ვალუტისა და პერიოდისთვის ოფიციალური მონაცემები ვერ მოიძებნა.",
        "periods": {
            "7d": "7 დღე",
            "14d": "14 დღე",
            "1m": "1 თვე",
            "3m": "3 თვე",
            "6m": "6 თვე",
            "1y": "1 წელი",
        },
    },
    "en": {
        "app_name": "GEL Rate Explorer",
        "subtitle": "Explore official Georgian lari exchange rates",
        "language": "Language",
        "currency": "Currency",
        "period": "Period",
        "current_rate": "Current Rate",
        "change": "Change",
        "change_help": "{currency} change against GEL over the selected period",
        "highest": "Highest",
        "lowest": "Lowest",
        "average": "Average",
        "history": "Exchange Rate History",
        "chart_title": "Official exchange rate: {period}",
        "rate_axis": "Rate (GEL)",
        "date_axis": "Date",
        "source": "Data source",
        "source_name": "National Bank of Georgia",
        "error": "Sorry, there was an error on the National Bank of Georgia's side while retrieving the data. Please try again later.",
        "no_data": "No official data is available for the selected currency and period.",
        "periods": {
            "7d": "7 days",
            "14d": "14 days",
            "1m": "1 month",
            "3m": "3 months",
            "6m": "6 months",
            "1y": "1 year",
        },
    },
}


class NBGDataError(Exception):
    """Raised when an NBG response cannot safely be used by the dashboard."""


def today_in_tbilisi() -> date:
    """Return today's date in the timezone used by the National Bank of Georgia."""
    return datetime.now(ZoneInfo("Asia/Tbilisi")).date()


def subtract_months(value: date, months: int) -> date:
    """Move a date backwards by whole calendar months without third-party date helpers."""
    month_index = value.year * 12 + value.month - 1 - months
    year, month_zero_index = divmod(month_index, 12)
    month = month_zero_index + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def period_start(period_key: str, end_date: date) -> date:
    """Calculate the inclusive start date for a selected rolling period."""
    definition = PERIODS[period_key]
    if definition["days"]:
        return end_date - timedelta(days=definition["days"] - 1)
    return subtract_months(end_date, definition["months"])


def as_api_datetime(value: date) -> str:
    """Format an inclusive date for the ISO-8601 parameters expected by NBG."""
    return f"{value.isoformat()}T00:00:00.000Z"


@st.cache_data(ttl=600, show_spinner=False)
def fetch_rates(currency: str, start_date: date, end_date: date) -> pd.DataFrame:
    """Fetch one currency's official NBG observations for an inclusive date range."""
    params = {
        "start": as_api_datetime(start_date),
        "end": as_api_datetime(end_date),
        "currencies": currency,
    }

    try:
        response = requests.get(NBG_RATES_URL, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        raise NBGDataError("The NBG request did not return valid JSON data.") from error

    if not isinstance(payload, list):
        raise NBGDataError("NBG returned an unexpected top-level JSON value.")

    rows: list[dict[str, Any]] = []
    for observation in payload:
        if not isinstance(observation, dict):
            continue

        currencies = observation.get("currencies")
        if not isinstance(currencies, list):
            continue

        matching_currency = next(
            (
                item
                for item in currencies
                if isinstance(item, dict) and item.get("code") == currency
            ),
            None,
        )
        if matching_currency is None:
            continue

        try:
            observation_date = pd.to_datetime(observation["date"], utc=True).date()
            published_rate = float(matching_currency["rate"])
            quantity = float(matching_currency["quantity"])
        except (KeyError, TypeError, ValueError):
            continue

        if quantity <= 0 or published_rate <= 0:
            continue

        # NBG can quote a rate for 10, 100, or 1,000 units. The dashboard always shows 1 unit.
        rows.append({"date": observation_date, "rate": published_rate / quantity})

    if not rows:
        raise NBGDataError("NBG did not provide usable observations for the selected currency.")

    dataframe = pd.DataFrame(rows)
    dataframe = dataframe.drop_duplicates(subset="date", keep="last")
    dataframe = dataframe.sort_values("date").reset_index(drop=True)
    return dataframe


def calculate_statistics(dataframe: pd.DataFrame) -> dict[str, float]:
    """Calculate dashboard KPIs from sorted, official observations only."""
    first_rate = float(dataframe.iloc[0]["rate"])
    latest_rate = float(dataframe.iloc[-1]["rate"])
    return {
        "current": latest_rate,
        "change": ((latest_rate - first_rate) / first_rate) * 100,
        "highest": float(dataframe["rate"].max()),
        "lowest": float(dataframe["rate"].min()),
        "average": float(dataframe["rate"].mean()),
    }


def format_rate(value: float) -> str:
    """Show a consistent precision that still keeps small rates readable."""
    return f"{value:.4f}"


def make_chart(
    dataframe: pd.DataFrame, currency: str, period_label: str, text: dict[str, Any]
) -> go.Figure:
    """Build the responsive Plotly line chart for the selected official observations."""
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=dataframe["date"],
            y=dataframe["rate"],
            mode="lines",
            line={"color": "#0f766e", "width": 3},
            hovertemplate=(
                "%{x|%d %b %Y}<br>"
                f"1 {currency} = %{{y:.4f}} GEL<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title={
            "text": f"{currency} / GEL<br><sup>{text['chart_title'].format(period=period_label)}</sup>",
            "x": 0,
            "xanchor": "left",
        },
        height=400,
        margin={"l": 48, "r": 20, "t": 76, "b": 52},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        hovermode="x unified",
        font={
            "family": "Inter, Noto Sans Georgian, Arial, sans-serif",
            "color": "#0f172a",
            "size": 14,
        },
        hoverlabel={
            "bgcolor": "#172554",
            "bordercolor": "#172554",
            "font": {"color": "#ffffff", "size": 14},
        },
        showlegend=False,
    )
    figure.update_xaxes(
        title=text["date_axis"],
        showgrid=False,
        tickformat="%d %b",
        tickfont={"color": "#334155", "size": 12},
        title_font={"color": "#1e293b", "size": 13},
        linecolor="#94a3b8",
        tickcolor="#64748b",
        ticks="outside",
        fixedrange=False,
    )
    figure.update_yaxes(
        title=text["rate_axis"],
        gridcolor="#edf1f1",
        gridwidth=1,
        zeroline=False,
        tickformat=".4f",
        tickfont={"color": "#334155", "size": 12},
        title_font={"color": "#1e293b", "size": 13},
        linecolor="#94a3b8",
        tickcolor="#64748b",
        ticks="outside",
        fixedrange=False,
    )
    return figure


def add_styles() -> None:
    """Apply a small visual theme without adding another frontend dependency."""
    st.markdown(
        """
        <style>
        :root { --ink: #1f2937; --muted: #64748b; --line: #d9e1e1; --accent: #0f766e; --radius: 6px; --space: 1rem; }
        .stApp { background: #ffffff; color: var(--ink); overflow-x: hidden; }
        .stApp *, [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { box-sizing: border-box; min-width: 0; }
        .block-container { max-width: 1120px; padding: 1.25rem; }
        h1, h2, h3, p, label, div { font-family: Inter, "Noto Sans Georgian", Arial, sans-serif; }
        .app-header { padding: .15rem 0; margin: 0 0 1.25rem; }
        .app-header h1 { color: var(--ink); font-size: clamp(1.2rem, 3vw, 1.5rem); font-weight: 600; margin: 0; letter-spacing: -.02em; }
        .app-header p { margin: .2rem 0 0; color: var(--muted); font-size: .9rem; }
        .language-control-label { color: var(--ink); font-size: .82rem; font-weight: 500; margin: .15rem 0 .2rem; }
        .current-summary { padding: 1.25rem 0 .9rem; margin: .8rem 0 .65rem; }
        .eyebrow { color: var(--muted); font-weight: 500; font-size: .8rem; letter-spacing: .04em; text-transform: uppercase; margin-bottom: .3rem; }
        .current-rate { color: var(--ink); font-size: clamp(1.7rem, 4vw, 2.3rem); font-weight: 700; line-height: 1.12; }
        .subtle { color: var(--muted); margin-top: .4rem; font-size: .9rem; }
        .kpi-card { background: transparent; border-radius: 0; padding: .75rem 0; min-height: auto;
                    border: 0; border-top: 1px solid var(--line); box-shadow: none; }
        .kpi-card .label { color: var(--muted); font-weight: 500; font-size: .86rem; margin-bottom: .28rem; }
        .kpi-card .value { color: var(--ink); font-size: 1.15rem; font-weight: 700; }
        .info-tooltip { display: inline-flex; position: relative; align-items: center; justify-content: center;
                        width: .9rem; height: .9rem; margin-left: .22rem; border: 1px solid #94a3b8;
                        border-radius: 50%; color: #64748b; font-size: .65rem; font-style: normal;
                        line-height: 1; vertical-align: .05rem; cursor: default; }
        .info-tooltip-text { display: none; position: absolute; z-index: 10; left: 0; bottom: calc(100% + .4rem);
                             width: max-content; max-width: min(240px, 72vw); padding: .45rem .55rem;
                             border: 1px solid var(--line); border-radius: var(--radius); background: #ffffff;
                             color: var(--ink); font-size: .78rem; font-weight: 400; line-height: 1.35;
                             white-space: normal; }
        .info-tooltip:hover .info-tooltip-text,
        .info-tooltip:focus .info-tooltip-text { display: block; }
        .positive { color: #047857 !important; } .negative { color: #be123c !important; }
        .source { color: var(--muted); font-size: .86rem; padding: .25rem 0 .8rem; }
        .source a { color: var(--accent); font-weight: 500; }
        .source-author { color: var(--muted); font-size: .86rem; padding: .25rem 0 .8rem; text-align: right; white-space: nowrap; }

        /* Streamlit widgets need an explicit dark foreground on this light theme. */
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] label,
        [data-testid="stWidgetLabel"] span,
        .stSelectbox label,
        .stRadio > label,
        .stRadio label p,
        .stRadio label span { color: #0f172a !important; font-weight: 650; }
        [data-baseweb="select"] > div {
            color: #0f172a !important; background-color: #ffffff !important;
            border-color: #aab8b8 !important; min-height: 2.35rem;
        }
        [data-baseweb="select"] * { color: #0f172a; }
        [data-baseweb="select"] svg { fill: #0f766e; }
        .stRadio > label { font-size: .82rem; margin-bottom: .2rem; }
        .stRadio > div { background: #f1f4f4; border-radius: var(--radius); gap: 0; padding: 3px; flex-wrap: wrap; }
        .stRadio label { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: .3rem .55rem; }
        .stRadio label:has(input:checked) { background: #ffffff; border-color: var(--line); }
        .stRadio [data-checked="true"] { background-color: var(--accent) !important; border-color: var(--accent) !important; }
        [data-testid="stPlotlyChart"] { background: transparent; border: 0; border-radius: 0; padding: 0; max-width: 100%; }
        @media (max-width: 900px) {
            .block-container { padding: .75rem .85rem 1.25rem; }
            .app-header { margin-top: 0; padding-left: .75rem; }
            .source-author { text-align: left; padding-top: 0; }
            .current-rate { font-size: 1.6rem; }
            div[data-testid="stHorizontalBlock"]:not(:has(.kpi-card)) { flex-wrap: wrap; gap: .4rem; }
            div[data-testid="stHorizontalBlock"]:not(:has(.kpi-card)) > div[data-testid="stColumn"] { min-width: 100% !important; }
            div[data-testid="stHorizontalBlock"]:has(.kpi-card) { flex-wrap: wrap; gap: .65rem; }
            div[data-testid="stHorizontalBlock"]:has(.kpi-card) > div[data-testid="stColumn"] { min-width: calc(50% - .35rem) !important; }
            .kpi-card { min-height: 0; padding: .7rem 0; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(
    label: str, value: str, extra_class: str = "", help_text: str = ""
) -> None:
    """Render a compact KPI card inside a Streamlit column."""
    help_icon = (
        f'<span class="info-tooltip" tabindex="0" aria-label="{help_text}">i'
        f'<span class="info-tooltip-text" role="tooltip">{help_text}</span></span>'
        if help_text
        else ""
    )
    st.markdown(
        f'<div class="kpi-card"><div class="label">{label}{help_icon}</div>'
        f'<div class="value {extra_class}">{value}</div></div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="GEL Rate Explorer", page_icon="₾", layout="wide")
    add_styles()

    header_left, header_right = st.columns([3, 2])
    with header_right:
        st.markdown('<div class="language-control-label">ენა / Language</div>', unsafe_allow_html=True)
        language_label = st.radio(
            "ენა / Language",
            options=["ქართული", "English"],
            horizontal=True,
            label_visibility="collapsed",
        )
    language = "ka" if language_label == "ქართული" else "en"
    text = TEXT[language]

    with header_left:
        st.markdown(
            f'<section class="app-header"><h1>{text["app_name"]}</h1>'
            f'<p>{text["subtitle"]}</p></section>',
            unsafe_allow_html=True,
        )

    controls_left, controls_right = st.columns([1, 2])
    with controls_left:
        currency = st.selectbox(text["currency"], CURRENCIES)
    with controls_right:
        period_key = st.radio(
            text["period"],
            options=list(PERIODS),
            format_func=lambda key: text["periods"][key],
            horizontal=True,
        )

    end_date = today_in_tbilisi()
    start_date = period_start(period_key, end_date)

    try:
        with st.spinner(""):
            dataframe = fetch_rates(currency, start_date, end_date)
        statistics = calculate_statistics(dataframe)
    except (NBGDataError, IndexError, KeyError, ValueError):
        st.error(text["error"])
        return

    if dataframe.empty:
        st.info(text["no_data"])
        return

    period_label = text["periods"][period_key]
    st.markdown(
        f'<section class="current-summary"><div class="eyebrow">{text["current_rate"]}</div>'
        f'<div class="current-rate">1 {currency} = {format_rate(statistics["current"])} GEL</div></section>',
        unsafe_allow_html=True,
    )

    change_class = "positive" if statistics["change"] >= 0 else "negative"
    change_value = f'{statistics["change"]:+.2f}%'
    columns = st.columns(4)
    with columns[0]:
        kpi_card(
            text["change"],
            change_value,
            change_class,
            text["change_help"].format(currency=currency),
        )
    with columns[1]:
        kpi_card(text["highest"], f'{format_rate(statistics["highest"])} GEL')
    with columns[2]:
        kpi_card(text["lowest"], f'{format_rate(statistics["lowest"])} GEL')
    with columns[3]:
        kpi_card(text["average"], f'{format_rate(statistics["average"])} GEL')

    st.markdown("<div style='height: 1.2rem'></div>", unsafe_allow_html=True)
    st.plotly_chart(
        make_chart(dataframe, currency, period_label, text),
        use_container_width=True,
        config={"displaylogo": False, "responsive": True},
    )

    source_left, source_right = st.columns([3, 2])
    with source_left:
        st.markdown(
            f'<div class="source">{text["source"]}: <a href="{NBG_CURRENCY_PAGE_URL}" target="_blank">'
            f'{text["source_name"]}</a></div>',
            unsafe_allow_html=True,
        )
    with source_right:
        st.markdown('<div class="source-author">Built By: @Latishi</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
