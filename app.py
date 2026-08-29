"""
Bird Species Observation Analysis - Streamlit Dashboard
=========================================================
Interactive exploration of NPS bird-monitoring observations across
Forest and Grassland habitats: temporal trends, spatial patterns, species
diversity, environmental correlations, distance & behavior, observer
trends, conservation (watchlist) insights, and actionable recommendations.

Chart variety by design: 3D bar/ribbon/surface/scatter where a third
dimension genuinely adds insight, plus donuts, treemaps, a sunburst, radar
and polar-bar charts, lollipop charts, an area chart, a violin plot, a
funnel, and a trend line elsewhere - not a wall of bar charts.

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
# Palette - fixed categorical identity, nature-themed: Forest = leaf green,
# Grassland = sunlit gold. A livelier teal/amber/coral accent set layers on
# top for the modern UI chrome (buttons, hero, cards).
# ---------------------------------------------------------------------------
SLOT = {
    "blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100",
    "magenta": "#e87ba4", "green": "#008300", "violet": "#4a3aa7", "red": "#e34948",
}
SEQUENTIAL_GREEN = ["#d7f0e2", "#a9e0c3", "#6cc79c", "#1baf7a", "#0d7f56", "#075939"]
MUTED_INK = "#6b6350"
GRID = "#e6dfd0"
PRIMARY_INK = "#20291f"
SCENE_BG = "#fbfaf4"
EDGE_COLOR = "rgba(32, 41, 31, 0.30)"

HABITAT_COLORS = {"Forest": SLOT["aqua"], "Grassland": SLOT["yellow"]}
SEX_COLORS = {"Male": SLOT["blue"], "Female": SLOT["magenta"], "Undetermined": MUTED_INK}
FONT_STACK = "'Plus Jakarta Sans', 'Nunito Sans', system-ui, -apple-system, Segoe UI, sans-serif"

# ---------------------------------------------------------------------------
# Modern bird / nature theme (CSS)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Nunito+Sans:wght@400;600&display=swap');

    html, body, [class*="css"] { font-family: 'Nunito Sans', system-ui, sans-serif; }
    h1, h2, h3, h4 { font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 700 !important; letter-spacing: -0.01em; }

    .stApp { background: radial-gradient(1200px 600px at 15% -10%, #e3f3e6 0%, transparent 60%),
                          radial-gradient(1000px 500px at 100% 0%, #fbf0d8 0%, transparent 55%),
                          #faf8f1; }

    /* ---------- Hero banner (glassmorphic, layered blobs) ---------- */
    .bird-hero {
        position: relative;
        background: linear-gradient(120deg, rgba(31,77,58,0.94) 0%, rgba(20,92,66,0.92) 45%, rgba(230,166,60,0.85) 130%);
        border-radius: 26px;
        padding: 34px 38px;
        margin-bottom: 22px;
        overflow: hidden;
        box-shadow: 0 18px 40px rgba(31, 77, 58, 0.22);
    }
    .bird-hero::before, .bird-hero::after {
        content: ""; position: absolute; border-radius: 50%; filter: blur(38px); opacity: 0.45;
    }
    .bird-hero::before { width: 260px; height: 260px; background: #ffd873; top: -110px; right: -60px; }
    .bird-hero::after { width: 220px; height: 220px; background: #7be6b8; bottom: -120px; left: 10%; }
    .bird-hero h1 {
        position: relative; margin: 0 0 8px 0; font-size: 2.15rem; color: #ffffff;
        display: flex; align-items: center; gap: 12px; text-shadow: 0 2px 12px rgba(0,0,0,0.15);
    }
    .bird-hero p { position: relative; margin: 0; color: rgba(255,255,255,0.92); font-size: 1.02rem; max-width: 760px; }
    .bird-hero .flock { position: absolute; right: 30px; top: 22px; font-size: 1.5rem; opacity: 0.5; letter-spacing: 10px; }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #eef6ee 0%, #f7f1e1 100%);
        border-right: 1px solid #e2ddc8;
    }
    section[data-testid="stSidebar"] h1 { color: #1f4d3a; }

    /* ---------- Metric cards ---------- */
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #ece5cf;
        border-left: 5px solid #1baf7a;
        border-radius: 16px;
        padding: 12px 16px 8px 16px;
        box-shadow: 0 3px 14px rgba(43, 36, 23, 0.06);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    div[data-testid="stMetric"]:hover { transform: translateY(-3px); box-shadow: 0 10px 22px rgba(43, 36, 23, 0.10); }
    div[data-testid="stMetricLabel"] { color: #7a7256; }

    /* ---------- Chart cards (bordered containers) ---------- */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 18px !important;
        border-color: #ece5cf !important;
        box-shadow: 0 4px 18px rgba(43, 36, 23, 0.05);
        background: #fffefb;
    }

    /* ---------- Nav buttons: modern pill grid ---------- */
    div[data-testid="column"] .stButton > button {
        border-radius: 999px !important;
        border: 1.5px solid #dfe6d8 !important;
        padding: 0.5rem 0.9rem !important;
        font-weight: 600 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
        box-shadow: 0 1px 3px rgba(43,36,23,0.05);
    }
    div[data-testid="column"] .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 18px rgba(31, 77, 58, 0.18);
        border-color: #1f4d3a !important;
    }
    div[data-testid="column"] .stButton > button[kind="primary"] {
        background: linear-gradient(120deg, #1f4d3a, #12805c) !important;
        border-color: transparent !important;
        box-shadow: 0 6px 16px rgba(18, 128, 92, 0.35) !important;
    }
    div[data-testid="column"] .stButton > button[kind="secondary"] {
        background: #ffffff !important;
        color: #4a4636 !important;
    }

    /* ---------- Recommendation cards ---------- */
    .insight-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-top: 6px; }
    .insight-card {
        background: linear-gradient(160deg, #ffffff 0%, #f6f8ef 100%);
        border: 1px solid #e6e0cc; border-radius: 18px; padding: 18px 20px;
        box-shadow: 0 4px 16px rgba(43,36,23,0.06);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .insight-card:hover { transform: translateY(-4px); box-shadow: 0 12px 26px rgba(31,77,58,0.14); }
    .insight-card .tag {
        display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.03em;
        text-transform: uppercase; color: #12805c; background: #e3f3e6; border-radius: 999px;
        padding: 3px 10px; margin-bottom: 10px;
    }
    .insight-card h4 { margin: 0 0 6px 0; font-size: 1.05rem; color: #1f4d3a; display:flex; align-items:center; gap:8px; }
    .insight-card p { margin: 0; color: #4a4636; font-size: 0.9rem; line-height: 1.45; }

    .section-caption { color: #8a8266; font-size: 0.85rem; margin-top: -6px; margin-bottom: 10px; }
    hr { border-color: #e6e0cc !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# 3D bar helpers - fully opaque + crisp dark edge outline so bars read as
# solid from every angle (no "hollow" look when rotated).
# ---------------------------------------------------------------------------
_CUBE_I = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
_CUBE_J = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
_CUBE_K = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]


def _cuboid_mesh(x0, x1, y0, y1, z0, z1, color):
    xs = [x0, x0, x1, x1, x0, x0, x1, x1]
    ys = [y0, y1, y1, y0, y0, y1, y1, y0]
    zs = [z0, z0, z0, z0, z1, z1, z1, z1]
    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=_CUBE_I, j=_CUBE_J, k=_CUBE_K,
        color=color, opacity=1.0, flatshading=True, hoverinfo="skip",
        lighting=dict(ambient=0.62, diffuse=0.55, specular=0.18, roughness=0.9, fresnel=0.02),
        lightposition=dict(x=120, y=200, z=300),
    )


def _cuboid_edges(x0, x1, y0, y1, z0, z1):
    corners = dict(
        b0=(x0, y0, z0), b1=(x1, y0, z0), b2=(x1, y1, z0), b3=(x0, y1, z0),
        t0=(x0, y0, z1), t1=(x1, y0, z1), t2=(x1, y1, z1), t3=(x0, y1, z1),
    )
    segs = [("b0", "b1"), ("b1", "b2"), ("b2", "b3"), ("b3", "b0"),
            ("t0", "t1"), ("t1", "t2"), ("t2", "t3"), ("t3", "t0"),
            ("b0", "t0"), ("b1", "t1"), ("b2", "t2"), ("b3", "t3")]
    xs, ys, zs = [], [], []
    for a, b in segs:
        xs += [corners[a][0], corners[b][0], None]
        ys += [corners[a][1], corners[b][1], None]
        zs += [corners[a][2], corners[b][2], None]
    return go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", line=dict(color=EDGE_COLOR, width=3),
                         hoverinfo="skip", showlegend=False)


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


def _figure_chrome(fig, height, legend=False):
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=30, b=0),
        template="plotly_white", paper_bgcolor="#fffefb", plot_bgcolor="#fffefb",
        font=dict(color=PRIMARY_INK, family=FONT_STACK),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0.0,
                     bgcolor="rgba(255,255,255,0)") if legend else None,
    )
    return fig


def bar3d(categories, values, color=SLOT["aqua"], height=440, x_title="", z_title="Observations",
           max_bars=15, color_map=None):
    """Single-series 3D bar chart: solid, edge-outlined cuboids with hover markers at each top."""
    categories = list(categories)[:max_bars]
    values = list(values)[:max_bars]
    n = max(len(categories), 1)
    colors = [color_map.get(c, color) for c in categories] if color_map else [color] * n
    fig = go.Figure()
    for idx, v in enumerate(values):
        x0, x1 = idx - 0.32, idx + 0.32
        y0, y1 = -0.32, 0.32
        z1 = max(v, 0.0001)
        fig.add_trace(_cuboid_mesh(x0, x1, y0, y1, 0, z1, colors[idx]))
        fig.add_trace(_cuboid_edges(x0, x1, y0, y1, 0, z1))
    bump = (max(values) * 0.02 if values else 0.1)
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
        camera=dict(eye=dict(x=1.65, y=-1.95, z=1.05)),
        aspectmode="manual", aspectratio=dict(x=min(3.0, max(1.3, n * 0.17)), y=0.55, z=0.9),
    ))
    return _figure_chrome(fig, height)


def ribbon3d(series: dict, x_labels, colors, height=440, x_title="", z_title="Observations"):
    fig = go.Figure()
    y_positions = {name: i * 0.9 for i, name in enumerate(series.keys())}
    for name, values in series.items():
        yc = y_positions[name]
        fig.add_trace(go.Scatter3d(
            x=list(range(len(x_labels))), y=[yc] * len(x_labels), z=values,
            mode="lines+markers", line=dict(color=colors.get(name, SLOT["blue"]), width=7),
            marker=dict(size=4, color=colors.get(name, SLOT["blue"])),
            name=name, hovertext=[f"<b>{name}</b><br>{x_labels[i]}: {values[i]:,.0f}" for i in range(len(x_labels))],
            hoverinfo="text",
        ))
    fig.update_layout(scene=dict(
        xaxis=_scene_axis(x_title, tickvals=list(range(len(x_labels))), ticktext=x_labels),
        yaxis=_scene_axis("", tickvals=list(y_positions.values()), ticktext=list(y_positions.keys())),
        zaxis=_scene_axis(z_title),
        camera=dict(eye=dict(x=1.7, y=-1.7, z=0.95)),
        aspectmode="manual", aspectratio=dict(x=1.9, y=0.5, z=0.8),
    ))
    return _figure_chrome(fig, height, legend=True)


def surface3d(pivot_df, height=460, x_title="", y_title="", z_title="Observations",
              colorscale=SEQUENTIAL_GREEN):
    fig = go.Figure(data=[go.Surface(
        z=pivot_df.values, x=list(range(len(pivot_df.columns))), y=list(range(len(pivot_df.index))),
        colorscale=colorscale, showscale=True, colorbar=dict(title=z_title, thickness=14, len=0.7),
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
    return _figure_chrome(fig, height)


def scatter3d_chart(df_plot, x, y, z, color_col, color_map, height=520,
                     x_title=None, y_title=None, z_title=None, size_col=None):
    fig = go.Figure()
    for cat, sub in df_plot.groupby(color_col):
        marker = dict(
            size=(8 + 22 * (sub[size_col] / df_plot[size_col].max())) if size_col else 6,
            color=color_map.get(cat, SLOT["blue"]), opacity=0.85, line=dict(color="white", width=0.5),
        )
        fig.add_trace(go.Scatter3d(
            x=sub[x], y=sub[y], z=sub[z], mode="markers", marker=marker, name=str(cat),
            hovertext=[f"<b>{cat}</b><br>{x_title or x}: {a}<br>{y_title or y}: {b}<br>{z_title or z}: {c:,.0f}"
                       for a, b, c in zip(sub[x], sub[y], sub[z])],
            hoverinfo="text",
        ))
    fig.update_layout(scene=dict(
        xaxis=_scene_axis(x_title or x), yaxis=_scene_axis(y_title or y), zaxis=_scene_axis(z_title or z),
        camera=dict(eye=dict(x=1.6, y=-1.7, z=1.0)), aspectmode="cube",
    ))
    return _figure_chrome(fig, height, legend=True)


# ---------------------------------------------------------------------------
# Non-bar 2D chart helpers (the "different charts" the app now leans on)
# ---------------------------------------------------------------------------
def donut_chart(labels, values, color_map=None, colors=None, height=380, center_label=None):
    labels = list(labels)
    values = list(values)
    if color_map:
        marker_colors = [color_map.get(lbl, SLOT["blue"]) for lbl in labels]
    elif colors:
        marker_colors = colors
    else:
        marker_colors = [SLOT["aqua"], SLOT["yellow"], SLOT["blue"], SLOT["magenta"], SLOT["violet"]][:len(labels)]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.62, marker=dict(colors=marker_colors, line=dict(color="#fffefb", width=2)),
        textinfo="percent", textfont=dict(color="#fffefb", size=13), sort=False,
        hovertemplate="<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>",
    ))
    annotations = []
    if center_label:
        annotations.append(dict(text=center_label, x=0.5, y=0.5, font=dict(size=15, color=PRIMARY_INK, family=FONT_STACK),
                                 showarrow=False))
    fig.update_layout(annotations=annotations, legend=dict(orientation="h", yanchor="bottom", y=-0.12))
    return _figure_chrome(fig, height, legend=True)


def treemap_chart(labels, values, height=440, colorscale=SEQUENTIAL_GREEN, max_items=20):
    labels = list(labels)[:max_items]
    values = list(values)[:max_items]
    fig = go.Figure(go.Treemap(
        labels=labels, parents=[""] * len(labels), values=values,
        marker=dict(colors=values, colorscale=colorscale, line=dict(width=2, color="#fffefb")),
        textinfo="label+value", textfont=dict(family=FONT_STACK, size=13),
        hovertemplate="<b>%{label}</b><br>%{value:,}<extra></extra>",
    ))
    return _figure_chrome(fig, height)


def sunburst_chart(ids, labels, parents, values, colors, height=460):
    fig = go.Figure(go.Sunburst(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
        marker=dict(colors=colors, line=dict(color="#fffefb", width=2)),
        textfont=dict(family=FONT_STACK, size=12),
        hovertemplate="<b>%{label}</b><br>%{value:,}<extra></extra>",
    ))
    return _figure_chrome(fig, height)


def radar_chart(categories, series: dict, colors, height=440):
    fig = go.Figure()
    cats_closed = list(categories) + [categories[0]]
    for name, values in series.items():
        vals_closed = list(values) + [values[0]]
        color = colors.get(name, SLOT["blue"])
        fig.add_trace(go.Scatterpolar(
            r=vals_closed, theta=cats_closed, name=name, fill="toself",
            fillcolor=color + "38",  # hex + alpha suffix (~22% opacity fill)
            line=dict(color=color, width=3), marker=dict(size=6, color=color),
            hovertemplate=f"<b>{name}</b><br>%{{theta}}: %{{r:,.0f}}<extra></extra>",
        ))
    fig.update_layout(polar=dict(
        bgcolor="#fffefb",
        radialaxis=dict(gridcolor=GRID, tickfont=dict(color=MUTED_INK, size=10), linecolor=GRID),
        angularaxis=dict(gridcolor=GRID, tickfont=dict(color=PRIMARY_INK, size=12), linecolor=GRID),
    ))
    return _figure_chrome(fig, height, legend=True)


def barpolar_chart(categories, values, color=SLOT["violet"], height=420):
    fig = go.Figure(go.Barpolar(
        r=values, theta=categories, marker=dict(color=color, line=dict(color="#fffefb", width=1.5)), opacity=0.9,
        hovertemplate="<b>%{theta}</b><br>%{r:,} observations<extra></extra>",
    ))
    fig.update_layout(polar=dict(
        bgcolor="#fffefb",
        radialaxis=dict(gridcolor=GRID, tickfont=dict(color=MUTED_INK, size=10)),
        angularaxis=dict(gridcolor=GRID, tickfont=dict(color=PRIMARY_INK, size=11), rotation=90, direction="clockwise"),
    ))
    return _figure_chrome(fig, height)


def lollipop_chart(categories, values, color=SLOT["blue"], height=420, x_title="Observations"):
    categories = list(categories)
    values = list(values)
    xs, ys = [], []
    for cat, val in zip(categories, values):
        xs += [0, val, None]
        ys += [cat, cat, None]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=3), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=values, y=categories, mode="markers", marker=dict(size=14, color=color, line=dict(color="#fffefb", width=2)),
        hovertemplate="<b>%{y}</b><br>" + x_title + ": %{x:,}<extra></extra>", showlegend=False,
    ))
    fig.update_layout(xaxis=dict(title=x_title, gridcolor=GRID, zerolinecolor=GRID),
                       yaxis=dict(gridcolor="rgba(0,0,0,0)"))
    return _figure_chrome(fig, height)


def area_chart(x, y, color=SLOT["aqua"], height=360, x_title="", y_title="Observations"):
    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="lines+markers", line=dict(color=color, width=3, shape="spline"),
        marker=dict(size=6, color=color), fill="tozeroy", fillcolor=color + "33",
        hovertemplate=f"{x_title}: %{{x}}<br>{y_title}: %{{y:,}}<extra></extra>",
    ))
    fig.update_layout(xaxis=dict(title=x_title, gridcolor=GRID), yaxis=dict(title=y_title, gridcolor=GRID))
    return _figure_chrome(fig, height)


def line_trend_chart(x, y, color=SLOT["violet"], height=380, x_title="", y_title=""):
    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="lines+markers", line=dict(color=color, width=3), marker=dict(size=9, color=color),
        hovertemplate=f"{x_title}: %{{x}}<br>{y_title}: %{{y:,}}<extra></extra>",
    ))
    fig.update_layout(xaxis=dict(title=x_title, gridcolor=GRID, dtick=1), yaxis=dict(title=y_title, gridcolor=GRID))
    return _figure_chrome(fig, height)


def violin_chart(df_plot, value_col, group_col, color_map, height=420):
    fig = go.Figure()
    for cat, sub in df_plot.groupby(group_col):
        color = color_map.get(cat, SLOT["blue"])
        fig.add_trace(go.Violin(
            y=sub[value_col], name=cat, box_visible=True, meanline_visible=True,
            fillcolor=color + "55", line=dict(color=color), points=False,
        ))
    fig.update_layout(yaxis=dict(gridcolor=GRID))
    return _figure_chrome(fig, height, legend=True)


def funnel_chart(categories, values, height=420):
    fig = go.Figure(go.Funnel(
        y=categories, x=values, marker=dict(color=[SLOT["aqua"], SLOT["yellow"], MUTED_INK][:len(categories)]),
        textinfo="value+percent initial",
        connector=dict(line=dict(color=GRID, width=2)),
    ))
    return _figure_chrome(fig, height)


ROTATE_HINT = "🔄 *Drag to rotate, scroll to zoom, hover a shape for its exact value.*"
HOVER_HINT = "✨ *Hover any segment for its exact value.*"

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
    "environmental correlations, conservation insights, and recommendations."
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
        insights, conservation priorities, and recommendations for action.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if df.empty:
    st.warning("No observations match the current filter selection. Adjust the filters in the sidebar.")
    st.stop()

# ---------------------------------------------------------------------------
# Section navigation - real interactive buttons (not st.tabs).
# ---------------------------------------------------------------------------
# NOTE: several sections build 3D (WebGL) charts, and browsers cap the number
# of simultaneously-live WebGL contexts on one page (commonly ~16). st.tabs
# renders every tab's content into the DOM at once and would blow past that
# cap, silently blanking charts out. These buttons instead only *build* the
# charts for the one section currently selected, keeping things fast and
# reliable no matter how many sections the app has.
SECTIONS = [
    ("overview", "🏠 Overview"), ("temporal", "📅 Temporal"), ("spatial", "🗺️ Spatial"),
    ("species", "🐦 Species"), ("environment", "🌤️ Environment"),
    ("distance", "📏 Distance & Behavior"), ("observers", "🔭 Observers"),
    ("conservation", "🛡️ Conservation"), ("recommendations", "💡 Recommendations"),
    ("explorer", "🔎 Data Explorer"),
]
if "section" not in st.session_state:
    st.session_state.section = "overview"

nav_cols = st.columns(5)
for i, (key, label) in enumerate(SECTIONS):
    with nav_cols[i % 5]:
        is_active = st.session_state.section == key
        if st.button(label, key=f"nav_{key}", type="primary" if is_active else "secondary",
                      width="stretch"):
            st.session_state.section = key
            st.rerun()

section = st.session_state.section
st.write("")

month_order = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"]

# ============================================================ OVERVIEW ====
if section == "overview":
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
        with st.container(border=True):
            st.subheader("🌲 Observations by Habitat")
            hab_counts = df["Habitat"].value_counts()
            fig = donut_chart(hab_counts.index.tolist(), hab_counts.values.tolist(),
                                color_map=HABITAT_COLORS, height=360, center_label=f"{len(df):,}<br>total")
            st.plotly_chart(fig, width="stretch", key="chart_1")
            st.markdown(f'<p class="section-caption">{HOVER_HINT}</p>', unsafe_allow_html=True)

    with col2:
        with st.container(border=True):
            st.subheader("🏆 Top 15 Most-Observed Species (3D)")
            top_sp = df["Common_Name"].value_counts().head(15)
            fig = bar3d(top_sp.index.tolist(), top_sp.values.tolist(), color=SLOT["aqua"],
                         height=430, x_title="Species", z_title="Observations")
            st.plotly_chart(fig, width="stretch", key="chart_2")
            st.markdown(f'<p class="section-caption">{ROTATE_HINT}</p>', unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("📍 Observations by Admin Unit × Habitat (3D surface)")
        pivot = df.groupby(["Habitat", "Admin_Unit_Code"]).size().unstack(fill_value=0)
        pivot = pivot.reindex(habitats).fillna(0)
        fig = surface3d(pivot, x_title="Admin Unit", y_title="Habitat", height=440)
        st.plotly_chart(fig, width="stretch", key="chart_3")
        st.markdown(f'<p class="section-caption">{ROTATE_HINT}</p>', unsafe_allow_html=True)

# ============================================================ TEMPORAL ====
if section == "temporal":
    with st.container(border=True):
        st.subheader("📈 Observations by Month (3D ribbon per habitat)")
        month_counts = df.groupby(["Month_Name", "Habitat"]).size().unstack(fill_value=0)
        month_counts = month_counts.reindex(month_order).fillna(0)
        series = {h: month_counts[h].tolist() for h in habitats if h in month_counts.columns}
        fig = ribbon3d(series, month_order, HABITAT_COLORS, x_title="Month")
        st.plotly_chart(fig, width="stretch", key="chart_4")
        st.markdown(f'<p class="section-caption">{ROTATE_HINT}</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("🍂 Observations by Season (radar)")
            season_counts = df.groupby(["Season", "Habitat"]).size().unstack(fill_value=0).reindex(seasons_present).fillna(0)
            series = {h: season_counts[h].tolist() for h in habitats if h in season_counts.columns}
            fig = radar_chart(seasons_present, series, HABITAT_COLORS, height=420)
            st.plotly_chart(fig, width="stretch", key="chart_5")

    with col2:
        with st.container(border=True):
            st.subheader("⏰ Observations by Start Hour")
            hour_counts = df.groupby("Start_Hour").size().sort_index()
            fig = area_chart(hour_counts.index.tolist(), hour_counts.values.tolist(), color=SLOT["blue"],
                               x_title="Hour of Day (24h)", height=420)
            st.plotly_chart(fig, width="stretch", key="chart_6")

    with st.container(border=True):
        st.subheader("⏱️ Observation Session Duration by Habitat (violin)")
        fig = violin_chart(df.dropna(subset=["Observation_Duration_Min"]), "Observation_Duration_Min",
                             "Habitat", HABITAT_COLORS, height=400)
        st.plotly_chart(fig, width="stretch", key="chart_7")

    with st.container(border=True):
        st.subheader("🗓️ Month × Season Activity Surface (3D)")
        heat = df.groupby(["Month_Name", "Season"]).size().reset_index(name="Observations")
        heat["Month_Name"] = pd.Categorical(heat["Month_Name"], categories=month_order, ordered=True)
        pivot = heat.pivot(index="Season", columns="Month_Name", values="Observations").reindex(seasons_order).fillna(0)
        pivot = pivot.dropna(how="all", axis=1)
        fig = surface3d(pivot, x_title="Month", y_title="Season", height=440)
        st.plotly_chart(fig, width="stretch", key="chart_8")
        st.markdown(f'<p class="section-caption">{ROTATE_HINT}</p>', unsafe_allow_html=True)

# ============================================================= SPATIAL ====
if section == "spatial":
    with st.container(border=True):
        st.subheader("🗺️ Administrative Unit Map")
        st.caption(
            "Marker position = approximate park centroid (not exact plot GPS, which "
            "isn't in the source data). Size = observation count, color = habitat mix. "
            "Map is tilted for a 3D perspective — drag to rotate/pan."
        )
        if not loc_df.empty:
            admin_summary = df.groupby("Admin_Unit_Code").agg(
                Observations=("Common_Name", "size"), Species=("Common_Name", "nunique"),
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
                lat=admin_summary["Latitude"], lon=admin_summary["Longitude"], mode="markers",
                marker=dict(size=(admin_summary["Observations"] / admin_summary["Observations"].max() * 38 + 10),
                             color=admin_summary["Pct_Forest"], colorscale=SEQUENTIAL_GREEN,
                             showscale=True, colorbar=dict(title="% Forest", thickness=14)),
                text=[f"<b>{n}</b> ({c})<br>{o:,} observations<br>{s} species"
                      for n, c, o, s in zip(admin_summary["Admin_Unit_Name"], admin_summary["Admin_Unit_Code"],
                                              admin_summary["Observations"], admin_summary["Species"])],
                hoverinfo="text",
            ))
            fig.update_layout(
                map=dict(style="open-street-map", zoom=6.3, pitch=55,
                          center=dict(lat=admin_summary["Latitude"].mean(), lon=admin_summary["Longitude"].mean())),
                height=480, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="#fffefb",
            )
            st.plotly_chart(fig, width="stretch", key="chart_9")
        else:
            st.info("Admin unit location lookup not found in the database.")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("🌳 Species Richness by Admin Unit (treemap)")
            rich = df.groupby("Admin_Unit_Code")["Common_Name"].nunique().sort_values(ascending=False)
            fig = treemap_chart(rich.index.tolist(), rich.values.tolist(), height=420)
            st.plotly_chart(fig, width="stretch", key="chart_10")

    with col2:
        with st.container(border=True):
            st.subheader("📌 Top 15 Plots by Observation Count")
            plot_counts = df["Plot_Name"].value_counts().head(15)
            fig = lollipop_chart(plot_counts.index.tolist()[::-1], plot_counts.values.tolist()[::-1],
                                   color=SLOT["blue"], height=420)
            st.plotly_chart(fig, width="stretch", key="chart_11")

# ============================================================= SPECIES ====
if section == "species":
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("🌿 Species Count by Habitat")
            sp_hab = df.groupby("Habitat")["Common_Name"].nunique()
            fig = donut_chart(sp_hab.index.tolist(), sp_hab.values.tolist(), color_map=HABITAT_COLORS, height=360)
            st.plotly_chart(fig, width="stretch", key="chart_12")

    with col2:
        with st.container(border=True):
            st.subheader("⚥ Sex Ratio")
            sex_counts = df["Sex"].value_counts()
            fig = donut_chart(sex_counts.index.tolist(), sex_counts.values.tolist(), color_map=SEX_COLORS, height=360)
            st.plotly_chart(fig, width="stretch", key="chart_13")

    with st.container(border=True):
        st.subheader("🎧 Identification Method (polar)")
        id_counts = df["ID_Method"].dropna().value_counts()
        fig = barpolar_chart(id_counts.index.tolist(), id_counts.values.tolist(), color=SLOT["violet"], height=400)
        st.plotly_chart(fig, width="stretch", key="chart_14")

    with st.container(border=True):
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
                fig = lollipop_chart(by_admin.index.tolist()[::-1], by_admin.values.tolist()[::-1],
                                       color=SLOT["blue"], height=320)
                st.plotly_chart(fig, width="stretch", key="chart_15")
            with colB:
                by_month = sp_df["Month_Name"].value_counts().reindex(month_order).fillna(0)
                by_month = by_month[by_month > 0]
                if len(by_month):
                    fig = area_chart(by_month.index.tolist(), by_month.values.tolist(), color=SLOT["aqua"], height=320)
                    st.plotly_chart(fig, width="stretch", key="chart_16")
                else:
                    st.info("No monthly data for this species under the current filters.")

# ========================================================= ENVIRONMENT ====
if section == "environment":
    with st.container(border=True):
        st.subheader("🌡️ Temperature × Humidity × Observation Volume (3D scatter)")
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
        with st.container(border=True):
            st.subheader("☁️ Sky Condition (polar)")
            sky_counts = df["Sky"].value_counts()
            fig = barpolar_chart(sky_counts.index.tolist(), sky_counts.values.tolist(), color=SLOT["blue"], height=400)
            st.plotly_chart(fig, width="stretch", key="chart_18")

    with col2:
        with st.container(border=True):
            st.subheader("🌬️ Wind Condition")
            wind_counts = df["Wind"].value_counts()
            fig = lollipop_chart(wind_counts.index.tolist()[::-1], wind_counts.values.tolist()[::-1],
                                   color=SLOT["aqua"], height=400)
            st.plotly_chart(fig, width="stretch", key="chart_19")

    with st.container(border=True):
        st.subheader("⚠️ Disturbance Effect on Observations")
        dist_counts = df["Disturbance"].value_counts()
        fig = donut_chart(dist_counts.index.tolist(), dist_counts.values.tolist(),
                            colors=[SLOT["aqua"], SLOT["yellow"], SLOT["orange"], SLOT["red"]][:len(dist_counts)], height=380)
        st.plotly_chart(fig, width="stretch", key="chart_20")

# =================================================== DISTANCE & BEHAVIOR ===
if section == "distance":
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("📏 Observation Distance (funnel)")
            st.caption("Ranked largest to smallest, as a funnel should read.")
            dcounts = df["Distance"].value_counts()  # already sorted descending
            fig = funnel_chart(dcounts.index.tolist(), dcounts.values.tolist(), height=400)
            st.plotly_chart(fig, width="stretch", key="chart_21")

    with col2:
        with st.container(border=True):
            st.subheader("🦅 Flyover Observed")
            fly_counts = df["Flyover_Observed"].value_counts(dropna=False)
            labels = [{True: "Flyover", False: "Not a Flyover"}.get(k, "Unknown") for k in fly_counts.index]
            fig = donut_chart(labels, fly_counts.values.tolist(), colors=[SLOT["red"], MUTED_INK, "#c3c2b7"], height=400)
            st.plotly_chart(fig, width="stretch", key="chart_22")

    with st.container(border=True):
        st.subheader("📐 Distance by Habitat (radar)")
        order = ["<= 50 Meters", "50 - 100 Meters", "Not Recorded"]
        dist_hab = df.groupby(["Distance", "Habitat"]).size().unstack(fill_value=0)
        order = [o for o in order if o in dist_hab.index] + [o for o in dist_hab.index if o not in order]
        dist_hab = dist_hab.reindex(order).fillna(0)
        series = {h: dist_hab[h].tolist() for h in habitats if h in dist_hab.columns}
        fig = radar_chart(order, series, HABITAT_COLORS, height=440)
        st.plotly_chart(fig, width="stretch", key="chart_23")

# ============================================================ OBSERVERS ===
if section == "observers":
    with st.container(border=True):
        st.subheader("🔭 Observations by Observer")
        obs_counts = df["Observer"].value_counts()
        fig = donut_chart(obs_counts.index.tolist(), obs_counts.values.tolist(),
                            colors=[SLOT["blue"], SLOT["aqua"], SLOT["yellow"], SLOT["violet"], SLOT["magenta"]][:len(obs_counts)],
                            height=380)
        st.plotly_chart(fig, width="stretch", key="chart_24")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("🌈 Species Diversity per Observer")
            div = df.groupby("Observer")["Common_Name"].nunique().sort_values()
            fig = lollipop_chart(div.index.tolist(), div.values.tolist(), color=SLOT["aqua"],
                                   height=380, x_title="Unique Species")
            st.plotly_chart(fig, width="stretch", key="chart_25")

    with col2:
        with st.container(border=True):
            st.subheader("🔁 Visit Number vs. Species Count")
            visit_div = df.groupby("Visit")["Common_Name"].nunique().sort_index()
            fig = line_trend_chart(visit_div.index.tolist(), visit_div.values.tolist(), color=SLOT["violet"],
                                     height=380, x_title="Visit #", y_title="Unique Species")
            st.plotly_chart(fig, width="stretch", key="chart_26")

# ========================================================= CONSERVATION ===
if section == "conservation":
    col1, col2, col3 = st.columns(3)
    watch_species = df.loc[df["PIF_Watchlist_Status"] == True, "Common_Name"].nunique()  # noqa: E712
    steward_species = df.loc[df["Regional_Stewardship_Status"] == True, "Common_Name"].nunique()  # noqa: E712
    watch_df = df[df["PIF_Watchlist_Status"] == True]  # noqa: E712
    col1.metric("Watchlist Species", watch_species)
    col2.metric("Regional Stewardship Species", steward_species)
    col3.metric("Watchlist Sightings", int((df["PIF_Watchlist_Status"] == True).sum()))  # noqa: E712

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("🛡️ Top Watchlist Species by Sightings (3D)")
            if not watch_df.empty:
                wc = watch_df["Common_Name"].value_counts().head(15)
                fig = bar3d(wc.index.tolist(), wc.values.tolist(), color=SLOT["red"], x_title="Species", height=430)
                st.plotly_chart(fig, width="stretch", key="chart_27")
                st.markdown(f'<p class="section-caption">{ROTATE_HINT}</p>', unsafe_allow_html=True)
            else:
                st.info("No PIF Watchlist species in the current filter selection.")

    with col2:
        with st.container(border=True):
            st.subheader("📍 Watchlist Sightings: Habitat → Admin Unit (sunburst)")
            if not watch_df.empty:
                wa = watch_df.groupby(["Habitat", "Admin_Unit_Code"]).size().reset_index(name="n")
                ids, labels, parents, values, colors = [], [], [], [], []
                for h in habitats:
                    hsum = wa.loc[wa["Habitat"] == h, "n"].sum()
                    if hsum <= 0:
                        continue
                    ids.append(h); labels.append(h); parents.append(""); values.append(hsum)
                    colors.append(HABITAT_COLORS.get(h, SLOT["blue"]))
                    for _, row in wa[wa["Habitat"] == h].iterrows():
                        ids.append(f"{h}-{row['Admin_Unit_Code']}"); labels.append(row["Admin_Unit_Code"])
                        parents.append(h); values.append(row["n"])
                        colors.append(HABITAT_COLORS.get(h, SLOT["blue"]))
                fig = sunburst_chart(ids, labels, parents, values, colors, height=430)
                st.plotly_chart(fig, width="stretch", key="chart_28")
            else:
                st.info("No PIF Watchlist species in the current filter selection.")

    with st.container(border=True):
        st.subheader("🔤 AOU Code Distribution (treemap, top 20)")
        aou_counts = df["AOU_Code"].value_counts().head(20)
        fig = treemap_chart(aou_counts.index.tolist(), aou_counts.values.tolist(), height=440)
        st.plotly_chart(fig, width="stretch", key="chart_29")

# ===================================================== RECOMMENDATIONS ====
if section == "recommendations":
    st.subheader("💡 Actionable Recommendations")
    st.caption(
        "Data-driven suggestions tied to the project's business use cases — "
        "wildlife conservation, land management, eco-tourism, sustainable "
        "agriculture, policy support, and biodiversity monitoring. Recomputed "
        "live from your current filter selection."
    )

    cards = []

    if not df.empty:
        hotspot_unit = df.groupby("Admin_Unit_Code").size().idxmax()
        hotspot_n = int(df.groupby("Admin_Unit_Code").size().max())
        richest_unit = df.groupby("Admin_Unit_Code")["Common_Name"].nunique().idxmax()
        richest_n = int(df.groupby("Admin_Unit_Code")["Common_Name"].nunique().max())
        peak_season = df.groupby("Season").size().idxmax() if len(df["Season"].dropna()) else None
        peak_hour = int(df.groupby("Start_Hour").size().idxmax()) if len(df["Start_Hour"].dropna()) else None
        top_plot = df.groupby("Plot_Name")["Common_Name"].nunique().idxmax()
        top_plot_n = int(df.groupby("Plot_Name")["Common_Name"].nunique().max())
        disturbance_common = df["Disturbance"].value_counts().idxmax()
        watch_df = df[df["PIF_Watchlist_Status"] == True]  # noqa: E712

        cards.append((
            "🛡️", "Wildlife Conservation",
            f"<b>{hotspot_unit}</b> logs the most observations ({hotspot_n:,}) under the current filters. "
            f"Prioritize it for continued protection and monitoring effort, especially if watchlist species are present there."
        ))
        cards.append((
            "🌲", "Land Management",
            f"<b>{richest_unit}</b> has the highest species richness ({richest_n} unique species). "
            f"Treat it as a reference site for habitat-restoration standards applied to lower-diversity units."
        ))
        cards.append((
            "🧭", "Eco-Tourism",
            f"Plot <b>{top_plot}</b> recorded the most unique species ({top_plot_n}) — "
            f"a strong candidate for guided birding trails or eco-tourism promotion."
        ))
        if peak_season and peak_hour is not None:
            cards.append((
                "📊", "Biodiversity Monitoring",
                f"Activity peaks in <b>{peak_season}</b> around <b>{peak_hour}:00</b>. "
                f"Schedule future survey visits in this window to maximize detection efficiency per unit of field effort."
            ))
        cards.append((
            "🌾", "Sustainable Agriculture",
            f"\"{disturbance_common}\" is the most frequently logged disturbance note. "
            f"Coordinate any nearby land-use or agricultural activity outside peak activity hours to minimize impact on counts."
        ))
        if not watch_df.empty:
            watch_habitat = watch_df.groupby("Habitat").size().idxmax()
            watch_habitat_n = int(watch_df.groupby("Habitat").size().max())
            cards.append((
                "📜", "Policy Support",
                f"{watch_df['Common_Name'].nunique()} PIF Watchlist species were sighted "
                f"({watch_habitat_n:,} sightings concentrated in <b>{watch_habitat}</b>). "
                f"This habitat should anchor any regional stewardship or protected-status policy proposal."
            ))
        else:
            cards.append((
                "📜", "Policy Support",
                "No PIF Watchlist species appear under the current filters — a good sign for this "
                "slice of the data, but continue monitoring as conditions or seasons change."
            ))

    cards_html = "".join(
        f"""<div class="insight-card"><span class="tag">Business Use Case</span>
            <h4>{icon} {title}</h4><p>{body}</p></div>"""
        for icon, title, body in cards
    )
    st.markdown(f'<div class="insight-grid">{cards_html}</div>', unsafe_allow_html=True)

# ============================================================ EXPLORER ====
if section == "explorer":
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
