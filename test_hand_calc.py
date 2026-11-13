"""
Checks the sizing engine against independent hand calculations.

1. Heavy shuttle, sharp-cornered (trapezoid) profile: every number in
   HAND_CALC.md, worked out step by step below, must match the app within 0.1 %.
2. S-curve smoothing: peak acceleration must equal v / (ta - tj).
3. Gearbox: reflected inertia drops with ratio², motor speed rises with ratio.
4. Vertical axis: gravity opposes the lift and helps on the way down.

Run it with:   python3 test_hand_calc.py
"""

import math
from dataclasses import replace

from sizing import PRESETS, size_axis

# ---- Hand calculation: Heavy shuttle, trapezoid ---------------------------------
m = 5.0 + 1.0                       # kg
S, T, dwell = 0.500, 1.0, 0.5       # m, s, s
t_a = 0.25 * T                      # 0.25 s accel (and decel)
t_c = T - 2 * t_a                   # 0.50 s constant velocity
v = S / (T - t_a)                   # 0.6667 m/s
a = v / t_a                         # 2.6667 m/s²

eta = 0.9
drag = 0.08                         # N·m, ball screw preload + seals + support bearings
F_fric = 0.01 * m * 9.81            # 0.5886 N
lead = 0.020
k = lead / (2 * math.pi)            # 0.0031831 m/rad
J_mass = m * k**2                   # 6.079e-5 kg·m²
J_screw = math.pi * 7850 * 0.700 * 0.020**4 / 32   # 8.632e-5 kg·m²
J_load = J_mass + J_screw           # 1.471e-4 kg·m²
J_motor = 3.7e-5
J_rot = J_screw + J_motor           # spinning parts (the 6 kg is handled as a force)

rpm = v / lead * 60                 # 2000 rpm
alpha = a / k                       # 837.8 rad/s²

# Moving out. Motor drives the load -> divide by efficiency.
T_acc = ((m * a + F_fric) * k + drag) / eta + J_rot * alpha    # 0.2509 N·m
T_con = (F_fric * k + drag) / eta                               # 0.0910 N·m
# Decelerating: the shaft torque is still positive because drag outweighs
# the load's momentum, so the motor still drives -> divide by efficiency.
T_dec_shaft = (-m * a + F_fric) * k + drag                      # +0.0309 N·m
T_dec = (T_dec_shaft / eta if T_dec_shaft >= 0 else T_dec_shaft * eta) - J_rot * alpha
T_dwell = 0.0
# Moving back is the mirror image, so it adds the same squared torques.
T_cycle = 2 * (T + dwell)                                       # 3.0 s
T_rms = math.sqrt(2 * (T_acc**2 * t_a + T_con**2 * t_c + T_dec**2 * t_a + T_dwell**2 * dwell)
                  / T_cycle)                                    # 0.1185 N·m
T_peak = max(abs(T_acc), abs(T_dec))

expected = {
    "v_max": v, "a": a, "rpm_max": rpm, "j_load": J_load,
    "inertia_ratio": J_load / J_motor, "t_accel_phase": T_acc,
    "t_const_phase": T_con, "t_decel_phase": T_dec, "t_peak": T_peak, "t_rms": T_rms,
}


def shuttle_trapezoid():
    return replace(PRESETS["Heavy shuttle"], s_curve_pct=0)


def test_heavy_shuttle_matches_hand_calc():
    r = size_axis(shuttle_trapezoid(), n=12000)
    for name, hand in expected.items():
        app = getattr(r, name)
        assert math.isclose(app, hand, rel_tol=1e-3), f"{name}: app={app} hand={hand}"
    assert r.overall_ok is True


def test_s_curve_peak_acceleration():
    p = PRESETS["Heavy shuttle"]                     # 50 % smoothing
    r = size_axis(p)
    tj = 0.5 * t_a / 2
    assert math.isclose(r.a, v / (t_a - tj), rel_tol=1e-9)
    assert math.isclose(r.v_max, v, rel_tol=1e-9)    # smoothing doesn't change top speed
    assert r.t_peak > size_axis(shuttle_trapezoid()).t_peak


def test_gearbox_divides_inertia_by_ratio_squared():
    base = replace(shuttle_trapezoid(), motor_j_kgm2=0)
    r1 = size_axis(base)
    r5 = size_axis(replace(base, gear_ratio=5))
    assert math.isclose(r5.j_load, r1.j_load / 25, rel_tol=1e-9)
    assert math.isclose(r5.rpm_max, r1.rpm_max * 5, rel_tol=1e-9)


def test_vertical_gravity_helps_on_the_way_down():
    r = size_axis(PRESETS["Vertical Z pick axis"])
    assert r.t_const_phase > 0                       # lifting
    assert abs(r.t_back_const) < r.t_const_phase     # lowering needs less
    assert r.t_dwell_phase > 0                       # holding against gravity


if __name__ == "__main__":
    test_heavy_shuttle_matches_hand_calc()
    test_s_curve_peak_acceleration()
    test_gearbox_divides_inertia_by_ratio_squared()
    test_vertical_gravity_helps_on_the_way_down()
    print("All checks PASSED. Heavy shuttle (trapezoid) vs hand calculation:")
    r = size_axis(shuttle_trapezoid(), n=12000)
    for name, hand in expected.items():
        print(f"  {name:15s} hand = {hand:12.6g}   app = {getattr(r, name):12.6g}")
