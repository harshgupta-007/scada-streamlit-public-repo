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
    build_intraday_weather_summary,
    build_weather_kpis,
    build_weather_correlation_summary,
)
from utils.data_loader import DATA_FILE, filter_data_by_date, get_date_range, load_scada_data, get_merged_scada_weather
from utils.agent_chat import ask_scada_agent, is_agent_chat_configured
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
    st.sidebar.caption("Phase 1 public deployment uses sample data only.")
    st.sidebar.caption("Deferred features: " + ", ".join(DEFERRED_PAGES))

    return page


def main():
    st.title("SCADA System Intelligence Dashboard")
    st.markdown("Monitor and analyze SCADA demand patterns using the public sample dataset.")

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

    daily_tab, intraday_tab = st.tabs(["Daily Relationship", "Intraday Calendar"])

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

    prompt = st.chat_input("Ask about the selected SCADA sample data...")
    if not prompt:
        return

    st.session_state["agent_messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing selected SCADA and weather data..."):
            response = ask_scada_agent(prompt, df, st.session_state["agent_messages"])
        st.markdown(response)

    st.session_state["agent_messages"].append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
