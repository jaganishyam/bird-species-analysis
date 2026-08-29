"""
data_prep.py
=============
Bird Species Observation Analysis - Data Cleaning & Preprocessing

Reads every administrative-unit sheet from the two source workbooks
(Forest and Grassland monitoring data), reconciles the small schema
differences between them, cleans and standardizes the data, engineers a
handful of analysis-friendly columns, and writes two outputs:

  1. data/cleaned_bird_data.csv   - flat cleaned dataset (all habitats)
  2. bird_monitoring.db           - SQLite database with:
        - bird_observations   (the cleaned fact table)
        - admin_unit_locations (lookup table with approx. park centroids
                                 used for the map view in the Streamlit app)

Run:
    python data_prep.py

This only needs to be re-run when the source Excel files change - the
Streamlit app reads the generated CSV/SQLite outputs, not the raw
workbooks, so the dashboard stays fast.
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FOREST_PATH = DATA_DIR / "Bird_Monitoring_Data_FOREST.XLSX"
GRASSLAND_PATH = DATA_DIR / "Bird_Monitoring_Data_GRASSLAND.XLSX"

CSV_OUT = DATA_DIR / "cleaned_bird_data.csv"
DB_OUT = BASE_DIR / "bird_monitoring.db"

# --------------------------------------------------------------------------
# Reference lookup: approximate centroid coordinates for each NPS
# administrative unit represented in the data. These are approximate,
# publicly-known park locations (not exact plot-level GPS, which the
# source data does not include) - used only to place each unit on the
# overview map in the Streamlit app.
# --------------------------------------------------------------------------
ADMIN_UNIT_INFO = {
    "ANTI": ("Antietam National Battlefield", 39.4756, -77.7495),
    "CATO": ("Catoctin Mountain Park", 39.6455, -77.4491),
    "CHOH": ("Chesapeake & Ohio Canal National Historical Park", 39.0004, -77.2519),
    "GWMP": ("George Washington Memorial Parkway", 38.9300, -77.1150),
    "HAFE": ("Harpers Ferry National Historical Park", 39.3253, -77.7378),
    "MANA": ("Manassas National Battlefield Park", 38.8138, -77.5217),
    "MONO": ("Monocacy National Battlefield", 39.3765, -77.3944),
    "NACE": ("National Capital Parks-East", 38.8833, -76.9667),
    "PRWI": ("Prince William Forest Park", 38.5678, -77.3736),
    "ROCR": ("Rock Creek Park", 38.9556, -77.0522),
    "WOTR": ("Wolf Trap National Park for the Performing Arts", 38.9384, -77.2653),
}

BOOL_COLUMNS = [
    "Flyover_Observed",
    "PIF_Watchlist_Status",
    "Regional_Stewardship_Status",
    "Previously_Obs",
    "Initial_Three_Min_Cnt",
]

SEASON_MAP = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer",
    9: "Fall", 10: "Fall", 11: "Fall",
}


def load_workbook(path: Path, habitat: str) -> pd.DataFrame:
    """Load every admin-unit sheet from one workbook into a single frame."""
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    frames = []
    for sheet_name, df in sheets.items():
        df = df.copy()
        df["Source_Sheet"] = sheet_name
        df["Habitat"] = habitat
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True, sort=False)
    return combined


def reconcile_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Align the Forest/Grassland column differences into one schema."""
    df = df.copy()

    # Forest uses NPSTaxonCode, Grassland uses TaxonCode -> unify.
    if "NPSTaxonCode" in df.columns and "TaxonCode" in df.columns:
        df["Taxon_Code"] = df["NPSTaxonCode"].combine_first(df["TaxonCode"])
        df = df.drop(columns=["NPSTaxonCode", "TaxonCode"])
    elif "NPSTaxonCode" in df.columns:
        df = df.rename(columns={"NPSTaxonCode": "Taxon_Code"})
    elif "TaxonCode" in df.columns:
        df = df.rename(columns={"TaxonCode": "Taxon_Code"})

    # Forest has Site_Name, Grassland does not.
    if "Site_Name" not in df.columns:
        df["Site_Name"] = np.nan

    # Grassland has Previously_Obs, Forest does not.
    if "Previously_Obs" not in df.columns:
        df["Previously_Obs"] = np.nan

    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # --- strip whitespace on all object/string columns -------------------
    obj_cols = df.select_dtypes(include="object").columns
    for c in obj_cols:
        df[c] = df[c].apply(lambda v: v.strip() if isinstance(v, str) else v)

    # --- drop fully duplicate rows ---------------------------------------
    before = len(df)
    df = df.drop_duplicates()
    dupes_dropped = before - len(df)

    # --- standardize booleans ---------------------------------------------
    for c in BOOL_COLUMNS:
        if c in df.columns:
            df[c] = (
                df[c]
                .map({True: True, False: False, "TRUE": True, "FALSE": False,
                      "True": True, "False": False, 1: True, 0: False})
                .where(df[c].notna(), other=np.nan)
            )

    # --- Sex: fill missing with 'Undetermined' -----------------------------
    if "Sex" in df.columns:
        df["Sex"] = df["Sex"].fillna("Undetermined")
        df.loc[df["Sex"].astype(str).str.strip() == "", "Sex"] = "Undetermined"

    # --- Distance: fill missing with 'Not Recorded' ------------------------
    if "Distance" in df.columns:
        df["Distance"] = df["Distance"].fillna("Not Recorded")

    # --- numeric columns ----------------------------------------------------
    for c in ["Temperature", "Humidity", "Year", "Visit"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "Year" in df.columns:
        df["Year"] = df["Year"].astype("Int64")

    # --- Date / time parsing -------------------------------------------------
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    def to_time_string(v):
        if pd.isna(v):
            return None
        if hasattr(v, "hour"):
            return f"{v.hour:02d}:{v.minute:02d}"
        try:
            return pd.to_datetime(str(v)).strftime("%H:%M")
        except Exception:
            return None

    df["Start_Time"] = df["Start_Time"].apply(to_time_string)
    df["End_Time"] = df["End_Time"].apply(to_time_string)

    def duration_minutes(row):
        try:
            sh, sm = map(int, row["Start_Time"].split(":"))
            eh, em = map(int, row["End_Time"].split(":"))
            start = sh * 60 + sm
            end = eh * 60 + em
            if end < start:  # crossed midnight, rare but handle gracefully
                end += 24 * 60
            return end - start
        except Exception:
            return np.nan

    df["Observation_Duration_Min"] = df.apply(duration_minutes, axis=1)

    # --- engineered temporal features ---------------------------------------
    df["Month_Num"] = df["Date"].dt.month
    df["Month_Name"] = df["Date"].dt.strftime("%B")
    df["Day_Of_Week"] = df["Date"].dt.strftime("%A")
    df["Season"] = df["Month_Num"].map(SEASON_MAP)
    # Prefer the Year column when present/valid, else derive from Date
    df["Year"] = df["Year"].fillna(df["Date"].dt.year).astype("Int64")

    # Start hour, useful for "which time window sees more activity"
    def start_hour(v):
        if not v:
            return np.nan
        return int(v.split(":")[0])

    df["Start_Hour"] = df["Start_Time"].apply(start_hour)

    # --- habitat / admin unit standardization -------------------------------
    df["Location_Type"] = df["Location_Type"].fillna(df["Habitat"])
    df["Admin_Unit_Code"] = df["Admin_Unit_Code"].fillna(df["Source_Sheet"])

    # --- final column order ---------------------------------------------------
    preferred_order = [
        "Habitat", "Admin_Unit_Code", "Sub_Unit_Code", "Site_Name", "Plot_Name",
        "Location_Type", "Year", "Date", "Month_Name", "Month_Num", "Season",
        "Day_Of_Week", "Start_Time", "End_Time", "Observation_Duration_Min",
        "Start_Hour", "Observer", "Visit", "Interval_Length", "ID_Method",
        "Distance", "Flyover_Observed", "Sex", "Common_Name", "Scientific_Name",
        "AcceptedTSN", "Taxon_Code", "AOU_Code", "PIF_Watchlist_Status",
        "Regional_Stewardship_Status", "Temperature", "Humidity", "Sky", "Wind",
        "Disturbance", "Previously_Obs", "Initial_Three_Min_Cnt", "Source_Sheet",
    ]
    cols = [c for c in preferred_order if c in df.columns]
    remaining = [c for c in df.columns if c not in cols]
    df = df[cols + remaining]

    print(f"  dropped {dupes_dropped} exact duplicate rows")
    return df


def build_admin_unit_lookup() -> pd.DataFrame:
    rows = [
        {"Admin_Unit_Code": code, "Admin_Unit_Name": name, "Latitude": lat, "Longitude": lon}
        for code, (name, lat, lon) in ADMIN_UNIT_INFO.items()
    ]
    return pd.DataFrame(rows)


def main():
    print("Loading Forest workbook (all sheets)...")
    forest = load_workbook(FOREST_PATH, "Forest")
    print(f"  {len(forest):,} rows loaded")

    print("Loading Grassland workbook (all sheets)...")
    grassland = load_workbook(GRASSLAND_PATH, "Grassland")
    print(f"  {len(grassland):,} rows loaded")

    print("Reconciling schema differences between habitats...")
    forest = reconcile_schema(forest)
    grassland = reconcile_schema(grassland)

    combined = pd.concat([forest, grassland], ignore_index=True, sort=False)
    print(f"Combined raw rows: {len(combined):,}")

    print("Cleaning...")
    cleaned = clean(combined)
    print(f"Final cleaned rows: {len(cleaned):,}")

    missing_summary = cleaned.isna().sum()
    missing_summary = missing_summary[missing_summary > 0].sort_values(ascending=False)
    print("\nRemaining missing values by column:")
    print(missing_summary.to_string() if len(missing_summary) else "  (none)")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(CSV_OUT, index=False)
    print(f"\nWrote cleaned CSV -> {CSV_OUT}")

    lookup = build_admin_unit_lookup()

    print(f"Writing SQLite database -> {DB_OUT}")
    with sqlite3.connect(DB_OUT) as conn:
        cleaned.to_sql("bird_observations", conn, if_exists="replace", index=False)
        lookup.to_sql("admin_unit_locations", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_habitat ON bird_observations(Habitat)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_admin_unit ON bird_observations(Admin_Unit_Code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_year ON bird_observations(Year)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_species ON bird_observations(Common_Name)")

    print("\nDone. Summary:")
    print(f"  Total observations : {len(cleaned):,}")
    print(f"  Unique species      : {cleaned['Common_Name'].nunique():,}")
    print(f"  Admin units         : {cleaned['Admin_Unit_Code'].nunique()}")
    print(f"  Year range          : {cleaned['Year'].min()} - {cleaned['Year'].max()}")
    print(f"  Habitats             : {', '.join(sorted(cleaned['Habitat'].unique()))}")


if __name__ == "__main__":
    main()
