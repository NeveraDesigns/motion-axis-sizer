# Motion Axis Sizer

A web tool for sizing the motor on one linear axis of an automation machine, such as the
X, Y or Z axis of a pick-and-place mechanism in a semiconductor test handler.

You describe the axis (load, move and drive). The tool works out the torque, speed and
inertia the motor needs, checks real motors against those numbers, and shows every equation
it used.

![Results tab](docs/screenshot-results.png)

## What it does

- **Sizes the axis.** Trapezoidal motion profile, forces, reflected inertia, motor speed,
  torque in every phase of the cycle, and peak and RMS torque with a safety factor.
- **Handles three drive types**: ball screw, belt and pulley, rack and pinion, with an
  optional gearbox.
- **Checks a motor** from its datasheet. It reports PASS or FAIL on peak torque,
  continuous torque, speed and load-to-rotor inertia ratio, and explains failures in
  plain English.
- **Compares real motors.** CubeMars 48 V outrunner motors are compared with StepperOnline
  220 V AC servo kits, ranked by total cost including the driver. It picks the cheapest
  motor that passes and the smallest CubeMars that passes.
- **Shows its work.** Every formula is shown with your numbers plugged in and a sentence on
  what it means physically.
- **Saves and compares designs** side by side, and exports a one-page PDF report or a CSV.

![Motor selection tab](docs/screenshot-motors.png)

## Run it

**Online:** see the link at the top of this repository.

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

`HAND_CALC.md` works the "Heavy shuttle" example by hand. `test_hand_calc.py` confirms the
app matches it to within 0.1 %:

```
python test_hand_calc.py
```

## Files

| File | What it is |
|---|---|
| `app.py` | The screens: inputs, results, motor selection, equations, designs |
| `sizing.py` | The engineering math and the motor catalog (no screen code) |
| `extras.py` | Datasheet links, saved designs and the PDF report |
| `test_hand_calc.py` | Checks the math against an independent hand calculation |
| `HAND_CALC.md` | The hand calculation, step by step |
| `datasheets/DATASHEET INDEX.md` | Sources, specs and prices for every motor in the catalog |

## Model assumptions

- Trapezoidal or triangular move profile, with equal acceleration and deceleration times.
- Vertical axes are sized moving up, the worst case. Guide friction is ignored on vertical axes.
- External force acts for the whole cycle.
- Ball screw modeled as a solid steel cylinder; pulleys and pinions as solid discs.
- Couplings, bearings, seals and cable carriers are covered by the safety factor.
- Motor prices were checked online on 2026-11-12 and change. Rotor inertia for some
  CubeMars motors is estimated and marked with ≈.

This is an early-sizing tool. Confirm final selections with the manufacturer's sizing software.

## About

Engineering requirements, example axes and verification by Daniel Zubovic, mechanical
engineer. Code written with AI assistance (Claude).
