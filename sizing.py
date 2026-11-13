"""
Motion axis sizing engine.

All math lives here, separate from the screen layout in app.py, so it can be
tested on its own. Everything is SI internally (m, kg, s, N, N·m, rad).

How a cycle is modeled
  Move out (+ direction), dwell, move back (- direction), dwell.
  For a vertical axis "+" is UP, so the out move lifts the load and the
  back move lowers it (gravity helps on the way down).

Each move uses an S-curve velocity profile: acceleration ramps up and down
smoothly instead of switching on instantly. "S-curve smoothing" sets how much
of each acceleration period is spent ramping (0 % = trapezoid, 100 % = pure S).
For the same move time, smoothing raises the peak acceleration.

Torque at the motor is computed at every instant of the cycle:
  force on the load  F = m·a + gravity + external force + friction (opposes motion)
  at the drive shaft T_shaft = F·k + drag torque (opposes motion)
  through the drive  T = T_shaft / (η·N)  when the motor drives the load
                     T = T_shaft · η / N  when the load drives the motor
  plus spinning up   (J_drive/N² + J_motor)·α
Peak and RMS torque come straight from that time history.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import math

import numpy as np

G = 9.81            # gravity, m/s²
RHO_STEEL = 7850.0  # steel density, kg/m³

DRIVES = ("Ball screw", "Belt & pulley", "Rack & pinion")
DRAG_DEFAULTS = {"Ball screw": 0.05, "Belt & pulley": 0.02, "Rack & pinion": 0.03}


@dataclass
class Inputs:
    drive: str = "Ball screw"
    # Load
    payload_kg: float = 1.0
    carriage_kg: float = 0.5
    vertical: bool = False
    mu: float = 0.01
    f_ext_n: float = 0.0
    # Move profile
    stroke_mm: float = 200.0
    move_time_s: float = 0.5
    accel_pct: float = 25.0
    s_curve_pct: float = 50.0
    dwell_s: float = 0.2
    # Ball screw
    lead_mm: float = 10.0
    screw_dia_mm: float = 12.0
    screw_len_mm: float = 300.0
    screw_eff: float = 0.90
    # Belt / rack & pinion
    pulley_pd_mm: float = 30.0
    pulley_kg: float = 0.05
    belt_eff: float = 0.95
    pinion_pd_mm: float = 30.0
    pinion_kg: float = 0.10
    rack_eff: float = 0.95
    # Drag torque of the drive (screw preload, seals, support bearings, belt tension)
    drag_nm: float = 0.05
    # Gearbox
    gear_ratio: float = 1.0
    gear_eff: float = 1.0
    # Motor (optional; 0 = not entered)
    motor_rated_nm: float = 0.0
    motor_peak_nm: float = 0.0
    motor_max_rpm: float = 0.0
    motor_j_kgm2: float = 0.0
    # Margins
    safety_factor: float = 1.5
    max_inertia_ratio: float = 10.0


@dataclass
class Results:
    # Motion profile (one move)
    m_kg: float = 0.0
    t_acc: float = 0.0
    t_jerk: float = 0.0
    t_const: float = 0.0
    t_move: float = 0.0
    t_cycle: float = 0.0          # out + dwell + back + dwell
    v_max: float = 0.0
    a: float = 0.0                # peak acceleration (m/s²)
    a_trap: float = 0.0           # what a trapezoid would need, for comparison
    # Drive
    k: float = 0.0                # m of travel per rad of drive shaft
    drive_eff: float = 1.0
    eff_total: float = 1.0
    # Forces (N), outbound move
    f_friction: float = 0.0
    f_gravity: float = 0.0
    f_ext: float = 0.0
    f_const: float = 0.0          # steady force while moving out
    f_accel: float = 0.0          # m·a at peak acceleration
    # Inertia at the motor (kg·m²)
    j_mass: float = 0.0
    j_drive: float = 0.0
    j_load: float = 0.0           # (j_mass + j_drive) / N²
    j_motor: float = 0.0
    j_total: float = 0.0
    inertia_ratio: float = float("nan")
    # Speed / acceleration at the motor
    omega_max: float = 0.0
    rpm_max: float = 0.0
    alpha: float = 0.0            # peak, rad/s²
    # Key torques at the motor (N·m), outbound move
    t_drag: float = 0.0           # drag torque reflected to the motor
    t_load: float = 0.0           # steady torque while moving out
    t_inertia: float = 0.0        # extra torque at peak acceleration
    t_accel_phase: float = 0.0    # peak during acceleration (out)
    t_const_phase: float = 0.0
    t_decel_phase: float = 0.0    # most negative / smallest during deceleration (out)
    t_dwell_phase: float = 0.0
    t_back_const: float = 0.0     # steady torque on the return move
    t_peak: float = 0.0
    t_rms: float = 0.0
    t_peak_req: float = 0.0
    t_rms_req: float = 0.0
    phases: list = field(default_factory=list)   # (name, duration, peak force N, peak torque N·m)
    checks: list = field(default_factory=list)   # (name, required, available, ok)
    warnings: list = field(default_factory=list)
    motor_entered: bool = False
    overall_ok: bool | None = None
    # Time history over one full cycle
    ts: np.ndarray | None = None
    pos: np.ndarray | None = None  # mm
    vel: np.ndarray | None = None  # m/s
    acc: np.ndarray | None = None  # m/s²
    tq: np.ndarray | None = None   # N·m at motor


def drive_geometry(inp: Inputs):
    """Return (k, J_drive, efficiency) for the selected drive.

    k is the 'transmission constant': metres of linear travel per radian of
    the drive shaft. Every drive type reduces to this one number.
    """
    if inp.drive == "Ball screw":
        lead = inp.lead_mm / 1000
        k = lead / (2 * math.pi)
        d = inp.screw_dia_mm / 1000
        L = inp.screw_len_mm / 1000
        j_drive = math.pi * RHO_STEEL * L * d**4 / 32   # solid steel cylinder
        eff = inp.screw_eff
    elif inp.drive == "Belt & pulley":
        r = inp.pulley_pd_mm / 2000
        k = r
        j_drive = 2 * 0.5 * inp.pulley_kg * r**2       # drive + idler pulley
        eff = inp.belt_eff
    elif inp.drive == "Rack & pinion":
        r = inp.pinion_pd_mm / 2000
        k = r
        j_drive = 0.5 * inp.pinion_kg * r**2
        eff = inp.rack_eff
    else:
        raise ValueError(f"Unknown drive: {inp.drive}")
    return k, j_drive, eff


def _accel_shape(tau, ta, tj):
    """Acceleration (as a fraction of peak) during one accel period of length ta,
    with jerk ramps of length tj at each end. tau is time since the period began."""
    if tj <= 0:
        return np.where((tau >= 0) & (tau < ta), 1.0, 0.0)
    up = np.clip(tau / tj, 0, 1)
    down = np.clip((ta - tau) / tj, 0, 1)
    return np.where((tau >= 0) & (tau < ta), np.minimum(up, down), 0.0)


def _one_move(t, ta, tj, tc, a_pk):
    """Acceleration over one move (accel, constant, decel), t from move start."""
    return a_pk * (_accel_shape(t, ta, tj) - _accel_shape(t - ta - tc, ta, tj))


def size_axis(inp: Inputs, n: int = 6000) -> Results:
    r = Results()
    N = inp.gear_ratio if inp.gear_ratio > 0 else 1.0

    # 1. Motion profile -------------------------------------------------
    r.m_kg = inp.payload_kg + inp.carriage_kg
    S = inp.stroke_mm / 1000
    T = inp.move_time_s
    pct = min(max(inp.accel_pct, 1.0), 50.0) / 100
    s = min(max(inp.s_curve_pct, 0.0), 100.0) / 100
    r.t_move = T
    r.t_acc = pct * T
    r.t_jerk = s * r.t_acc / 2
    r.t_const = T - 2 * r.t_acc
    # A symmetric accel period covers v·ta/2 whatever its shape, so v_max is the
    # same as for a trapezoid; only the peak acceleration changes.
    r.v_max = S / (T - r.t_acc)
    r.a_trap = r.v_max / r.t_acc
    r.a = r.v_max / (r.t_acc - r.t_jerk)
    r.t_cycle = 2 * (T + inp.dwell_s)

    # 2. Forces (outbound move, for display) --------------------------------
    if inp.vertical:
        r.f_gravity = r.m_kg * G       # guides carry almost no normal force
        r.f_friction = 0.0
    else:
        r.f_gravity = 0.0
        r.f_friction = inp.mu * r.m_kg * G
    r.f_ext = inp.f_ext_n
    r.f_const = r.f_friction + r.f_gravity + r.f_ext
    r.f_accel = r.m_kg * r.a

    # 3. Inertia ------------------------------------------------------------
    r.k, r.j_drive, r.drive_eff = drive_geometry(inp)
    eta = r.drive_eff * (inp.gear_eff if inp.gear_eff > 0 else 1.0)
    r.eff_total = eta
    r.j_mass = r.m_kg * r.k**2
    r.j_load = (r.j_mass + r.j_drive) / N**2
    r.j_motor = inp.motor_j_kgm2
    r.j_total = r.j_load + r.j_motor
    if r.j_motor > 0:
        r.inertia_ratio = r.j_load / r.j_motor
    j_rot = r.j_drive / N**2 + r.j_motor   # rotating parts (mass is handled as a force)

    # 4. Speed ----------------------------------------------------------------
    r.omega_max = r.v_max / r.k * N
    r.rpm_max = r.omega_max * 60 / (2 * math.pi)
    r.alpha = r.a / r.k * N

    # 5. Time history over the full cycle -------------------------------------
    dt = r.t_cycle / n
    ts = (np.arange(n) + 0.5) * dt                      # bin centres (midpoint rule)
    tm = np.mod(ts, T + inp.dwell_s)                    # time within out or back half
    back = ts >= (T + inp.dwell_s)
    sign = np.where(back, -1.0, 1.0)
    moving = tm < T
    acc = np.where(moving, _one_move(tm, r.t_acc, r.t_jerk, r.t_const, r.a), 0.0) * sign
    # velocity and position from the exact profile, sampled finely
    nf = 20000
    tf = np.linspace(0, T, nf + 1)
    af = _one_move(tf, r.t_acc, r.t_jerk, r.t_const, r.a)
    vf = np.concatenate([[0], np.cumsum((af[1:] + af[:-1]) / 2 * np.diff(tf))])
    xf = np.concatenate([[0], np.cumsum((vf[1:] + vf[:-1]) / 2 * np.diff(tf))])
    xf *= S / xf[-1] if xf[-1] > 0 else 1
    v1 = np.interp(np.minimum(tm, T), tf, vf)
    x1 = np.interp(np.minimum(tm, T), tf, xf)
    vel = np.where(moving, v1, 0.0) * sign
    pos = np.where(back, S - np.where(moving, x1, S), np.where(moving, x1, S))

    d = np.sign(vel)                                      # direction of motion, 0 when stopped
    F = r.m_kg * acc + (r.f_gravity + r.f_ext) + r.f_friction * d
    t_shaft = F * r.k + inp.drag_nm * d
    motoring = t_shaft * d >= 0
    t_mot = np.where(d == 0, t_shaft * eta / N,               # holding: load back-drives
                     np.where(motoring, t_shaft / (eta * N), t_shaft * eta / N))
    tq = t_mot + j_rot * acc / r.k * N
    r.ts, r.pos, r.vel, r.acc, r.tq = ts, pos * 1000, vel, acc, tq

    r.t_peak = float(np.max(np.abs(tq)))
    r.t_rms = float(np.sqrt(np.mean(tq**2)))
    r.t_peak_req = r.t_peak * inp.safety_factor
    r.t_rms_req = r.t_rms * inp.safety_factor

    # Key outbound numbers for the equations section
    r.t_drag = inp.drag_nm / (eta * N)
    r.t_load = (r.f_const * r.k + inp.drag_nm) / (eta * N)
    r.t_inertia = (r.m_kg * r.k**2 / eta / N**2 + j_rot) * r.alpha
    out = ~back
    seg_a = out & moving & (tm < r.t_acc)
    seg_c = out & moving & (tm >= r.t_acc) & (tm < T - r.t_acc)
    seg_d = out & moving & (tm >= T - r.t_acc)
    seg_w = out & ~moving
    r.t_accel_phase = float(tq[seg_a].max()) if seg_a.any() else 0.0
    r.t_const_phase = float(tq[seg_c].mean()) if seg_c.any() else r.t_load
    r.t_decel_phase = float(tq[seg_d].min()) if seg_d.any() else 0.0
    r.t_dwell_phase = float(tq[seg_w].mean()) if seg_w.any() else 0.0
    seg_bc = back & moving & (tm >= r.t_acc) & (tm < T - r.t_acc)
    r.t_back_const = float(tq[seg_bc].mean()) if seg_bc.any() else 0.0

    def peak(x, m):
        if not m.any():
            return 0.0
        i = np.argmax(np.abs(x[m]))
        return float(x[m][i])

    names = ("Accelerate", "Constant velocity", "Decelerate", "Dwell")
    dur = (r.t_acc, r.t_const, r.t_acc, inp.dwell_s)
    for label, half in (("out", out), ("back", back)):
        segs = (half & moving & (tm < r.t_acc),
                half & moving & (tm >= r.t_acc) & (tm < T - r.t_acc),
                half & moving & (tm >= T - r.t_acc),
                half & ~moving)
        for nm, du, m in zip(names, dur, segs):
            r.phases.append((f"{nm} ({label})", du, peak(F, m), peak(tq, m)))

    # 6. Motor checks ----------------------------------------------------------
    r.motor_entered = any(v > 0 for v in (inp.motor_rated_nm, inp.motor_peak_nm,
                                          inp.motor_max_rpm, inp.motor_j_kgm2))
    if inp.motor_peak_nm > 0:
        r.checks.append(("Peak torque (N·m)", r.t_peak_req, inp.motor_peak_nm,
                         r.t_peak_req <= inp.motor_peak_nm))
    if inp.motor_rated_nm > 0:
        r.checks.append(("RMS vs rated torque (N·m)", r.t_rms_req, inp.motor_rated_nm,
                         r.t_rms_req <= inp.motor_rated_nm))
    if inp.motor_max_rpm > 0:
        r.checks.append(("Max speed (rpm)", r.rpm_max, inp.motor_max_rpm,
                         r.rpm_max <= inp.motor_max_rpm))
    if inp.motor_j_kgm2 > 0:
        r.checks.append(("Inertia ratio (load : motor)", r.inertia_ratio,
                         inp.max_inertia_ratio,
                         r.inertia_ratio <= inp.max_inertia_ratio))
    if r.checks:
        r.overall_ok = all(c[3] for c in r.checks)

    # Plain-English warnings ----------------------------------------------------
    w = r.warnings
    if r.checks:
        for name, req, avail, ok in r.checks:
            if ok:
                continue
            if name.startswith("Inertia"):
                w.append(f"Inertia ratio {req:.1f}:1 is above your {avail:.0f}:1 limit. "
                         "Response may be sluggish or unstable. Consider a gearbox "
                         "(inertia drops with ratio²) or a motor with a bigger rotor.")
            elif name.startswith("Peak"):
                w.append(f"Peak torque needed ({req:.3f} N·m with safety factor) is more than "
                         f"the motor's peak rating ({avail:.3f} N·m). Choose a bigger motor, add "
                         "a gearbox, or lengthen the acceleration time.")
            elif name.startswith("RMS"):
                w.append(f"RMS torque ({req:.3f} N·m with safety factor) exceeds the motor's "
                         f"continuous rating ({avail:.3f} N·m). The motor will overheat over "
                         "time. Add dwell, slow the move, or pick a bigger motor.")
            elif name.startswith("Max speed"):
                w.append(f"Required speed ({req:.0f} rpm) is above the motor's max "
                         f"({avail:.0f} rpm). Use a longer screw lead or bigger pulley, or "
                         "reduce the gear ratio.")
    elif not r.motor_entered:
        w.append("No motor data entered yet, so there is no PASS/FAIL. Enter values "
                 "from a motor datasheet, or load one from the Motor selection tab.")
    if inp.motor_j_kgm2 <= 0:
        w.append("Rotor inertia not entered, so the inertia ratio can't be checked and "
                 "acceleration torque ignores the motor's own rotor.")
    if r.t_drag > 0.4 * max(r.t_rms, 1e-12):
        w.append(f"Drag torque ({r.t_drag:.3f} N·m at the motor) is a large share of the "
                 "continuous torque. Use the drive maker's actual drag or preload torque "
                 "figure, because it decides the motor size here.")
    if inp.drive == "Ball screw" and r.rpm_max / N > 3000:
        w.append(f"Screw speed is {r.rpm_max / N:.0f} rpm. Long or thin screws can whip "
                 "near their critical speed; check the manufacturer's critical-speed chart "
                 "or use a longer lead.")
    if inp.s_curve_pct > 0:
        w.append(f"S-curve smoothing raises peak acceleration to {r.a:.2f} m/s², "
                 f"{(r.a / r.a_trap - 1) * 100:.0f}% above a sharp-cornered profile, in "
                 "exchange for less vibration and faster settling.")
    if inp.vertical and inp.dwell_s > 0:
        w.append("Vertical axis: the motor must hold the load during dwell. Most designs "
                 "add a motor brake so the load can't drop when power is off.")
    if inp.vertical and inp.drive != "Ball screw":
        w.append("Vertical belt or rack axes back-drive easily. You will need a brake "
                 "and possibly a counterbalance.")
    if np.min(tq * np.sign(r.vel + 1e-30)) < 0 and np.any(r.vel != 0):
        w.append("At times the load drives the motor (braking, or lowering a vertical "
                 "load), so energy flows back into the drive. Fine for most servo drives; "
                 "on heavy, fast axes check whether the drive needs a braking resistor.")
    return r


def profile_timeseries(inp: Inputs, r: Results, n: int | None = None):
    """Time (s), position (mm), velocity (m/s), acceleration (m/s²), torque (N·m)."""
    return r.ts, r.pos, r.vel, r.acc, r.tq


PRESETS = {
    "IC pick-and-place X axis": Inputs(
        drive="Belt & pulley", payload_kg=0.5, carriage_kg=0.2, vertical=False, mu=0.01,
        stroke_mm=300, move_time_s=0.4, accel_pct=25, s_curve_pct=50, dwell_s=0.2,
        pulley_pd_mm=30, pulley_kg=0.05, belt_eff=0.95, drag_nm=0.02,
        motor_rated_nm=0.64, motor_peak_nm=1.91, motor_max_rpm=6000, motor_j_kgm2=1.8e-5),
    "Vertical Z pick axis": Inputs(
        drive="Ball screw", payload_kg=0.3, carriage_kg=0.2, vertical=True, mu=0.01,
        stroke_mm=20, move_time_s=0.1, accel_pct=25, s_curve_pct=50, dwell_s=0.3,
        lead_mm=10, screw_dia_mm=8, screw_len_mm=150, screw_eff=0.9, drag_nm=0.02,
        motor_rated_nm=0.32, motor_peak_nm=0.95, motor_max_rpm=6000, motor_j_kgm2=6e-6),
    "Heavy shuttle": Inputs(
        drive="Ball screw", payload_kg=5.0, carriage_kg=1.0, vertical=False, mu=0.01,
        stroke_mm=500, move_time_s=1.0, accel_pct=25, s_curve_pct=50, dwell_s=0.5,
        lead_mm=20, screw_dia_mm=20, screw_len_mm=700, screw_eff=0.9, drag_nm=0.08,
        motor_rated_nm=1.27, motor_peak_nm=3.82, motor_max_rpm=6000, motor_j_kgm2=3.7e-5),
}


# ---------------------------------------------------------------------------
# Motor catalog. Specs and prices checked online 2026-11-12; see
# datasheets/DATASHEET INDEX.md for every source.
#
# Families
#   Industrial servo (200 V AC): Yaskawa Sigma-7, Panasonic MINAS A6,
#     Mitsubishi MELSERVO-JE. Motor + matching drive. Prices are new-unit
#     distributor list prices where published; otherwise "quote".
#   Budget servo kit (220 V AC): StepperOnline T6, drive included.
#   Robotics torque motor (48 V DC): CubeMars, need a separate driver
#     (ODrive S1, $149, used for total cost).
#
# max_rpm: the maker's maximum speed for servos; for CubeMars the speed held at
# rated torque. Torque falls near max speed; that curve is not modeled.
# Rotor inertia marked estimated: CubeMars R80/R100/RO80 (scaled from published
# R60 and RO80 Lite values).
# ---------------------------------------------------------------------------
ODRIVE_S1_USD = 149.0
FAMILIES = ("Industrial servo", "Budget servo kit", "Robotics torque motor")


@dataclass
class Motor:
    model: str
    rated_nm: float
    peak_nm: float
    max_rpm: float
    j_kgm2: float
    weight_g: float | None
    j_estimated: bool = False
    note: str = ""
    brand: str = ""
    family: str = ""
    supply: str = ""
    drive_model: str = ""
    price: float | None = None        # motor or kit price as listed (None = quote)
    currency: str = "USD"
    drive_included: bool = False
    drive_usd: float | None = 0.0     # extra drive cost if not included (None = quote)
    seller: str = ""
    status: str = ""
    url: str = ""

    @property
    def total_usd(self):
        if self.price is None or self.currency != "USD":
            return None
        if self.drive_included:
            return self.price
        if self.drive_usd is None:
            return None
        return self.price + self.drive_usd


ALL_MOTORS = [
    # Industrial servos ------------------------------------------------------
    Motor("Yaskawa SGM7J-02A (200 W)", 0.637, 2.23, 6000, 0.263e-4, None,
          brand="Yaskawa", family="Industrial servo", supply="200 V AC",
          drive_model="SGD7S-1R6A00A", price=933.0, drive_usd=1080.0,
          seller="Automation Distribution", status="New, list price",
          url="https://automationdistribution.com/yaskawa-sgm7j-02afa61-s7-motor-200w-200v-incremental-keyed-tapered-shaft/",
          note="Sigma-7 medium inertia. Drive SGD7S-1R6A00A $1,080."),
    Motor("Yaskawa SGM7J-04A (400 W)", 1.27, 4.46, 6000, 0.486e-4, 1100,
          brand="Yaskawa", family="Industrial servo", supply="200 V AC",
          drive_model="SGD7S-2R8A00A", price=1186.0, drive_usd=1168.0,
          seller="Automation Distribution", status="New, list price",
          url="https://automationdistribution.com/yaskawa-sgm7j-04afa6s-s7-motor-400w-200v-incremental-keyed-taper-shaft/",
          note="Sigma-7 medium inertia. Drive SGD7S-2R8A00A $1,168."),
    Motor("Panasonic MSMF022 (200 W)", 0.64, 1.91, 6000, 0.14e-4, None,
          brand="Panasonic", family="Industrial servo", supply="200 V AC",
          drive_model="MADLN15SE", price=None, drive_usd=None,
          seller="Powermatic (quote)", status="Quote",
          url="https://powermatic.net/part/panasonic/msmf022l1u2/2774006",
          note="MINAS A6 low inertia."),
    Motor("Panasonic MSMF042 (400 W)", 1.27, 3.82, 6000, 0.30e-4, None,
          brand="Panasonic", family="Industrial servo", supply="200 V AC",
          drive_model="MBDLN25SE", price=499.0, drive_usd=None,
          seller="e-motionsupply", status="Motor new $499; drive quote",
          url="https://www.e-motionsupply.com/Panasonic_AC_Servo_Motors_MSMF042L1U2M_p/msmf042l1u2m.htm",
          note="MINAS A6 low inertia. Inertia from Panasonic's MSMF042L1T2 page."),
    Motor("Mitsubishi HG-KN23 (200 W)", 0.64, 1.9, 5000, 0.225e-4, 980,
          brand="Mitsubishi", family="Industrial servo", supply="200 V AC",
          drive_model="MR-JE-20A", price=None, drive_usd=None,
          seller="Mitsubishi distributor (quote)", status="Quote",
          url="https://us.mitsubishielectric.com/fa/en/products/drive-products/ac-servos-melservo/mrje/motor/specifications/",
          note="MELSERVO-JE low inertia. 6000 rpm with parameter change."),
    Motor("Mitsubishi HG-KN43 (400 W)", 1.3, 3.8, 5000, 0.375e-4, 1500,
          brand="Mitsubishi", family="Industrial servo", supply="200 V AC",
          drive_model="MR-JE-40A", price=None, drive_usd=None,
          seller="Mitsubishi distributor (quote)", status="Quote",
          url="https://us.mitsubishielectric.com/fa/en/products/drive-products/ac-servos-melservo/mrje/motor/specifications/",
          note="MELSERVO-JE low inertia."),
    Motor("Mitsubishi HG-KN73 (750 W)", 2.4, 7.2, 5000, 1.28e-4, 3000,
          brand="Mitsubishi", family="Industrial servo", supply="200 V AC",
          drive_model="MR-JE-70A", price=None, drive_usd=None,
          seller="Mitsubishi distributor (quote)", status="Quote",
          url="https://us.mitsubishielectric.com/fa/en/products/drive-products/ac-servos-melservo/mrje/motor/specifications/",
          note="MELSERVO-JE low inertia."),
    # Budget servo kits --------------------------------------------------------
    Motor("StepperOnline T6 400W kit", 1.27, 3.81, 5000, 0.56e-4, 1300,
          brand="StepperOnline", family="Budget servo kit", supply="220 V AC",
          drive_model="included", price=192.56, drive_included=True,
          seller="StepperOnline", status="In stock",
          url="https://www.omc-stepperonline.com/t6-series-400w-ac-servo-motor-kit-3000rpm-1-27nm-17-bit-encoder-ip65-t6-rs400h2a3-m17s",
          note="T6-RS400H2A3-M17S: motor + drive + cables."),
    Motor("StepperOnline T6 1000W kit", 3.19, 9.56, 5000, 2.15e-4, 3400,
          brand="StepperOnline", family="Budget servo kit", supply="220 V AC",
          drive_model="included", price=266.81, drive_included=True,
          seller="StepperOnline", status="Backorder",
          url="https://www.omc-stepperonline.com/t6-series-1000w-ac-servo-motor-kit-3000rpm-3-19nm-w-brake-17-bit-encoder-ip65-t6-rs1000h2b3-m17s",
          note="T6-RS1000H2A3-M17S: motor + drive + cables."),
    # Robotics torque motors ----------------------------------------------------
    Motor("CubeMars R60 KV115", 0.8, 2.4, 4200, 1161e-7, 248, brand="CubeMars",
          family="Robotics torque motor", supply="48 V DC", drive_model="ODrive S1",
          price=177.90, drive_usd=ODRIVE_S1_USD, seller="OZ Robotics",
          status="Discontinued (successor: RO60)",
          url="https://ozrobotics.com/shop/cubemars-r60-kv115-bldc-motor-with-built-in-hall-sensor/",
          note="Your motor. All values from datasheet."),
    Motor("CubeMars RO60 KV115", 0.8, 2.4, 4200, 1161e-7, 248, brand="CubeMars",
          family="Robotics torque motor", supply="48 V DC", drive_model="ODrive S1",
          price=85.90, drive_usd=ODRIVE_S1_USD, seller="DigiKey", status="In stock",
          url="https://www.digikey.com/en/products/detail/cubemars/RO60-KV115/27612270",
          note="R60 successor, same ratings. Inertia from R60 datasheet."),
    Motor("CubeMars RO80 KV105", 1.3, 4.0, 3600, 2125e-7, 352, j_estimated=True,
          brand="CubeMars", family="Robotics torque motor", supply="48 V DC",
          drive_model="ODrive S1", price=100.99, currency="EUR", drive_usd=ODRIVE_S1_USD,
          seller="MAB Robotics (EU)", status="Listed",
          url="https://www.mabrobotics.pl/product-page/ro80-cubemars-t-motor",
          note="Inertia scaled from RO80 Lite datasheet (1,600 g·cm²) by weight."),
    Motor("CubeMars R80 KV110", 1.3, 4.0, 3600, 2490e-7, 354, j_estimated=True,
          brand="CubeMars", family="Robotics torque motor", supply="48 V DC",
          drive_model="ODrive S1", price=258.90, drive_usd=ODRIVE_S1_USD,
          seller="OZ Robotics", status="Listed",
          url="https://ozrobotics.com/shop/cubemars-r80-kv110-bldc-motor-with-built-in-hall-sensor/",
          note="Ø87 mm. Rotor inertia estimated."),
    Motor("CubeMars R100 KV90", 3.7, 11.0, 3800, 7630e-7, 731, j_estimated=True,
          brand="CubeMars", family="Robotics torque motor", supply="48 V DC",
          drive_model="ODrive S1", price=426.90, drive_usd=ODRIVE_S1_USD,
          seller="OZ Robotics", status="Listed",
          url="https://ozrobotics.com/shop/cubemars-r100-kv90-bldc-motor-with-built-in-hall-sensor/",
          note="35 A continuous: near ODrive S1 limit. Rotor inertia estimated."),
]

CUBEMARS_R = sorted([m for m in ALL_MOTORS if m.brand == "CubeMars"],
                    key=lambda m: (m.rated_nm, m.total_usd if m.total_usd is not None else 1e9))
INDUSTRIAL = sorted([m for m in ALL_MOTORS if m.family == "Industrial servo"],
                    key=lambda m: (m.rated_nm, m.total_usd if m.total_usd is not None else 1e9))


def pick_motor(inp: Inputs, catalog=ALL_MOTORS):
    """Size the axis once per catalog motor (its rotor inertia changes the torque)
    and return (rows, smallest passing model)."""
    rows, best = [], None
    for m in catalog:
        r = size_axis(replace(inp, motor_rated_nm=m.rated_nm, motor_peak_nm=m.peak_nm,
                              motor_max_rpm=m.max_rpm, motor_j_kgm2=m.j_kgm2), n=2000)
        status = {c[0].split(" (")[0]: c[3] for c in r.checks}
        fails = [k for k, ok in status.items() if not ok]
        rows.append({"motor": m, "result": r, "ok": r.overall_ok, "fails": fails,
                     "peak_use": r.t_peak_req / m.peak_nm,
                     "rms_use": r.t_rms_req / m.rated_nm,
                     "speed_use": r.rpm_max / m.max_rpm})
        if best is None and r.overall_ok:
            best = m.model
    return rows, best
