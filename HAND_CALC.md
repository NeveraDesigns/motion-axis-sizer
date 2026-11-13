# Hand calculation: "Heavy shuttle" preset

Work through this on paper, then compare with the app. Load the **Heavy shuttle** preset
and set **S-curve smoothing to 0 %**: a sharp-cornered (trapezoid) profile is the one you
can do by hand. `test_hand_calc.py` confirms the app matches every number below.

## Given
| Item | Value |
|---|---|
| Moving mass m | 5.0 kg payload + 1.0 kg carriage = **6.0 kg** |
| Orientation | Horizontal, μ = 0.01 |
| Move | 500 mm in 1.0 s, accel 25 % of the move, then 0.5 s dwell, then the same move back |
| Ball screw | lead 20 mm, Ø20 × 700 mm steel, η = 0.90, **drag torque 0.08 N·m** |
| Motor | rated 1.27 N·m, peak 3.82 N·m, 6000 rpm, rotor J = 0.37×10⁻⁴ kg·m² |
| Safety factor | 1.5 |

Drag torque is the torque needed just to turn the screw with no load: ball-nut preload,
seals and support bearings. Catalogs list it; for a preloaded Ø20 screw 0.05 to 0.15 N·m
is typical.

## 1. Motion profile
- t_a = 0.25 × 1.0 = **0.25 s** (decel also 0.25 s, constant velocity 0.50 s)
- v_max = S / (t_move − t_a) = 0.5 / 0.75 = **0.667 m/s**
- a = v_max / t_a = 0.667 / 0.25 = **2.67 m/s²**
- One cycle = out (1.0 s) + dwell (0.5 s) + back (1.0 s) + dwell (0.5 s) = **3.0 s**

## 2. Forces on the load (moving out)
- Friction F_f = μ m g = 0.01 × 6 × 9.81 = **0.589 N** (always opposes motion)
- Accelerating F = m a + F_f = 16.0 + 0.589 = **16.59 N**
- Decelerating F = −m a + F_f = −16.0 + 0.589 = **−15.41 N**

## 3. Transmission constant and inertia
- k = lead / 2π = 0.020 / 6.283 = **0.003183 m/rad**
- J_screw = π ρ L D⁴ / 32 = π × 7850 × 0.7 × 0.02⁴ / 32 = **8.63×10⁻⁵ kg·m²**
- J_load = m k² + J_screw = 6.08×10⁻⁵ + 8.63×10⁻⁵ = **1.471×10⁻⁴ kg·m²**
- Inertia ratio = 1.471×10⁻⁴ / 0.37×10⁻⁴ = **4.0 : 1** → OK
- Spinning parts J_rot = J_screw + J_motor = **1.233×10⁻⁴ kg·m²** (the 6 kg is handled as a force)

## 4. Speed
- rpm = v / lead × 60 = **2000 rpm**, α = a / k = **838 rad/s²**

## 5. Torque at the motor
The rule for efficiency: when the motor drives the load, divide by η; when the load
drives the motor (braking), multiply by η.

| Phase | Shaft torque F·k + drag | Through the screw | + J_rot·α | Motor torque |
|---|---|---|---|---|
| Accelerate | 16.59 × 0.003183 + 0.08 = 0.1328 | ÷ 0.9 = 0.1476 | + 0.1033 | **0.2509 N·m** |
| Constant | 0.589 × 0.003183 + 0.08 = 0.0819 | ÷ 0.9 = 0.0910 | 0 | **0.0910 N·m** |
| Decelerate | −15.41 × 0.003183 + 0.08 = +0.0309 | still driving, ÷ 0.9 = 0.0344 | − 0.1033 | **−0.0689 N·m** |
| Dwell | 0 | 0 | 0 | **0** |

The return move is the mirror image (same sizes, opposite signs).

Notice the deceleration row: drag is big enough that the motor is *still pushing* while
the load slows down. Without drag this axis would brake hard instead.

## 6. Peak and RMS
- T_peak = **0.251 N·m** → with SF 1.5: 0.376 N·m (motor peak 3.82 → PASS)
- T_rms = √[2 × (0.2509²·0.25 + 0.0910²·0.50 + 0.0689²·0.25 + 0²·0.5) / 3.0] = **0.1185 N·m**
  → with SF 1.5: 0.178 N·m (motor rated 1.27 → PASS)

## 7. What the app adds on top
The app's default is **50 % S-curve smoothing**. The ramps in acceleration take a quarter of
each accel period at each end, so peak acceleration rises to v / (t_a − t_j) =
0.667 / (0.25 − 0.0625) = **3.56 m/s²** (33 % higher) and peak torque rises to about
**0.304 N·m**. Top speed is unchanged. The app calculates the S-curve case by evaluating
torque at 6,000 points through the cycle.

## Takeaway for the interview
Before drag torque was included, this axis looked like it needed 0.156 N·m peak and
0.089 N·m RMS. With realistic drag and the return move, it needs **0.251 N·m peak and
0.118 N·m RMS**, 33 % more continuous torque. On small, fast axes, drag torque and
acceleration decide the motor; load friction barely matters.
