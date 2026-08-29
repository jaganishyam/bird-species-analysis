"""
Bird Species Observation Analysis - Streamlit Dashboard
=========================================================
Interactive exploration of NPS bird-monitoring observations across
Forest and Grassland habitats: temporal trends, spatial patterns, species
diversity, environmental correlations, distance & behavior, observer
trends, and conservation (watchlist) insights.

Every chart in this app is an interactive, rotatable/zoomable 3D Plotly
visualization (3D bar charts, a 3D scatter plot, a 3D surface, and 3D
ribbon lines), wrapped in a bird/nature-themed skin.

Data source: bird_monitoring.db (SQLite), produced by data_prep.py from
the two raw workbooks (Bird_Monitoring_Data_FOREST.XLSX /
Bird_Monitoring_Data_GRASSLAND.XLSX).
"""

import sqlite3
from pathlib import Path

import pandas as pd
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
# Palette - fixed categorical order (identity, not rank), nature-themed
# assignment: Forest = leaf green, Grassland = sunlit gold.
# ---------------------------------------------------------------------------
SLOT = {
    "blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100",
    "magenta": "#e87ba4", "green": "#008300", "violet": "#4a3aa7", "red": "#e34948",
}
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95", "#0d366b"]
SEQUENTIAL_GREEN = ["#d7f0e2", "#a9e0c3", "#6cc79c", "#1baf7a", "#0d7f56", "#075939"]
MUTED_INK = "#7a6f5c"
GRID = "#e6dfd0"
PRIMARY_INK = "#2b2417"
SCENE_BG = "#fdfbf5"

HABITAT_COLORS = {"Forest": SLOT["aqua"], "Grassland": SLOT["yellow"]}
SEX_COLORS = {"Male": SLOT["blue"], "Female": SLOT["magenta"], "Undetermined": MUTED_INK}
FONT_STACK = "'Quicksand', 'Nunito Sans', system-ui, -apple-system, Segoe UI, sans-serif"

# ---------------------------------------------------------------------------
# Bird / nature theme (CSS)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@500;600;700&family=Nunito+Sans:wght@400;600&display=swap');

    html, body, [class*="css"] { font-family: 'Nunito Sans', system-ui, sans-serif; }
    h1, h2, h3, h4 { font-family: 'Quicksand', sans-serif !important; font-weight: 700 !important; }

    .stApp { background: linear-gradient(180deg, #eaf4ee 0%, #faf7ef 320px, #faf7ef 100%); }

    /* Hero banner */
    .bird-hero {
        background: linear-gradient(120deg, #dcefe3 0%, #eaf4ee 55%, #fbf1d9 100%);
        border-radius: 22px;
        padding: 28px 34px;
        margin-bottom: 18px;
        border: 1px solid #d8ead9;
        box-shadow: 0 6px 20px rgba(43, 36, 23, 0.06);
        position: relative;
        overflow: hidden;
    }
    .bird-hero h1 {
        margin: 0 0 6px 0;
        font-size: 2.1rem;
        color: #1f4d3a;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .bird-hero p { margin: 0; color: #5a5340; font-size: 1rem; max-width: 780px; }
    .bird-hero .flock { position: absolute; right: 26px; top: 18px; font-size: 1.6rem; opacity: 0.55; letter-spacing: 10px; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #eef6ee 0%, #f6f1e2 100%);
        border-right: 1px solid #dfe6d8;
    }
    section[data-testid="stSidebar"] h1 { color: #1f4d3a; }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e6e0cc;
        border-left: 5px solid #1baf7a;
        border-radius: 14px;
        padding: 12px 16px 8px 16px;
        box-shadow: 0 2px 8px rgba(43, 36, 23, 0.05);
    }
    div[data-testid="stMetricLabel"] { color: #6b6350; }

    .section-caption {
        color: #7a7256; font-size: 0.85rem; margin-top: -8px; margin-bottom: 10px;
    }
    hr { border-color: #e6e0cc !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# 3D chart helpers
# ---------------------------------------------------------------------------
# Standard 12-triangle / 6-face cube index set (Plotly Mesh3d cube recipe),
# reused for every 3D bar so each bar is a solid, lit, hoverable cuboid.
_CUBE_I = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
_CUBE_J = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
_CUBE_K = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]


def _cuboid(x0, x1, y0, y1, z0, z1, color, opacity=0.93):
    xs = [x0, x0, x1, x1, x0, x0, x1, x1]
    ys = [y0, y1, y1, y0, y0, y1, y1, y0]
    zs = [z0, z0, z0, z0, z1, z1, z1, z1]
    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=_CUBE_I, j=_CUBE_J, k=_CUBE_K,
        color=color, opacity=opacity, flatshading=True, hoverinfo="skip",
        lighting=dict(ambient=0.6, diffuse=0.55, specular=0.3, roughness=0.85, fresnel=0.15),
        lightposition=dict(x=120, y=200, z=300),
    )


def _scene_axis(title, tickvals=None, ticktext=None, visible=True):
    ax = dict(
        title=dict(text=title, font=dict(size=11, color=MUTED_INK)),
        backgroundcolor=SCENE_BG, gridcolor=GRID, zerolinecolor=GRID,
        tickfont=dict(color=MUTED_INK, size=10), showspikes=False, visible=visible,
    )
    if tickvals is not None:
        ax["tickmode"] = "array"
        ax["tickvals"] = tickvals
        ax["ticktext"] = ticktext
    return ax


def _base_scene_layout(fig, height, camera, aspect, legend=False):
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=30, b=0),
        template="plotly_white",
        paper_bgcolor="#fdfbf5",
        font=dict(color=PRIMARY_INK, family=FONT_STACK),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=0.02, xanchor="left", x=0.01,
                     bgcolor="rgba(255,255,255,0.7)") if legend else None,
        scene=dict(camera=camera, aspectmode="manual", aspectratio=aspect, **fig.layout.scene.to_plotly_json()
                   if fig.layout.scene else {}),
    )
    return fig


def bar3d(categories, values, color=SLOT["aqua"], height=420, x_title="", z_title="Observations",
           max_bars=15, color_map=None):
    """Single-series 3D bar chart: one lit cuboid per category, hover markers at each bar top.

    Pass `color_map` (dict of category -> hex color) instead of `color` to give each bar its
    own identity color (e.g. habitat or sex) while keeping hover markers in sync.
    """
    categories = list(categories)[:max_bars]
    values = list(values)[:max_bars]
    n = max(len(categories), 1)
    colors = [color_map.get(c, color) for c in categories] if color_map else [color] * n
    fig = go.Figure()
    for idx, v in enumerate(values):
        fig.add_trace(_cuboid(idx - 0.32, idx + 0.32, -0.32, 0.32, 0, max(v, 0.0001), colors[idx]))
    bump = (max(values) * 0.015 if values else 0.1)
    fig.add_trace(go.Scatter3d(
        x=list(range(n)), y=[0] * n, z=[v + bump for v in values],
        mode="markers", marker=dict(size=5, color=colors, line=dict(color="white", width=1)),
        hovertext=[f"<b>{c}</b><br>{z_title}: {v:,.0f}" for c, v in zip(categories, values)],
        hoverinfo="text", showlegend=False,
    ))
    fig.update_layout(scene=dict(
        xaxis=_scene_axis(x_title, tickvals=list(range(n)), ticktext=categories),
        yaxis=_scene_axis("", visible=False),
        zaxis=_scene_axis(z_title),
    ))
    camera = dict(eye=dict(x=1.65, y=-1.95, z=1.05))
    aspect = dict(x=min(3.0, max(1.3, n * 0.17)), y=0.55, z=0.9)
    return _base_scene_layout(fig, height, camera, aspect)


def bar3d_grouped(x_categories, group_categories, value_lookup, colors, height=460,
                   x_title="", z_title="Observations", bar_size=0.55, gap=0.35):
    """Two-dimension 3D bar chart: category on x, group (e.g. Habitat) on y-depth, value on z."""
    x_categories = list(x_categories)
    fig = go.Figure()
    y_positions = [gi * (bar_size + gap) for gi in range(len(group_categories))]
    for gi, g in enumerate(group_categories):
        color = colors.get(g, SLOT["blue"])
        yc = y_positions[gi]
        xs_hover, zs_hover, texts = [], [], []
        for xi, xc in enumerate(x_categories):
            val = value_lookup.get((xc, g), 0)
            if val <= 0:
                continue
            fig.add_trace(_cuboid(xi - bar_size / 2, xi + bar_size / 2,
                                   yc - bar_size / 2, yc + bar_size / 2, 0, val, color))
            xs_hover.append(xi)
            zs_hover.append(val * 1.03)
            texts.append(f"<b>{xc}</b><br>{g}: {val:,.0f}")
        fig.add_trace(go.Scatter3d(
            x=xs_hover, y=[yc] * len(xs_hover), z=zs_hover, mode="markers",
            marker=dict(size=5, color=color, line=dict(color="white", width=1)),
            hovertext=texts, hoverinfo="text", name=g, showlegend=True,
        ))
    fig.update_layout(scene=dict(
        xaxis=_scene_axis(x_title, tickvals=list(range(len(x_categories))), ticktext=x_categories),
        yaxis=_scene_axis("", tickvals=y_positions, ticktext=group_categories),
        zaxis=_scene_axis(z_title),
    ))
    camera = dict(eye=dict(x=1.7, y=-1.9, z=1.05))
    aspect = dict(x=min(3.0, max(1.3, len(x_categories) * 0.18)), y=0.7, z=0.9)
    return _base_scene_layout(fig, height, camera, aspect, legend=True)


def ribbon3d(series: dict, x_labels, colors, height=440, x_title="", z_title="Observations"):
    """3D line/ribbon chart: one line+marker trace per series, offset along y so ribbons sit apart in space."""
    fig = go.Figure()
    y_positions = {name: i * 0.9 for i, name in enumerate(series.keys())}
    for name, values in series.items():
        yc = y_positions[name]
        fig.add_trace(go.Scatter3d(
            x=list(range(len(x_labels))), y=[yc] * len(x_labels), z=values,
            mode="lines+markers", line=dict(color=colors.get(name, SLOT["blue"]), width=6),
            marker=dict(size=4, color=colors.get(name, SLOT["blue"])),
            name=name, hovertext=[f"<b>{name}</b><br>{x_labels[i]}: {values[i]:,.0f}" for i in range(len(x_labels))],
            hoverinfo="text",
        ))
    fig.update_layout(scene=dict(
        xaxis=_scene_axis(x_title, tickvals=list(range(len(x_labels))), ticktext=x_labels),
        yaxis=_scene_axis("", tickvals=list(y_positions.values()), ticktext=list(y_positions.keys())),
        zaxis=_scene_axis(z_title),
    ))
    camera = dict(eye=dict(x=1.7, y=-1.7, z=0.95))
    aspect = dict(x=1.9, y=0.5, z=0.8)
    return _base_scene_layout(fig, height, camera, aspect, legend=True)


def surface3d(pivot_df, height=460, x_title="Month", y_title="Season", z_title="Observations",
              colorscale=SEQUENTIAL_GREEN):
    fig = go.Figure(data=[go.Surface(
        z=pivot_df.values, x=list(range(len(pivot_df.columns))), y=list(range(len(pivot_df.index))),
        colorscale=colorscale, showscale=True,
        colorbar=dict(title=z_title, thickness=14, len=0.7),
        hovertemplate=f"{x_title}: %{{x}}<br>{y_title}: %{{y}}<br>{z_title}: %{{z}}<extra></extra>",
        contours=dict(z=dict(show=True, usecolormap=True, project=dict(z=True))),
    )])
    fig.update_layout(scene=dict(
        xaxis=_scene_axis(x_title, tickvals=list(range(len(pivot_df.columns))), ticktext=list(pivot_df.columns)),
        yaxis=_scene_axis(y_title, tickvals=list(range(len(pivot_df.index))), ticktext=list(pivot_df.index)),
        zaxis=_scene_axis(z_title),
        camera=dict(eye=dict(x=1.6, y=-1.6, z=1.1)),
        aspectmode="manual", aspectratio=dict(x=1.6, y=1.0, z=0.7),
    ))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=30, b=0), template="plotly_white",
                       paper_bgcolor="#fdfbf5", font=dict(color=PRIMARY_INK, family=FONT_STACK))
    return fig


def scatter3d_chart(df_plot, x, y, z, color_col, color_map, height=520,
                     x_title=None, y_title=None, z_title=None, size_col=None):
    fig = go.Figure()
    for cat, sub in df_plot.groupby(color_col):
        marker = dict(
            size=(8 + 22 * (sub[size_col] / df_plot[size_col].max())) if size_col else 6,
            color=color_map.get(cat, SLOT["blue"]),
            opacity=0.82, line=dict(color="white", width=0.5),
        )
        fig.add_trace(go.Scatter3d(
            x=sub[x], y=sub[y], z=sub[z], mode="markers", marker=marker, name=str(cat),
            hovertext=[
                f"<b>{cat}</b><br>{x_title or x}: {a}<br>{y_title or y}: {b}<br>{z_title or z}: {c:,.0f}"
                for a, b, c in zip(sub[x], sub[y], sub[z])
            ],
            hoverinfo="text",
        ))
    fig.update_layout(scene=dict(
        xaxis=_scene_axis(x_title or x),
        yaxis=_scene_axis(y_title or y),
        zaxis=_scene_axis(z_title or z),
        camera=dict(eye=dict(x=1.6, y=-1.7, z=1.0)),
        aspectmode="cube",
    ))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=30, b=0), template="plotly_white",
                       paper_bgcolor="#fdfbf5", font=dict(color=PRIMARY_INK, family=FONT_STACK),
                       showlegend=True,
                       legend=dict(orientation="h", yanchor="bottom", y=0.02, xanchor="left", x=0.01,
                                   bgcolor="rgba(255,255,255,0.7)"))
    return fig


ROTATE_HINT = "🔄 *Drag to rotate, scroll to zoom, hover a bar/point for its exact value.*"

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
    "**About**\n\n🪶 Explore NPS bird-monitoring observations across Forest and "
    "Grassland plots: temporal & spatial patterns, species diversity, "
    "environmental correlations, and conservation insights — every chart is "
    "a rotatable 3D view."
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

st.markdown(
    """
    <div class="bird-hero">
        <div class="flock">🐦 🕊️ 🦅</div>
        <h1>🐦 Bird Species Observation Analysis</h1>
        <p>Distribution and diversity of bird species across Forest and Grassland
        habitats — temporal trends, spatial patterns, species &amp; environmental
        insights, and conservation priorities. Every chart below is a fully
        interactive 3D visualization.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if df.empty:
    st.warning("No observations match the current filter selection. Adjust the filters in the sidebar.")
    st.stop()

# ---------------------------------------------------------------------------
# Section navigation
# ---------------------------------------------------------------------------
# NOTE: each section below builds several 3D (WebGL) charts, and browsers cap
# the number of simultaneously-live WebGL contexts on one page (commonly
# ~16). Using st.tabs would render every tab's charts into the DOM at once
# and blow past that cap, silently blanking out charts. A segmented control
# instead only *builds* the charts for the one section the user has
# selected, so total concurrent WebGL contexts always stays small.
SECTIONS = [
    "🏠 Overview", "📅 Temporal", "🗺️ Spatial", "🐦 Species", "🌤️ Environment",
    "📏 Distance & Behavior", "🔭 Observers", "🛡️ Conservation", "🔎 Data Explorer",
]
section = st.segmented_control("Section", SECTIONS, default=SECTIONS[0],
                                 required=True, label_visibility="collapsed")
if not section:
    section = SECTIONS[0]
st.divider()

month_order = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"]

# ============================================================ OVERVIEW ====
if section == "🏠 Overview":
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
        st.subheader("🌲 Observations by Habitat")
        hab_counts = df["Habitat"].value_counts()
        fig = bar3d(hab_counts.index.tolist(), hab_counts.values.tolist(),
                     height=380, x_title="Habitat", color_map=HABITAT_COLORS)
        st.plotly_chart(fig, width="stretch", key="chart_1")
        st.markdown(f'<p class="section-caption">{ROTATE_HINT}</p>', unsafe_allow_html=True)

    with col2:
        st.subheader("🏆 Top 15 Most-Observed Species")
        top_sp = df["Common_Name"].value_counts().head(15)
        fig = bar3d(top_sp.index.tolist(), top_sp.values.tolist(), color=SLOT["aqua"],
                     height=440, x_title="Species", z_title="Observations")
        st.plotly_chart(fig, width="stretch", key="chart_2")

    st.subheader("📍 Observations by Administrative Unit & Habitat")
    admin_counts = df.groupby(["Admin_Unit_Code", "Habitat"]).size()
    lookup = admin_counts.to_dict()
    fig = bar3d_grouped(sorted(df["Admin_Unit_Code"].unique()), habitats, lookup, HABITAT_COLORS,
                          x_title="Admin Unit", height=420)
    st.plotly_chart(fig, width="stretch", key="chart_3")
    st.markdown(f'<p class="section-caption">{ROTATE_HINT}</p>', unsafe_allow_html=True)

# ============================================================ TEMPORAL ====
if section == "📅 Temporal":
    st.subheader("📈 Observations by Month (3D ribbon per habitat)")
    month_counts = df.groupby(["Month_Name", "Habitat"]).size().unstack(fill_value=0)
    month_counts = month_counts.reindex(month_order).fillna(0)
    series = {h: month_counts[h].tolist() for h in habitats if h in month_counts.columns}
    fig = ribbon3d(series, month_order, HABITAT_COLORS, x_title="Month")
    st.plotly_chart(fig, width="stretch", key="chart_4")
    st.markdown(f'<p class="section-caption">{ROTATE_HINT}</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🍂 Observations by Season")
        season_counts = df.groupby(["Season", "Habitat"]).size().to_dict()
        fig = bar3d_grouped(seasons_present, habitats, season_counts, HABITAT_COLORS,
                              x_title="Season", height=420)
        st.plotly_chart(fig, width="stretch", key="chart_5")

    with col2:
        st.subheader("⏰ Observations by Start Hour")
        hour_counts = df.groupby("Start_Hour").size().sort_index()
        fig = bar3d([str(int(h)) for h in hour_counts.index], hour_counts.values.tolist(),
                     color=SLOT["blue"], x_title="Hour of Day (24h)", max_bars=24, height=420)
        st.plotly_chart(fig, width="stretch", key="chart_6")

    st.subheader("⏱️ Observation Session Duration (minutes)")
    dur = df["Observation_Duration_Min"].dropna()
    bins = pd.cut(dur, bins=10)
    dur_counts = bins.value_counts().sort_index()
    fig = bar3d([f"{int(iv.left)}-{int(iv.right)}" for iv in dur_counts.index],
                 dur_counts.values.tolist(), color=SLOT["violet"], x_title="Duration bucket (min)", height=400)
    st.plotly_chart(fig, width="stretch", key="chart_7")

    st.subheader("🗓️ Month × Season Activity Surface")
    heat = df.groupby(["Month_Name", "Season"]).size().reset_index(name="Observations")
    heat["Month_Name"] = pd.Categorical(heat["Month_Name"], categories=month_order, ordered=True)
    pivot = heat.pivot(index="Season", columns="Month_Name", values="Observations").reindex(seasons_order).fillna(0)
    pivot = pivot.dropna(how="all", axis=1)
    fig = surface3d(pivot, x_title="Month", y_title="Season")
    st.plotly_chart(fig, width="stretch", key="chart_8")
    st.markdown(f'<p class="section-caption">{ROTATE_HINT}</p>', unsafe_allow_html=True)

# ============================================================= SPATIAL ====
if section == "🗺️ Spatial":
    st.subheader("🗺️ Administrative Unit Map")
    st.caption(
        "Marker position = approximate park centroid (not exact plot GPS, which "
        "isn't in the source data). Size = observation count, color = habitat mix. "
        "Map is tilted for a 3D perspective — drag to rotate/pan."
    )
    if not loc_df.empty:
        admin_summary = df.groupby("Admin_Unit_Code").agg(
            Observations=("Common_Name", "size"),
            Species=("Common_Name", "nunique"),
        ).reset_index()
        hab_share = df.groupby(["Admin_Unit_Code", "Habitat"]).size().unstack(fill_value=0)
        if "Forest" in hab_share and "Grassland" in hab_share:
            hab_share["Pct_Forest"] = hab_share["Forest"] / (hab_share["Forest"] + hab_share["Grassland"]).replace(0, 1) * 100
        else:
            hab_share["Pct_Forest"] = 100 if "Forest" in hab_share else 0
        admin_summary = admin_summary.merge(loc_df, on="Admin_Unit_Code", how="left")
        admin_summary = admin_summary.merge(hab_share[["Pct_Forest"]], on="Admin_Unit_Code", how="left")
        admin_summary = admin_summary.dropna(subset=["Latitude", "Longitude"])

        fig = go.Figure(go.Scattermap(
            lat=admin_summary["Latitude"], lon=admin_summary["Longitude"],
            mode="markers",
            marker=dict(
                size=(admin_summary["Observations"] / admin_summary["Observations"].max() * 38 + 10),
                color=admin_summary["Pct_Forest"], colorscale=SEQUENTIAL_GREEN,
                showscale=True, colorbar=dict(title="% Forest", thickness=14),
            ),
            text=[f"<b>{n}</b> ({c})<br>{o:,} observations<br>{s} species"
                  for n, c, o, s in zip(admin_summary["Admin_Unit_Name"], admin_summary["Admin_Unit_Code"],
                                          admin_summary["Observations"], admin_summary["Species"])],
            hoverinfo="text",
        ))
        fig.update_layout(
            map=dict(style="open-street-map", zoom=6.3, pitch=55,
                      center=dict(lat=admin_summary["Latitude"].mean(), lon=admin_summary["Longitude"].mean())),
            height=480, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="#fdfbf5",
        )
        st.plotly_chart(fig, width="stretch", key="chart_9")
    else:
        st.info("Admin unit location lookup not found in the database.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🌳 Species Richness by Admin Unit")
        rich = df.groupby("Admin_Unit_Code")["Common_Name"].nunique().sort_values(ascending=False)
        fig = bar3d(rich.index.tolist(), rich.values.tolist(), color=SLOT["aqua"],
                     x_title="Admin Unit", z_title="Unique Species", height=420)
        st.plotly_chart(fig, width="stretch", key="chart_10")

    with col2:
        st.subheader("📌 Top 15 Plots by Observation Count")
        plot_counts = df["Plot_Name"].value_counts().head(15)
        fig = bar3d(plot_counts.index.tolist(), plot_counts.values.tolist(), color=SLOT["blue"],
                     x_title="Plot", height=420)
        st.plotly_chart(fig, width="stretch", key="chart_11")

# ============================================================= SPECIES ====
if section == "🐦 Species":
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🌿 Species Count by Habitat")
        sp_hab = df.groupby("Habitat")["Common_Name"].nunique()
        fig = bar3d(sp_hab.index.tolist(), sp_hab.values.tolist(),
                     x_title="Habitat", z_title="Unique Species", height=380, color_map=HABITAT_COLORS)
        st.plotly_chart(fig, width="stretch", key="chart_12")

    with col2:
        st.subheader("⚥ Sex Ratio")
        sex_counts = df["Sex"].value_counts()
        fig = bar3d(sex_counts.index.tolist(), sex_counts.values.tolist(),
                     x_title="Sex", height=380, color_map=SEX_COLORS)
        st.plotly_chart(fig, width="stretch", key="chart_13")

    st.subheader("🎧 Identification Method")
    id_counts = df["ID_Method"].value_counts()
    fig = bar3d(id_counts.index.tolist(), id_counts.values.tolist(), color=SLOT["violet"],
                 x_title="ID Method", height=380)
    st.plotly_chart(fig, width="stretch", key="chart_14")

    st.subheader("🔎 Species Explorer")
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
            by_admin = sp_df["Admin_Unit_Code"].value_counts()
            fig = bar3d(by_admin.index.tolist(), by_admin.values.tolist(), color=SLOT["blue"],
                         x_title="Admin Unit", height=340)
            st.plotly_chart(fig, width="stretch", key="chart_15")
        with colB:
            by_month = sp_df["Month_Name"].value_counts().reindex(month_order).fillna(0)
            by_month = by_month[by_month > 0]
            if len(by_month):
                fig = bar3d(by_month.index.tolist(), by_month.values.tolist(), color=SLOT["aqua"],
                             x_title="Month", height=340)
                st.plotly_chart(fig, width="stretch", key="chart_16")
            else:
                st.info("No monthly data for this species under the current filters.")

# ========================================================= ENVIRONMENT ====
if section == "🌤️ Environment":
    st.subheader("🌡️ Temperature × Humidity × Observation Volume")
    st.caption("Each point is one Temperature/Humidity combination; bubble size = observation count, colored by habitat.")
    env_agg = df.dropna(subset=["Temperature", "Humidity"]).copy()
    env_agg["Temp_Bucket"] = pd.cut(env_agg["Temperature"], bins=8).apply(lambda i: round(i.mid, 1))
    env_agg["Humidity_Bucket"] = pd.cut(env_agg["Humidity"], bins=8).apply(lambda i: round(i.mid, 1))
    env_grouped = env_agg.groupby(["Temp_Bucket", "Humidity_Bucket", "Habitat"]).size().reset_index(name="Observations")
    fig = scatter3d_chart(
        env_grouped, x="Temp_Bucket", y="Humidity_Bucket", z="Observations", color_col="Habitat",
        color_map=HABITAT_COLORS, size_col="Observations",
        x_title="Temperature (°F)", y_title="Humidity (%)", z_title="Observations",
    )
    st.plotly_chart(fig, width="stretch", key="chart_17")
    st.markdown(f'<p class="section-caption">{ROTATE_HINT}</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("☁️ Sky Condition")
        sky_counts = df["Sky"].value_counts()
        fig = bar3d(sky_counts.index.tolist(), sky_counts.values.tolist(), color=SLOT["blue"],
                     x_title="Sky", height=400)
        st.plotly_chart(fig, width="stretch", key="chart_18")

    with col2:
        st.subheader("🌬️ Wind Condition")
        wind_counts = df["Wind"].value_counts()
        fig = bar3d(wind_counts.index.tolist(), wind_counts.values.tolist(), color=SLOT["aqua"],
                     x_title="Wind", height=400)
        st.plotly_chart(fig, width="stretch", key="chart_19")

    st.subheader("⚠️ Disturbance Effect on Observations")
    dist_counts = df["Disturbance"].value_counts()
    fig = bar3d(dist_counts.index.tolist(), dist_counts.values.tolist(), color=SLOT["red"],
                 x_title="Disturbance", height=400)
    st.plotly_chart(fig, width="stretch", key="chart_20")

# =================================================== DISTANCE & BEHAVIOR ===
if section == "📏 Distance & Behavior":
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📏 Observation Distance from Observer")
        dcounts = df["Distance"].value_counts()
        fig = bar3d(dcounts.index.tolist(), dcounts.values.tolist(), color=SLOT["blue"],
                     x_title="Distance", height=400)
        st.plotly_chart(fig, width="stretch", key="chart_21")

    with col2:
        st.subheader("🦅 Flyover Observed")
        fly_counts = df["Flyover_Observed"].value_counts(dropna=False)
        labels = [{True: "Flyover", False: "Not a Flyover"}.get(k, "Unknown") for k in fly_counts.index]
        fig = bar3d(labels, fly_counts.values.tolist(), color=SLOT["red"], x_title="Flyover", height=400)
        st.plotly_chart(fig, width="stretch", key="chart_22")

    st.subheader("📐 Distance by Habitat")
    dist_hab = df.groupby(["Distance", "Habitat"]).size().to_dict()
    fig = bar3d_grouped(sorted(df["Distance"].unique()), habitats, dist_hab, HABITAT_COLORS,
                          x_title="Distance", height=420)
    st.plotly_chart(fig, width="stretch", key="chart_23")
    st.markdown(f'<p class="section-caption">{ROTATE_HINT}</p>', unsafe_allow_html=True)

# ============================================================ OBSERVERS ===
if section == "🔭 Observers":
    st.subheader("🔭 Observations by Observer")
    obs_counts = df["Observer"].value_counts()
    fig = bar3d(obs_counts.index.tolist(), obs_counts.values.tolist(), color=SLOT["blue"],
                 x_title="Observer", height=420, max_bars=20)
    st.plotly_chart(fig, width="stretch", key="chart_24")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🌈 Species Diversity per Observer")
        div = df.groupby("Observer")["Common_Name"].nunique().sort_values(ascending=False)
        fig = bar3d(div.index.tolist(), div.values.tolist(), color=SLOT["aqua"],
                     x_title="Observer", z_title="Unique Species", height=400, max_bars=20)
        st.plotly_chart(fig, width="stretch", key="chart_25")

    with col2:
        st.subheader("🔁 Visit Number vs. Species Count")
        visit_div = df.groupby("Visit")["Common_Name"].nunique().sort_index()
        fig = bar3d([str(int(v)) for v in visit_div.index], visit_div.values.tolist(), color=SLOT["violet"],
                     x_title="Visit #", z_title="Unique Species", height=400)
        st.plotly_chart(fig, width="stretch", key="chart_26")

# ========================================================= CONSERVATION ===
if section == "🛡️ Conservation":
    col1, col2, col3 = st.columns(3)
    watch_species = df.loc[df["PIF_Watchlist_Status"] == True, "Common_Name"].nunique()  # noqa: E712
    steward_species = df.loc[df["Regional_Stewardship_Status"] == True, "Common_Name"].nunique()  # noqa: E712
    col1.metric("Watchlist Species", watch_species)
    col2.metric("Regional Stewardship Species", steward_species)
    col3.metric("Watchlist Sightings", int((df["PIF_Watchlist_Status"] == True).sum()))  # noqa: E712

    watch_df = df[df["PIF_Watchlist_Status"] == True]  # noqa: E712
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🛡️ Top Watchlist Species by Sightings")
        if not watch_df.empty:
            wc = watch_df["Common_Name"].value_counts().head(15)
            fig = bar3d(wc.index.tolist(), wc.values.tolist(), color=SLOT["red"], x_title="Species", height=420)
            st.plotly_chart(fig, width="stretch", key="chart_27")
        else:
            st.info("No PIF Watchlist species in the current filter selection.")

    with col2:
        st.subheader("📍 Watchlist Sightings by Admin Unit & Habitat")
        if not watch_df.empty:
            wa = watch_df.groupby(["Admin_Unit_Code", "Habitat"]).size().to_dict()
            wa_units = sorted(watch_df["Admin_Unit_Code"].unique())
            fig = bar3d_grouped(wa_units, habitats, wa, HABITAT_COLORS, x_title="Admin Unit", height=420)
            st.plotly_chart(fig, width="stretch", key="chart_28")
        else:
            st.info("No PIF Watchlist species in the current filter selection.")

    st.subheader("🔤 AOU Code Distribution (Top 20)")
    aou_counts = df["AOU_Code"].value_counts().head(20)
    fig = bar3d(aou_counts.index.tolist(), aou_counts.values.tolist(), color=SLOT["violet"],
                 x_title="AOU Code", height=440, max_bars=20)
    st.plotly_chart(fig, width="stretch", key="chart_29")

# ============================================================ EXPLORER ====
if section == "🔎 Data Explorer":
    st.subheader("Filtered Observation Records")
    st.caption(f"{len(df):,} rows match the current filters.")
    display_cols = [
        "Habitat", "Admin_Unit_Code", "Site_Name", "Plot_Name", "Date", "Season",
        "Start_Time", "End_Time", "Observer", "Visit", "Common_Name", "Scientific_Name",
        "Sex", "Distance", "ID_Method", "Flyover_Observed", "PIF_Watchlist_Status",
        "Temperature", "Humidity", "Sky", "Wind", "Disturbance",
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols], width="stretch", height=460)

    csv_bytes = df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered data as CSV", data=csv_bytes,
        file_name="bird_observations_filtered.csv", mime="text/csv",
    )
