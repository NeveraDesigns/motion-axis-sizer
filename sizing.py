"""
Motion axis sizing engine.

All math lives here, separate from the screen layout in app.py, so it can be
tested on its own. Everything is SI internally (m, kg, s, N, N·m, rad).

Sign convention: the axis moves in the positive direction (for a vertical
axis that means moving UP, the worst case, because the motor lifts the load).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np

G = 9.81            # gravity, m/s²
RHO_STEEL = 7850.0  # steel density, kg/m³

DRIVES = ("Ball screw", "Belt & pulley", "Rack & pinion")


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
    # Motion profile
    m_kg: float = 0.0
    t_acc: float = 0.0
    t_const: float = 0.0
    t_cycle: float = 0.0
    v_max: float = 0.0
    a: float = 0.0
    # Drive
    k: float = 0.0              # m of travel per rad of drive shaft
    drive_eff: float = 1.0
    eff_total: float = 1.0
    # Forces (N)
    f_friction: float = 0.0
    f_gravity: float = 0.0
    f_ext: float = 0.0
    f_const: float = 0.0        # force the motor fights while moving
    f_hold: float = 0.0         # force while stopped (dwell)
    f_accel: float = 0.0        # m·a
    # Inertia at the motor (kg·m²)
    j_mass: float = 0.0         # moving mass reflected
    j_drive: float = 0.0        # screw / pulleys / pinion
    j_load: float = 0.0         # (j_mass + j_drive) / N²
    j_motor: float = 0.0
    j_total: float = 0.0
    inertia_ratio: float = float("nan")
    # Motor speed / accel
    omega_max: float = 0.0      # rad/s at motor
    rpm_max: float = 0.0
    alpha: float = 0.0          # rad/s² at motor
    # Torques at motor (N·m)
    t_load: float = 0.0
    t_inertia: float = 0.0
    t_accel_phase: float = 0.0
    t_const_phase: float = 0.0
    t_decel_phase: float = 0.0
    t_dwell_phase: float = 0.0
    t_peak: float = 0.0
    t_rms: float = 0.0
    t_peak_req: float = 0.0
    t_rms_req: float = 0.0
    phases: list = field(default_factory=list)
    checks: list = field(default_factory=list)    # (name, required, available, ok)
    warnings: list = field(default_factory=list)
    motor_entered: bool = False
    overall_ok: bool | None = None


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


def size_axis(inp: Inputs) -> Results:
    r = Results()
    N = inp.gear_ratio if inp.gear_ratio > 0 else 1.0

    # 1. Trapezoidal motion profile ------------------------------------
    r.m_kg = inp.payload_kg + inp.carriage_kg
    S = inp.stroke_mm / 1000
    T = inp.move_time_s
    pct = min(max(inp.accel_pct, 1.0), 50.0) / 100
    r.t_acc = pct * T
    r.t_const = T - 2 * r.t_acc
    r.v_max = S / (T - r.t_acc)
    r.a = r.v_max / r.t_acc
    r.t_cycle = T + inp.dwell_s

    # 2. Forces ----------------------------------------------------------
    if inp.vertical:
        # Load hangs on the drive; guides carry almost no normal force.
        r.f_gravity = r.m_kg * G
        r.f_friction = 0.0
    else:
        r.f_gravity = 0.0
        r.f_friction = inp.mu * r.m_kg * G
    r.f_ext = inp.f_ext_n
    r.f_const = r.f_friction + r.f_gravity + r.f_ext
    r.f_hold = r.f_gravity + r.f_ext          # no sliding friction at rest
    r.f_accel = r.m_kg * r.a

    # 3. Reflected inertia ----------------------------------------------
    r.k, r.j_drive, r.drive_eff = drive_geometry(inp)
    r.eff_total = r.drive_eff * (inp.gear_eff if inp.gear_eff > 0 else 1.0)
    r.j_mass = r.m_kg * r.k**2
    r.j_load = (r.j_mass + r.j_drive) / N**2
    r.j_motor = inp.motor_j_kgm2
    r.j_total = r.j_load + r.j_motor
    if r.j_motor > 0:
        r.inertia_ratio = r.j_load / r.j_motor

    # 4. Motor speed and angular acceleration ----------------------------
    r.omega_max = r.v_max / r.k * N
    r.rpm_max = r.omega_max * 60 / (2 * math.pi)
    r.alpha = r.a / r.k * N

    # 5. Torque at the motor in each phase -------------------------------
    r.t_load = r.f_const * r.k / (r.eff_total * N)
    r.t_inertia = r.j_total * r.alpha
    r.t_accel_phase = r.t_load + r.t_inertia
    r.t_const_phase = r.t_load
    r.t_decel_phase = r.t_load - r.t_inertia
    r.t_dwell_phase = r.f_hold * r.k / (r.eff_total * N)

    r.phases = [
        ("Accelerate", r.t_acc, r.f_const + r.f_accel, r.t_accel_phase),
        ("Constant velocity", r.t_const, r.f_const, r.t_const_phase),
        ("Decelerate", r.t_acc, r.f_const - r.f_accel, r.t_decel_phase),
        ("Dwell", inp.dwell_s, r.f_hold, r.t_dwell_phase),
    ]

    r.t_peak = max(abs(p[3]) for p in r.phases)
    r.t_rms = math.sqrt(sum(p[3] ** 2 * p[1] for p in r.phases) / r.t_cycle)
    r.t_peak_req = r.t_peak * inp.safety_factor
    r.t_rms_req = r.t_rms * inp.safety_factor

    # 6. Motor checks ------------------------------------------------------
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

    # Plain-English warnings ----------------------------------------------
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
                 "from a motor datasheet to check a specific motor.")
    if inp.motor_j_kgm2 <= 0:
        w.append("Rotor inertia not entered, so the inertia ratio can't be checked and "
                 "acceleration torque ignores the motor's own rotor.")
    if inp.drive == "Ball screw" and r.rpm_max / N > 3000:
        w.append(f"Screw speed is {r.rpm_max / N:.0f} rpm. Long or thin screws can whip "
                 "near their critical speed; check the manufacturer's critical-speed chart "
                 "or use a longer lead.")
    if inp.accel_pct >= 50:
        w.append("Accel time is 50% of the move: this is a triangular profile with no "
                 "constant-velocity section. It gives the lowest peak speed but the "
                 "highest acceleration torque for the same move time.")
    if inp.vertical and inp.drive == "Ball screw" and inp.dwell_s > 0:
        w.append("Vertical axis: the motor must hold the load during dwell. Most designs "
                 "add a motor brake so the load can't drop when power is off.")
    if inp.vertical and inp.drive != "Ball screw":
        w.append("Vertical belt or rack axes back-drive easily. You will need a brake "
                 "and possibly a counterbalance.")
    if r.t_decel_phase < 0:
        w.append("During deceleration the torque goes negative: the load is driving the "
                 "motor (regeneration). Fine for most servo drives, but on heavy, fast "
                 "axes check whether the drive needs a regen/braking resistor.")
    return r


def profile_timeseries(inp: Inputs, r: Results, n: int = 400):
    """Position (mm), velocity (m/s), acceleration (m/s²), torque (N·m) vs time."""
    t = np.linspace(0, r.t_cycle, n)
    t1, t2, T = r.t_acc, r.t_acc + r.t_const, inp.move_time_s
    a, v = r.a, r.v_max
    pos = np.zeros_like(t); vel = np.zeros_like(t)
    acc = np.zeros_like(t); tq = np.zeros_like(t)
    s1 = 0.5 * a * t1**2
    s2 = s1 + v * r.t_const
    for i, ti in enumerate(t):
        if ti < t1:
            acc[i], vel[i], pos[i], tq[i] = a, a * ti, 0.5 * a * ti**2, r.t_accel_phase
        elif ti < t2:
            acc[i], vel[i], pos[i], tq[i] = 0, v, s1 + v * (ti - t1), r.t_const_phase
        elif ti < T:
            dt = ti - t2
            acc[i], vel[i] = -a, v - a * dt
            pos[i], tq[i] = s2 + v * dt - 0.5 * a * dt**2, r.t_decel_phase
        else:
            acc[i], vel[i], pos[i], tq[i] = 0, 0, inp.stroke_mm / 1000, r.t_dwell_phase
    return t, pos * 1000, vel, acc, tq


PRESETS = {
    "IC pick-and-place X axis": Inputs(
        drive="Belt & pulley", payload_kg=0.5, carriage_kg=0.2, vertical=False, mu=0.01,
        stroke_mm=300, move_time_s=0.4, accel_pct=25, dwell_s=0.2,
        pulley_pd_mm=30, pulley_kg=0.05, belt_eff=0.95,
        motor_rated_nm=0.64, motor_peak_nm=1.91, motor_max_rpm=6000, motor_j_kgm2=1.8e-5),
    "Vertical Z pick axis": Inputs(
        drive="Ball screw", payload_kg=0.3, carriage_kg=0.2, vertical=True, mu=0.01,
        stroke_mm=20, move_time_s=0.1, accel_pct=25, dwell_s=0.3,
        lead_mm=10, screw_dia_mm=8, screw_len_mm=150, screw_eff=0.9,
        motor_rated_nm=0.32, motor_peak_nm=0.95, motor_max_rpm=6000, motor_j_kgm2=6e-6),
    "Heavy shuttle": Inputs(
        drive="Ball screw", payload_kg=5.0, carriage_kg=1.0, vertical=False, mu=0.01,
        stroke_mm=500, move_time_s=1.0, accel_pct=25, dwell_s=0.5,
        lead_mm=20, screw_dia_mm=20, screw_len_mm=700, screw_eff=0.9,
        motor_rated_nm=1.27, motor_peak_nm=3.82, motor_max_rpm=6000, motor_j_kgm2=3.7e-5),
}


# ---------------------------------------------------------------------------
# Motor catalog (prices and specs checked online 2026-11-12).
#
#   CubeMars R / RO series: 48 V DC outrunner torque motors. They need a
#   separate motor driver; ODrive S1 (12-48 V, 40 A continuous, $149) is used
#   as the reference driver for total cost.
#   StepperOnline T6 series: 220 V AC industrial servo kits, drive included.
#
#   Rotor inertia: R60 is published (1,161 g·cm²); RO80 Lite is published
#   (1,600 g·cm² at 265 g). R80, R100 and RO80 Standard are ESTIMATED by
#   scaling those by weight (and diameter² for R80/R100).
#   max_rpm = speed the motor holds at rated torque (not no-load speed).
# ---------------------------------------------------------------------------
ODRIVE_S1_USD = 149.0


@dataclass
class Motor:
    model: str
    rated_nm: float
    peak_nm: float
    max_rpm: float
    j_kgm2: float
    weight_g: float
    j_estimated: bool = False
    note: str = ""
    brand: str = ""
    supply: str = ""
    price: float | None = None        # motor (or kit) price as listed
    currency: str = "USD"
    drive_included: bool = False
    drive_usd: float = 0.0            # extra drive cost if not included
    seller: str = ""
    status: str = ""
    url: str = ""

    @property
    def total_usd(self):
        if self.price is None or self.currency != "USD":
            return None
        return self.price + (0.0 if self.drive_included else self.drive_usd)


ALL_MOTORS = [
    Motor("CubeMars R60 KV115", 0.8, 2.4, 4200, 1161e-7, 248, brand="CubeMars",
          supply="48 V DC", price=177.90, drive_usd=ODRIVE_S1_USD, seller="OZ Robotics",
          status="Discontinued (successor: RO60)",
          url="https://ozrobotics.com/shop/cubemars-r60-kv115-bldc-motor-with-built-in-hall-sensor/",
          note="Your motor. All values from datasheet."),
    Motor("CubeMars RO60 KV115", 0.8, 2.4, 4200, 1161e-7, 248, brand="CubeMars",
          supply="48 V DC", price=85.90, drive_usd=ODRIVE_S1_USD, seller="DigiKey",
          status="In stock (37)",
          url="https://www.digikey.com/en/products/detail/cubemars/RO60-KV115/27612270",
          note="R60 successor, same ratings. Inertia from R60 datasheet."),
    Motor("CubeMars RO80 KV105", 1.3, 4.0, 3600, 2125e-7, 352, j_estimated=True,
          brand="CubeMars", supply="48 V DC", price=100.99, currency="EUR",
          drive_usd=ODRIVE_S1_USD, seller="MAB Robotics (EU)", status="Listed",
          url="https://www.mabrobotics.pl/product-page/ro80-cubemars-t-motor",
          note="Inertia scaled from RO80 Lite datasheet (1,600 g·cm²) by weight."),
    Motor("CubeMars R80 KV110", 1.3, 4.0, 3600, 2490e-7, 354, j_estimated=True,
          brand="CubeMars", supply="48 V DC", price=258.90, drive_usd=ODRIVE_S1_USD,
          seller="OZ Robotics", status="Listed",
          url="https://ozrobotics.com/shop/cubemars-r80-kv110-bldc-motor-with-built-in-hall-sensor/",
          note="Ø87 mm. Rotor inertia estimated."),
    Motor("CubeMars R100 KV90", 3.7, 11.0, 3800, 7630e-7, 731, j_estimated=True,
          brand="CubeMars", supply="48 V DC", price=426.90, drive_usd=ODRIVE_S1_USD,
          seller="OZ Robotics", status="Listed",
          url="https://ozrobotics.com/shop/cubemars-r100-kv90-bldc-motor-with-built-in-hall-sensor/",
          note="Ø~106 mm. Rotor inertia estimated. 35 A continuous: near ODrive S1 limit."),
    Motor("StepperOnline T6 400W kit (T6-RS400H2A3-M17S)", 1.27, 3.81, 3000, 0.56e-4, 1300,
          brand="StepperOnline", supply="220 V AC", price=192.56, drive_included=True,
          seller="StepperOnline", status="In stock",
          url="https://www.omc-stepperonline.com/t6-series-400w-ac-servo-motor-kit-3000rpm-1-27nm-17-bit-encoder-ip65-t6-rs400h2a3-m17s",
          note="Motor + drive + cables. 17-bit encoder."),
    Motor("StepperOnline T6 1000W kit (T6-RS1000H2A3-M17S)", 3.19, 9.56, 3000, 2.15e-4, 3400,
          brand="StepperOnline", supply="220 V AC", price=266.81, drive_included=True,
          seller="StepperOnline", status="Backorder",
          url="https://www.omc-stepperonline.com/t6-series-1000w-ac-servo-motor-kit-3000rpm-3-19nm-w-brake-17-bit-encoder-ip65-t6-rs1000h2b3-m17s",
          note="Motor + drive + cables. Inertia/weight from the brake version's page."),
]

CUBEMARS_R = sorted([m for m in ALL_MOTORS if m.brand == "CubeMars"],
                    key=lambda m: (m.rated_nm, m.total_usd if m.total_usd is not None else 1e9))


def pick_motor(inp: Inputs, catalog=CUBEMARS_R):
    """Size the axis once per catalog motor (rotor inertia changes the torque),
    and return (rows, recommended_model). Recommended = first (smallest) that
    passes every check."""
    from dataclasses import replace
    rows, best = [], None
    for m in catalog:
        r = size_axis(replace(inp, motor_rated_nm=m.rated_nm, motor_peak_nm=m.peak_nm,
                              motor_max_rpm=m.max_rpm, motor_j_kgm2=m.j_kgm2))
        status = {c[0].split(" (")[0]: c[3] for c in r.checks}
        fails = [k for k, ok in status.items() if not ok]
        rows.append({"motor": m, "result": r, "ok": r.overall_ok, "fails": fails,
                     "peak_use": r.t_peak_req / m.peak_nm,
                     "rms_use": r.t_rms_req / m.rated_nm,
                     "speed_use": r.rpm_max / m.max_rpm})
        if best is None and r.overall_ok:
            best = m.model
    return rows, best
