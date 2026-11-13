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
    motor_rated_rpm: float = 0.0      # 0 = not entered (assume half of max speed)
    # Torque-speed envelope shape (approximate, see torque_envelope)
    env_cont_end: float = 0.5         # continuous torque at max speed, fraction of rated
    env_peak_knee_rpm: float = 0.0    # peak torque held up to this speed (0 = rated speed)
    env_peak_end: float = 0.35        # peak-zone torque at max speed, fraction of peak
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
    phases: list = field(default_factory=list)   # (name, duration, force N at peak torque, peak torque N·m)
    phase_ranges: list = field(default_factory=list)  # (lowest, highest) motor torque in each phase
    rpm: np.ndarray | None = None  # motor speed (signed) over the cycle
    env_rpm_worst: float = 0.0     # speed where torque-vs-speed is tightest
    governing: tuple | None = None # (check name, fraction of limit used) for the tightest check
    brake_note: str = ""
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


def torque_envelope(n_rpm, rated, peak, rated_rpm, max_rpm,
                    cont_end=0.5, peak_knee_rpm=0.0, peak_end=0.35):
    """Approximate torque a motor can give at speed n (rpm): (continuous, peak zone).

    Continuous zone: rated torque up to rated speed, then a straight line down to
    cont_end x rated at max speed. Peak (intermittent) zone: peak torque up to the
    knee speed, then a straight line down to peak_end x peak at max speed. Above max
    speed nothing is available. Real curves come from the maker's datasheet and
    depend on drive and supply voltage; this shape is a stand-in for early sizing.
    """
    n = np.abs(np.asarray(n_rpm, dtype=float))
    rated_rpm = rated_rpm if rated_rpm > 0 else max_rpm / 2
    knee = peak_knee_rpm if peak_knee_rpm > 0 else rated_rpm
    knee = min(knee, max_rpm)

    def ramp(x0, y0, y1):
        span = max(max_rpm - x0, 1e-9)
        return np.where(n <= x0, y0, y0 + (y1 - y0) * (n - x0) / span)

    cont = ramp(min(rated_rpm, max_rpm), rated, cont_end * rated)
    pk = np.maximum(ramp(knee, peak, peak_end * peak), cont)
    over = n > max_rpm * (1 + 1e-9)
    return np.where(over, 0.0, cont), np.where(over, 0.0, pk)


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
    # Most samples go to the moves; torque is constant while stopped, so dwells
    # need only a few. That keeps short, fast moves well resolved even when a
    # long dwell dominates the cycle. Each sample is the midpoint of its slice.
    half = T + inp.dwell_s
    n_dw = 40 if inp.dwell_s > 0 else 0
    n_mv = max(200, n // 2 - n_dw)
    t_mv = (np.arange(n_mv) + 0.5) * (T / n_mv)
    t_dw = T + (np.arange(n_dw) + 0.5) * (inp.dwell_s / max(n_dw, 1))
    t_half = np.concatenate([t_mv, t_dw])
    w_half = np.concatenate([np.full(n_mv, T / n_mv), np.full(n_dw, inp.dwell_s / max(n_dw, 1))])
    ts = np.concatenate([t_half, t_half + half])
    wts = np.concatenate([w_half, w_half])
    tm = np.concatenate([t_half, t_half])                 # time within out or back half
    back = ts >= half
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
    r.rpm = vel / r.k * N * 60 / (2 * math.pi)

    r.t_peak = float(np.max(np.abs(tq)))
    r.t_rms = float(np.sqrt(np.sum(tq**2 * wts) / r.t_cycle))
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

    def at_peak(m):
        """(force at the instant of peak torque, peak torque, lowest, highest)."""
        if not m.any():
            return 0.0, 0.0, 0.0, 0.0
        i = np.argmax(np.abs(tq[m]))
        return float(F[m][i]), float(tq[m][i]), float(tq[m].min()), float(tq[m].max())

    names = ("Accelerate", "Constant velocity", "Decelerate", "Dwell")
    dur = (r.t_acc, r.t_const, r.t_acc, inp.dwell_s)
    for label, half in (("out", out), ("back", back)):
        segs = (half & moving & (tm < r.t_acc),
                half & moving & (tm >= r.t_acc) & (tm < T - r.t_acc),
                half & moving & (tm >= T - r.t_acc),
                half & ~moving)
        for nm, du, m in zip(names, dur, segs):
            f_pk, t_pk, t_lo, t_hi = at_peak(m)
            r.phases.append((f"{nm} ({label})", du, f_pk, t_pk))
            r.phase_ranges.append((t_lo, t_hi))

    # 6. Motor checks ----------------------------------------------------------
    r.motor_entered = any(v > 0 for v in (inp.motor_rated_nm, inp.motor_peak_nm,
                                          inp.motor_max_rpm, inp.motor_j_kgm2))
    rpm_abs = np.abs(r.rpm)
    rated_rpm = inp.motor_rated_rpm if inp.motor_rated_rpm > 0 else inp.motor_max_rpm / 2
    if inp.motor_peak_nm > 0:
        r.checks.append(("Peak torque (N·m)", r.t_peak_req, inp.motor_peak_nm,
                         r.t_peak_req <= inp.motor_peak_nm))
    have_env = inp.motor_peak_nm > 0 and inp.motor_rated_nm > 0 and inp.motor_max_rpm > 0
    if have_env:
        _, pk_avail = torque_envelope(rpm_abs, inp.motor_rated_nm, inp.motor_peak_nm, rated_rpm,
                                      inp.motor_max_rpm, inp.env_cont_end,
                                      inp.env_peak_knee_rpm, inp.env_peak_end)
        need = np.abs(tq) * inp.safety_factor
        use = np.where(pk_avail > 0, need / np.maximum(pk_avail, 1e-12),
                       np.where(need > 0, np.inf, 0.0))
        i = int(np.argmax(use))
        r.env_rpm_worst = float(rpm_abs[i])
        r.checks.append((f"Torque at speed (N·m at {rpm_abs[i]:,.0f} rpm)", float(need[i]),
                         float(pk_avail[i]), bool(use[i] <= 1.0)))
    if inp.motor_rated_nm > 0:
        if have_env:
            n_avg = float(np.sum(rpm_abs * wts) / r.t_cycle)
            cont_avail = float(torque_envelope(n_avg, inp.motor_rated_nm, inp.motor_peak_nm,
                                               rated_rpm, inp.motor_max_rpm, inp.env_cont_end,
                                               inp.env_peak_knee_rpm, inp.env_peak_end)[0])
        else:
            cont_avail = inp.motor_rated_nm
        r.checks.append(("RMS vs continuous torque (N·m)", r.t_rms_req, cont_avail,
                         r.t_rms_req <= cont_avail))
    if inp.motor_max_rpm > 0:
        r.checks.append(("Max speed (rpm)", r.rpm_max, inp.motor_max_rpm,
                         r.rpm_max <= inp.motor_max_rpm))
    if inp.motor_j_kgm2 > 0:
        r.checks.append(("Inertia ratio (load : motor)", r.inertia_ratio,
                         inp.max_inertia_ratio,
                         r.inertia_ratio <= inp.max_inertia_ratio))
    if r.checks:
        r.overall_ok = all(c[3] for c in r.checks)
        uses = [(c[0].split(" (")[0], c[1] / c[2] if c[2] > 0 else float("inf")) for c in r.checks]
        r.governing = max(uses, key=lambda u: u[1])

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
            elif name.startswith("Torque at speed"):
                w.append(f"At {r.env_rpm_worst:,.0f} rpm the motor can give only about "
                         f"{avail:.3f} N·m, but the move needs {req:.3f} N·m there (with safety "
                         "factor). A motor's torque falls as it nears top speed. Choose a motor "
                         "with more speed headroom, a finer screw lead or a smaller pulley.")
            elif name.startswith("RMS"):
                w.append(f"RMS torque ({req:.3f} N·m with safety factor) exceeds the motor's "
                         f"continuous torque ({avail:.3f} N·m at this axis's average speed). The motor will overheat over "
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
    if inp.vertical:
        r.brake_note = (
            f"Vertical axis: while powered, the motor holds the load with "
            f"{abs(r.t_dwell_phase):.3f} N·m during dwell. With power off, nothing holds it"
            + (", and a belt or rack axis drops immediately" if inp.drive != "Ball screw"
               else ", and most ball screws back-drive")
            + ". Choose the motor's brake option (or a counterbalance) so the load can't fall.")
    if inp.motor_rated_nm > 0 and inp.motor_rated_rpm <= 0 and inp.motor_max_rpm > 0:
        w.append("Rated speed not entered, so the torque-vs-speed check assumes half the max "
                 "speed. Enter the datasheet's rated speed for a better check.")
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
        motor_rated_nm=0.64, motor_peak_nm=1.91, motor_max_rpm=6000, motor_j_kgm2=1.8e-5, motor_rated_rpm=3000),
    "Vertical Z pick axis": Inputs(
        drive="Ball screw", payload_kg=0.3, carriage_kg=0.2, vertical=True, mu=0.01,
        stroke_mm=20, move_time_s=0.1, accel_pct=25, s_curve_pct=50, dwell_s=0.3,
        lead_mm=10, screw_dia_mm=8, screw_len_mm=150, screw_eff=0.9, drag_nm=0.02,
        motor_rated_nm=0.32, motor_peak_nm=0.95, motor_max_rpm=6000, motor_j_kgm2=6e-6, motor_rated_rpm=3000),
    "Heavy shuttle": Inputs(
        drive="Ball screw", payload_kg=5.0, carriage_kg=1.0, vertical=False, mu=0.01,
        stroke_mm=500, move_time_s=1.0, accel_pct=25, s_curve_pct=50, dwell_s=0.5,
        lead_mm=20, screw_dia_mm=20, screw_len_mm=700, screw_eff=0.9, drag_nm=0.08,
        motor_rated_nm=1.27, motor_peak_nm=3.82, motor_max_rpm=6000, motor_j_kgm2=3.7e-5, motor_rated_rpm=3000),
}


# ---------------------------------------------------------------------------
# Motor catalog: a market search across makers. Specs and prices checked online
# 2026-11-12; see
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
FAMILIES = ("Industrial servo", "Integrated servo", "Budget servo kit", "Robotics torque motor")
ROBUST_FAMILIES = ("Industrial servo", "Integrated servo")
ROBUST_RESERVE = 0.30   # "robust" = at least 30 % spare on every check


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
    rated_rpm: float = 3000.0         # speed up to which rated torque holds
    cont_end: float = 0.5             # continuous torque at max speed, fraction of rated
    peak_knee_rpm: float = 0.0        # peak torque held up to here (0 = rated speed)
    peak_end: float = 0.35            # peak-zone torque at max speed, fraction of peak
    curve_note: str = "Approximate shape from rated, peak and speed ratings."

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
    # AutomationDirect SureServo2 (230 V AC). Motor list prices from the June 2025
    # SureServo2 selection guide; SV2A-2040 drive $429 and SV2L-202B $521 are the
    # current automationdirect.com prices. Curve shape from the published 230 V
    # torque-speed charts (peak held to about 4000 rpm, ~30 % of peak at 6000 rpm).
    Motor("AutomationDirect SV2L-202N (200 W)", 0.64, 2.24, 6000, 0.25e-4, 1100,
          brand="AutomationDirect", family="Industrial servo", supply="230 V AC",
          drive_model="SV2A-2040", price=315.0, drive_usd=429.0,
          seller="AutomationDirect", status="List price (motor: 2025 guide)",
          url="https://cdn.automationdirect.com/static/specs/ss2motors.pdf",
          peak_knee_rpm=4000, peak_end=0.30, curve_note="Shape from AutomationDirect's 230 V curves.",
          note="SureServo2 low inertia. Sold online at published prices."),
    Motor("AutomationDirect SV2L-202B (200 W, brake)", 0.64, 2.24, 6000, 0.28e-4, 1600,
          brand="AutomationDirect", family="Industrial servo", supply="230 V AC",
          drive_model="SV2A-2040", price=521.0, drive_usd=429.0,
          seller="AutomationDirect", status="In catalog, list price",
          url="https://www.automationdirect.com/adc/shopping/catalog/motion_control/sureservo2_(sv2a_series)_servo_systems/115-z-230v_servo_motors,_drives,_motor_cables/sv2l-202b",
          peak_knee_rpm=4000, peak_end=0.30, curve_note="Shape from AutomationDirect's 230 V curves.",
          note="Same motor with a holding brake: the choice for a vertical axis."),
    Motor("AutomationDirect SV2L-204N (400 W)", 1.27, 3.96, 6000, 0.45e-4, 1400,
          brand="AutomationDirect", family="Industrial servo", supply="230 V AC",
          drive_model="SV2A-2040", price=340.0, drive_usd=429.0,
          seller="AutomationDirect", status="List price (motor: 2025 guide)",
          url="https://cdn.automationdirect.com/static/specs/ss2motors.pdf",
          peak_knee_rpm=4000, peak_end=0.30, curve_note="Shape from AutomationDirect's 230 V curves.",
          note="SureServo2 low inertia."),
    Motor("AutomationDirect SV2L-207N (750 W)", 2.39, 7.86, 6000, 1.51e-4, 2800,
          brand="AutomationDirect", family="Industrial servo", supply="230 V AC",
          drive_model="SV2A-2075", price=364.0, drive_usd=477.0,
          seller="AutomationDirect", status="List price (2025 guide)",
          url="https://cdn.automationdirect.com/static/specs/ss2motors.pdf",
          peak_knee_rpm=4000, peak_end=0.30, curve_note="Shape from AutomationDirect's 230 V curves.",
          note="SureServo2 low inertia."),
    # Delta ASDA-B3 (220 V AC). Specs from Delta's ASDA-B3 catalog.
    Motor("Delta ECM-B3M-C20602 (200 W)", 0.64, 2.24, 6000, 0.141e-4, 900,
          brand="Delta", family="Industrial servo", supply="220 V AC",
          drive_model="ASD-B3-0221", price=None, drive_usd=None,
          seller="Delta distributor (quote)", status="Quote",
          url="https://www.mouser.com/datasheet/2/632/DELTA_IA_ASDA_ASDA_B3_C_EN_20230523_web-3318784.pdf",
          note="ASDA-B3 low inertia."),
    Motor("Delta ECM-B3M-C20604 (400 W)", 1.27, 4.45, 6000, 0.254e-4, 1200,
          brand="Delta", family="Industrial servo", supply="220 V AC",
          drive_model="ASD-B3-0421", price=918.22, currency="CAD", drive_usd=None,
          seller="DigiKey Canada", status="Motor C$918; drive quote",
          url="https://www.digikey.ca/en/products/detail/delta-electronics-industrial-automation/ECM-B3M-C20604RS1/21852603",
          note="ASDA-B3 low inertia. Price in Canadian dollars, motor only."),
    Motor("Delta ECM-B3M-C20807 (750 W)", 2.4, 8.4, 6000, 1.07e-4, 2340,
          brand="Delta", family="Industrial servo", supply="220 V AC",
          drive_model="ASD-B3-0721", price=None, drive_usd=None,
          seller="Delta distributor (quote)", status="Quote",
          url="https://www.mouser.com/datasheet/2/632/DELTA_IA_ASDA_ASDA_B3_C_EN_20230523_web-3318784.pdf",
          note="ASDA-B3 medium inertia."),
    # Omron 1S (200 V AC)
    Motor("Omron R88M-1M40030T (400 W)", 1.27, 4.5, 6000, 0.44e-4, None,
          brand="Omron", family="Industrial servo", supply="200 V AC",
          drive_model="R88D-1SN04H-ECT", price=2116.95, currency="NZD", drive_usd=None,
          seller="RS New Zealand", status="Motor NZ$2,117; drive quote",
          url="https://nz.rs-online.com/web/p/servo-motors/1362816",
          note="1S series. Price in New Zealand dollars, motor only."),
    # Leadshine EL7 / ELM2H (220 V AC)
    Motor("Leadshine ELM2H-0400LA60F (400 W)", 1.27, 3.81, 6500, 0.56e-4, 1300,
          brand="Leadshine", family="Industrial servo", supply="220 V AC",
          drive_model="EL7-EC400F", price=None, drive_usd=None,
          seller="Leadshine distributor (quote)", status="Quote",
          url="https://www.leadshine.com/product-detail/ELM2H-0400LA60F.html",
          note="Pairs with the EL7 EtherCAT drive."),
    # Integrated servos (motor + drive + encoder in one housing)
    Motor("Teknic ClearPath CPM-SDSK-2321S", 0.7, 3.5, 3240, 0.2e-4, 900,
          brand="Teknic", family="Integrated servo", supply="75 V DC (supply extra)",
          drive_model="built in", price=315.0, drive_included=True,
          seller="Teknic", status="In stock, list price",
          url="https://teknic.com/model-info/CPM-SDSK-2321S-RLN/",
          rated_rpm=1950, cont_end=0.6, peak_knee_rpm=1100, peak_end=0.3,
          curve_note="DC-bus motor: torque falls steadily with speed (approximate).",
          note="NEMA 23 with drive built in. Specs at 75 V DC."),
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
          note="Your motor. All values from datasheet.",
          cont_end=1.0, peak_end=0.0, curve_note="Rated torque held to the listed speed; peak falls toward rated near it (48 V)."),
    Motor("CubeMars RO60 KV115", 0.8, 2.4, 4200, 1161e-7, 248, brand="CubeMars",
          family="Robotics torque motor", supply="48 V DC", drive_model="ODrive S1",
          price=85.90, drive_usd=ODRIVE_S1_USD, seller="DigiKey", status="In stock",
          url="https://www.digikey.com/en/products/detail/cubemars/RO60-KV115/27612270",
          note="R60 successor, same ratings. Inertia from R60 datasheet.",
          cont_end=1.0, peak_end=0.0, curve_note="Rated torque held to the listed speed; peak falls toward rated near it (48 V)."),
    Motor("CubeMars RO80 KV105", 1.3, 4.0, 3600, 2125e-7, 352, j_estimated=True,
          brand="CubeMars", family="Robotics torque motor", supply="48 V DC",
          drive_model="ODrive S1", price=100.99, currency="EUR", drive_usd=ODRIVE_S1_USD,
          seller="MAB Robotics (EU)", status="Listed",
          url="https://www.mabrobotics.pl/product-page/ro80-cubemars-t-motor",
          note="Inertia scaled from RO80 Lite datasheet (1,600 g·cm²) by weight.",
          cont_end=1.0, peak_end=0.0, curve_note="Rated torque held to the listed speed; peak falls toward rated near it (48 V)."),
    Motor("CubeMars R80 KV110", 1.3, 4.0, 3600, 2490e-7, 354, j_estimated=True,
          brand="CubeMars", family="Robotics torque motor", supply="48 V DC",
          drive_model="ODrive S1", price=258.90, drive_usd=ODRIVE_S1_USD,
          seller="OZ Robotics", status="Listed",
          url="https://ozrobotics.com/shop/cubemars-r80-kv110-bldc-motor-with-built-in-hall-sensor/",
          note="Ø87 mm. Rotor inertia estimated.",
          cont_end=1.0, peak_end=0.0, curve_note="Rated torque held to the listed speed; peak falls toward rated near it (48 V)."),
    Motor("CubeMars R100 KV90", 3.7, 11.0, 3800, 7630e-7, 731, j_estimated=True,
          brand="CubeMars", family="Robotics torque motor", supply="48 V DC",
          drive_model="ODrive S1", price=426.90, drive_usd=ODRIVE_S1_USD,
          seller="OZ Robotics", status="Listed",
          url="https://ozrobotics.com/shop/cubemars-r100-kv90-bldc-motor-with-built-in-hall-sensor/",
          note="35 A continuous: near ODrive S1 limit. Rotor inertia estimated.",
          cont_end=1.0, peak_end=0.0, curve_note="Rated torque held to the listed speed; peak falls toward rated near it (48 V)."),
]

for _m in ALL_MOTORS:
    if _m.brand == "CubeMars":              # rated torque is held right up to max_rpm
        _m.rated_rpm, _m.peak_knee_rpm = _m.max_rpm, 0.5 * _m.max_rpm

CUBEMARS_R = sorted([m for m in ALL_MOTORS if m.brand == "CubeMars"],
                    key=lambda m: (m.rated_nm, m.total_usd if m.total_usd is not None else 1e9))
INDUSTRIAL = sorted([m for m in ALL_MOTORS if m.family == "Industrial servo"],
                    key=lambda m: (m.rated_nm, m.total_usd if m.total_usd is not None else 1e9))


def motor_inputs(inp: Inputs, m: Motor) -> Inputs:
    """The axis inputs with a catalog motor's data filled in."""
    return replace(inp, motor_rated_nm=m.rated_nm, motor_peak_nm=m.peak_nm,
                   motor_max_rpm=m.max_rpm, motor_j_kgm2=m.j_kgm2, motor_rated_rpm=m.rated_rpm,
                   env_cont_end=m.cont_end, env_peak_knee_rpm=m.peak_knee_rpm,
                   env_peak_end=m.peak_end)


def pick_motor(inp: Inputs, catalog=ALL_MOTORS):
    """Size the axis once per catalog motor (its rotor inertia changes the torque).

    Returns (rows, picks). Each row has the motor, its result, PASS/FAIL, what it
    fails on, how much of each limit it uses, and its headroom: 1 minus the
    largest share of any limit used (0.4 = 40 % spare on its tightest check).
    picks["cheapest"]: lowest listed total cost in USD that passes.
    picks["robust"]: an industrial or integrated servo with published specs that
    keeps at least ROBUST_RESERVE spare on every check; the smallest such motor
    (oversizing past that only adds cost and rotor inertia), cheapest among equal
    sizes, and one with a holding brake for a vertical axis. If none reaches
    the reserve, the one with the most headroom.
    """
    rows = []
    for m in catalog:
        r = size_axis(motor_inputs(inp, m), n=2000)
        status = {c[0].split(" (")[0]: c[3] for c in r.checks}
        fails = [k for k, ok in status.items() if not ok]
        uses = {c[0].split(" (")[0]: (c[1] / c[2] if c[2] > 0 else float("inf")) for c in r.checks}
        rows.append({"motor": m, "result": r, "ok": r.overall_ok, "fails": fails,
                     "peak_use": r.t_peak_req / m.peak_nm,
                     "rms_use": uses.get("RMS vs continuous torque", r.t_rms_req / m.rated_nm),
                     "speed_use": r.rpm_max / m.max_rpm,
                     "curve_use": uses.get("Torque at speed", 0.0),
                     "inertia_use": uses.get("Inertia ratio", 0.0),
                     "governing": r.governing,
                     "headroom": 1 - max(uses.values())})
    passing = [x for x in rows if x["ok"]]
    priced = [x for x in passing if x["motor"].total_usd is not None]
    robust = [x for x in passing if x["motor"].family in ROBUST_FAMILIES and not x["motor"].j_estimated]
    picks = {
        "cheapest": min(priced, key=lambda x: x["motor"].total_usd) if priced else None,
        "robust": None,
    }
    solid = [x for x in robust if x["headroom"] >= ROBUST_RESERVE]
    if solid:
        # vertical axes: a motor with a holding brake first
        picks["robust"] = min(solid, key=lambda x: (inp.vertical and "brake" not in x["motor"].model,
                                                    round(x["motor"].rated_nm, 1),
                                                    x["motor"].total_usd or 1e9))
    elif robust:
        picks["robust"] = max(robust, key=lambda x: x["headroom"])
    return rows, picks
