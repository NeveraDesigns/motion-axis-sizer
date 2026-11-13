"""
Checks the sizing engine against independent hand calculations.

1. Heavy shuttle, sharp-cornered (trapezoid) profile: every number in
   HAND_CALC.md, worked out step by step below, must match the app within 0.1 %.
2. S-curve smoothing: peak acceleration must equal v / (ta - tj).
3. Gearbox: reflected inertia drops with ratio², motor speed rises with ratio.
4. Vertical axis: gravity opposes the lift and helps on the way down.
5. The seven-case validation set in validation.py (also shown in the app).
6. Short, sharp S-curve move with a long dwell: the sampled peak acceleration
   must land within 0.5 % of the true peak.
7. Torque-speed envelope: the shape passes through its defining points.

Run it with:   python3 test_hand_calc.py
"""

import math
from dataclasses import replace

import numpy as np

import validation
from sizing import PRESETS, Inputs, size_axis, torque_envelope

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


def test_validation_set():
    bad = [r for r in validation.table() if not r["Match"]]
    assert not bad, bad


def test_short_move_peak_is_captured():
    inp = replace(validation._screw(stroke_mm=5, move_time_s=0.02, dwell_s=3.0), s_curve_pct=100)
    r = size_axis(inp)
    assert np.max(np.abs(r.acc)) >= 0.995 * r.a


def test_torque_envelope_shape():
    cont, pk = torque_envelope([0, 3000, 6000, 6001], rated=1.0, peak=3.0, rated_rpm=3000,
                               max_rpm=6000, cont_end=0.5, peak_knee_rpm=4000, peak_end=0.3)
    assert np.allclose(cont[:3], [1.0, 1.0, 0.5]) and cont[3] == 0
    assert np.allclose(pk[:3], [3.0, 3.0, 0.9]) and pk[3] == 0


def test_heating_check_weights_each_instant():
    # Below rated speed the continuous zone is flat, so the check is plain RMS vs rated.
    base = validation._screw(motor_rated_nm=0.5, motor_peak_nm=1.5, motor_max_rpm=6000,
                             motor_rated_rpm=4000)
    r = size_axis(base)
    c = {n.split(" (")[0]: (q, a) for n, q, a, ok in r.checks}
    assert abs(c["RMS vs continuous torque"][1] - 0.5) < 1e-9
    # Fast moves near top speed with a long dwell: weighting by each instant's
    # speed must be at least as strict as using one average speed.
    hot = replace(base, motor_max_rpm=1.02 * r.rpm_max, motor_rated_rpm=0.2 * r.rpm_max,
                  dwell_s=3.0)
    rh = size_axis(hot)
    n_avg = np.sum(np.abs(rh.rpm) * np.r_[np.diff(rh.ts), 0]) / rh.t_cycle
    cont_avg = float(torque_envelope(n_avg, 0.5, 1.5, hot.motor_rated_rpm, hot.motor_max_rpm)[0])
    avail = {n.split(" (")[0]: a for n, q, a, ok in rh.checks}["RMS vs continuous torque"]
    assert avail < cont_avg


def test_time_above_rated():
    # Rated torque set just under the accel torque: only the speed-up and slow-down
    # stretches are above it, each one accel time long.
    base = validation._screw(eta=1.0, drag=0.0)
    r0 = size_axis(base)
    inp = replace(base, motor_rated_nm=0.9 * r0.t_peak, motor_peak_nm=3 * r0.t_peak,
                  motor_max_rpm=3 * r0.rpm_max, motor_rated_rpm=3 * r0.rpm_max)
    r = size_axis(inp)
    assert abs(r.t_over_rated_s - r.t_acc) < 0.01 * r.t_acc


if __name__ == "__main__":
    test_heavy_shuttle_matches_hand_calc()
    test_s_curve_peak_acceleration()
    test_gearbox_divides_inertia_by_ratio_squared()
    test_vertical_gravity_helps_on_the_way_down()
    test_validation_set()
    test_short_move_peak_is_captured()
    test_torque_envelope_shape()
    test_heating_check_weights_each_instant()
    test_time_above_rated()
    print(f"Validation set: {len(validation.table())} quantities in {len(validation.cases())} cases match hand calcs.")
    print("All checks PASSED. Heavy shuttle (trapezoid) vs hand calculation:")
    r = size_axis(shuttle_trapezoid(), n=12000)
    for name, hand in expected.items():
        print(f"  {name:15s} hand = {hand:12.6g}   app = {getattr(r, name):12.6g}")
