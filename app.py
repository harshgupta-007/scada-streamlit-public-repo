from pathlib import Path

import streamlit as st

from utils.charts import (
    generate_anomaly_insights,
    generate_intraday_anomaly_insights,
    generate_intraday_insights,
    generate_ramp_insights,
    generate_regional_insights,
    generate_variability_insights,
    plot_demand_stats,
    plot_demand_trend,
    plot_demand_with_anomalies,
    plot_generation_mix,
    plot_intraday_curve,
    plot_intraday_with_anomalies,
    plot_ramp_trend,
    plot_regional_contribution,
    plot_regional_distribution,
    plot_regional_trend,
    plot_variability,
    plot_daily_weather_overlay,
    plot_weather_demand_scatter,
    plot_intraday_weather_scatter,
    plot_intraday_weather_overlay,
    plot_multi_date_weather_comparison,
    plot_intraday_quadrant_analysis,
    plot_intraday_quadrant_diagnostic_scatter,
    build_intraday_weather_summary,
    build_intraday_quadrant_summary,
    build_multi_date_weather_comparison,
    build_weather_kpis,
    build_weather_correlation_summary,
    interpret_intraday_quadrant_analysis,
    plot_forecast_profile,
    plot_forecast_daily_context,
    plot_forecast_weather_adjustment,
)
from utils.data_loader import DATA_FILE, filter_data_by_date, get_date_range, load_scada_data, get_merged_scada_weather
from utils.data_loader import get_data_source_label
from utils.forecasting import build_intraday_forecast, get_forecast_target_dates, summarize_forecast, weather_label
from utils.agent_chat import (
    ask_scada_agent_with_trace,
    is_agent_chat_configured,
    is_langsmith_configured,
    submit_langsmith_feedback,
)
from utils.insights import generate_master_insights
from utils.kpi_cards import render_kpi_cards


BASE_DIR = Path(__file__).resolve().parent
ASSET_IMAGE = BASE_DIR / "assets" / "scada_architecture.png"
AVAILABLE_PAGES = [
    "Overview",
    "Regional Analysis",
    "Generation Mix",
    "Intraday Profile",
    "Weather Correlation",
    "Forecasting",
]
DEFERRED_PAGES = [
]


st.set_page_config(
    page_title="SCADA Demand Dashboard",
    page_icon=":zap:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def build_sidebar(df):
    if ASSET_IMAGE.exists():
        st.sidebar.image(str(ASSET_IMAGE), use_container_width=True)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Navigation")
    pages = AVAILABLE_PAGES.copy()
    if is_agent_chat_configured():
        pages.append("Agent Chat")
    page = st.sidebar.radio("Select View", pages, label_visibility="collapsed")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Global Filters")

    if df.empty:
        st.sidebar.warning("Unable to initialize filters. Data not loaded.")
        return page

    min_date, max_date = get_date_range(df)
    date_input = st.sidebar.date_input(
        "Select Date Range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )

    if isinstance(date_input, (tuple, list)):
        if len(date_input) == 2:
            start_date, end_date = date_input
        elif len(date_input) == 1:
            start_date = end_date = date_input[0]
        else:
            start_date = end_date = min_date.date()
    else:
        start_date = end_date = date_input

    if start_date > end_date:
        st.sidebar.error("Start date cannot be after end date.")
        return page

    st.sidebar.markdown("---")
    st.sidebar.subheader("Data Exclusion Filters")
    exclude_weekends = st.sidebar.checkbox("Exclude Weekends (Sat/Sun)", value=False)
    exclude_holidays = st.sidebar.checkbox("Exclude Holidays", value=False)
    exclude_events = st.sidebar.checkbox("Exclude Special Events", value=False)

    filtered_df = filter_data_by_date(df, start_date, end_date)

    if exclude_weekends and "is_weekend" in filtered_df.columns:
        filtered_df = filtered_df[~filtered_df["is_weekend"]]
    if exclude_holidays and "is_holiday" in filtered_df.columns:
        filtered_df = filtered_df[~filtered_df["is_holiday"]]
    if exclude_events and "is_special_event" in filtered_df.columns:
        filtered_df = filtered_df[~filtered_df["is_special_event"]]

    st.session_state["filtered_df"] = filtered_df
    st.session_state["start_date"] = start_date
    st.session_state["end_date"] = end_date
    st.session_state["exclude_weekends"] = exclude_weekends
    st.session_state["exclude_holidays"] = exclude_holidays
    st.session_state["exclude_events"] = exclude_events

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Data source: {get_data_source_label()}")
    st.sidebar.caption("MongoDB is used when configured; otherwise the app falls back to approved sample files.")
    st.sidebar.caption("Deferred features: " + ", ".join(DEFERRED_PAGES))

    return page


def main():
    st.title("SCADA System Intelligence Dashboard")
    st.markdown("Monitor and analyze SCADA demand patterns using MongoDB data when configured, with sample-data fallback.")

    df = load_scada_data(DATA_FILE)
    if df.empty:
        st.error("Application cannot start without SCADA data.")
        return

    page = build_sidebar(df)

    if page == "Overview":
        render_overview()
    elif page == "Regional Analysis":
        render_regional()
    elif page == "Generation Mix":
        render_generation()
    elif page == "Intraday Profile":
        render_intraday()
    elif page == "Weather Correlation":
        render_weather_correlation()
    elif page == "Forecasting":
        render_forecasting()
    elif page == "Agent Chat":
        render_agent_chat()


def render_overview():
    st.header("System Overview")

    df = st.session_state.get("filtered_df")
    if df is None or df.empty:
        st.info("Please select a valid date range containing data.")
        return

    render_kpi_cards(df)

    col1, col2 = st.columns(2)
    with col1:
        fig1 = plot_demand_trend(df)
        if fig1:
            st.plotly_chart(fig1, use_container_width=True)
    with col2:
        fig2 = plot_demand_stats(df)
        if fig2:
            st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Key System Insights")
    for insight in generate_master_insights(df):
        st.success(insight)

    st.subheader("Anomaly Detection")
    fig_anomaly = plot_demand_with_anomalies(df)
    if fig_anomaly:
        st.plotly_chart(fig_anomaly, use_container_width=True)
    st.warning(generate_anomaly_insights(df))


def render_regional():
    st.header("Regional Demand Intelligence")

    df = st.session_state.get("filtered_df")
    if df is None or df.empty:
        st.info("Please select a valid date range containing data.")
        return

    st.subheader("Regional Contribution (%)")
    fig_pct = plot_regional_contribution(df)
    if fig_pct:
        st.plotly_chart(fig_pct, use_container_width=True)

    st.subheader("Regional Demand Trend")
    fig_trend = plot_regional_trend(df)
    if fig_trend:
        st.plotly_chart(fig_trend, use_container_width=True)

    st.subheader("Demand Distribution")
    fig_box = plot_regional_distribution(df)
    if fig_box:
        st.plotly_chart(fig_box, use_container_width=True)

    st.success(generate_regional_insights(df))

    st.subheader("Demand Variability and Risk Analysis")
    fig_var = plot_variability(df)
    if fig_var:
        st.plotly_chart(fig_var, use_container_width=True)
    st.warning(generate_variability_insights(df))


def render_generation():
    st.header("Generation Mix")
    st.markdown("View the proportion of energy generated from thermal, hydel, and renewable sources.")

    df = st.session_state.get("filtered_df")
    if df is None or df.empty:
        st.info("Please select a valid date range containing data.")
        return

    fig = plot_generation_mix(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)


def render_intraday():
    st.header("Intraday Demand Intelligence")

    df = load_scada_data(DATA_FILE)
    if df.empty:
        st.error("Data not available.")
        return

    min_date, max_date = get_date_range(df)
    selected_date = st.date_input(
        "Select Date for Intraday Analysis",
        value=min_date.date(),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )
    st.info(f"Showing intraday profile for {selected_date}")

    df_intraday = df[df["date"].dt.date == selected_date]
    if df_intraday.empty:
        st.warning("No data available for the selected date.")
        return

    fig = plot_intraday_curve(df_intraday)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    st.success(generate_intraday_insights(df_intraday))

    st.subheader("Ramp Analysis")
    fig_ramp = plot_ramp_trend(df_intraday)
    if fig_ramp:
        st.plotly_chart(fig_ramp, use_container_width=True)
    st.warning(generate_ramp_insights(df_intraday))

    st.subheader("Intraday Anomaly Detection")
    fig_anomaly = plot_intraday_with_anomalies(df_intraday)
    if fig_anomaly:
        st.plotly_chart(fig_anomaly, use_container_width=True)
    st.warning(generate_intraday_anomaly_insights(df_intraday))


def render_weather_correlation():
    st.header("Weather Correlation")
    st.markdown(
        "Analyze how public Open-Meteo sample weather aligns with SCADA demand, "
        "from daily correlation down to 96-block intraday behavior."
    )

    df = get_merged_scada_weather()
    if df.empty:
        st.warning("Weather sample data is unavailable.")
        return

    start_date = st.session_state.get("start_date")
    end_date = st.session_state.get("end_date")
    if start_date and end_date:
        df = filter_data_by_date(df, start_date, end_date)

    if st.session_state.get("exclude_weekends", False) and "is_weekend" in df.columns:
        df = df[~df["is_weekend"]]
    if st.session_state.get("exclude_holidays", False) and "is_holiday" in df.columns:
        df = df[~df["is_holiday"]]
    if st.session_state.get("exclude_events", False) and "is_special_event" in df.columns:
        df = df[~df["is_special_event"]]

    if df.empty:
        st.info("No weather and demand records remain after the selected filters.")
        return

    weather_options = {
        "Temperature": "temperature_2m",
        "Relative Humidity": "relativehumidity_2m",
        "Wind Speed": "windspeed_10m",
        "Apparent Temperature": "apparent_temperature",
        "Precipitation": "precipitation",
    }
    selected_label = st.selectbox("Weather variable", list(weather_options.keys()), key="weather_variable")
    weather_col = weather_options[selected_label]

    kpis = build_weather_kpis(df, weather_col)
    if kpis:
        kpi_cols = st.columns(5)
        kpi_cols[0].metric("Matched Blocks", f"{kpis['records']:,}")
        kpi_cols[1].metric("Avg Demand", f"{kpis['avg_demand']:,.0f} MW")
        kpi_cols[2].metric("Peak Demand", f"{kpis['peak_demand']:,.0f} MW")
        kpi_cols[3].metric(f"Avg {selected_label}", f"{kpis['avg_weather']:,.1f}")
        kpi_cols[4].metric("Correlation", f"{kpis['correlation']:.2f}")

    daily_tab, intraday_tab, comparison_tab = st.tabs(
        ["Daily Relationship", "Intraday Calendar", "Date Comparison"]
    )

    with daily_tab:
        st.info(build_weather_correlation_summary(df, weather_col))
        st.caption(
            "How to read this: the blue line shows average demand by date, while the orange dotted line "
            "shows the selected weather variable for the same dates."
        )
        fig_daily_overlay = plot_daily_weather_overlay(df, weather_col)
        if fig_daily_overlay:
            st.plotly_chart(fig_daily_overlay, use_container_width=True)
        else:
            st.warning("Could not build the daily weather overlay chart.")

        with st.expander("Advanced: daily sensitivity scatter"):
            st.caption(
                "Use this when you want to inspect whether higher or lower weather values usually align "
                "with higher demand. Each point represents one day."
            )
            fig_scatter = plot_weather_demand_scatter(df, weather_col)
            if fig_scatter:
                st.plotly_chart(fig_scatter, use_container_width=True)
            else:
                st.warning("Could not build the daily weather-demand scatter chart.")

    with intraday_tab:
        available_dates = sorted(df["date"].dt.date.unique())
        if not available_dates:
            st.warning("No dates are available for intraday weather analysis.")
            return

        default_date = available_dates[-1]
        selected_date = st.date_input(
            "Select date for 96-block intraday weather analysis",
            value=default_date,
            min_value=available_dates[0],
            max_value=available_dates[-1],
            key="weather_intraday_date",
        )

        df_intraday = df[df["date"].dt.date == selected_date]
        if df_intraday.empty:
            st.warning("No merged weather and demand records are available for the selected date.")
            return

        st.success(build_intraday_weather_summary(df_intraday, weather_col))
        st.caption(
            "How to read this: follow demand across the day first. Then compare whether the dotted weather "
            "line rises or falls before demand changes."
        )
        fig_overlay = plot_intraday_weather_overlay(df_intraday, weather_col)
        if fig_overlay:
            st.plotly_chart(fig_overlay, use_container_width=True)
        else:
            st.warning("Could not build the selected-day intraday weather overlay chart.")

        with st.expander("Advanced: selected-day block sensitivity scatter"):
            st.caption(
                "This is useful for deeper analysis, but it is less intuitive than the time profile. "
                "Each point is one 15-minute block, and color shows the block sequence through the day."
            )
            fig_block_scatter = plot_intraday_weather_scatter(df_intraday, weather_col)
            if fig_block_scatter:
                st.plotly_chart(fig_block_scatter, use_container_width=True)
            else:
                st.warning("Could not build the selected-day block scatter chart.")

        st.subheader("Quadrant Analysis")
        z_threshold = st.slider(
            "Abnormality threshold (z-score)",
            min_value=0.5,
            max_value=2.5,
            value=1.0,
            step=0.1,
            key="weather_quadrant_threshold",
            help="Blocks beyond this same-block baseline deviation are classified as abnormal.",
        )
        st.info(
            "This view compares each 15-minute block of the selected day against the average of the other filtered days "
            "at the same block number, then classifies demand and weather as normal or abnormal."
        )
        st.success(interpret_intraday_quadrant_analysis(df, selected_date, weather_col, z_threshold))

        fig_quadrant = plot_intraday_quadrant_analysis(df, selected_date, weather_col, z_threshold)
        if fig_quadrant:
            st.plotly_chart(fig_quadrant, use_container_width=True)
        else:
            st.warning("Could not build the selected-day quadrant analysis chart.")

        quadrant_summary = build_intraday_quadrant_summary(df, selected_date, weather_col, z_threshold)
        if not quadrant_summary.empty:
            st.dataframe(quadrant_summary, use_container_width=True, hide_index=True)
        else:
            st.warning("Could not build the quadrant summary table.")

        st.markdown(
            f"""
            **How the bifurcation is calculated**

            For each 15-minute block of the selected day, we compare it against the average of the **other filtered days**
            at the **same block number**.

            `demand_z = (selected_block_demand - baseline_block_mean_demand) / baseline_block_std_demand`

            `weather_z = (selected_block_{weather_col} - baseline_block_mean_{weather_col}) / baseline_block_std_{weather_col}`

            Then we classify using the selected threshold `T = {z_threshold:.1f}`:

            - `|demand_z| < T` -> Normal Demand
            - `|demand_z| >= T` -> Abnormal Demand
            - `|weather_z| < T` -> Normal Weather
            - `|weather_z| >= T` -> Abnormal Weather

            The **2x2 quadrant chart** is the best operational view because it shows the final decision cleanly.
            The **diagnostic scatter** below is the more mathematically complete view because it preserves direction
            and exact signed z-scores.
            """
        )

        with st.expander("Diagnostic view for analysts", expanded=False):
            st.caption(
                "This view keeps the signed z-scores. Use it when you want the exact magnitude and direction of deviation, "
                "not just the final quadrant classification."
            )
            fig_diagnostic = plot_intraday_quadrant_diagnostic_scatter(df, selected_date, weather_col, z_threshold)
            if fig_diagnostic:
                st.plotly_chart(fig_diagnostic, use_container_width=True)
            else:
                st.warning("Could not build the diagnostic quadrant scatter.")

    with comparison_tab:
        available_dates = sorted(df["date"].dt.date.unique())
        if len(available_dates) < 2:
            st.warning("At least two dates are required for comparison.")
            return

        default_dates = available_dates[-3:] if len(available_dates) >= 3 else available_dates
        selected_dates = st.multiselect(
            "Select 2 to 5 dates for comparison",
            options=available_dates,
            default=default_dates,
            format_func=lambda date_value: date_value.strftime("%d %b %Y"),
            key="weather_compare_dates",
        )

        if len(selected_dates) < 2:
            st.info("Select at least two dates to compare weather and demand profiles.")
            return
        if len(selected_dates) > 5:
            st.warning("Showing the first 5 selected dates to keep the comparison readable.")
            selected_dates = selected_dates[:5]

        st.caption(
            "How to read this: compare the shape and timing of demand in the top chart, then check "
            "whether the selected weather variable follows a similar or opposite pattern in the bottom chart."
        )
        fig_compare = plot_multi_date_weather_comparison(df, weather_col, selected_dates)
        if fig_compare:
            st.plotly_chart(fig_compare, use_container_width=True)
        else:
            st.warning("Could not build the multi-date comparison chart.")

        comparison_df = build_multi_date_weather_comparison(df, weather_col, selected_dates)
        if not comparison_df.empty:
            st.subheader("Selected-Date Comparison Table")
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)
        else:
            st.warning("Could not build the selected-date comparison table.")


def render_forecasting():
    st.header("Forecasting")
    st.markdown(
        "Backtest a weather-aware 96-block demand forecast using recent history. "
        "This is the right first production step because we can measure forecast quality on known days before moving to fully forward-looking operations."
    )

    df = get_merged_scada_weather()
    if df.empty:
        df = load_scada_data(DATA_FILE)

    start_date = st.session_state.get("start_date")
    end_date = st.session_state.get("end_date")
    if start_date and end_date and not df.empty:
        df = filter_data_by_date(df, start_date, end_date)

    if st.session_state.get("exclude_weekends", False) and "is_weekend" in df.columns:
        df = df[~df["is_weekend"]]
    if st.session_state.get("exclude_holidays", False) and "is_holiday" in df.columns:
        df = df[~df["is_holiday"]]
    if st.session_state.get("exclude_events", False) and "is_special_event" in df.columns:
        df = df[~df["is_special_event"]]

    if df.empty:
        st.info("No records remain after the selected filters.")
        return

    weather_options = {
        "Apparent Temperature": "apparent_temperature",
        "Temperature": "temperature_2m",
        "Relative Humidity": "relativehumidity_2m",
        "Wind Speed": "windspeed_10m",
        "Precipitation": "precipitation",
        "Demand Only Baseline": "__demand_only__",
    }

    available_target_dates = get_forecast_target_dates(df, min_history_days=5)
    if not available_target_dates:
        st.warning("At least 6 filtered dates are needed to run the forecasting backtest.")
        return

    control_col1, control_col2, control_col3 = st.columns([1.2, 1, 1])
    with control_col1:
        target_date = st.selectbox(
            "Target date to forecast",
            options=available_target_dates,
            format_func=lambda date_value: date_value.strftime("%d %b %Y"),
            index=len(available_target_dates) - 1,
            key="forecast_target_date",
        )
    with control_col2:
        lookback_days = st.slider(
            "Lookback days",
            min_value=5,
            max_value=min(14, len(sorted(df["date"].dt.date.unique())) - 1),
            value=min(7, len(sorted(df["date"].dt.date.unique())) - 1),
            step=1,
            key="forecast_lookback_days",
        )
    with control_col3:
        selected_weather_label = st.selectbox(
            "Weather signal",
            options=list(weather_options.keys()),
            index=0,
            key="forecast_weather_signal",
        )

    weather_col = weather_options[selected_weather_label]
    actual_weather_col = None if weather_col == "__demand_only__" else weather_col
    artifacts = build_intraday_forecast(
        df,
        target_date=target_date,
        weather_col=actual_weather_col or "__no_weather__",
        lookback_days=lookback_days,
    )

    if artifacts is None or artifacts.profile.empty:
        st.warning("Forecast could not be built for the selected date and lookback window.")
        return

    summary = artifacts.summary
    profile_df = artifacts.profile

    kpi_cols = st.columns(5)
    kpi_cols[0].metric("Forecast Peak", f"{summary['forecast_peak_mw']:,.0f} MW", summary["forecast_peak_time"])
    kpi_cols[1].metric("Actual Peak", f"{summary['actual_peak_mw']:,.0f} MW", summary["actual_peak_time"])
    kpi_cols[2].metric("Forecast Energy", f"{summary['forecast_energy_gwh']:.2f} GWh")
    kpi_cols[3].metric("MAE", f"{summary['mae_mw']:,.0f} MW")
    kpi_cols[4].metric("MAPE", f"{summary['mape'] * 100:.1f}%" if summary["mape"] == summary["mape"] else "NA")

    st.success(summarize_forecast(summary))
    st.caption(
        "How to read this: the blue line is the forecast, the orange dotted line is the actual selected day, "
        "and the shaded band is the model's operating confidence range."
    )

    fig_forecast = plot_forecast_profile(profile_df)
    if fig_forecast:
        st.plotly_chart(fig_forecast, use_container_width=True)
    else:
        st.warning("Could not build the 96-block forecast chart.")

    context_col1, context_col2 = st.columns(2)
    with context_col1:
        fig_context = plot_forecast_daily_context(artifacts.recent_daily, summary)
        if fig_context:
            st.plotly_chart(fig_context, use_container_width=True)
        else:
            st.warning("Could not build the recent peak context chart.")

    with context_col2:
        if actual_weather_col:
            fig_weather_adjustment = plot_forecast_weather_adjustment(profile_df, actual_weather_col)
            if fig_weather_adjustment:
                st.plotly_chart(fig_weather_adjustment, use_container_width=True)
            else:
                st.warning("Could not build the weather contribution chart.")
        else:
            st.info("Demand-only baseline is selected, so no weather adjustment chart is shown.")

    st.subheader("Operational Notes")
    for risk_flag in summary["risk_flags"]:
        st.warning(risk_flag)

    with st.expander("Forecast mathematics", expanded=False):
        if actual_weather_col:
            st.markdown(
                f"""
                For each block `b`, we build a same-block baseline from the previous `{summary['lookback_days']}` days:

                `baseline_b = mean(demand_b over lookback days)`

                `beta_b = cov(weather_b, demand_b) / var(weather_b)`

                `forecast_b = baseline_b + beta_b * (target_weather_b - mean(weather_b))`

                The weather term uses **{weather_label(actual_weather_col)}**. Confidence bands are built from recent block-level residual spread.
                """
            )
        else:
            st.markdown(
                f"""
                For each block `b`, we use the mean of the same block across the previous `{summary['lookback_days']}` days:

                `forecast_b = mean(demand_b over lookback days)`

                Confidence bands are built from recent block-level variability.
                """
            )

    st.subheader("Block-Level Forecast Table")
    display_columns = [
        "block_no",
        "time",
        "forecast_demand",
        "forecast_lower",
        "forecast_upper",
        "demand_energy",
        "demand_mean",
        "weather_adjustment",
    ]
    if actual_weather_col and actual_weather_col in profile_df.columns:
        display_columns.extend([actual_weather_col, "weather_mean", "weather_beta"])
    st.dataframe(profile_df[display_columns], use_container_width=True, hide_index=True)


def render_agent_chat():
    st.header("SCADA Agent Chat")
    st.markdown(
        "Ask questions about the currently selected sample SCADA and weather dataset. "
        "This chat does not access live SCADA systems or private databases."
    )

    df = st.session_state.get("filtered_df")
    if df is None or df.empty:
        st.info("Please select a valid date range containing data before using Agent Chat.")
        return

    weather_df = get_merged_scada_weather()
    if not weather_df.empty:
        start_date = st.session_state.get("start_date")
        end_date = st.session_state.get("end_date")
        if start_date and end_date:
            weather_df = filter_data_by_date(weather_df, start_date, end_date)
        if st.session_state.get("exclude_weekends", False) and "is_weekend" in weather_df.columns:
            weather_df = weather_df[~weather_df["is_weekend"]]
        if st.session_state.get("exclude_holidays", False) and "is_holiday" in weather_df.columns:
            weather_df = weather_df[~weather_df["is_holiday"]]
        if st.session_state.get("exclude_events", False) and "is_special_event" in weather_df.columns:
            weather_df = weather_df[~weather_df["is_special_event"]]
        if not weather_df.empty:
            df = weather_df

    if not is_agent_chat_configured():
        st.warning("Agent Chat is not configured. Add GOOGLE_API_KEY in Streamlit secrets to enable it.")
        return

    if is_langsmith_configured():
        st.caption("Observability: LangSmith tracing is enabled for Agent Chat.")
    else:
        st.caption("Observability: LangSmith tracing is not configured.")

    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button {
            min-height: 2rem;
            padding: 0.15rem 0.45rem;
            border-radius: 999px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "Example questions: "
        "`Did temperature affect peak demand?`  "
        "`Give intraday weather-demand analysis for 26 Nov.`  "
        "`Which day had the highest temperature and demand?`  "
        "`Compare 1 Nov and 26 Nov with weather.`"
    )

    if "agent_messages" not in st.session_state:
        st.session_state["agent_messages"] = [
            {
                "role": "assistant",
                "content": (
                    "Ask me about demand peaks, regional contribution, generation mix, ramps, anomalies, "
                    "or weather-demand relationships in the selected public sample data."
                ),
            }
        ]

    for message in st.session_state["agent_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    latest_assistant_message = next(
        (message for message in reversed(st.session_state["agent_messages"]) if message["role"] == "assistant"),
        None,
    )
    if latest_assistant_message and is_langsmith_configured():
        latest_trace_id = latest_assistant_message.get("trace_id")
        latest_feedback_key = f"feedback_submitted_{latest_trace_id}"
        if latest_trace_id:
            if st.session_state.get(latest_feedback_key):
                st.caption("Feedback recorded for the latest response.")
            else:
                col1, col2, col3, col4 = st.columns([0.7, 0.7, 0.7, 8])
                with col1:
                    helpful_clicked = st.button("\U0001F44D", key=f"latest_feedback_up_{latest_trace_id}", help="Helpful")
                with col2:
                    not_helpful_clicked = st.button("\U0001F44E", key=f"latest_feedback_down_{latest_trace_id}", help="Not helpful")
                with col3:
                    with st.popover("\u22EF", help="Optional comment"):
                        st.text_input(
                            "Add a short note",
                            key=f"latest_feedback_comment_{latest_trace_id}",
                            label_visibility="collapsed",
                            placeholder="What was good or missing?",
                        )
                        st.caption("Optional comment is used on the next feedback click.")

                latest_comment = st.session_state.get(f"latest_feedback_comment_{latest_trace_id}", "")
                if helpful_clicked or not_helpful_clicked:
                    latest_score = 1.0 if helpful_clicked else 0.0
                    latest_status = submit_langsmith_feedback(latest_trace_id, latest_score, latest_comment)
                    if latest_status == "Feedback submitted to LangSmith.":
                        st.session_state[latest_feedback_key] = True
                        st.rerun()
                    else:
                        st.warning(latest_status)

    prompt = st.chat_input("Ask about the selected SCADA sample data...")
    if not prompt:
        return

    st.session_state["agent_messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    trace_metadata = {
        "page": "Agent Chat",
        "start_date": str(st.session_state.get("start_date", "")),
        "end_date": str(st.session_state.get("end_date", "")),
        "exclude_weekends": bool(st.session_state.get("exclude_weekends", False)),
        "exclude_holidays": bool(st.session_state.get("exclude_holidays", False)),
        "exclude_events": bool(st.session_state.get("exclude_events", False)),
        "selected_weather_variable": st.session_state.get("weather_variable", ""),
    }

    with st.chat_message("assistant"):
        with st.spinner("Analyzing selected SCADA and weather data..."):
            result = ask_scada_agent_with_trace(
                prompt,
                df,
                st.session_state["agent_messages"],
                trace_metadata=trace_metadata,
            )
        st.markdown(result["response"])

    st.session_state["agent_messages"].append(
        {
            "role": "assistant",
            "content": result["response"],
            "trace_id": result.get("trace_id"),
            "project": result.get("project"),
        }
    )
    st.rerun()

    latest_message = st.session_state["agent_messages"][-1]
    trace_id = latest_message.get("trace_id")
    feedback_key = f"feedback_submitted_{trace_id}"
    if trace_id and is_langsmith_configured():
        if st.session_state.get(feedback_key):
            st.caption("Feedback recorded for the latest response.")
        else:
            col1, col2, col3, col4, col5 = st.columns([0.7, 0.7, 0.7, 0.7, 8])
            with col1:
                copy_clicked = st.button("⧉", key=f"compact_feedback_copy_{trace_id}", help="Copy")
            with col2:
                helpful_clicked = st.button("👍", key=f"compact_feedback_up_{trace_id}", help="Helpful")
            with col3:
                not_helpful_clicked = st.button("👎", key=f"compact_feedback_down_{trace_id}", help="Not helpful")
            with col4:
                with st.popover("⋯", help="Optional comment"):
                    st.text_input(
                        "Add a short note",
                        key=f"compact_feedback_comment_{trace_id}",
                        label_visibility="collapsed",
                        placeholder="What was good or missing?",
                    )
                    st.caption("Optional comment is used on the next feedback click.")

            if copy_clicked:
                st.caption("Copy action is not wired yet. Use browser text selection for now.")

            comment = st.session_state.get(f"compact_feedback_comment_{trace_id}", "")
            if helpful_clicked or not_helpful_clicked:
                score = 1.0 if helpful_clicked else 0.0
                status = submit_langsmith_feedback(trace_id, score, comment)
                if status == "Feedback submitted to LangSmith.":
                    st.session_state[feedback_key] = True
                    st.caption("Feedback submitted.")
                else:
                    st.warning(status)
        return

    if trace_id and is_langsmith_configured():
        if st.session_state.get(feedback_key):
            st.caption("Feedback recorded for the latest response.")
        else:
            st.caption("Rate the latest response")
            col1, col2, col3 = st.columns([1, 1, 6])
            with col1:
                helpful_clicked = st.button("👍", key=f"feedback_up_{trace_id}", help="Helpful")
            with col2:
                not_helpful_clicked = st.button("👎", key=f"feedback_down_{trace_id}", help="Not helpful")

            comment = ""
            with st.expander("Optional comment", expanded=False):
                comment = st.text_input(
                    "Add a short note",
                    key=f"feedback_comment_{trace_id}",
                    label_visibility="collapsed",
                    placeholder="What was good or missing?",
                )

            if helpful_clicked or not_helpful_clicked:
                score = 1.0 if helpful_clicked else 0.0
                status = submit_langsmith_feedback(trace_id, score, comment)
                if status == "Feedback submitted to LangSmith.":
                    st.session_state[feedback_key] = True
                    st.success("Feedback submitted.")
                else:
                    st.warning(status)


if __name__ == "__main__":
    main()
