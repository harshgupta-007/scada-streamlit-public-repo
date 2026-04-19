from pathlib import Path
from typing import Union

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR / "data" / "sample_scada.csv"
WEATHER_FILE = BASE_DIR / "data" / "mp_weather_96_blocks_nov_2025.csv"


@st.cache_data(ttl=3600)
def load_special_events() -> pd.DataFrame:
    """Phase 1 public deployment does not ship private event data."""
    return pd.DataFrame(columns=["date", "is_special_event", "event_description"])


@st.cache_data(ttl=3600)
def load_scada_data(filepath: Union[Path, str] = DATA_FILE) -> pd.DataFrame:
    """Load and preprocess the public sample SCADA dataset."""
    data_path = Path(filepath)
    if not data_path.exists():
        st.error(f"Data file not found at {data_path}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(data_path)

        if "date_int" in df.columns:
            df["date"] = pd.to_datetime(df["date_int"], format="%Y%m%d")
        elif "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        else:
            st.warning("Missing 'date' column in dataset.")
            return pd.DataFrame()

        column_mapping = {
            "block": "block_no",
            "MP_Demand": "demand_energy",
            "Total_Thermal_Gen_Ex_Auxillary": "thermal_gen",
            "Total_Hydel": "hydel_gen",
            "Raw_Frequency": "Raw_Freq",
        }
        df = df.rename(columns=column_mapping)

        if "Solar" in df.columns and "Wind" in df.columns:
            df["renewable_gen"] = df["Solar"] + df["Wind"]

        numeric_cols = ["demand_energy", "thermal_gen", "hydel_gen", "renewable_gen", "Raw_Freq"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["day_of_week"] = df["date"].dt.day_name()
        df["is_weekend"] = df["date"].dt.dayofweek >= 5

        try:
            import holidays

            in_holidays = holidays.India(years=df["date"].dt.year.unique())
            df["is_holiday"] = df["date"].dt.date.apply(lambda day: day in in_holidays)
        except Exception:
            df["is_holiday"] = False

        df_events = load_special_events()
        if not df_events.empty and "date" in df_events.columns:
            df = df.merge(df_events, on="date", how="left")
            df["is_special_event"] = df["is_special_event"].fillna(False)
            df["event_description"] = df["event_description"].fillna("")
        else:
            df["is_special_event"] = False
            df["event_description"] = ""

        return df
    except Exception as exc:
        st.error(f"Error loading SCADA data: {exc}")
        return pd.DataFrame()


def get_date_range(df: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    if df.empty or "date" not in df.columns:
        return pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-31")
    return df["date"].min(), df["date"].max()


def filter_data_by_date(df: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return df
    mask = (df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date)
    return df.loc[mask]


def get_daily_aggregations(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    agg_dict = {
        "demand_energy": "sum",
        "thermal_gen": "sum",
        "hydel_gen": "sum",
    }

    if "renewable_gen" in df.columns:
        agg_dict["renewable_gen"] = "sum"
    if "Raw_Freq" in df.columns:
        agg_dict["Raw_Freq"] = ["max", "min", "mean"]

    daily_df = df.groupby("date").agg(agg_dict).reset_index()

    if isinstance(daily_df.columns, pd.MultiIndex):
        daily_df.columns = ["_".join(col).strip("_") for col in daily_df.columns.values]
        daily_df = daily_df.rename(
            columns={
                "demand_energy_sum": "demand_energy",
                "thermal_gen_sum": "thermal_gen",
                "hydel_gen_sum": "hydel_gen",
                "renewable_gen_sum": "renewable_gen",
                "Raw_Freq_max": "frequency_max",
                "Raw_Freq_min": "frequency_min",
                "Raw_Freq_mean": "frequency_avg",
            }
        )

    daily_block_stats = df.groupby("date")["demand_energy"].agg(
        peak_demand="max",
        min_demand="min",
        avg_demand="mean",
    ).reset_index()

    return pd.merge(daily_df, daily_block_stats, on="date")


def get_intraday_profile(df: pd.DataFrame):
    if df.empty:
        return None
    return df.groupby("block_no")["demand_energy"].mean().reset_index()


@st.cache_data(ttl=3600)
def load_weather_mapping() -> pd.DataFrame:
    """Weather mapping is not required for the public CSV weather sample."""
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_weather_data(filepath: Union[Path, str] = WEATHER_FILE) -> pd.DataFrame:
    """Load and aggregate the public Open-Meteo 96-block weather sample."""
    weather_path = Path(filepath)
    if not weather_path.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(weather_path)
        required_cols = {
            "date",
            "block",
            "temperature_2m",
            "relativehumidity_2m",
            "windspeed_10m",
            "apparent_temperature",
            "precipitation",
        }
        if not required_cols.issubset(df.columns):
            return pd.DataFrame()

        df["date"] = pd.to_datetime(df["date"])
        df = df.rename(columns={"block": "block_no"})

        weather_cols = [
            "temperature_2m",
            "relativehumidity_2m",
            "windspeed_10m",
            "apparent_temperature",
            "precipitation",
        ]
        for col in weather_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.groupby(["date", "block_no"], as_index=False)[weather_cols].mean()
    except Exception as exc:
        st.warning(f"Could not load weather sample data: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_merged_scada_weather() -> pd.DataFrame:
    """Merge SCADA sample data with public Open-Meteo weather sample data."""
    df_scada = load_scada_data()
    df_weather = load_weather_data()

    if df_scada.empty or df_weather.empty:
        return pd.DataFrame()

    return df_scada.merge(df_weather, on=["date", "block_no"], how="left")
