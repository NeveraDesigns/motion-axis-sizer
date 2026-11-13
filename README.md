# Motion Axis Sizer

A web tool for sizing the motor on one linear axis of an automation machine, such as the
X, Y or Z axis of a pick-and-place mechanism in a semiconductor test handler.

You describe the axis (load, move and drive). The tool works out the torque, speed and
inertia the motor needs, checks real motors against those numbers, and shows every equation
it used.

**Try it online: https://motion-axis-sizer.streamlit.app**

![Results tab](docs/screenshot-results.png)

## What it does

- **Sizes the axis.** S-curve motion profile, forces, drive drag torque, reflected inertia,
  motor speed, and torque at every instant of a full out-and-back cycle (including gravity
  helping on the way down and losses switching direction when the load drives the motor),
  then peak and RMS torque with a safety factor.
- **Handles three drive types**: ball screw, belt and pulley, rack and pinion, with an
  optional gearbox.
- **Checks a motor** from its datasheet: peak torque, torque at every speed of the cycle
  against the motor's torque-speed envelope, continuous (RMS) torque, speed and
  load-to-rotor inertia ratio. It names the check that decides the motor and explains
  failures in plain English. A pass is a pass of these preliminary checks.
- **Torque vs speed chart.** Every instant of the cycle plotted over the motor's peak and
  continuous zones, the picture servo engineers use to qualify a motor.
- **Searches the market.** 24 motors from 10 makers: industrial servos (Yaskawa,
  Panasonic, Mitsubishi, Delta, Omron, Leadshine, AutomationDirect), an integrated servo
  (Teknic ClearPath), budget servo kits (StepperOnline) and robotics torque motors
  (CubeMars). It picks the **cheapest that passes** and the **most robust that passes**:
  the smallest industrial servo that keeps at least 30 % in reserve on every check (with
  a brake on vertical axes).
- **Shows its work.** Every formula is shown with your numbers plugged in and a sentence on
  what it means physically.
- **Saves and compares designs** side by side, and exports a one-page PDF report or a CSV.

![Motor selection tab](docs/screenshot-motors.png)

## Run it

**Online:** https://motion-axis-sizer.streamlit.app (nothing to install).

**On a Mac:** double-click `Start Motion Sizer.command`. The first run installs what it
needs; after that the tool opens at http://localhost:8501 in a few seconds.

**Anywhere with Python 3.9+:**

```
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Check the math

`HAND_CALC.md` works the "Heavy shuttle" example by hand. `validation.py` holds six more
independent hand calculations (frictionless axis, drag and efficiency, vertical lift/lower/
hold, gearbox, S-curve limits, and a very short move in a long dwell); the app shows them
live under *How it's calculated*. `test_hand_calc.py` runs them all, to within 0.1 %:

```
python test_hand_calc.py
```

## Files

| File | What it is |
|---|---|
| `app.py` | The screens: inputs, results, motor selection, equations, designs |
| `sizing.py` | The engineering math and the motor catalog (no screen code) |
| `extras.py` | Datasheet links, saved designs and the PDF report |
| `validation.py` | Six independent hand calculations the engine must match |
| `test_hand_calc.py` | Runs the hand calculations and other checks |
| `HAND_CALC.md` | The hand calculation, step by step |
| `Start Motion Sizer.command` | Mac: double-click to run the app |
| `Publish to GitHub.command` | Mac: double-click to upload your latest changes to GitHub |
| `datasheets/DATASHEET INDEX.md` | Sources, specs and prices for every motor in the catalog |

## Model assumptions

- S-curve move profile (0 % smoothing = trapezoid), equal acceleration and deceleration times.
- One cycle is move out, dwell, move back, dwell. Vertical axes lift on the way out.
- Guide friction is ignored on vertical axes. External force acts for the whole cycle.
- Drag torque is constant whenever the axis moves.
- Ball screw modeled as a solid steel cylinder; pulleys and pinions as solid discs.
- Torque-speed envelopes are approximate shapes built from each motor's ratings (using the
  maker's published shape where available). The real curve depends on drive and voltage.
- Not modeled: settling, compliance, accuracy, ball screw critical speed and life,
  cable-carrier forces.
- Coupling inertia and cable carriers are covered by the safety factor.
- Motor prices were checked online on 2026-11-12 and change. Totals are motor plus drive;
  power supplies are not included. "Cheapest" and "smallest" mean within this catalog. Rotor inertia for some
  CubeMars motors is estimated and marked with ≈.

This is an early-sizing tool. Confirm final selections with the manufacturer's sizing software.

## About

Engineering requirements, example axes and verification by Daniel Zubovic, mechanical
engineer. Code written with AI assistance (Claude).
