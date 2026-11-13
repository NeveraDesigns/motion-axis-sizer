"""
Validation set: six independent hand calculations the sizing engine must match.

Each case sets up a simple axis whose answer can be worked out on paper, works
it out here without using the engine, then runs the engine and compares. The
app shows the table live (How it's calculated tab) and test_hand_calc.py runs it.
"""

from __future__ import annotations

import math
from dataclasses import replace

from sizing import G, RHO_STEEL, Inputs, size_axis

TOL = 1e-3   # 0.1 %


def _screw(m=2.0, lead=10.0, dia=12.0, length=300.0, eta=0.9, drag=0.05, J_motor=2e-5, **kw):
    base = Inputs(drive="Ball screw", payload_kg=m, carriage_kg=0.0, mu=0.0, f_ext_n=0.0,
                  stroke_mm=200, move_time_s=0.5, accel_pct=25, s_curve_pct=0, dwell_s=0.2,
                  lead_mm=lead, screw_dia_mm=dia, screw_len_mm=length, screw_eff=eta,
                  drag_nm=drag, motor_j_kgm2=J_motor, safety_factor=1.0)
    return replace(base, **kw)


def _geom(inp):
    k = inp.lead_mm / 1000 / (2 * math.pi)
    J_screw = math.pi * RHO_STEEL * (inp.screw_len_mm / 1000) * (inp.screw_dia_mm / 1000) ** 4 / 32
    T, ta = inp.move_time_s, inp.accel_pct / 100 * inp.move_time_s
    v = inp.stroke_mm / 1000 / (T - ta)
    return k, J_screw, T, ta, v


def cases():
    out = []

    # 1. Horizontal, frictionless, no losses: torque is pure inertia ------------
    inp = _screw(eta=1.0, drag=0.0)
    k, Js, T, ta, v = _geom(inp)
    a = v / ta
    m = inp.payload_kg
    hand = (m * k**2 + Js + inp.motor_j_kgm2) * a / k
    r = size_axis(inp)
    out.append(("Horizontal, frictionless", "Pure inertia: T = (m·k² + J_screw + J_motor)·α",
                [("Peak torque (N·m)", hand, r.t_peak),
                 ("Acceleration (m/s²)", a, r.a)]))

    # 2. Constant speed with friction, drag and efficiency ----------------------
    inp = _screw(mu=0.05, eta=0.85, drag=0.08)
    k, Js, T, ta, v = _geom(inp)
    F = 0.05 * inp.payload_kg * G
    hand = (F * k + inp.drag_nm) / inp.screw_eff
    r = size_axis(inp)
    out.append(("Constant speed with drag", "T = (μ·m·g·k + drag) / η",
                [("Constant-speed torque (N·m)", hand, r.t_const_phase)]))

    # 3. Vertical: lift, lower, hold -------------------------------------------
    inp = _screw(vertical=True, m=3.0, eta=0.9, drag=0.02)
    k, Js, T, ta, v = _geom(inp)
    W = inp.payload_kg * G
    up = (W * k + inp.drag_nm) / inp.screw_eff          # motor lifts: divide by η
    down = (W * k - inp.drag_nm) * inp.screw_eff        # load drives the motor: multiply by η
    assert W * k > inp.drag_nm                          # (gravity outweighs drag here)
    hold = W * k * inp.screw_eff
    r = size_axis(inp)
    out.append(("Vertical lift, lower, hold", "Lift ÷ η, lower and hold × η",
                [("Lifting torque (N·m)", up, r.t_const_phase),
                 ("Lowering torque (N·m)", down, r.t_back_const),
                 ("Holding torque (N·m)", hold, r.t_dwell_phase)]))

    # 4. Gear reduction --------------------------------------------------------
    N, eg = 5.0, 0.95
    base = _screw(mu=0.02, J_motor=0.0)
    inp = replace(base, gear_ratio=N, gear_eff=eg)
    k, Js, T, ta, v = _geom(inp)
    m = inp.payload_kg
    r1, r = size_axis(base), size_axis(inp)
    hand_c = (0.02 * m * G * k + inp.drag_nm) / (inp.screw_eff * eg * N)
    out.append(("Gear reduction 5:1", "Speed × N, inertia ÷ N², torque ÷ (N·η_gear)",
                [("Motor speed (rpm)", r1.rpm_max * N, r.rpm_max),
                 ("Reflected inertia (kg·m²)", (m * k**2 + Js) / N**2, r.j_load),
                 ("Constant-speed torque (N·m)", hand_c, r.t_const_phase)]))

    # 5. S-curve limits: 0 % (trapezoid) and 100 % (pure S) ---------------------
    inp0, inp1 = _screw(s_curve_pct=0), _screw(s_curve_pct=100)
    k, Js, T, ta, v = _geom(inp0)
    r0, r1 = size_axis(inp0), size_axis(inp1)
    r50 = size_axis(_screw(s_curve_pct=50))
    out.append(("S-curve 0, 50 and 100 %", "Peak accel = v / (t_a − t_j), t_j = smoothing × t_a / 2",
                [("Peak accel at 0 % (m/s²)", v / ta, r0.a),
                 ("Peak accel at 50 % (m/s²)", v / (0.75 * ta), r50.a),
                 ("Peak accel at 100 % (m/s²)", 2 * v / ta, r1.a)]))

    # 6. Very short move with a long dwell --------------------------------------
    inp = _screw(stroke_mm=10, move_time_s=0.04, dwell_s=2.0, mu=0.01)
    k, Js, T, ta, v = _geom(inp)
    a = v / ta
    m = inp.payload_kg
    J_rot = Js + inp.motor_j_kgm2
    eta = inp.screw_eff
    Ff = 0.01 * m * G
    T_acc = ((m * a + Ff) * k + inp.drag_nm) / eta + J_rot * a / k
    T_con = (Ff * k + inp.drag_nm) / eta
    sh = (-m * a + Ff) * k + inp.drag_nm
    T_dec = (sh / eta if sh >= 0 else sh * eta) - J_rot * a / k
    tc = T - 2 * ta
    cyc = 2 * (T + inp.dwell_s)
    rms = math.sqrt(2 * (T_acc**2 * ta + T_con**2 * tc + T_dec**2 * ta) / cyc)
    r = size_axis(inp)
    out.append(("Short move, long dwell", "10 mm in 40 ms, then 2 s stopped: RMS by hand",
                [("Peak torque (N·m)", max(abs(T_acc), abs(T_dec)), r.t_peak),
                 ("RMS torque (N·m)", rms, r.t_rms)]))
    return out


def table():
    """Rows for display: case, quantity, hand, app, error %, match."""
    rows = []
    for name, rule, items in cases():
        for q, hand, app in items:
            err = abs(app - hand) / max(abs(hand), 1e-15)
            rows.append({"Case": name, "Rule": rule, "Quantity": q, "Hand calc": hand,
                         "App": app, "Error %": err * 100, "Match": err <= TOL})
    return rows
