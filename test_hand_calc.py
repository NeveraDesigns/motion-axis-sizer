"""
Hand-calculation check for the "Heavy shuttle" preset.

The numbers below are worked out step by step, independently of sizing.py,
exactly as you would on paper (see HAND_CALC.md). The test passes if the app's
engine agrees with the hand calc to within 0.1%.

Run it with:   python3 test_hand_calc.py
"""

import math
from sizing import PRESETS, size_axis

# ---- Hand calculation: Heavy shuttle --------------------------------------
m = 5.0 + 1.0                       # kg, payload + carriage
S, T, dwell = 0.500, 1.0, 0.5       # m, s, s
t_a = 0.25 * T                      # 0.25 s accel (and decel)
t_c = T - 2 * t_a                   # 0.50 s constant velocity
v = S / (T - t_a)                   # 0.6667 m/s
a = v / t_a                         # 2.6667 m/s²

F_fric = 0.01 * m * 9.81            # 0.5886 N
lead = 0.020
k = lead / (2 * math.pi)            # 0.0031831 m/rad
J_mass = m * k**2                   # 6.079e-5 kg·m²
J_screw = math.pi * 7850 * 0.700 * 0.020**4 / 32   # 8.632e-5 kg·m²
J_load = J_mass + J_screw           # 1.471e-4 kg·m²
J_motor = 3.7e-5
J_total = J_load + J_motor          # 1.841e-4 kg·m²

rpm = v / lead * 60                 # 2000 rpm
alpha = a / k                       # 837.8 rad/s²

T_load = F_fric * k / 0.9           # 0.002082 N·m
T_inert = J_total * alpha           # 0.15424 N·m
T_acc = T_load + T_inert            # 0.15632 N·m
T_con = T_load
T_dec = T_load - T_inert            # -0.15216 N·m
T_dwell = 0.0

T_rms = math.sqrt((T_acc**2 * t_a + T_con**2 * t_c + T_dec**2 * t_a + T_dwell**2 * dwell)
                  / (T + dwell))    # 0.0890 N·m
T_peak = max(abs(T_acc), abs(T_dec))

expected = {
    "v_max": v, "a": a, "rpm_max": rpm, "j_load": J_load,
    "inertia_ratio": J_load / J_motor, "t_load": T_load, "t_inertia": T_inert,
    "t_accel_phase": T_acc, "t_decel_phase": T_dec, "t_peak": T_peak, "t_rms": T_rms,
}


def test_heavy_shuttle():
    r = size_axis(PRESETS["Heavy shuttle"])
    for name, hand in expected.items():
        app = getattr(r, name)
        assert math.isclose(app, hand, rel_tol=1e-3), f"{name}: app={app} hand={hand}"
    assert r.overall_ok is True


def test_gearbox_divides_inertia_by_ratio_squared():
    from dataclasses import replace
    base = PRESETS["Heavy shuttle"]
    r1 = size_axis(replace(base, motor_j_kgm2=0))
    r5 = size_axis(replace(base, motor_j_kgm2=0, gear_ratio=5))
    assert math.isclose(r5.j_load, r1.j_load / 25, rel_tol=1e-9)
    assert math.isclose(r5.rpm_max, r1.rpm_max * 5, rel_tol=1e-9)


if __name__ == "__main__":
    test_heavy_shuttle()
    test_gearbox_divides_inertia_by_ratio_squared()
    print("Hand-calc test PASSED. App matches the hand calculation:")
    r = size_axis(PRESETS["Heavy shuttle"])
    for name, hand in expected.items():
        print(f"  {name:15s} hand = {hand:12.6g}   app = {getattr(r, name):12.6g}")
