"""
Motion Axis Sizing Calculator — Streamlit app.
Run with:  streamlit run app.py
"""

from dataclasses import asdict, fields
import io
import math
import os
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import extras

from sizing import (ALL_MOTORS, CUBEMARS_R, DRIVES, FAMILIES, INDUSTRIAL, ODRIVE_S1_USD, PRESETS, Inputs, pick_motor,
                    profile_timeseries, size_axis)

# Running on your own Mac (full features) or hosted online (no local folders).
IS_LOCAL = sys.platform == "darwin" or os.environ.get("MOTION_SIZER_LOCAL") == "1"

st.set_page_config(page_title="Motion Axis Sizer", page_icon="⚙️", layout="wide",
                   initial_sidebar_state="expanded")

# --------------------------------------------------------------------------
# Session state: one key per input. Re-assigning each key to itself keeps the
# value alive when a widget is hidden (e.g. ball screw fields while "Belt" is
# selected), so switching drives back and forth doesn't lose your numbers.
# --------------------------------------------------------------------------
DEFAULTS = asdict(Inputs())
DEFAULTS["orientation"] = "Horizontal"
DEFAULTS["use_motor"] = False
DEFAULTS.pop("vertical")
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v
    st.session_state[k] = st.session_state[k]


def load_preset(name: str):
    p = asdict(PRESETS[name])
    st.session_state["orientation"] = "Vertical" if p.pop("vertical") else "Horizontal"
    for k, v in p.items():
        st.session_state[k] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
    st.session_state["use_motor"] = True
    st.session_state["active_preset"] = name


PRESET_INFO = {
    "IC pick-and-place X axis": (
        "The horizontal arm that carries a chip from the tray to the test socket.",
        "Belt drive, 0.7 kg moving, 300 mm in 0.4 s.",
        "Light, fast and long, which is what belts are good at. Watch the inertia ratio."),
    "Vertical Z pick axis": (
        "The up-and-down move that lowers a vacuum nozzle onto a chip.",
        "Ball screw, 0.5 kg moving, 20 mm in 0.1 s, vertical.",
        "Short and very quick, and gravity pulls on it the whole time, so the motor "
        "must hold the load even when stopped."),
    "Heavy shuttle": (
        "A carriage that moves trays or a heavy fixture across the machine.",
        "Ball screw, 6 kg moving, 500 mm in 1 s.",
        "Most of the torque goes into speeding things up. The spinning screw itself "
        "takes more torque than the 6 kg load."),
}


def load_design_cb(path: str):
    d = next(x for x in extras.list_designs() if str(x["_path"]) == path)
    p = dict(d["inputs"])
    st.session_state["orientation"] = "Vertical" if p.pop("vertical", False) else "Horizontal"
    for k, v in p.items():
        if k in DEFAULTS:
            st.session_state[k] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
    st.session_state["use_motor"] = any(p.get(k, 0) > 0 for k in
                                        ("motor_rated_nm", "motor_peak_nm", "motor_max_rpm", "motor_j_kgm2"))
    st.session_state["design_msg"] = f"Loaded design: {d['name']}"


def ds_request(model: str, idx: int):
    st.session_state["ds_pending"] = (model, idx)
    st.session_state.pop("ds_msg", None)


def ds_do(action: str):
    model, idx = st.session_state.pop("ds_pending")
    label, kind, url, fname = extras.docs_for(model)[idx]
    if action == "cancel":
        return
    msgs = []
    try:
        if action in ("save", "both") and kind == "pdf":
            local = extras.local_copy(fname)
            if local:
                msgs.append(f"Already in the datasheets folder: {fname}")
            else:
                local = extras.download_pdf(url, fname)
                msgs.append(f"Saved to datasheets/{fname}")
            if action == "both":
                extras.open_target(local)
                msgs.append("Opened the saved copy.")
        elif action == "open":
            local = extras.local_copy(fname)
            extras.open_target(local if local else url)
            msgs.append("Opened " + ("the saved copy." if local else "it in your browser."))
        st.session_state["ds_msg"] = ("ok", " ".join(msgs))
    except Exception as e:
        st.session_state["ds_msg"] = ("err", f"Couldn't get {label}: {e}. "
                                      f"You can still open it directly: {url}")


def use_catalog_motor(model: str):
    m = next(x for x in ALL_MOTORS if x.model == model)
    st.session_state["motor_rated_nm"] = float(m.rated_nm)
    st.session_state["motor_peak_nm"] = float(m.peak_nm)
    st.session_state["motor_max_rpm"] = float(m.max_rpm)
    st.session_state["motor_j_kgm2"] = float(m.j_kgm2)
    st.session_state["use_motor"] = True


# --------------------------------------------------------------------------
# Look and feel: dark theme with an orange edge glow (.streamlit/config.toml), IBM Plex
# Sans, and an engineering-drawing title block as the page's one bold element.
# --------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@500;600&display=swap');
html, body, .stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea,
.stApp button, .stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stCaptionContainer"],
.stApp [data-testid="stMetricLabel"], .stApp [data-baseweb="tab"], .stApp [data-baseweb="select"] {
  font-family: 'IBM Plex Sans', system-ui, sans-serif;
}
.stApp [data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded' !important; }
h1, h2, h3 { font-family: 'IBM Plex Sans', system-ui, sans-serif; letter-spacing: -0.01em; }
h1 { font-weight: 600 !important; }
.block-container { padding-top: 2.2rem; max-width: 1280px; }
[data-testid="stSidebar"] h2 { font-size: 1.05rem; }
[data-testid="stSidebar"] { min-width: 340px; max-width: 340px; }
[data-testid="stMetricValue"] { font-family: 'IBM Plex Sans Condensed', 'IBM Plex Sans', sans-serif; font-weight: 600; }
.stTabs [data-baseweb="tab-list"] { gap: 1.6rem; border-bottom: 1px solid #2A3A50; }
.stTabs [data-baseweb="tab"] { font-size: 1rem; padding: 0.6rem 0; }
.lede { color: #9FB0C6; font-size: 1.02rem; margin: -0.4rem 0 1.2rem 0; max-width: 70ch; }

/* Orange edge glow: one accent, used on every framed element */
:root { --amber: #F28C28; --amber-soft: rgba(242, 140, 40, 0.16); --glow: 0 0 12px rgba(242, 140, 40, 0.28); }

/* Sidebar input groups: bold border + glow, tinted header strip only */
[data-testid="stSidebar"] [data-testid="stExpander"] details {
  border: 2px solid var(--amber) !important; border-radius: 0.6rem;
  box-shadow: var(--glow); overflow: hidden; }
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
  background: var(--amber-soft); font-weight: 600; }
[data-testid="stSidebar"] [data-testid="stExpander"] details[open] > summary {
  border-bottom: 1px solid rgba(242, 140, 40, 0.45); }
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover { background: rgba(242, 140, 40, 0.24); }

.start-here { display: inline-block; font-weight: 600; font-size: 1.15rem; color: var(--amber);
  border-bottom: 2px solid var(--amber); padding-bottom: 0.15rem; margin: 0.2rem 0 0.4rem 0; }
[data-testid="stSidebar"] .stButton button[kind="primary"] { color: #0E1622; font-weight: 600;
  box-shadow: var(--glow); }

/* Main-area frames get the same glow, softer */
.main [data-testid="stExpander"] details, section[data-testid="stMain"] [data-testid="stExpander"] details {
  border-color: rgba(242, 140, 40, 0.45) !important; box-shadow: 0 0 8px rgba(242, 140, 40, 0.12); }
[data-testid="stMetric"] { border-color: rgba(242, 140, 40, 0.55) !important; box-shadow: var(--glow); }

/* Title block */
.tb { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)) 1.15fr;
      border: 1.5px solid var(--amber); background: #121C2A; margin: 0 0 1.6rem 0; box-shadow: var(--glow); }
.tb > div { padding: 0.55rem 0.8rem; border-right: 1px solid #33445C; min-width: 0; }
.tb > div:last-child { border-right: none; }
.tb .k { font-size: 0.72rem; color: #8FA2BA; margin-bottom: 0.15rem; }
.tb .v { font-family: 'IBM Plex Sans Condensed', 'IBM Plex Sans', sans-serif; font-weight: 600;
         font-size: 1.05rem; color: #E6EDF5; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tb .verdict { display: flex; flex-direction: column; justify-content: center; }
.tb .verdict .v { font-size: 1.35rem; }
.tb .pass { background: #0F3B2A; } .tb .pass .v { color: #5BE0A0; }
.tb .fail { background: #4A1A18; } .tb .fail .v { color: #FF8A80; }
.tb .open { background: #1B2738; } .tb .open .v { color: #9FB0C6; }
@media (max-width: 900px) {
  .tb { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tb > div { border-bottom: 1px solid #33445C; }
}
</style>
""", unsafe_allow_html=True)


def num(label, key, min_value=0.0, step=0.1, fmt="%.3f", help=None):
    st.session_state[key] = float(st.session_state[key])
    return st.number_input(label, key=key, min_value=min_value, step=step,
                           format=fmt, help=help)


# --------------------------------------------------------------------------
# Sidebar: the axis you're sizing
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="start-here">Start here</div>', unsafe_allow_html=True)
    st.markdown("**1. Pick the example closest to your machine.**")
    active = st.session_state.get("active_preset")
    for name in PRESETS:
        st.button(name, on_click=load_preset, args=(name,), width="stretch",
                  type="primary" if name == active else "secondary",
                  help=" ".join(PRESET_INFO[name][:2]))
    with st.expander("Which example should I pick?"):
        for name, (what, spec, lesson) in PRESET_INFO.items():
            st.markdown(f"**{name}**  \n{what}  \n*{spec}*  \n{lesson}")
        st.caption("Not sure? Pick the one that moves most like your axis, then change the "
                   "numbers. An example only fills in starting values.")
    st.markdown("**2. Adjust the numbers below.** The results on the right update as you type.")

    with st.expander("Load", expanded=True):
        num("Payload mass (kg)", "payload_kg", step=0.1)
        num("Carriage / moving mass (kg)", "carriage_kg", step=0.1,
            help="Everything that moves with the payload: carriage, gripper, nozzle, belt clamp.")
        st.radio("Orientation", ["Horizontal", "Vertical"], key="orientation", horizontal=True)
        num("Friction coefficient μ", "mu", step=0.005, fmt="%.4f",
            help="Profile-rail linear guides are about 0.002–0.01. Plain bushings 0.05–0.2.")
        num("External force (N)", "f_ext_n", min_value=None, step=1.0, fmt="%.2f",
            help="Extra constant force the axis pushes against, e.g. a test-contact or press "
                 "force. Applied for the whole cycle.")

    with st.expander("Move", expanded=True):
        num("Stroke (mm)", "stroke_mm", min_value=0.1, step=10.0, fmt="%.1f")
        num("Move time (s)", "move_time_s", min_value=0.001, step=0.05)
        st.session_state["accel_pct"] = float(st.session_state["accel_pct"])
        st.slider("Accel time (% of move time)", 5.0, 50.0, key="accel_pct", step=1.0,
                  help="25% is a common starting point. 50% = triangular profile.")
        st.session_state["s_curve_pct"] = float(st.session_state["s_curve_pct"])
        st.slider("S-curve smoothing (%)", 0.0, 100.0, key="s_curve_pct", step=5.0,
                  help="How gradually acceleration builds up and dies away. 0% = sharp corners "
                       "(trapezoid). Real machines use 30–70% to cut vibration; it raises peak "
                       "acceleration for the same move time.")
        num("Dwell time (s)", "dwell_s", step=0.05,
            help="Time stopped between moves, e.g. while a part is picked or tested.")

    with st.expander("Drive", expanded=True):
        st.selectbox("Drive type", DRIVES, key="drive")
        drive = st.session_state["drive"]
        if drive == "Ball screw":
            num("Lead (mm/rev)", "lead_mm", min_value=0.1, step=1.0, fmt="%.2f")
            num("Screw diameter (mm)", "screw_dia_mm", min_value=0.1, step=1.0, fmt="%.1f")
            num("Screw length (mm)", "screw_len_mm", min_value=1.0, step=10.0, fmt="%.0f")
            num("Screw efficiency η", "screw_eff", min_value=0.05, step=0.01, fmt="%.2f",
                help="Ball screws: 0.85–0.95. Lead (acme) screws: 0.3–0.7.")
        elif drive == "Belt & pulley":
            num("Pulley pitch diameter (mm)", "pulley_pd_mm", min_value=0.1, step=1.0, fmt="%.1f")
            num("Pulley mass, each (kg)", "pulley_kg", step=0.01)
            num("Belt efficiency η", "belt_eff", min_value=0.05, step=0.01, fmt="%.2f")
        else:
            num("Pinion pitch diameter (mm)", "pinion_pd_mm", min_value=0.1, step=1.0, fmt="%.1f")
            num("Pinion mass (kg)", "pinion_kg", step=0.01)
            num("Rack & pinion efficiency η", "rack_eff", min_value=0.05, step=0.01, fmt="%.2f")
        num("Drag torque (N·m)", "drag_nm", step=0.01, fmt="%.3f",
            help="Torque to turn the drive with no load: ball-nut preload, seals, support "
                 "bearings, belt tension. Use the catalog figure. Typical: small ball screw "
                 "0.02–0.1, Ø20+ screw 0.05–0.3, belt drive 0.01–0.05 N·m.")
        num("Gearbox ratio (1 = none)", "gear_ratio", min_value=0.01, step=1.0, fmt="%.2f",
            help="Motor turns per output turn. 5 means the motor spins 5× faster than the screw/pulley.")
        num("Gearbox efficiency", "gear_eff", min_value=0.05, step=0.01, fmt="%.2f",
            help="1.0 if no gearbox. Planetary gearboxes are about 0.90–0.97.")

    with st.expander("Motor to check", expanded=st.session_state["use_motor"]):
        st.checkbox("Check a specific motor", key="use_motor",
                    help="Type values from a datasheet, or load one from the Motor selection tab.")
        if st.session_state["use_motor"]:
            num("Rated (continuous) torque (N·m)", "motor_rated_nm", step=0.01)
            num("Peak torque (N·m)", "motor_peak_nm", step=0.01)
            num("Max speed (rpm)", "motor_max_rpm", step=100.0, fmt="%.0f")
            num("Rotor inertia (kg·m²)", "motor_j_kgm2", step=1e-6, fmt="%.3e",
                help="Datasheets often list this in kg·cm² or g·cm². "
                     "1 kg·cm² = 1e-4 kg·m².  1 g·cm² = 1e-7 kg·m².")

    with st.expander("Design margins"):
        num("Safety factor on torque", "safety_factor", min_value=1.0, step=0.1, fmt="%.2f")
        num("Max inertia ratio (load : motor)", "max_inertia_ratio", min_value=0.1, step=1.0, fmt="%.1f",
            help="10:1 is a common servo rule of thumb; high-performance axes aim for 5:1 or less.")

# --------------------------------------------------------------------------
# Build Inputs and run the engine
# --------------------------------------------------------------------------
vals = {f.name: st.session_state[f.name] for f in fields(Inputs) if f.name in st.session_state}
vals["vertical"] = st.session_state["orientation"] == "Vertical"
if not st.session_state["use_motor"]:
    for k in ("motor_rated_nm", "motor_peak_nm", "motor_max_rpm", "motor_j_kgm2"):
        vals[k] = 0.0
inp = Inputs(**vals)
r = size_axis(inp)
t, pos, vel, acc, tq = profile_timeseries(inp, r)
N = inp.gear_ratio


def eq(formula: str, numbers: str, meaning: str):
    st.latex(formula)
    st.latex(numbers)
    st.markdown(f"*{meaning}*")


def eq(formula: str, numbers: str, meaning: str):
    st.latex(formula)
    st.latex(numbers)
    st.markdown(f"*{meaning}*")


def pct(x):
    return f"{x * 100:.0f}%"


def price_txt(m):
    if m.price is None:
        return "Quote"
    sym = {"USD": "$", "EUR": "€"}.get(m.currency, m.currency + " ")
    return f"{sym}{m.price:,.2f}"


def tightest(x):
    return max(("peak torque", x["peak_use"]), ("continuous torque", x["rms_use"]),
               ("speed", x["speed_use"]), key=lambda t: t[1])


# Motor comparison is computed once and used by several tabs.
rows, _ = pick_motor(inp, ALL_MOTORS)
rows_sorted = sorted(rows, key=lambda x: (not x["ok"], x["motor"].total_usd is None,
                                          x["motor"].total_usd or 0))
passing = [x for x in rows_sorted if x["ok"]]
priced = [x for x in passing if x["motor"].total_usd is not None]
ind_order = {m.model: i for i, m in enumerate(INDUSTRIAL)}
ind_pass = sorted([x for x in rows if x["motor"].family == "Industrial servo" and x["ok"]],
                  key=lambda x: ind_order[x["motor"].model])
cube_order = {m.model: i for i, m in enumerate(CUBEMARS_R)}
cube_pass = sorted([x for x in rows if x["motor"].brand == "CubeMars" and x["ok"]],
                   key=lambda x: cube_order[x["motor"].model])
n_fail = sum(1 for c in r.checks if not c[3])
critical, notes = r.warnings[:n_fail], r.warnings[n_fail:]

# --------------------------------------------------------------------------
# Header + title block
# --------------------------------------------------------------------------
st.title("Motion axis sizer")
st.markdown('<p class="lede">Size the motor for one linear axis of an automation machine: '
            'what torque, speed and inertia it needs, and which real motors can deliver it.</p>',
            unsafe_allow_html=True)

drive_txt = inp.drive + (f" + {N:g}:1 gearbox" if N != 1 else "")
cycles_h = 3600 / r.t_cycle if r.t_cycle > 0 else 0
if r.overall_ok is None:
    v_cls, v_key, v_val = "open", "Motor check", "No motor entered"
else:
    v_cls = "pass" if r.overall_ok else "fail"
    v_key = "Motor check"
    v_val = "PASS" if r.overall_ok else f"FAIL: {n_fail} of {len(r.checks)} checks"
st.markdown(f"""
<div class="tb">
  <div><div class="k">Drive</div><div class="v">{drive_txt}</div></div>
  <div><div class="k">Orientation</div><div class="v">{st.session_state['orientation']}</div></div>
  <div><div class="k">Moving mass</div><div class="v">{r.m_kg:.2f} kg</div></div>
  <div><div class="k">Move</div><div class="v">{inp.stroke_mm:g} mm in {inp.move_time_s:g} s</div></div>
  <div><div class="k">Cycle, out and back</div><div class="v">{r.t_cycle:.2f} s ({cycles_h:,.0f}/h)</div></div>
  <div class="verdict {v_cls}"><div class="k">{v_key}</div><div class="v">{v_val}</div></div>
</div>
""", unsafe_allow_html=True)

tab_res, tab_mot, tab_how, tab_des = st.tabs(
    ["Results", "Motor selection", "How it's calculated", "Designs & report"])

# --------------------------------------------------------------------------
# Tab 1: Results
# --------------------------------------------------------------------------
with tab_res:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Peak torque needed", f"{r.t_peak_req:.3f} N·m",
              help=f"{r.t_peak:.4f} N·m before the {inp.safety_factor:g}× safety factor. "
                   "Must stay below the motor's peak torque.", border=True)
    m2.metric("Continuous (RMS) torque", f"{r.t_rms_req:.3f} N·m",
              help=f"{r.t_rms:.4f} N·m before the safety factor. Must stay below the motor's "
                   "rated torque or it overheats.", border=True)
    m3.metric("Max motor speed", f"{r.rpm_max:,.0f} rpm",
              help=f"Load moves at up to {r.v_max:.3f} m/s.", border=True)
    m4.metric("Inertia ratio", "—" if math.isnan(r.inertia_ratio) else f"{r.inertia_ratio:.1f} : 1",
              help=f"Load : motor rotor. Your limit is {inp.max_inertia_ratio:g}:1. "
                   "Needs the motor's rotor inertia.", border=True)

    for msg in critical:
        st.error(msg)
    if r.checks:
        st.dataframe(pd.DataFrame(
            [{"Motor check": n, "Required": f"{req:.4g}", "Motor / limit": f"{av:.4g}",
              "Result": "PASS ✅" if ok else "FAIL ❌"} for n, req, av, ok in r.checks]),
            hide_index=True, width="stretch")
    if notes:
        with st.expander(f"Engineering notes ({len(notes)})"):
            for msg in notes:
                st.markdown(f"- {msg}")

    st.subheader("Motion and torque over one cycle (out and back)")
    panels = [((1, 1), pos, "#38BDF8", "Position", "Position (mm)"),
              ((1, 2), vel, "#4ADE80", "Velocity", "Velocity (m/s)"),
              ((2, 1), acc, "#F87171", "Acceleration", "Acceleration (m/s²)"),
              ((2, 2), tq, "#FB923C", "Motor torque", "Torque (N·m)")]
    fig = make_subplots(rows=2, cols=2, vertical_spacing=0.2, horizontal_spacing=0.13,
                        subplot_titles=[p[3] for p in panels])
    for (row, col), y, color, _, ytitle in panels:
        fig.add_trace(go.Scatter(x=t, y=y, mode="lines", line=dict(color=color, width=3),
                                 showlegend=False,
                                 hovertemplate="t = %{x:.3f} s<br>%{y:.4g}<extra></extra>"),
                      row=row, col=col)
        fig.update_yaxes(title_text=ytitle, title_standoff=8, row=row, col=col)
        fig.update_xaxes(title_text="Time (s)", title_standoff=6, row=row, col=col)
    if inp.motor_rated_nm > 0:
        for sgn in (1, -1):
            fig.add_hline(y=sgn * inp.motor_rated_nm, line_dash="dot", line_color="#8FA2BA",
                          annotation_text="motor rated" if sgn > 0 else None, row=2, col=2)
    if inp.motor_peak_nm > 0 and inp.motor_peak_nm < 3 * max(abs(tq.max()), abs(tq.min()), 1e-9):
        fig.add_hline(y=inp.motor_peak_nm, line_dash="dash", line_color="#8FA2BA",
                      annotation_text="motor peak", row=2, col=2)
    fig.update_xaxes(showgrid=True, gridcolor="#223047", zeroline=False, range=[0, r.t_cycle],
                     title_font=dict(size=13, color="#9FB0C6"), tickfont=dict(size=11))
    fig.update_yaxes(showgrid=True, gridcolor="#223047", zerolinecolor="#3A4C66",
                     title_font=dict(size=13, color="#9FB0C6"), tickfont=dict(size=11))
    fig.update_annotations(font=dict(size=15, color="#E6EDF5"), yshift=6)
    fig.update_layout(height=760, margin=dict(l=70, r=30, t=70, b=60),
                      paper_bgcolor="#121C2A", plot_bgcolor="#121C2A",
                      font=dict(family="IBM Plex Sans, sans-serif", color="#E6EDF5", size=12))
    st.plotly_chart(fig, theme=None, config={"displaylogo": False})

    st.subheader("Cycle phases")
    st.dataframe(pd.DataFrame([{"Phase": n, "Duration (s)": round(d, 4),
                                "Force on load (N)": round(f, 3),
                                "Motor torque (N·m)": round(tqv, 4)} for n, d, f, tqv in r.phases]),
                 hide_index=True, width="stretch")
    st.caption("Not modeled: how torque falls near a motor's top speed, settling time, belt "
               "and coupling stiffness, positioning accuracy, and component life. The safety "
               "factor covers small unknowns; confirm a final choice in the motor maker's "
               "sizing software.")

# --------------------------------------------------------------------------
# Tab 2: Motor selection
# --------------------------------------------------------------------------
with tab_mot:
    st.markdown("Every motor in the catalog is run against your axis, including its own rotor "
                "inertia. Bigger motors also spend torque spinning themselves up, so bigger "
                "isn't always better.")


    def cost_txt(m):
        if m.total_usd is not None:
            return f"${m.total_usd:,.0f}"
        if m.price is not None and m.currency == "USD":
            return f"${m.price:,.0f} + drive"
        if m.price is not None:
            return f"{price_txt(m)} + driver"
        return "Quote"


    def card(col, title, x, key, empty):
        with col.container(border=True):
            st.markdown(f"**{title}**")
            if x is None:
                st.markdown(empty)
                return
            mm = x["motor"]
            tt = tightest(x)
            drive = "drive included" if mm.drive_included else f"drive {mm.drive_model}"
            st.markdown(f"#### {mm.model}")
            st.markdown(f"**{cost_txt(mm)}**, {mm.supply}, {drive}  \n"
                        f"Tightest limit: {tt[0]} at {pct(tt[1])}  \n"
                        f"Availability: {mm.status}")
            st.button("Use this motor in the motor check", key=key,
                      on_click=use_catalog_motor, args=(mm.model,))


    rc1, rc2 = st.columns(2)
    card(rc1, "Industrial servo: smallest that passes", ind_pass[0] if ind_pass else None,
         "load_ind", "No industrial servo in the catalog passes this axis.")
    card(rc2, "Lowest listed total cost that passes", priced[0] if priced else None,
         "load_cheapest", "None of the priced motors pass this axis.")
    if not passing:
        st.error("No motor in the catalog passes. Try a gearbox (multiplies torque, divides "
                 "reflected inertia), a longer move or accel time, or a finer screw lead or "
                 "smaller pulley if speed isn't the problem.")

    st.subheader("All motors")
    fam = st.radio("Show", ["All", *FAMILIES], horizontal=True, key="fam_filter", label_visibility="collapsed")
    shown = [x for x in rows_sorted if fam in (None, "All") or x["motor"].family == fam]
    st.dataframe(pd.DataFrame([{
        "Motor": x["motor"].model,
        "Result": "PASS ✅" if x["ok"] else "FAIL ❌",
        "Total cost": cost_txt(x["motor"]),
        "Peak torque used": pct(x["peak_use"]),
        "Continuous used": pct(x["rms_use"]),
        "Speed used": pct(x["speed_use"]),
        "Inertia ratio": f"{x['result'].inertia_ratio:.2f} : 1",
        "Fails on": ", ".join(x["fails"]) or "—",
        "Type": x["motor"].family,
        "Supply": x["motor"].supply,
        "Drive": ("Included" if x["motor"].drive_included else
                  x["motor"].drive_model + (f" (${x['motor'].drive_usd:,.0f})" if x["motor"].drive_usd else " (quote)")),
        "Rated / peak (N·m)": f"{x['motor'].rated_nm} / {x['motor'].peak_nm}",
        "Max speed (rpm)": f"{x['motor'].max_rpm:,.0f}",
        "Rotor inertia (g·cm²)": ("≈" if x["motor"].j_estimated else "") + f"{x['motor'].j_kgm2 * 1e7:,.0f}",
        "Availability": x["motor"].status,
        "Source": x["motor"].url,
    } for x in shown]), hide_index=True, width="stretch",
        column_config={"Source": st.column_config.LinkColumn("Source", display_text="Open")})
    st.caption("Sorted: passing first, then by listed total cost. % used = what the axis needs "
               "(with safety factor) ÷ what the motor can do. Industrial servos run on 200 V AC "
               "with a matching drive; prices are new-unit distributor list prices, and most "
               "makers sell through distributors on quote. Budget kits include their drive. "
               f"CubeMars robotics motors need a 48 V driver (ODrive S1, ${ODRIVE_S1_USD:.0f}). "
               "≈ = estimated rotor inertia. Checked online 2026-11-12; prices change.")

    st.subheader("Datasheets")
    model_names = [x["motor"].model for x in rows_sorted]
    default_model = priced[0]["motor"].model if priced else model_names[0]
    if not IS_LOCAL:
        st.caption("Open the manufacturer's datasheet or product page for any motor in the table.")
        dc1, dc2 = st.columns(2)
        ds_model = dc1.selectbox("Motor", model_names, index=model_names.index(default_model), key="ds_model")
        ds_docs = extras.docs_for(ds_model)
        ds_idx = dc2.selectbox("Document", range(len(ds_docs)), key="ds_doc",
                               format_func=lambda i: f"{ds_docs[i][0]} ({'PDF' if ds_docs[i][1] == 'pdf' else 'web page'})")
        st.link_button("Open datasheet", ds_docs[ds_idx][2])
    else:
        st.caption("Nothing downloads automatically. Choose a motor and document, click Get datasheet, "
                   "then open it, save it into the datasheets folder, or both. Saved files are reused.")
        dc1, dc2 = st.columns(2)
        ds_model = dc1.selectbox("Motor", model_names, index=model_names.index(default_model), key="ds_model")
        ds_docs = extras.docs_for(ds_model)
        ds_labels = [f"{lab} ({'PDF' if kind == 'pdf' else 'web page'})"
                     + ("  ✓ saved" if extras.local_copy(fn) else "") for lab, kind, _, fn in ds_docs]
        ds_idx = dc2.selectbox("Document", range(len(ds_docs)), format_func=lambda i: ds_labels[i], key="ds_doc")
        st.button("Get datasheet", on_click=ds_request, args=(ds_model, ds_idx))
        pend = st.session_state.get("ds_pending")
        if pend:
            p_model, p_idx = pend
            lab, kind, url, fn = extras.docs_for(p_model)[p_idx]
            with st.container(border=True):
                st.markdown(f"**{lab}** for {p_model}  \n<{url}>")
                if kind == "pdf":
                    st.write("How do you want this datasheet?")
                    b1, b2, b3, b4 = st.columns(4)
                    b1.button("Open it", on_click=ds_do, args=("open",), key="ds_open")
                    b2.button("Save to datasheets folder", on_click=ds_do, args=("save",), key="ds_save")
                    b3.button("Both", on_click=ds_do, args=("both",), key="ds_both")
                    b4.button("Cancel", on_click=ds_do, args=("cancel",), key="ds_cancel")
                else:
                    st.write("This one is a web page (no PDF published), so it can only be opened.")
                    b1, b2 = st.columns(2)
                    b1.button("Open it", on_click=ds_do, args=("open",), key="ds_open")
                    b2.button("Cancel", on_click=ds_do, args=("cancel",), key="ds_cancel")
    msg = st.session_state.get("ds_msg")
    if msg:
        (st.success if msg[0] == "ok" else st.error)(msg[1])

# --------------------------------------------------------------------------
# Tab 3: How it's calculated
# --------------------------------------------------------------------------
with tab_how:
    st.markdown("Each step uses the result of the one before. Open a step to see the formula, "
                "your numbers plugged in, and what it means physically.")

    with st.expander("Step 1: Motion profile (S-curve)"):
        S = inp.stroke_mm / 1000
        eq(r"t_a = \text{accel\%} \times t_{move}",
           rf"t_a = {inp.accel_pct/100:.2f} \times {inp.move_time_s:.3f} = {r.t_acc:.4f}\ \text{{s}}",
           "Time spent speeding up. Slowing down takes the same time.")
        eq(r"v_{max} = \dfrac{S}{t_{move} - t_a}",
           rf"v_{{max}} = \dfrac{{{S:.4f}}}{{{inp.move_time_s:.3f} - {r.t_acc:.4f}}} = {r.v_max:.4f}\ \text{{m/s}}",
           "Whatever the shape of a symmetric speed-up, the load covers half of v·t_a while "
           "accelerating, so top speed only depends on stroke, move time and accel time.")
        eq(r"t_j = \dfrac{s}{2}\,t_a \qquad a_{peak} = \dfrac{v_{max}}{t_a - t_j}",
           rf"t_j = \dfrac{{{inp.s_curve_pct/100:.2f}}}{{2}} \times {r.t_acc:.4f} = {r.t_jerk:.4f}\ \text{{s}}"
           rf"\qquad a_{{peak}} = \dfrac{{{r.v_max:.4f}}}{{{r.t_acc:.4f} - {r.t_jerk:.4f}}} = {r.a:.3f}\ \text{{m/s}}^2 \;({r.a/9.81:.2f}\,g)",
           f"With S-curve smoothing s, acceleration ramps up over t_j and down over t_j instead "
           f"of switching on instantly. That's gentler on the machine but needs a higher peak: "
           f"{r.a:.3f} vs {r.a_trap:.3f} m/s² for a sharp-cornered profile.")
        st.markdown(f"*One cycle is move out, dwell, move back, dwell: "
                    f"2 × ({inp.move_time_s:g} + {inp.dwell_s:g}) = {r.t_cycle:.3f} s.*")

    with st.expander("Step 2: Forces on the load"):
        if inp.vertical:
            eq(r"F_{gravity} = m\,g",
               rf"F_{{gravity}} = {r.m_kg:.3f} \times 9.81 = {r.f_gravity:.3f}\ \text{{N}}",
               "On a vertical axis the motor lifts the whole moving mass. Guide friction is "
               "near zero because the load doesn't press on the rails, so it's ignored. "
               "Moving up is the worst case, so that's what's sized.")
        else:
            eq(r"F_{friction} = \mu\,m\,g",
               rf"F_{{friction}} = {inp.mu:.4f} \times {r.m_kg:.3f} \times 9.81 = {r.f_friction:.4f}\ \text{{N}}",
               "Rolling friction in the linear guides while the axis moves. There is no "
               "sliding friction while it's stopped.")
        eq(r"F_{const} = F_{friction} + F_{gravity} + F_{ext}",
           rf"F_{{const}} = {r.f_friction:.3f} + {r.f_gravity:.3f} + {r.f_ext:.3f} = {r.f_const:.3f}\ \text{{N}}",
           "The steady force the drive must push against whenever the axis is moving.")
        eq(r"F_{accel} = m\,a_{peak}",
           rf"F_{{accel}} = {r.m_kg:.3f} \times {r.a:.3f} = {r.f_accel:.3f}\ \text{{N}}",
           "Newton's second law: the extra force needed to speed the mass up (and the "
           "force it gives back while slowing down).")
        st.latex(rf"T_{{drag}} = {inp.drag_nm:.3f}\ \text{{N·m at the drive shaft}}")
        st.markdown("*Drag torque is a fixed torque to turn the drive at all: ball-nut preload, "
                    "seals, support bearings or belt tension. Like friction, it always opposes "
                    "motion. On small axes it is often bigger than the load friction.*")

    with st.expander("Step 3: Converting linear to rotary: the transmission constant k"):
        if inp.drive == "Ball screw":
            eq(r"k = \dfrac{\text{lead}}{2\pi}",
               rf"k = \dfrac{{{inp.lead_mm/1000:.4f}}}{{2\pi}} = {r.k:.6f}\ \text{{m/rad}}",
               "One screw revolution (2π rad) moves the nut one lead. So k is the travel per "
               "radian of screw rotation.")
        else:
            pd_mm = inp.pulley_pd_mm if inp.drive == "Belt & pulley" else inp.pinion_pd_mm
            eq(r"k = r = \dfrac{d_{pitch}}{2}",
               rf"k = \dfrac{{{pd_mm/1000:.4f}}}{{2}} = {r.k:.5f}\ \text{{m/rad}}",
               "A belt or rack moves the pitch radius for every radian the pulley or pinion "
               "turns, just like a wheel rolling on the ground.")
        st.markdown("**Every drive type reduces to this one number.** Once you know k:")
        st.latex(r"v = k\,\omega \qquad F = \dfrac{T}{k} \qquad J_{reflected} = m\,k^2")
        st.markdown("*Small k (fine lead, small pulley) gives more force per unit torque "
                    "but needs more motor rpm. That trade-off is the core of drive selection.*")

    with st.expander("Step 4: Reflected inertia at the motor"):
        eq(r"J_{mass} = m\,k^2",
           rf"J_{{mass}} = {r.m_kg:.3f} \times ({r.k:.5g})^2 = {r.j_mass:.4e}\ \text{{kg·m}}^2",
           "How 'heavy' the linear load feels to the motor, expressed as rotational inertia.")
        if inp.drive == "Ball screw":
            eq(r"J_{screw} = \dfrac{\pi\,\rho\,L\,D^4}{32}",
               rf"J_{{screw}} = \dfrac{{\pi \times 7850 \times {inp.screw_len_mm/1000:.3f} \times "
               rf"({inp.screw_dia_mm/1000:.4f})^4}}{{32}} = {r.j_drive:.4e}\ \text{{kg·m}}^2",
               "A steel screw is a spinning solid cylinder. Inertia grows with diameter to the "
               "4th power, so a fatter screw quickly dominates the inertia.")
        elif inp.drive == "Belt & pulley":
            eq(r"J_{pulleys} = 2 \times \tfrac{1}{2}\,m_p\,r^2",
               rf"J_{{pulleys}} = 2 \times 0.5 \times {inp.pulley_kg:.3f} \times ({r.k:.4f})^2 = {r.j_drive:.4e}\ \text{{kg·m}}^2",
               "Drive pulley plus idler pulley, each treated as a solid disc.")
        else:
            eq(r"J_{pinion} = \tfrac{1}{2}\,m_p\,r^2",
               rf"J_{{pinion}} = 0.5 \times {inp.pinion_kg:.3f} \times ({r.k:.4f})^2 = {r.j_drive:.4e}\ \text{{kg·m}}^2",
               "The pinion treated as a solid disc.")
        eq(r"J_{load} = \dfrac{J_{mass} + J_{drive}}{N^2}",
           rf"J_{{load}} = \dfrac{{{r.j_mass:.4e} + {r.j_drive:.4e}}}{{{N:.2f}^2}} = {r.j_load:.4e}\ \text{{kg·m}}^2",
           "A gearbox divides reflected inertia by the ratio squared. That's why a small "
           "gearbox fixes a bad inertia ratio so effectively.")
        if r.j_motor > 0:
            eq(r"\text{Inertia ratio} = \dfrac{J_{load}}{J_{motor}}",
               rf"\dfrac{{{r.j_load:.4e}}}{{{r.j_motor:.4e}}} = {r.inertia_ratio:.2f} : 1",
               "If the load is much heavier than the motor's own rotor, the servo struggles to "
               "control it tightly: overshoot, ringing, slow settling. Below about 10:1 is a common target.")

    with st.expander("Step 5: Motor speed"):
        eq(r"\omega_{motor} = \dfrac{v_{max}}{k}\,N",
           rf"\omega = \dfrac{{{r.v_max:.4f}}}{{{r.k:.5g}}} \times {N:.2f} = {r.omega_max:.2f}\ \text{{rad/s}}",
           "Linear speed converted to shaft speed, then multiplied up through the gearbox.")
        eq(r"\text{rpm} = \omega \times \dfrac{60}{2\pi}",
           rf"\text{{rpm}} = {r.omega_max:.2f} \times 9.549 = {r.rpm_max:,.0f}",
           "Most servo motors top out around 3000–6000 rpm.")
        eq(r"\alpha = \dfrac{a}{k}\,N",
           rf"\alpha = \dfrac{{{r.a:.3f}}}{{{r.k:.5g}}} \times {N:.2f} = {r.alpha:.1f}\ \text{{rad/s}}^2",
           "Angular acceleration of the motor shaft.")

    with st.expander("Step 6: Torque at the motor"):
        eq(r"T_{shaft} = F\,k + T_{drag}",
           rf"T_{{shaft,const}} = {r.f_const:.3f} \times {r.k:.5g} + {inp.drag_nm:.3f} = {r.f_const * r.k + inp.drag_nm:.5f}\ \text{{N·m}}",
           "Force on the load turned into torque at the screw, pulley or pinion, plus the "
           "drive's own drag. Shown here for moving out at constant speed.")
        eq(r"T_{motor} = \dfrac{T_{shaft}}{\eta\,N}\ \text{(motor driving)} \qquad "
           r"T_{motor} = \dfrac{T_{shaft}\,\eta}{N}\ \text{(load driving)}",
           rf"T_{{const}} = \dfrac{{{r.f_const * r.k + inp.drag_nm:.5f}}}{{{r.eff_total:.3f} \times {N:.2f}}} = {r.t_const_phase:.5f}\ \text{{N·m}}",
           "Losses always cost the motor. When the motor pushes the load, it supplies the "
           "losses too (divide by η). When the load pushes back, while braking or lowering a "
           "vertical load, losses absorb part of it (multiply by η).")
        eq(r"T_{spin} = \left(\dfrac{J_{drive}}{N^2} + J_{motor}\right)\alpha",
           rf"T_{{spin}} = \left({r.j_drive / N**2:.4e} + {r.j_motor:.4e}\right) \times {r.alpha:.1f} = {(r.j_drive / N**2 + r.j_motor) * r.alpha:.5f}\ \text{{N·m}}",
           "Extra torque at peak acceleration to spin up the screw or pulleys and the motor's "
           "own rotor. The moving mass is already included in F.")
        st.latex(rf"T_{{accel,peak}} = {r.t_accel_phase:.5f} \quad T_{{const}} = {r.t_const_phase:.5f} \quad "
                 rf"T_{{decel,peak}} = {r.t_decel_phase:.5f} \quad T_{{dwell}} = {r.t_dwell_phase:.5f}\ \text{{N·m}}")
        if inp.vertical:
            st.markdown(f"*Moving back down, gravity helps: steady torque is "
                        f"{r.t_back_const:.5f} N·m instead of {r.t_const_phase:.5f} N·m going up. "
                        "During dwell the motor holds the load against gravity.*")
        st.markdown("*The app evaluates these at 6,000 points through the cycle, so the S-curve "
                    "ramps and every change of direction are included.*")

    with st.expander("Step 7: Peak and RMS torque"):
        eq(r"T_{rms} = \sqrt{\dfrac{1}{t_{cycle}}\int_0^{t_{cycle}} T(t)^2\,dt}",
           rf"T_{{rms}} = \sqrt{{\dfrac{{1}}{{{r.t_cycle:.3f}}}\int_0^{{{r.t_cycle:.3f}}} T(t)^2\,dt}} = {r.t_rms:.5f}\ \text{{N·m}}",
           "RMS torque is the motor's 'average heating' torque. Motor heat goes with current "
           "squared, and current is proportional to torque. RMS must stay below the "
           "continuous (rated) torque or the motor overheats over time.")
        eq(r"T_{peak} = \max |T_i|",
           rf"T_{{peak}} = {r.t_peak:.5f}\ \text{{N·m}}",
           "The highest torque in the cycle, usually during acceleration. Must stay below the "
           "motor's peak (intermittent) torque.")
        eq(r"T_{required} = T \times SF",
           rf"T_{{peak,req}} = {r.t_peak:.4f} \times {inp.safety_factor:.2f} = {r.t_peak_req:.4f}"
           rf"\qquad T_{{rms,req}} = {r.t_rms:.4f} \times {inp.safety_factor:.2f} = {r.t_rms_req:.4f}",
           "Margin covers what the model leaves out: coupling inertia, cable carriers, "
           "torque fall-off near top speed, and tuning.")


# --------------------------------------------------------------------------
# Tab 4: Designs & report
# --------------------------------------------------------------------------
with tab_des:
    st.markdown("Save the current design, compare saved designs side by side, or export a "
                "one-page PDF report to bring to a review or interview.")
    if not IS_LOCAL:
        st.info("You're using the online version. Saved designs are kept only until the app "
                "restarts, so download the PDF report or CSV to keep your results.")
    if st.session_state.get("design_msg"):
        st.success(st.session_state.pop("design_msg"))
    sc1, sc2 = st.columns([2, 3])
    d_name = sc1.text_input("Design name", placeholder="e.g. Pick X axis, belt, 0.7 kg")
    d_notes = sc2.text_input("Notes (optional)", placeholder="what you changed or why")
    cs1, cs2 = st.columns(2)
    if cs1.button("Save this design", type="primary", disabled=not d_name.strip()):
        p = extras.save_design(d_name, inp, d_notes)
        st.success(f"Saved to designs/{p.name}")
    cs2.download_button("Download PDF report", extras.build_report(inp, d_name.strip() or "Motion axis sizing report"),
                        file_name=f"{(d_name.strip() or 'motion_sizing_report').replace(' ', '_')}.pdf",
                        mime="application/pdf")

    saved = extras.list_designs()
    if saved:
        st.subheader("Saved designs")
        labels = {str(d["_path"]): f"{d['name']}  ({d['saved'][:16].replace('T', ' ')})" for d in saved}
        picked = st.multiselect("Pick designs to compare side by side", list(labels),
                                default=list(labels)[-min(3, len(labels)):], format_func=lambda k: labels[k])
        if picked:
            by_path = {str(d["_path"]): d for d in saved}
            table = {by_path[k]["name"]: extras.summarize(extras.design_inputs(by_path[k])) for k in picked}
            for k in picked:
                table[by_path[k]["name"]]["Notes"] = by_path[k].get("notes", "")
            st.dataframe(pd.DataFrame(table).astype(str), width="stretch")
            lc1, lc2 = st.columns(2)
            to_load = lc1.selectbox("Load a saved design back into the inputs", picked,
                                    format_func=lambda k: labels[k], key="to_load")
            lc1.button("Load design", on_click=load_design_cb, args=(to_load,))
            to_del = lc2.selectbox("Delete a saved design", picked, format_func=lambda k: labels[k], key="to_del")
            if lc2.button("Delete design"):
                st.session_state["confirm_del"] = to_del
            if st.session_state.get("confirm_del"):
                k = st.session_state["confirm_del"]
                st.warning(f"Delete '{labels.get(k, k)}'? This can't be undone.")
                y, n = st.columns(2)
                if y.button("Yes, delete"):
                    extras.delete_design(by_path[k])
                    st.session_state.pop("confirm_del")
                    st.rerun()
                if n.button("Keep it"):
                    st.session_state.pop("confirm_del")
                    st.rerun()
    else:
        st.caption("No saved designs yet. Name the current design and click Save; designs are "
                   "stored as small files in the designs folder.")


    csv_rows = [("Input", k, v) for k, v in asdict(inp).items()]
    csv_rows += [("Result", k, v) for k, v in [
        ("moving_mass_kg", r.m_kg), ("v_max_m_s", r.v_max), ("accel_m_s2", r.a),
        ("k_m_per_rad", r.k), ("J_load_kgm2", r.j_load), ("J_motor_kgm2", r.j_motor),
        ("inertia_ratio", r.inertia_ratio), ("rpm_max", r.rpm_max),
        ("T_peak_Nm", r.t_peak), ("T_rms_Nm", r.t_rms),
        ("T_peak_required_Nm", r.t_peak_req), ("T_rms_required_Nm", r.t_rms_req),
        ("motor_check", "n/a" if r.overall_ok is None else ("PASS" if r.overall_ok else "FAIL"))]]
    csv_rows += [("Phase", n, f"{d:.4f} s | {f:.3f} N | {tv:.5f} N·m") for n, d, f, tv in r.phases]
    buf = io.StringIO()
    pd.DataFrame(csv_rows, columns=["Section", "Item", "Value"]).to_csv(buf, index=False)
    st.download_button("Download results as CSV", buf.getvalue(),
                       file_name="motion_sizing_results.csv", mime="text/csv")

    st.caption("Simplified model for early sizing. Confirm final selections with the motor "
               "and drive manufacturers' sizing tools.")

