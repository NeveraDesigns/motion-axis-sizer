# Hand calculation: "Heavy shuttle" preset

Work through this on paper, then compare with the app (load the **Heavy shuttle** preset).
The automated check `test_hand_calc.py` confirms the app matches these numbers.

## Given
| Item | Value |
|---|---|
| Moving mass m | 5.0 kg payload + 1.0 kg carriage = **6.0 kg** |
| Orientation | Horizontal, μ = 0.01 |
| Stroke S / move time | 500 mm in 1.0 s, accel 25 % of move, dwell 0.5 s |
| Ball screw | lead 20 mm, Ø20 mm × 700 mm steel, η = 0.90 |
| Motor (400 W class) | rated 1.27 N·m, peak 3.82 N·m, 6000 rpm, J = 3.7×10⁻⁵ kg·m² |
| Safety factor | 1.5 |

## 1. Motion profile
- t_a = 0.25 × 1.0 = **0.25 s** (decel also 0.25 s, constant velocity 0.50 s)
- v_max = S / (t_move − t_a) = 0.5 / 0.75 = **0.667 m/s**
- a = v_max / t_a = 0.667 / 0.25 = **2.67 m/s²** (0.27 g)

## 2. Forces
- F_friction = μ m g = 0.01 × 6 × 9.81 = **0.589 N**
- F_accel = m a = 6 × 2.67 = **16.0 N** (inertia does most of the work here)

## 3. Transmission constant
- k = lead / 2π = 0.020 / 6.283 = **0.003183 m/rad**

## 4. Inertia at the motor
- J_mass = m k² = 6 × 0.003183² = **6.08×10⁻⁵ kg·m²**
- J_screw = π ρ L D⁴ / 32 = π × 7850 × 0.7 × 0.02⁴ / 32 = **8.63×10⁻⁵ kg·m²**
  (the screw is heavier, rotationally, than the 6 kg load!)
- J_load = 6.08 + 8.63 = **1.471×10⁻⁴ kg·m²**
- Inertia ratio = 1.471×10⁻⁴ / 3.7×10⁻⁵ = **4.0 : 1** → OK (< 10:1)

## 5. Speed
- rpm = v / lead × 60 = 0.667 / 0.020 × 60 = **2000 rpm**
- α = a / k = 2.67 / 0.003183 = **838 rad/s²**

## 6. Torques
- T_load = F_friction k / η = 0.589 × 0.003183 / 0.9 = **0.0021 N·m**
- T_inertia = (J_load + J_motor) α = (1.471×10⁻⁴ + 0.37×10⁻⁴) × 838 = **0.1542 N·m**
- T_accel = 0.0021 + 0.1542 = **0.1563 N·m**
- T_const = **0.0021 N·m**
- T_decel = 0.0021 − 0.1542 = **−0.1522 N·m**
- T_dwell = **0** (horizontal, nothing to hold)

## 7. Peak and RMS
- T_peak = **0.156 N·m** → with SF 1.5: 0.234 N·m (motor peak 3.82 → PASS)
- T_rms = √[(0.1563²·0.25 + 0.0021²·0.5 + 0.1522²·0.25 + 0)/1.5] = **0.0891 N·m**
  → with SF 1.5: 0.134 N·m (motor rated 1.27 → PASS)

## Takeaway for the interview
This motor is heavily oversized on torque. The real constraint on fast axes is usually
**acceleration torque and inertia ratio**, not friction. A smaller motor would pass torque
but its smaller rotor would push the inertia ratio up, which is why that check matters.
