"""
Extras for the Motion Axis Sizer:
  - Datasheet links per motor, and on-demand download into ./datasheets
  - Save / load / compare designs (JSON files in ./designs)
  - One-page PDF report

Nothing here downloads anything unless the user clicks a button in the app.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import shutil
import subprocess
import urllib.request
from dataclasses import asdict, fields
from pathlib import Path

from sizing import ALL_MOTORS, Inputs, pick_motor, size_axis

HERE = Path(__file__).resolve().parent
DATASHEET_DIR = HERE / "datasheets"
DESIGN_DIR = HERE / "designs"

# ---------------------------------------------------------------------------
# Datasheets. kind = "pdf" (can be saved) or "page" (web page: open only).
# ---------------------------------------------------------------------------
DOCS = {
    "CubeMars R60 KV115": [
        ("R60 product page (full spec table)", "page",
         "https://www.cubemars.com/goods-943-R60.html", None),
    ],
    "CubeMars RO60 KV115": [
        ("RO60 KV115 datasheet", "pdf",
         "https://img.cubemars.com/products/cubemars-product-parameter/RO60-KV115.pdf",
         "CubeMars_RO60-KV115.pdf"),
    ],
    "CubeMars RO80 KV105": [
        ("RO80 Lite KV105 datasheet (Standard version is similar, with Hall)", "pdf",
         "https://img.cubemars.com/products/cubemars-product-parameter/RO80-LITE-KV105.pdf",
         "CubeMars_RO80-LITE-KV105.pdf"),
    ],
    "CubeMars R80 KV110": [
        ("R80 product page", "page", "https://cubemars.com/goods-944-R80+KV110.html", None),
    ],
    "CubeMars R100 KV90": [
        ("R100 product page", "page", "https://www.cubemars.com/goods-945-R100%2BKV90.html", None),
        ("R100 Hall sensor instructions", "pdf",
         "https://ozrobotics.com/wp-content/uploads/2021/09/Instructions-for-the-Hall-Sensor.pdf",
         "CubeMars_R100_Hall_Sensor_Instructions.pdf"),
    ],
    "StepperOnline T6 400W kit (T6-RS400H2A3-M17S)": [
        ("T6 400 W motor drawing", "pdf",
         "https://files.omc-stepperonline.com/T6M60-400H2A3-M17S.pdf",
         "StepperOnline_T6M60-400H2A3-M17S_drawing.pdf"),
        ("T6 servo simple manual", "pdf",
         "https://files.omc-stepperonline.com/T6_Servo_Simple_Manual.pdf",
         "StepperOnline_T6_Servo_Simple_Manual.pdf"),
    ],
    "StepperOnline T6 1000W kit (T6-RS1000H2A3-M17S)": [
        ("T6 1000 W motor drawing (brake version)", "pdf",
         "https://files.omc-stepperonline.com/T6M80-1000H2B3-M17S.pdf",
         "StepperOnline_T6M80-1000H2B3-M17S_drawing.pdf"),
        ("T6 servo simple manual", "pdf",
         "https://files.omc-stepperonline.com/T6_Servo_Simple_Manual.pdf",
         "StepperOnline_T6_Servo_Simple_Manual.pdf"),
    ],
}
DOCS.update({
    "Yaskawa SGM7J-02A (200 W)": [
        ("Yaskawa SGM7J-02 product page (ratings)", "page",
         "https://www.yaskawa.eu.com/motion-control/Sigma-7/s7-rotary-servomotors/productdetail/product/sgm7j-02dff21_6842", None),
        ("Seller listing (Automation Distribution)", "page",
         "https://automationdistribution.com/yaskawa-sgm7j-02afa61-s7-motor-200w-200v-incremental-keyed-tapered-shaft/", None),
    ],
    "Yaskawa SGM7J-04A (400 W)": [
        ("Yaskawa SGM7J-04 product page (ratings)", "page",
         "https://www.yaskawa.eu.com/motion-control/Sigma-7/s7-rotary-servomotors/productdetail/product/sgm7j-04afa6s_1966", None),
        ("Seller listing (Automation Distribution)", "page",
         "https://automationdistribution.com/yaskawa-sgm7j-04afa6s-s7-motor-400w-200v-incremental-keyed-taper-shaft/", None),
    ],
    "Panasonic MSMF022 (200 W)": [
        ("Distributor spec page (Powermatic)", "page",
         "https://powermatic.net/part/panasonic/msmf022l1u2/2774006", None),
    ],
    "Panasonic MSMF042 (400 W)": [
        ("Panasonic MSMF042 product page (ratings)", "page",
         "https://industry.panasonic.com/ap/en/products/motor/fa-motor/ac-servo/number/msmf042l1t2", None),
        ("Seller listing (e-motionsupply)", "page",
         "https://www.e-motionsupply.com/Panasonic_AC_Servo_Motors_MSMF042L1U2M_p/msmf042l1u2m.htm", None),
    ],
    "Mitsubishi HG-KN23 (200 W)": [
        ("Mitsubishi HG-KN specifications", "page",
         "https://us.mitsubishielectric.com/fa/en/products/drive-products/ac-servos-melservo/mrje/motor/specifications/", None),
    ],
    "Mitsubishi HG-KN43 (400 W)": [
        ("Mitsubishi HG-KN specifications", "page",
         "https://us.mitsubishielectric.com/fa/en/products/drive-products/ac-servos-melservo/mrje/motor/specifications/", None),
    ],
    "Mitsubishi HG-KN73 (750 W)": [
        ("Mitsubishi HG-KN specifications", "page",
         "https://us.mitsubishielectric.com/fa/en/products/drive-products/ac-servos-melservo/mrje/motor/specifications/", None),
    ],
})
_AD_MOTORS = ("AutomationDirect SureServo2 motor specs (all 230 V motors)", "pdf",
              "https://cdn.automationdirect.com/static/specs/ss2motors.pdf",
              "AutomationDirect_SureServo2_motors.pdf")
_AD_GUIDE = ("SureServo2 selection guide with list prices (June 2025)", "pdf",
             "https://cdn.automationdirect.com/static/archive/specs/ss2selection-2025-06-11--01-30-34.pdf",
             "AutomationDirect_SureServo2_selection_2025-06.pdf")
_DELTA = ("Delta ASDA-B3 catalog", "pdf",
          "https://www.mouser.com/datasheet/2/632/DELTA_IA_ASDA_ASDA_B3_C_EN_20230523_web-3318784.pdf",
          "Delta_ASDA-B3_catalog.pdf")
DOCS.update({
    "AutomationDirect SV2L-202N (200 W)": [_AD_MOTORS, _AD_GUIDE],
    "AutomationDirect SV2L-202B (200 W, brake)": [
        ("SV2L-202B product page (price)", "page",
         "https://www.automationdirect.com/adc/shopping/catalog/motion_control/sureservo2_(sv2a_series)_servo_systems/115-z-230v_servo_motors,_drives,_motor_cables/sv2l-202b", None),
        ("SV2L-202B cut sheet", "pdf",
         "https://cdn.automationdirect.com/static/specs/cutsheet/SV2L-202B_cutsheet.pdf",
         "AutomationDirect_SV2L-202B_cutsheet.pdf"),
        _AD_MOTORS],
    "AutomationDirect SV2L-204N (400 W)": [_AD_MOTORS, _AD_GUIDE],
    "AutomationDirect SV2L-207N (750 W)": [
        ("SV2L-207B cut sheet (brake version)", "pdf",
         "https://cdn.automationdirect.com/static/specs/cutsheet/SV2L-207B_cutsheet.pdf",
         "AutomationDirect_SV2L-207B_cutsheet.pdf"),
        _AD_MOTORS, _AD_GUIDE],
    "Delta ECM-B3M-C20602 (200 W)": [_DELTA],
    "Delta ECM-B3M-C20604 (400 W)": [
        _DELTA,
        ("DigiKey listing (price)", "page",
         "https://www.digikey.ca/en/products/detail/delta-electronics-industrial-automation/ECM-B3M-C20604RS1/21852603", None)],
    "Delta ECM-B3M-C20807 (750 W)": [_DELTA],
    "Omron R88M-1M40030T (400 W)": [
        ("RS listing (specs and price)", "page", "https://nz.rs-online.com/web/p/servo-motors/1362816", None)],
    "Leadshine ELM2H-0400LA60F (400 W)": [
        ("Leadshine ELM2H-0400LA60F product page", "page",
         "https://www.leadshine.com/product-detail/ELM2H-0400LA60F.html", None)],
    "Teknic ClearPath CPM-SDSK-2321S": [
        ("Teknic model page (price, torque-speed curve)", "page",
         "https://teknic.com/model-info/CPM-SDSK-2321S-RLN/", None),
        ("Reseller spec summary (Automation Technologies)", "page",
         "https://www.automationtechnologiesinc.com/products-page/servo-products/clearpath-cpm-sdsk-2321s-rln", None)],
})
DOCS["StepperOnline T6 400W kit"] = DOCS.pop("StepperOnline T6 400W kit (T6-RS400H2A3-M17S)")
DOCS["StepperOnline T6 1000W kit"] = DOCS.pop("StepperOnline T6 1000W kit (T6-RS1000H2A3-M17S)")
DRIVER_DOC = ("ODrive S1 driver datasheet (for CubeMars motors)", "page",
              "https://docs.odriverobotics.com/v/latest/hardware/s1-datasheet.html", None)


def docs_for(model: str):
    d = list(DOCS.get(model, []))
    if model.startswith("CubeMars"):
        d.append(DRIVER_DOC)
    return d


def local_copy(filename: str | None) -> Path | None:
    if not filename:
        return None
    p = DATASHEET_DIR / filename
    return p if p.exists() and p.stat().st_size > 0 else None


def download_pdf(url: str, filename: str) -> Path:
    """Download a PDF into ./datasheets. Uses the Mac's curl first (most reliable
    with the system certificates), then Python as a fallback. Raises on failure."""
    DATASHEET_DIR.mkdir(exist_ok=True)
    dest = DATASHEET_DIR / filename
    tmp = dest.with_suffix(".part")
    ua = "Mozilla/5.0 (Macintosh) MotionAxisSizer/1.0"
    ok = False
    if shutil.which("curl"):
        r = subprocess.run(["curl", "-fsSL", "-A", ua, "--max-time", "60", "-o", str(tmp), url],
                           capture_output=True, text=True)
        ok = r.returncode == 0
    if not ok:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
            shutil.copyfileobj(resp, f)
    with open(tmp, "rb") as f:
        head = f.read(5)
    if head != b"%PDF-":
        tmp.unlink(missing_ok=True)
        raise ValueError("The link didn't return a PDF (the site may have moved it). "
                         "Use Open instead.")
    tmp.replace(dest)
    return dest


def open_target(target: str | Path):
    """Open a URL or local file with the Mac's default app (browser / Preview)."""
    target = str(target)
    if shutil.which("open"):
        subprocess.run(["open", target], check=False)
    else:
        import webbrowser
        webbrowser.open(target if target.startswith("http") else Path(target).as_uri())


# ---------------------------------------------------------------------------
# Designs
# ---------------------------------------------------------------------------
def _slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9 _-]+", "", name).strip().replace(" ", "_")
    return s[:60] or "design"


def save_design(name: str, inp: Inputs, notes: str = "") -> Path:
    DESIGN_DIR.mkdir(exist_ok=True)
    data = {"name": name.strip(), "saved": _dt.datetime.now().isoformat(timespec="seconds"),
            "notes": notes, "inputs": asdict(inp)}
    p = DESIGN_DIR / f"{_slug(name)}.json"
    p.write_text(json.dumps(data, indent=2))
    return p


def list_designs():
    if not DESIGN_DIR.exists():
        return []
    out = []
    for p in sorted(DESIGN_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            d["_path"] = p
            out.append(d)
        except Exception:
            continue
    return out


def design_inputs(d) -> Inputs:
    valid = {f.name for f in fields(Inputs)}
    return Inputs(**{k: v for k, v in d["inputs"].items() if k in valid})


def delete_design(d):
    Path(d["_path"]).unlink()


def summarize(inp: Inputs):
    """Key numbers for one design (used by the compare table and the report)."""
    r = size_axis(inp)
    rows, picks = pick_motor(inp, ALL_MOTORS)
    cheapest, robust = picks["cheapest"], picks["robust"]
    return {
        "Drive": inp.drive + (f" + {inp.gear_ratio:g}:1 gearbox" if inp.gear_ratio != 1 else ""),
        "Orientation": "Vertical" if inp.vertical else "Horizontal",
        "Moving mass (kg)": round(r.m_kg, 3),
        "Move": f"{inp.stroke_mm:g} mm in {inp.move_time_s:g} s",
        "Dwell (s)": inp.dwell_s,
        "Peak accel (g)": round(r.a / 9.81, 2),
        "Max motor speed (rpm)": round(r.rpm_max),
        "Peak torque req. (N·m)": round(r.t_peak_req, 4),
        "RMS torque req. (N·m)": round(r.t_rms_req, 4),
        "Motor entered": ("Passes prelim. checks" if r.overall_ok else "Fails") if r.overall_ok is not None else "none",
        "Cheapest passing motor": cheapest["motor"].model if cheapest else "none in catalog",
        "Its total cost (USD)": round(cheapest["motor"].total_usd, 2) if cheapest else None,
        "Most robust passing motor": robust["motor"].model if robust else "none in catalog",
        "Motors passing": f"{sum(x['ok'] for x in rows)} of {len(rows)}",
    }


# ---------------------------------------------------------------------------
# PDF report (fpdf2). Core PDF fonts are Latin-1 only, so symbols are mapped.
# ---------------------------------------------------------------------------
_MAP = {"≈": "~", "μ": "mu", "η": "eff", "Ø": "dia ", "✅": "", "❌": "", "—": "-", "–": "-",
        "÷": "/", "×": "x", "₀": "0", "⁻⁴": "^-4", "’": "'", "“": '"', "”": '"'}


def _t(s) -> str:
    s = str(s)
    for k, v in _MAP.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def build_report(inp: Inputs, title: str = "Motion axis sizing report") -> bytes:
    from fpdf import FPDF

    r = size_axis(inp)
    rows, picks = pick_motor(inp, ALL_MOTORS)
    pdf = FPDF(orientation="P", unit="mm", format="Letter")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    W = pdf.w - 2 * pdf.l_margin

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(W, 8, _t(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(W, 5, _t(f"Generated {_dt.datetime.now():%Y-%m-%d %H:%M} by Motion Axis Sizer. "
                      "Simplified early-sizing model; confirm with manufacturer tools."),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    def section(t):
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(235, 238, 245)
        pdf.cell(W, 6, _t(t), fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    def kv_table(pairs, cols=2):
        pdf.set_font("Helvetica", "", 9)
        cw = W / cols
        for i in range(0, len(pairs), cols):
            for k, v in pairs[i:i + cols]:
                pdf.set_font("Helvetica", "", 9)
                pdf.cell(cw * 0.55, 5, _t(k))
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(cw * 0.45, 5, _t(v))
            pdf.ln(5)
        pdf.ln(1)

    def table(headers, data, widths):
        pdf.set_font("Helvetica", "B", 8)
        for h, w in zip(headers, widths):
            pdf.cell(w, 5, _t(h), border=1)
        pdf.ln(5)
        pdf.set_font("Helvetica", "", 8)
        for row in data:
            for v, w in zip(row, widths):
                pdf.cell(w, 5, _t(v)[:int(w / 1.5)], border=1)
            pdf.ln(5)
        pdf.ln(2)

    # Inputs
    section("Axis inputs")
    drive_bits = {
        "Ball screw": [("Lead", f"{inp.lead_mm:g} mm/rev"),
                       ("Screw", f"dia {inp.screw_dia_mm:g} x {inp.screw_len_mm:g} mm, eff {inp.screw_eff:g}")],
        "Belt & pulley": [("Pulley pitch dia", f"{inp.pulley_pd_mm:g} mm ({inp.pulley_kg:g} kg each)"),
                          ("Belt efficiency", f"{inp.belt_eff:g}")],
        "Rack & pinion": [("Pinion pitch dia", f"{inp.pinion_pd_mm:g} mm ({inp.pinion_kg:g} kg)"),
                          ("Efficiency", f"{inp.rack_eff:g}")],
    }[inp.drive]
    kv_table([
        ("Drive", inp.drive), ("Orientation", "Vertical" if inp.vertical else "Horizontal"),
        ("Payload + carriage", f"{inp.payload_kg:g} + {inp.carriage_kg:g} kg"),
        ("Friction coeff / ext. force", f"{inp.mu:g} / {inp.f_ext_n:g} N"),
        ("Stroke / move time", f"{inp.stroke_mm:g} mm / {inp.move_time_s:g} s"),
        ("Accel time / dwell", f"{inp.accel_pct:g}% / {inp.dwell_s:g} s"),
        *drive_bits,
        ("Gearbox", f"{inp.gear_ratio:g}:1, eff {inp.gear_eff:g}"),
        ("Safety factor / max J ratio", f"{inp.safety_factor:g} / {inp.max_inertia_ratio:g}:1"),
    ])

    section("Results")
    kv_table([
        ("Max velocity", f"{r.v_max:.3f} m/s"), ("Acceleration", f"{r.a:.2f} m/s^2 ({r.a / 9.81:.2f} g)"),
        ("Max motor speed", f"{r.rpm_max:,.0f} rpm"), ("Reflected load inertia", f"{r.j_load:.3e} kg.m^2"),
        ("Peak torque (raw / with SF)", f"{r.t_peak:.4f} / {r.t_peak_req:.4f} N.m"),
        ("RMS torque (raw / with SF)", f"{r.t_rms:.4f} / {r.t_rms_req:.4f} N.m"),
    ])
    table(["Phase", "Duration (s)", "Force on load (N)", "Motor torque (N.m)"],
          [(n, f"{d:.4f}", f"{f:.3f}", f"{tq:.5f}") for n, d, f, tq in r.phases],
          [W * 0.31, W * 0.23, W * 0.23, W * 0.23])

    if r.checks:
        section("Motor check (motor entered in the app)")
        table(["Check", "Required", "Motor / limit", "Result"],
              [(n, f"{q:.4g}", f"{a:.4g}", "Pass" if ok else "Fail") for n, q, a, ok in r.checks],
              [W * 0.4, W * 0.2, W * 0.2, W * 0.2])

    for label, key in (("Cheapest that passes", "cheapest"), ("Most robust that passes", "robust")):
        x = picks[key]
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(W, 5, _t(f"{label}: " + (f"{x['motor'].model}, "
                          + (f"${x['motor'].total_usd:,.0f}" if x["motor"].total_usd is not None else "quote")
                          + f", {x['headroom'] * 100:.0f}% reserve" if x else "none in catalog")),
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    section("Motor comparison (prices checked 2026-11-12; totals include the drive)")
    srt = sorted(rows, key=lambda x: (not x["ok"], x["motor"].total_usd is None,
                                      x["motor"].total_usd or 0))
    table(["Motor", "Result", "Total USD", "Supply", "Peak", "Cont.", "Speed", "J ratio"],
          [(x["motor"].model, "Pass" if x["ok"] else "Fail",
            f"${x['motor'].total_usd:,.0f}" if x["motor"].total_usd is not None else "quote",
            x["motor"].supply, f"{x['peak_use'] * 100:.0f}%", f"{x['rms_use'] * 100:.0f}%",
            f"{x['speed_use'] * 100:.0f}%", f"{x['result'].inertia_ratio:.2f}")
           for x in srt],
          [W * 0.40, W * 0.08, W * 0.09, W * 0.09, W * 0.08, W * 0.08, W * 0.09, W * 0.09])

    # Torque vs time sketch
    section("Motor torque over one cycle")
    x0, y0, pw, ph = pdf.l_margin + 10, pdf.get_y() + 2, W - 20, 32
    if pdf.get_y() + ph + 12 > pdf.h - 12:
        pdf.add_page()
        y0 = pdf.get_y() + 2
    tvals = [p[3] for p in r.phases]
    tmax = max(max(abs(v) for v in tvals), 1e-9)
    mid = y0 + ph / 2
    pdf.set_draw_color(160, 160, 160)
    pdf.line(x0, mid, x0 + pw, mid)
    pdf.line(x0, y0, x0, y0 + ph)
    pdf.set_draw_color(200, 40, 40)
    pdf.set_line_width(0.6)
    t_acc = 0.0
    prev_y = None
    for name, dur, _, tq in r.phases:
        xa = x0 + pw * t_acc / r.t_cycle
        xb = x0 + pw * (t_acc + dur) / r.t_cycle
        y = mid - (tq / tmax) * (ph / 2 - 1)
        if prev_y is not None:
            pdf.line(xa, prev_y, xa, y)
        pdf.line(xa, y, xb, y)
        prev_y = y
        t_acc += dur
    pdf.set_line_width(0.2)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_xy(x0 - 10, y0 - 1)
    pdf.cell(10, 3, _t(f"+{tmax:.3f}"))
    pdf.set_xy(x0 - 10, y0 + ph - 2)
    pdf.cell(10, 3, _t(f"-{tmax:.3f}"))
    pdf.set_xy(x0 + pw - 30, y0 + ph + 1)
    pdf.cell(30, 3, _t(f"time (s), cycle {r.t_cycle:.3f}"), align="R")
    pdf.set_xy(pdf.l_margin, y0 + ph + 6)

    for msg in r.warnings[:4]:
        pdf.set_font("Helvetica", "I", 8)
        pdf.multi_cell(W, 4, _t("Note: " + msg), new_x="LMARGIN", new_y="NEXT")

    out = pdf.output()
    return bytes(out)
