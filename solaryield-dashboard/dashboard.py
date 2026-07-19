import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import math

st.set_page_config(
    page_title="SolarYield Dashboard",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background: #f8fafc !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    color: #1a2332 !important;
}
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stAppViewContainer"] > div:first-child { padding-top: 1.5rem; }

.sy-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: white;
    border: 1px solid #e8edf2;
    border-radius: 16px;
    padding: 20px 28px;
    margin-bottom: 20px;
}
.sy-logo { font-size: 22px; font-weight: 700; color: #1a2332; letter-spacing: -0.5px; }
.sy-logo span { color: #f59e0b; }
.sy-subtitle { font-size: 12px; color: #64748b; margin-top: 2px; letter-spacing: 0.02em; }
.sy-time { font-family: 'DM Mono', monospace; font-size: 13px; color: #94a3b8; }

.sy-banner-ok {
    background: #f0fdf4;
    border: 1.5px solid #86efac;
    border-radius: 12px;
    padding: 12px 20px;
    color: #166534;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 16px;
}
.sy-banner-alert {
    background: #fff7ed;
    border: 1.5px solid #fdba74;
    border-radius: 12px;
    padding: 12px 20px;
    color: #9a3412;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 16px;
}
.sy-banner-wait {
    background: #f1f5f9;
    border: 1.5px solid #cbd5e1;
    border-radius: 12px;
    padding: 12px 20px;
    color: #475569;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 16px;
}
.sy-banner-manual {
    background: #eef2ff;
    border: 1.5px solid #a5b4fc;
    border-radius: 12px;
    padding: 12px 20px;
    color: #3730a3;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 16px;
}

.metric-card {
    background: white;
    border: 1px solid #e8edf2;
    border-radius: 14px;
    padding: 18px 20px;
    position: relative;
}
.metric-top-bar {
    height: 3px;
    border-radius: 2px;
    margin-bottom: 14px;
}
.metric-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #94a3b8;
    margin-bottom: 6px;
}
.metric-value {
    font-size: 28px;
    font-weight: 700;
    color: #1a2332;
    line-height: 1;
    font-family: 'Plus Jakarta Sans', sans-serif;
}
.metric-unit { font-size: 13px; color: #94a3b8; margin-top: 4px; font-weight: 400; }
.metric-status-ok   { color: #16a34a; font-size: 11px; font-weight: 600; margin-top: 6px; }
.metric-status-warn { color: #d97706; font-size: 11px; font-weight: 600; margin-top: 6px; }
.metric-status-bad  { color: #dc2626; font-size: 11px; font-weight: 600; margin-top: 6px; }

.section-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #94a3b8;
    margin: 20px 0 10px;
}

.tilt-card {
    background: white;
    border: 1px solid #e8edf2;
    border-radius: 14px;
    padding: 20px;
    text-align: center;
}
.tilt-angle-label {
    font-size: 40px;
    font-weight: 700;
    color: #1a2332;
    line-height: 1;
}
.tilt-sub { font-size: 12px; color: #94a3b8; margin-top: 4px; }

.log-card {
    background: white;
    border: 1px solid #e8edf2;
    border-radius: 14px;
    padding: 20px;
}

.mode-card {
    background: white;
    border: 1px solid #e8edf2;
    border-radius: 14px;
    padding: 20px;
}

div[data-testid="stButton"] button {
    background: #1a2332 !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 8px 20px !important;
}
div[data-testid="stButton"] button:hover { background: #2d3f55 !important; }

div[data-testid="stSelectbox"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stSlider"] label {
    font-size: 12px !important;
    font-weight: 600 !important;
    color: #64748b !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}

.stTabs [data-baseweb="tab"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}

footer, #MainMenu { display: none; }

.pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
}
.pill-green  { background: #dcfce7; color: #166534; }
.pill-amber  { background: #fef3c7; color: #92400e; }
.pill-red    { background: #fee2e2; color: #991b1b; }
.pill-blue   { background: #dbeafe; color: #1e40af; }
.pill-purple { background: #ede9fe; color: #5b21b6; }
.pill-gray   { background: #f1f5f9; color: #475569; }
.pill-indigo { background: #e0e7ff; color: #3730a3; }
</style>
""", unsafe_allow_html=True)

API_BASE = "https://solaryield-api.onrender.com"

ANOMALY_META = {
    "none":              {"label": "Normal",            "pill": "pill-green",  "bar": "#22c55e"},
    "heat_stress":       {"label": "Heat stress",       "pill": "pill-red",    "bar": "#ef4444"},
    "low_humidity":      {"label": "Low humidity",      "pill": "pill-blue",   "bar": "#3b82f6"},
    "light_deficiency":  {"label": "Light deficiency",  "pill": "pill-purple", "bar": "#8b5cf6"},
    "voltage_drop":      {"label": "Voltage drop",      "pill": "pill-amber",  "bar": "#f97316"},
    "irradiance_limited":{"label": "Cloud cover",       "pill": "pill-gray",   "bar": "#94a3b8"},
    "manual":            {"label": "Manual override",   "pill": "pill-indigo", "bar": "#6366f1"},
}

CHART_COLORS = {
    "temperature":  "#ef4444",
    "humidity":     "#3b82f6",
    "lux":          "#8b5cf6",
    "power_mw":     "#22c55e",
    "tilt_angle":   "#f97316",
}

@st.cache_data(ttl=10)
def fetch_log(n=360):
    try:
        r = requests.get(f"{API_BASE}/log?n={n}", timeout=8)
        if r.status_code == 200:
            return r.json().get("readings", [])
    except Exception:
        pass
    return []

@st.cache_data(ttl=30)
def fetch_growth():
    try:
        r = requests.get(f"{API_BASE}/growth", timeout=8)
        if r.status_code == 200:
            return r.json().get("entries", [])
    except Exception:
        pass
    return []

def post_growth(condition, day, height, water, notes):
    try:
        r = requests.post(f"{API_BASE}/growth", json={
            "condition": condition, "day": day,
            "height_cm": height, "water_ml": water, "notes": notes
        }, timeout=8)
        return r.status_code == 200
    except Exception:
        return False

@st.cache_data(ttl=5)
def fetch_mode():
    try:
        r = requests.get(f"{API_BASE}/mode", timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {"mode": "auto", "manual_tilt_angle": 5}

def set_mode(mode, manual_tilt_angle, password):
    try:
        r = requests.post(f"{API_BASE}/mode", json={
            "mode": mode,
            "manual_tilt_angle": manual_tilt_angle,
            "password": password,
        }, timeout=8)
        if r.status_code == 200:
            return True, "OK"
        elif r.status_code == 401:
            return False, "Incorrect password"
        else:
            return False, f"Server error ({r.status_code})"
    except Exception as e:
        return False, str(e)

def mini_chart(df, col, color, title, unit, height=160):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df[col],
        mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy",
        fillcolor=color,
        opacity=0.07,
        hovertemplate=f"%{{y:.1f}} {unit}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(family="Plus Jakarta Sans", size=12,
                   color="#64748b"), x=0, pad=dict(l=0)),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Plus Jakarta Sans", color="#94a3b8", size=11),
        margin=dict(l=0, r=0, t=28, b=0),
        height=height,
        xaxis=dict(showgrid=False, showline=False, showticklabels=False),
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9", showline=False,
                   tickfont=dict(size=10, color="#94a3b8")),
        hovermode="x unified",
    )
    return fig

def tilt_svg(angle, anomaly_type):
    meta  = ANOMALY_META.get(anomaly_type, ANOMALY_META["none"])
    color = meta["bar"]
    rad   = math.radians(angle)
    w     = 100
    cx, cy = 110, 115
    x1 = cx - (w/2) * math.cos(rad)
    y1 = cy + (w/2) * math.sin(rad)
    x2 = cx + (w/2) * math.cos(rad)
    y2 = cy - (w/2) * math.sin(rad)
    return f"""
    <svg viewBox="0 0 220 170" xmlns="http://www.w3.org/2000/svg" width="100%" style="max-width:240px">
      <line x1="20" y1="148" x2="200" y2="148" stroke="#e8edf2" stroke-width="1.5"/>
      <rect x="60" y="126" width="7" height="22" rx="2" fill="#bbf7d0"/>
      <rect x="78" y="120" width="7" height="28" rx="2" fill="#86efac"/>
      <rect x="96" y="124" width="7" height="24" rx="2" fill="#bbf7d0"/>
      <rect x="114" y="118" width="7" height="30" rx="2" fill="#86efac"/>
      <rect x="132" y="122" width="7" height="26" rx="2" fill="#bbf7d0"/>
      <line x1="{cx}" y1="{cy}" x2="{cx}" y2="148"
            stroke="#e2e8f0" stroke-width="1.5" stroke-dasharray="4,3"/>
      <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"
            stroke="{color}" stroke-width="6" stroke-linecap="round"/>
      <circle cx="{cx}" cy="{cy}" r="4" fill="{color}"/>
    </svg>"""

def metric_card_html(label, value, unit, bar_color, status_text, status_class):
    return f"""
    <div class='metric-card'>
        <div class='metric-top-bar' style='background:{bar_color}'></div>
        <div class='metric-label'>{label}</div>
        <div class='metric-value'>{value}</div>
        <div class='metric-unit'>{unit}</div>
        <div class='{status_class}'>{status_text}</div>
    </div>"""

# ── Header ────────────────────────────────────────────────────────────────────
now_str = datetime.now().strftime("%d %b %Y  %H:%M:%S")
st.markdown(f"""
<div class='sy-header'>
    <div>
        <div class='sy-logo'>Solar<span>Yield</span></div>
        <div class='sy-subtitle'>ML-Optimised Agrivoltaic Control &nbsp;·&nbsp; Team J-43 &nbsp;·&nbsp; EIC 2026</div>
    </div>
    <div class='sy-time'>{now_str}</div>
</div>
""", unsafe_allow_html=True)

# ── Auto-refresh ──────────────────────────────────────────────────────────────
col_r, col_spacer = st.columns([1, 5])
with col_r:
    auto_refresh = st.toggle("Live updates", value=True)

# ── Mode control (auto / manual, password-gated) ───────────────────────────────
st.markdown("<div class='section-label'>Control mode</div>", unsafe_allow_html=True)

mode_state = fetch_mode()
current_mode = mode_state.get("mode", "auto")

mc1, mc2 = st.columns([1, 2])

with mc1:
    st.markdown(f"""
    <div class='mode-card'>
        <div class='metric-label'>Current mode</div>
        <div style='margin-top:8px'>
            <span class='pill {"pill-green" if current_mode == "auto" else "pill-indigo"}'>
                {"Automatic (RF control)" if current_mode == "auto" else "Manual override"}
            </span>
        </div>
    </div>""", unsafe_allow_html=True)

with mc2:
    st.markdown("<div class='mode-card'>", unsafe_allow_html=True)
    st.markdown("<div class='metric-label'>Switch mode — requires password</div>", unsafe_allow_html=True)

    mm1, mm2, mm3 = st.columns([1, 1, 1.4])
    with mm1:
        target_mode = st.radio("New mode", ["auto", "manual"],
                                index=0 if current_mode == "auto" else 1,
                                horizontal=True, label_visibility="collapsed")
    with mm2:
        manual_angle_input = st.slider("Tilt angle", 0, 30,
                                        value=int(mode_state.get("manual_tilt_angle", 5)),
                                        disabled=(target_mode != "manual"))
    with mm3:
        mode_password = st.text_input("Password", type="password", label_visibility="collapsed",
                                       placeholder="Password to apply change")

    if st.button("Apply"):
        if not mode_password:
            st.error("Enter the password to change mode.")
        else:
            ok, msg = set_mode(target_mode, manual_angle_input, mode_password)
            if ok:
                st.success(f"Mode set to {target_mode}.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(msg)
    st.markdown("</div>", unsafe_allow_html=True)

if current_mode == "manual":
    st.markdown(f"""
    <div class='sy-banner-manual'>
        🕹 &nbsp; Manual override active — panel held at {mode_state.get('manual_tilt_angle', 5)}°.
        The RF controller is not adjusting tilt while this is on.
    </div>""", unsafe_allow_html=True)

# ── Fetch data ────────────────────────────────────────────────────────────────
readings = fetch_log(360)

if not readings:
    st.markdown("""
    <div class='sy-banner-wait'>
        ⏳ &nbsp; Waiting for sensor data — ESP32 not yet connected
    </div>""", unsafe_allow_html=True)
    if auto_refresh:
        time.sleep(5)
        st.rerun()
    st.stop()

latest = readings[-1]
df = pd.DataFrame(readings)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["power_mw"]  = df["voltage"] * df["current"]

atype = latest.get("anomaly_type", "none")
meta  = ANOMALY_META.get(atype, ANOMALY_META["none"])

if current_mode == "manual":
    pass  # manual banner already shown above
elif latest.get("anomaly_detected"):
    st.markdown(f"""
    <div class='sy-banner-alert'>
        ⚠ &nbsp; Anomaly detected — <strong>{meta['label']}</strong>
        &nbsp;·&nbsp; Panel tilted to {latest['tilt_angle']}°
    </div>""", unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div class='sy-banner-ok'>
        ✓ &nbsp; System normal — panel at {latest['tilt_angle']}° baseline position
    </div>""", unsafe_allow_html=True)

# ── Live metrics ──────────────────────────────────────────────────────────────
st.markdown("<div class='section-label'>Live sensor readings</div>", unsafe_allow_html=True)

temp  = latest["temperature"]
hum   = latest["humidity"]
lux   = latest["lux"]
volts = latest["voltage"]
amps  = latest["current"]
power = volts * amps
tilt  = latest["tilt_angle"]

def temp_status(v):
    if v > 35: return "Above crop threshold", "metric-status-bad"
    if v > 30: return "Warm — monitor", "metric-status-warn"
    return "Normal range", "metric-status-ok"

def hum_status(v):
    if v < 50: return "Low — anomaly risk", "metric-status-warn"
    return "Normal range", "metric-status-ok"

c1, c2, c3 = st.columns(3)
ts, tc = temp_status(temp)
hs, hc = hum_status(hum)

with c1: st.markdown(metric_card_html("Temperature", f"{temp:.1f}", "°C",
    CHART_COLORS["temperature"], ts, tc), unsafe_allow_html=True)
with c2: st.markdown(metric_card_html("Humidity", f"{hum:.1f}", "%",
    CHART_COLORS["humidity"], hs, hc), unsafe_allow_html=True)
with c3: st.markdown(metric_card_html("Irradiance", f"{lux:.0f}", "lux",
    CHART_COLORS["lux"], "Light sensor reading", "metric-status-ok"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
c5, c6, c7, c8 = st.columns(4)
with c5: st.markdown(metric_card_html("Voltage", f"{volts:.2f}", "V",
    CHART_COLORS["power_mw"],
    "Below threshold" if volts < 3.0 else "Normal output",
    "metric-status-warn" if volts < 3.0 else "metric-status-ok"), unsafe_allow_html=True)
with c6: st.markdown(metric_card_html("Current", f"{amps:.1f}", "mA",
    CHART_COLORS["power_mw"], "Panel current draw", "metric-status-ok"), unsafe_allow_html=True)
with c7: st.markdown(metric_card_html("Power", f"{power:.1f}", "mW",
    CHART_COLORS["power_mw"], "Instantaneous output", "metric-status-ok"), unsafe_allow_html=True)
with c8:
    pill_cls = meta["pill"]
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-top-bar' style='background:{meta["bar"]}'></div>
        <div class='metric-label'>System status</div>
        <div style='margin-top:8px'>
            <span class='pill {pill_cls}'>{meta["label"]}</span>
        </div>
        <div class='metric-unit' style='margin-top:8px'>Tilt: {tilt}°</div>
        <div class='metric-status-ok' style='margin-top:4px'>
            {len(readings)} readings logged
        </div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tilt visual + decision log ────────────────────────────────────────────────
st.markdown("<div class='section-label'>Panel position &amp; decision log</div>", unsafe_allow_html=True)

col_tilt, col_log = st.columns([1, 2])

with col_tilt:
    st.markdown(f"""
    <div class='tilt-card'>
        <div class='tilt-angle-label'>{tilt}°</div>
        <div class='tilt-sub'>current tilt angle</div>
        {tilt_svg(tilt, "manual" if current_mode == "manual" else atype)}
        <div style='margin-top:12px'>
            <span class='pill {"pill-indigo" if current_mode == "manual" else meta["pill"]}'>
                {"Manual override" if current_mode == "manual" else meta["label"]}
            </span>
        </div>
    </div>""", unsafe_allow_html=True)

with col_log:
    st.markdown("<div class='log-card'>", unsafe_allow_html=True)
    recent = df.tail(25)[["timestamp","tilt_angle","anomaly_type",
                           "temperature","humidity"]].copy()
    recent["timestamp"] = recent["timestamp"].dt.strftime("%H:%M:%S")

    def fmt_anomaly(val):
        m = ANOMALY_META.get(val, ANOMALY_META["none"])
        return m["label"]

    recent["anomaly_type"] = recent["anomaly_type"].apply(fmt_anomaly)
    recent.columns = ["Time", "Tilt °", "Status", "Temp °C", "Hum %"]
    recent = recent.iloc[::-1]
    st.dataframe(recent, use_container_width=True, height=230, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Sensor charts ─────────────────────────────────────────────────────────────
st.markdown("<div class='section-label'>Sensor history — last hour</div>", unsafe_allow_html=True)

r1, r2 = st.columns(2)
r3, r4 = st.columns(2)

with r1: st.plotly_chart(mini_chart(df, "temperature", CHART_COLORS["temperature"],
    "Temperature (°C)", "°C"), use_container_width=True)
with r2: st.plotly_chart(mini_chart(df, "humidity", CHART_COLORS["humidity"],
    "Humidity (%)", "%"), use_container_width=True)
with r3: st.plotly_chart(mini_chart(df, "lux", CHART_COLORS["lux"],
    "Irradiance (lux)", "lux"), use_container_width=True)
with r4: st.plotly_chart(mini_chart(df, "tilt_angle", CHART_COLORS["tilt_angle"],
    "Tilt angle (°)", "°"), use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

r5, r6 = st.columns(2)
with r5: st.plotly_chart(mini_chart(df, "power_mw", CHART_COLORS["power_mw"],
    "Panel power (mW)", "mW"), use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Growth log ────────────────────────────────────────────────────────────────
st.markdown("<div class='section-label'>Plant growth log — Fenugreek</div>",
            unsafe_allow_html=True)

tab_view, tab_add = st.tabs(["View data", "Add measurement"])

with tab_view:
    growth = fetch_growth()
    if growth:
        gdf = pd.DataFrame(growth)
        gdf["timestamp"] = pd.to_datetime(gdf["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(gdf[["timestamp","condition","day","height_cm","water_ml","notes"]],
                     use_container_width=True, hide_index=True)
        if len(gdf) >= 2:
            fig_g = px.line(gdf, x="day", y="height_cm", color="condition",
                            markers=True,
                            color_discrete_map={"A":"#3b82f6","B":"#f59e0b","C":"#22c55e"},
                            labels={"height_cm":"Height (cm)","day":"Day","condition":"Condition"},
                            title="Plant height by condition")
            fig_g.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                font=dict(family="Plus Jakarta Sans", color="#64748b", size=12),
                title_font=dict(family="Plus Jakarta Sans", size=13, color="#64748b"),
                margin=dict(l=0, r=0, t=36, b=0), height=300,
                xaxis=dict(showgrid=False, title="Day"),
                yaxis=dict(showgrid=True, gridcolor="#f1f5f9", title="Height (cm)"),
                legend=dict(bgcolor="rgba(0,0,0,0)", title=""),
            )
            st.plotly_chart(fig_g, use_container_width=True)
    else:
        st.markdown("<p style='color:#94a3b8;font-size:13px;padding:8px 0;'>"
                    "No growth data yet — add your first measurement below.</p>",
                    unsafe_allow_html=True)

with tab_add:
    ga, gb, gc = st.columns(3)
    with ga:
        g_cond = st.selectbox("Condition", ["A — Open field", "B — Fixed tilt", "C — SolarYield"])
        g_cond = g_cond[0]
    with gb:
        g_day = st.number_input("Day", min_value=1, max_value=42, value=1)
    with gc:
        g_height = st.number_input("Height (cm)", min_value=0.0, value=5.0, step=0.5)
    gd, ge = st.columns(2)
    with gd:
        g_water = st.number_input("Water used (mL)", min_value=0.0, value=0.0, step=10.0)
    with ge:
        g_notes = st.text_input("Notes")
    if st.button("Save measurement"):
        if post_growth(g_cond, int(g_day), g_height, g_water, g_notes):
            st.success("Saved!")
            st.cache_data.clear()
        else:
            st.error("Failed — check API connection")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<hr style='border:none;border-top:1px solid #e8edf2;margin:32px 0 16px'>
<p style='color:#cbd5e1;font-size:11px;text-align:center;letter-spacing:0.08em;'>
    SOLARYIELD &nbsp;·&nbsp; TEAM J-43 &nbsp;·&nbsp;
    YUVABHARATHI INTERNATIONAL SCHOOL &nbsp;·&nbsp; EIC 2026
</p>
""", unsafe_allow_html=True)

if auto_refresh:
    time.sleep(10)
    st.rerun()
