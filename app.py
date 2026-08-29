"""
Bird Species Observation Analysis - Streamlit Dashboard
=========================================================
Interactive exploration of NPS bird-monitoring observations across
Forest and Grassland habitats: temporal trends, spatial/administrative-unit
patterns, species diversity, environmental correlations, distance &
behavior, observer trends, and conservation (watchlist) insights.

Data source: bird_monitoring.db (SQLite), produced by data_prep.py from
the two raw workbooks (Bird_Monitoring_Data_FOREST.XLSX /
Bird_Monitoring_Data_GRASSLAND.XLSX).
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Bird Species Observation Analysis",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bird_monitoring.db"
CSV_PATH = BASE_DIR / "data" / "cleaned_bird_data.csv"

# ---------------------------------------------------------------------------
# Palette (fixed categorical order - identity, not rank)
# ---------------------------------------------------------------------------
SLOT = {
    "blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100",
    "magenta": "#e87ba4", "green": "#008300", "violet": "#4a3aa7", "red": "#e34948",
}
CATEGORICAL_ORDER = [SLOT["blue"], SLOT["orange"], SLOT["aqua"], SLOT["yellow"],
                      SLOT["magenta"], SLOT["green"], SLOT["violet"], SLOT["red"]]
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95", "#0d366b"]
MUTED_INK = "#898781"
GRID = "#e1e0d9"
PRIMARY_INK = "#0b0b0b"

HABITAT_COLORS = {"Forest": SLOT["blue"], "Grassland": SLOT["orange"]}
SEX_COLORS = {"Male": SLOT["blue"], "Female": SLOT["orange"], "Undetermined": SLOT["aqua"]}
BOOL_COLORS = {True: SLOT["red"], False: MUTED_INK}

PLOTLY_TEMPLATE = "plotly_white"


def style_fig(fig, height=420, legend=True):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        font=dict(color=PRIMARY_INK, family="system-ui, -apple-system, Segoe UI, sans-serif"),
        plot_bgcolor="#fcfcfb",
        paper_bgcolor="#fcfcfb",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0) if legend else dict(),
        showlegend=legend,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=MUTED_INK))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, tickfont=dict(color=MUTED_INK))
    return fig


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading bird observation data...")
def load_data():
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            obs = pd.read_sql("SELECT * FROM bird_observations", conn)
            loc = pd.read_sql("SELECT * FROM admin_unit_locations", conn)
    elif CSV_PATH.exists():
        obs = pd.read_csv(CSV_PATH)
        loc = pd.DataFrame()
    else:
        st.error(
            "No data found. Run `python data_prep.py` first to generate "
            "`bird_monitoring.db` from the raw Excel files."
        )
        st.stop()

    obs["Date"] = pd.to_datetime(obs["Date"], errors="coerce")
    for c in ["Flyover_Observed", "PIF_Watchlist_Status", "Regional_Stewardship_Status"]:
        if c in obs.columns:
            obs[c] = obs[c].astype("boolean")
    return obs, loc


obs_df, loc_df = load_data()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.title("🐦 Filters")
st.sidebar.caption("Filters apply to every section of the dashboard.")

habitats = sorted(obs_df["Habitat"].dropna().unique())
sel_habitat = st.sidebar.multiselect("Habitat", habitats, default=habitats)

admin_units = sorted(obs_df["Admin_Unit_Code"].dropna().unique())
sel_admin = st.sidebar.multiselect("Admin Unit", admin_units, default=admin_units)

seasons_order = ["Spring", "Summer", "Fall", "Winter"]
seasons_present = [s for s in seasons_order if s in obs_df["Season"].unique()]
sel_season = st.sidebar.multiselect("Season", seasons_present, default=seasons_present)

years = sorted(obs_df["Year"].dropna().unique().tolist())
sel_year = st.sidebar.multiselect("Year", years, default=years)

species_options = sorted(obs_df["Common_Name"].dropna().unique())
sel_species = st.sidebar.multiselect(
    "Species (optional, leave empty = all)", species_options, default=[]
)

sex_options = sorted(obs_df["Sex"].dropna().unique())
sel_sex = st.sidebar.multiselect("Sex", sex_options, default=sex_options)

watchlist_only = st.sidebar.checkbox("PIF Watchlist species only", value=False)

st.sidebar.divider()
st.sidebar.markdown(
    "**About**\n\nExplore NPS bird-monitoring observations across Forest and "
    "Grassland plots: temporal & spatial patterns, species diversity, "
    "environmental correlations, and conservation insights."
)

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------
df = obs_df.copy()
if sel_habitat:
    df = df[df["Habitat"].isin(sel_habitat)]
if sel_admin:
    df = df[df["Admin_Unit_Code"].isin(sel_admin)]
if sel_season:
    df = df[df["Season"].isin(sel_season)]
if sel_year:
    df = df[df["Year"].isin(sel_year)]
if sel_species:
    df = df[df["Common_Name"].isin(sel_species)]
if sel_sex:
    df = df[df["Sex"].isin(sel_sex)]
if watchlist_only:
    df = df[df["PIF_Watchlist_Status"] == True]  # noqa: E712

st.title("Bird Species Observation Analysis")
st.caption(
    "Distribution and diversity of bird species across Forest and Grassland "
    "habitats — temporal trends, spatial patterns, species & environmental "
    "insights, and conservation priorities."
)

if df.empty:
    st.warning("No observations match the current filter selection. Adjust the filters in the sidebar.")
    st.stop()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
(
    tab_overview, tab_temporal, tab_spatial, tab_species, tab_env,
    tab_distance, tab_observer, tab_conservation, tab_explorer,
) = st.tabs([
    "🏠 Overview", "📅 Temporal", "🗺️ Spatial", "🐦 Species", "🌤️ Environment",
    "📏 Distance & Behavior", "🔭 Observers", "🛡️ Conservation", "🔎 Data Explorer",
])

# ============================================================ OVERVIEW ====
with tab_overview:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Observations", f"{len(df):,}")
    c2.metric("Unique Species", f"{df['Common_Name'].nunique():,}")
    c3.metric("Admin Units", f"{df['Admin_Unit_Code'].nunique()}")
    c4.metric("Observers", f"{df['Observer'].nunique()}")
    watch_n = int((df["PIF_Watchlist_Status"] == True).sum())  # noqa: E712
    c5.metric("Watchlist Sightings", f"{watch_n:,}")

    st.divider()
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Observations by Habitat")
        hab_counts = df["Habitat"].value_counts().reset_index()
        hab_counts.columns = ["Habitat", "Observations"]
        fig = px.pie(
            hab_counts, names="Habitat", values="Observations", hole=0.55,
            color="Habitat", color_discrete_map=HABITAT_COLORS,
        )
        fig.update_traces(textinfo="percent+label")
        st.plotly_chart(style_fig(fig, height=360), width='stretch')

    with col2:
        st.subheader("Top 15 Most-Observed Species")
        top_sp = df["Common_Name"].value_counts().head(15).reset_index()
        top_sp.columns = ["Common_Name", "Observations"]
        fig = px.bar(
            top_sp.sort_values("Observations"), x="Observations", y="Common_Name",
            orientation="h", color_discrete_sequence=[SLOT["blue"]],
        )
        st.plotly_chart(style_fig(fig, height=420, legend=False), width='stretch')

    st.subheader("Observations by Administrative Unit")
    admin_counts = df.groupby(["Admin_Unit_Code", "Habitat"]).size().reset_index(name="Observations")
    fig = px.bar(
        admin_counts, x="Admin_Unit_Code", y="Observations", color="Habitat",
        barmode="stack", color_discrete_map=HABITAT_COLORS,
    )
    st.plotly_chart(style_fig(fig, height=380), width='stretch')

# ============================================================ TEMPORAL ====
with tab_temporal:
    st.subheader("Seasonal & Monthly Trends")
    col1, col2 = st.columns(2)

    with col1:
        month_order = ["January", "February", "March", "April", "May", "June", "July",
                        "August", "September", "October", "November", "December"]
        month_counts = df.groupby(["Month_Name", "Habitat"]).size().reset_index(name="Observations")
        month_counts["Month_Name"] = pd.Categorical(month_counts["Month_Name"], categories=month_order, ordered=True)
        month_counts = month_counts.sort_values("Month_Name")
        fig = px.line(
            month_counts, x="Month_Name", y="Observations", color="Habitat",
            markers=True, color_discrete_map=HABITAT_COLORS,
        )
        fig.update_layout(title="Observations by Month")
        st.plotly_chart(style_fig(fig), width='stretch')

    with col2:
        season_counts = df.groupby(["Season", "Habitat"]).size().reset_index(name="Observations")
        season_counts["Season"] = pd.Categorical(season_counts["Season"], categories=seasons_order, ordered=True)
        season_counts = season_counts.sort_values("Season")
        fig = px.bar(
            season_counts, x="Season", y="Observations", color="Habitat",
            barmode="group", color_discrete_map=HABITAT_COLORS,
        )
        fig.update_layout(title="Observations by Season")
        st.plotly_chart(style_fig(fig), width='stretch')

    st.subheader("Observation Time Window")
    col1, col2 = st.columns(2)
    with col1:
        hour_counts = df.groupby("Start_Hour").size().reset_index(name="Observations")
        fig = px.bar(hour_counts, x="Start_Hour", y="Observations",
                      color_discrete_sequence=[SLOT["blue"]])
        fig.update_layout(title="Observations by Start Hour (24h)", xaxis_title="Hour of Day")
        st.plotly_chart(style_fig(fig, legend=False), width='stretch')

    with col2:
        fig = px.histogram(df, x="Observation_Duration_Min", nbins=20,
                            color_discrete_sequence=[SLOT["blue"]])
        fig.update_layout(title="Observation Session Duration (minutes)")
        st.plotly_chart(style_fig(fig, legend=False), width='stretch')

    st.subheader("Month × Season Activity Heatmap")
    heat = df.groupby(["Month_Name", "Season"]).size().reset_index(name="Observations")
    heat["Month_Name"] = pd.Categorical(heat["Month_Name"], categories=month_order, ordered=True)
    pivot = heat.pivot(index="Season", columns="Month_Name", values="Observations").reindex(seasons_order)
    fig = px.imshow(
        pivot, color_continuous_scale=SEQUENTIAL_BLUE, aspect="auto",
        labels=dict(color="Observations"),
    )
    st.plotly_chart(style_fig(fig, height=320, legend=False), width='stretch')

# ============================================================= SPATIAL ====
with tab_spatial:
    st.subheader("Administrative Unit Map")
    st.caption(
        "Marker position = approximate park centroid (not exact plot GPS, which "
        "isn't in the source data). Size = observation count, color = habitat mix."
    )
    if not loc_df.empty:
        admin_summary = df.groupby("Admin_Unit_Code").agg(
            Observations=("Common_Name", "size"),
            Species=("Common_Name", "nunique"),
        ).reset_index()
        hab_share = (
            df.groupby(["Admin_Unit_Code", "Habitat"]).size().unstack(fill_value=0)
        )
        if "Forest" in hab_share and "Grassland" in hab_share:
            hab_share["Pct_Forest"] = hab_share["Forest"] / (hab_share["Forest"] + hab_share["Grassland"]).replace(0, 1) * 100
        else:
            hab_share["Pct_Forest"] = 100 if "Forest" in hab_share else 0
        admin_summary = admin_summary.merge(loc_df, on="Admin_Unit_Code", how="left")
        admin_summary = admin_summary.merge(hab_share[["Pct_Forest"]], on="Admin_Unit_Code", how="left")
        admin_summary = admin_summary.dropna(subset=["Latitude", "Longitude"])

        fig = px.scatter_map(
            admin_summary, lat="Latitude", lon="Longitude", size="Observations",
            color="Pct_Forest", hover_name="Admin_Unit_Name",
            hover_data={"Admin_Unit_Code": True, "Observations": True, "Species": True,
                        "Latitude": False, "Longitude": False, "Pct_Forest": ":.0f"},
            color_continuous_scale=SEQUENTIAL_BLUE, size_max=40, zoom=6.3,
            map_style="open-street-map",
        )
        fig.update_layout(coloraxis_colorbar_title="% Forest")
        st.plotly_chart(style_fig(fig, height=480, legend=False), width='stretch')
    else:
        st.info("Admin unit location lookup not found in the database.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Species Richness by Admin Unit")
        rich = df.groupby("Admin_Unit_Code")["Common_Name"].nunique().reset_index(name="Unique Species")
        rich = rich.sort_values("Unique Species", ascending=True)
        fig = px.bar(rich, x="Unique Species", y="Admin_Unit_Code", orientation="h",
                      color_discrete_sequence=[SLOT["aqua"]])
        st.plotly_chart(style_fig(fig, legend=False), width='stretch')

    with col2:
        st.subheader("Top 15 Plots by Observation Count")
        plot_counts = df["Plot_Name"].value_counts().head(15).reset_index()
        plot_counts.columns = ["Plot_Name", "Observations"]
        fig = px.bar(plot_counts.sort_values("Observations"), x="Observations", y="Plot_Name",
                      orientation="h", color_discrete_sequence=[SLOT["blue"]])
        st.plotly_chart(style_fig(fig, legend=False), width='stretch')

# ============================================================= SPECIES ====
with tab_species:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Species Count by Habitat")
        sp_hab = df.groupby("Habitat")["Common_Name"].nunique().reset_index(name="Unique Species")
        fig = px.bar(sp_hab, x="Habitat", y="Unique Species", color="Habitat",
                      color_discrete_map=HABITAT_COLORS)
        st.plotly_chart(style_fig(fig, legend=False), width='stretch')

    with col2:
        st.subheader("Sex Ratio")
        sex_counts = df["Sex"].value_counts().reset_index()
        sex_counts.columns = ["Sex", "Observations"]
        fig = px.pie(sex_counts, names="Sex", values="Observations", hole=0.55,
                      color="Sex", color_discrete_map=SEX_COLORS)
        fig.update_traces(textinfo="percent+label")
        st.plotly_chart(style_fig(fig, legend=True), width='stretch')

    st.subheader("Identification Method")
    id_counts = df["ID_Method"].value_counts().reset_index()
    id_counts.columns = ["ID_Method", "Observations"]
    fig = px.bar(id_counts.sort_values("Observations"), x="Observations", y="ID_Method",
                  orientation="h", color_discrete_sequence=[SLOT["blue"]])
    st.plotly_chart(style_fig(fig, legend=False), width='stretch')

    st.subheader("Species Explorer")
    species_pick = st.selectbox("Choose a species to inspect", species_options, index=0)
    sp_df = df[df["Common_Name"] == species_pick]
    if not sp_df.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Observations", f"{len(sp_df):,}")
        c2.metric("Admin Units Seen In", f"{sp_df['Admin_Unit_Code'].nunique()}")
        c3.metric("Habitats", ", ".join(sorted(sp_df["Habitat"].unique())))
        c4.metric("On PIF Watchlist", "Yes" if (sp_df["PIF_Watchlist_Status"] == True).any() else "No")  # noqa: E712
        colA, colB = st.columns(2)
        with colA:
            by_admin = sp_df["Admin_Unit_Code"].value_counts().reset_index()
            by_admin.columns = ["Admin_Unit_Code", "Observations"]
            fig = px.bar(by_admin, x="Admin_Unit_Code", y="Observations",
                          color_discrete_sequence=[SLOT["blue"]])
            st.plotly_chart(style_fig(fig, height=320, legend=False), width='stretch')
        with colB:
            by_month = sp_df["Month_Name"].value_counts().reindex(month_order).fillna(0).reset_index()
            by_month.columns = ["Month_Name", "Observations"]
            fig = px.bar(by_month, x="Month_Name", y="Observations",
                          color_discrete_sequence=[SLOT["aqua"]])
            st.plotly_chart(style_fig(fig, height=320, legend=False), width='stretch')

# ========================================================= ENVIRONMENT ====
with tab_env:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Temperature vs. Observation Counts")
        temp_agg = df.groupby(pd.cut(df["Temperature"], bins=10)).size().reset_index(name="Observations")
        temp_agg["Temperature"] = temp_agg["Temperature"].astype(str)
        fig = px.bar(temp_agg, x="Temperature", y="Observations",
                      color_discrete_sequence=[SLOT["blue"]])
        fig.update_layout(xaxis_title="Temperature (°F) bucket")
        st.plotly_chart(style_fig(fig, legend=False), width='stretch')

    with col2:
        st.subheader("Humidity vs. Observation Counts")
        hum_agg = df.groupby(pd.cut(df["Humidity"], bins=10)).size().reset_index(name="Observations")
        hum_agg["Humidity"] = hum_agg["Humidity"].astype(str)
        fig = px.bar(hum_agg, x="Humidity", y="Observations",
                      color_discrete_sequence=[SLOT["orange"]])
        fig.update_layout(xaxis_title="Humidity (%) bucket")
        st.plotly_chart(style_fig(fig, legend=False), width='stretch')

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Sky Condition")
        sky_counts = df["Sky"].value_counts().reset_index()
        sky_counts.columns = ["Sky", "Observations"]
        fig = px.bar(sky_counts.sort_values("Observations"), x="Observations", y="Sky",
                      orientation="h", color_discrete_sequence=[SLOT["blue"]])
        st.plotly_chart(style_fig(fig, legend=False), width='stretch')

    with col2:
        st.subheader("Wind Condition")
        wind_counts = df["Wind"].value_counts().reset_index()
        wind_counts.columns = ["Wind", "Observations"]
        fig = px.bar(wind_counts.sort_values("Observations"), x="Observations", y="Wind",
                      orientation="h", color_discrete_sequence=[SLOT["aqua"]])
        st.plotly_chart(style_fig(fig, legend=False), width='stretch')

    st.subheader("Disturbance Effect on Observations")
    dist_counts = df["Disturbance"].value_counts().reset_index()
    dist_counts.columns = ["Disturbance", "Observations"]
    fig = px.bar(dist_counts.sort_values("Observations"), x="Observations", y="Disturbance",
                  orientation="h", color_discrete_sequence=[SLOT["blue"]])
    st.plotly_chart(style_fig(fig, legend=False), width='stretch')

# =================================================== DISTANCE & BEHAVIOR ===
with tab_distance:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Observation Distance from Observer")
        dist_order = df["Distance"].value_counts().index.tolist()
        dcounts = df["Distance"].value_counts().reset_index()
        dcounts.columns = ["Distance", "Observations"]
        fig = px.bar(dcounts.sort_values("Observations"), x="Observations", y="Distance",
                      orientation="h", color_discrete_sequence=[SLOT["blue"]])
        st.plotly_chart(style_fig(fig, legend=False), width='stretch')

    with col2:
        st.subheader("Flyover Observed")
        fly_counts = df["Flyover_Observed"].value_counts(dropna=False).reset_index()
        fly_counts.columns = ["Flyover_Observed", "Observations"]
        fly_counts["Flyover_Observed"] = fly_counts["Flyover_Observed"].map(
            {True: "Flyover", False: "Not a Flyover"}
        ).fillna("Unknown")
        fig = px.pie(fly_counts, names="Flyover_Observed", values="Observations", hole=0.55,
                      color_discrete_sequence=[SLOT["red"], MUTED_INK, "#c3c2b7"])
        fig.update_traces(textinfo="percent+label")
        st.plotly_chart(style_fig(fig), width='stretch')

    st.subheader("Distance by Habitat")
    dist_hab = df.groupby(["Distance", "Habitat"]).size().reset_index(name="Observations")
    fig = px.bar(dist_hab, x="Distance", y="Observations", color="Habitat",
                  barmode="group", color_discrete_map=HABITAT_COLORS,
                  category_orders={"Distance": dist_order})
    st.plotly_chart(style_fig(fig), width='stretch')

# ============================================================ OBSERVERS ===
with tab_observer:
    st.subheader("Observations by Observer")
    obs_counts = df["Observer"].value_counts().reset_index()
    obs_counts.columns = ["Observer", "Observations"]
    fig = px.bar(obs_counts.sort_values("Observations"), x="Observations", y="Observer",
                  orientation="h", color_discrete_sequence=[SLOT["blue"]])
    st.plotly_chart(style_fig(fig, height=max(320, 24 * len(obs_counts)), legend=False), width='stretch')

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Species Diversity per Observer")
        div = df.groupby("Observer")["Common_Name"].nunique().reset_index(name="Unique Species")
        div = div.sort_values("Unique Species", ascending=True)
        fig = px.bar(div, x="Unique Species", y="Observer", orientation="h",
                      color_discrete_sequence=[SLOT["aqua"]])
        st.plotly_chart(style_fig(fig, height=max(320, 22 * len(div)), legend=False), width='stretch')

    with col2:
        st.subheader("Visit Number vs. Species Count")
        visit_div = df.groupby("Visit")["Common_Name"].nunique().reset_index(name="Unique Species")
        fig = px.bar(visit_div, x="Visit", y="Unique Species",
                      color_discrete_sequence=[SLOT["blue"]])
        st.plotly_chart(style_fig(fig, legend=False), width='stretch')

# ========================================================= CONSERVATION ===
with tab_conservation:
    col1, col2, col3 = st.columns(3)
    watch_species = df.loc[df["PIF_Watchlist_Status"] == True, "Common_Name"].nunique()  # noqa: E712
    steward_species = df.loc[df["Regional_Stewardship_Status"] == True, "Common_Name"].nunique()  # noqa: E712
    col1.metric("Watchlist Species", watch_species)
    col2.metric("Regional Stewardship Species", steward_species)
    col3.metric("Watchlist Sightings", int((df["PIF_Watchlist_Status"] == True).sum()))  # noqa: E712

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top Watchlist Species by Sightings")
        watch_df = df[df["PIF_Watchlist_Status"] == True]  # noqa: E712
        if not watch_df.empty:
            wc = watch_df["Common_Name"].value_counts().head(15).reset_index()
            wc.columns = ["Common_Name", "Observations"]
            fig = px.bar(wc.sort_values("Observations"), x="Observations", y="Common_Name",
                          orientation="h", color_discrete_sequence=[SLOT["red"]])
            st.plotly_chart(style_fig(fig, legend=False), width='stretch')
        else:
            st.info("No PIF Watchlist species in the current filter selection.")

    with col2:
        st.subheader("Watchlist Sightings by Habitat & Admin Unit")
        if not watch_df.empty:
            wa = watch_df.groupby(["Admin_Unit_Code", "Habitat"]).size().reset_index(name="Observations")
            fig = px.bar(wa, x="Admin_Unit_Code", y="Observations", color="Habitat",
                          barmode="stack", color_discrete_map=HABITAT_COLORS)
            st.plotly_chart(style_fig(fig, legend=True), width='stretch')
        else:
            st.info("No PIF Watchlist species in the current filter selection.")

    st.subheader("AOU Code Distribution (Top 20)")
    aou_counts = df["AOU_Code"].value_counts().head(20).reset_index()
    aou_counts.columns = ["AOU_Code", "Observations"]
    fig = px.bar(aou_counts.sort_values("Observations"), x="Observations", y="AOU_Code",
                  orientation="h", color_discrete_sequence=[SLOT["violet"]])
    st.plotly_chart(style_fig(fig, legend=False), width='stretch')

# ============================================================ EXPLORER ====
with tab_explorer:
    st.subheader("Filtered Observation Records")
    st.caption(f"{len(df):,} rows match the current filters.")
    display_cols = [
        "Habitat", "Admin_Unit_Code", "Site_Name", "Plot_Name", "Date", "Season",
        "Start_Time", "End_Time", "Observer", "Visit", "Common_Name", "Scientific_Name",
        "Sex", "Distance", "ID_Method", "Flyover_Observed", "PIF_Watchlist_Status",
        "Temperature", "Humidity", "Sky", "Wind", "Disturbance",
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols], width='stretch', height=460)

    csv_bytes = df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered data as CSV", data=csv_bytes,
        file_name="bird_observations_filtered.csv", mime="text/csv",
    )
