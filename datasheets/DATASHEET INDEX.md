# Datasheet index — Motion Axis Sizer

Specs and prices checked online on 2026-11-12. Prices and stock change; check the link before buying.
"Official datasheet" = the manufacturer's PDF. Where none is published, the product page is the source.

## CubeMars (48 V DC outrunner torque motors — need a separate driver)

| Motor | Rated / peak torque | Speed at rated torque | Rotor inertia | Weight | Price found | Status |
|---|---|---|---|---|---|---|
| R60 KV115 (your motor) | 0.8 / 2.4 N·m | 4200 rpm | 1,161 g·cm² (published) | 248 g | $177.90 OZ Robotics | Discontinued, successor RO60 |
| RO60 KV115 | 0.8 / 2.4 N·m | 4200 rpm | use R60 value | 248 g | **$85.90 DigiKey** | In stock (37) |
| RO80 KV105 | 1.3 / 4.0 N·m | 3600 rpm | 1,600 g·cm² Lite (published); ≈2,125 Standard (est.) | 352 g | €100.99 MAB Robotics; $164.14 RobotShop CA | Listed |
| R80 KV110 | 1.3 / 4.0 N·m | 3600 rpm | ≈2,490 g·cm² (estimated) | 354 g | $258.90 OZ Robotics | Listed |
| R100 KV90 | 3.7 / 11 N·m | 3800 rpm | ≈7,630 g·cm² (estimated) | 731 g | $426.90 OZ Robotics | Listed |

- RO60 KV115 official datasheet (PDF): https://img.cubemars.com/products/cubemars-product-parameter/RO60-KV115.pdf
- RO80 Lite KV105 official datasheet (PDF): https://img.cubemars.com/products/cubemars-product-parameter/RO80-LITE-KV105.pdf
- R60 product page (full spec table, incl. inertia): https://www.cubemars.com/goods-943-R60.html
- R80 product page: https://cubemars.com/goods-944-R80+KV110.html
- R100 product page: https://www.cubemars.com/goods-945-R100%2BKV90.html
- R100 Hall sensor instructions (PDF): https://ozrobotics.com/wp-content/uploads/2021/09/Instructions-for-the-Hall-Sensor.pdf

## Driver for CubeMars motors

- ODrive S1: $149 (sold out when checked), 12–48 V, 40 A continuous. Datasheet: https://docs.odriverobotics.com/v/latest/hardware/s1-datasheet.html

## StepperOnline T6 series (220 V AC servo kits — motor + drive + cables)

| Kit | Rated / peak torque | Rated / peak speed | Rotor inertia | Motor weight | Price | Status |
|---|---|---|---|---|---|---|
| T6-RS400H2A3-M17S (400 W) | 1.27 / 3.81 N·m | 3000 / 5000 rpm | 0.56 ×10⁻⁴ kg·m² (560 g·cm²) | 1.3 kg | **$192.56** | In stock |
| T6-RS750H2A3-M17S (750 W) | (not captured) | | | | $228.28 | In stock |
| T6-RS1000H2A3-M17S (1000 W) | 3.19 / 9.56 N·m | 3000 / 5000 rpm | 2.15 ×10⁻⁴ kg·m² | 3.4 kg | $266.81 | Backorder |

- T6 400 W motor drawing (PDF): https://files.omc-stepperonline.com/T6M60-400H2A3-M17S.pdf
- T6 1000 W motor drawing, brake version (PDF, 186 KB): https://files.omc-stepperonline.com/T6M80-1000H2B3-M17S.pdf
- T6 servo simple manual (PDF, 539 KB): https://files.omc-stepperonline.com/T6_Servo_Simple_Manual.pdf
- T6 servo quick start (PDF, 2.0 MB): https://files.omc-stepperonline.com/T6_Servo_Quick_Start.pdf
- Cheaper alternative noted: A6-EC400H2A1-M17 400 W kit $112.05 (in stock) — EtherCAT only, needs an EtherCAT controller.

## Also checked (reference, not in the app's table)

- Yaskawa Sigma-7 SGM7J-02 (200 W): 0.637 / 2.23 N·m, 6000 rpm max, 0.263 ×10⁻⁴ kg·m². No public price. https://www.yaskawa.eu.com/motion-control/Sigma-7/s7-rotary-servomotors/productdetail/product/sgm7j-02dff21_6842
- Leadshine iSV2-RS6020V48H (200 W integrated 48 V DC servo): 0.64 / 1.92 N·m, 4000 rpm, 1.1 kg. No public price.
- StepperOnline iSV2-60TR-48V200A and E6 200 W kit: discontinued.

## Industrial servos (200 V AC, motor + matching drive) — added 2026-11-12

These are the families used on industrial machines such as semiconductor test handlers.
Prices are new-unit distributor list prices where one is published; most makers sell
through distributors on quote. "Max speed" is the maker's maximum; torque falls near it.

| Motor | Drive | Rated / peak torque | Max speed | Rotor inertia | Price found |
|---|---|---|---|---|---|
| Yaskawa SGM7J-02A (200 W) | SGD7S-1R6A00A | 0.637 / 2.23 N·m | 6000 rpm | 0.263×10⁻⁴ kg·m² | Motor $933 + drive $1,080 = **$2,013** (Automation Distribution, new) |
| Yaskawa SGM7J-04A (400 W) | SGD7S-2R8A00A | 1.27 / 4.46 N·m | 6000 rpm | 0.486×10⁻⁴ kg·m² | Motor $1,186 + drive $1,168 = **$2,354** (Automation Distribution, new) |
| Panasonic MSMF022 (200 W) | MADLN15SE | 0.64 / 1.91 N·m | 6000 rpm | 0.14×10⁻⁴ kg·m² | Quote |
| Panasonic MSMF042 (400 W) | MBDLN25SE | 1.27 / 3.82 N·m | 6000 rpm | 0.30×10⁻⁴ kg·m² | Motor $499 (e-motionsupply, new); drive quote |
| Mitsubishi HG-KN23 (200 W) | MR-JE-20A | 0.64 / 1.9 N·m | 5000 rpm (6000 with parameter) | 0.225×10⁻⁴ kg·m² | Quote |
| Mitsubishi HG-KN43 (400 W) | MR-JE-40A | 1.3 / 3.8 N·m | 5000 rpm | 0.375×10⁻⁴ kg·m² | Quote |
| Mitsubishi HG-KN73 (750 W) | MR-JE-70A | 2.4 / 7.2 N·m | 5000 rpm | 1.28×10⁻⁴ kg·m² | Quote |

Sources
- Yaskawa SGM7J-02 ratings: https://www.yaskawa.eu.com/motion-control/Sigma-7/s7-rotary-servomotors/productdetail/product/sgm7j-02dff21_6842
- Yaskawa SGM7J-04 ratings: https://www.yaskawa.eu.com/motion-control/Sigma-7/s7-rotary-servomotors/productdetail/product/sgm7j-04afa6s_1966
- Yaskawa prices: https://automationdistribution.com/yaskawa-sgm7j-02afa61-s7-motor-200w-200v-incremental-keyed-tapered-shaft/ ,
  https://automationdistribution.com/yaskawa-sgm7j-04afa6s-s7-motor-400w-200v-incremental-keyed-taper-shaft/ ,
  https://automationdistribution.com/yaskawa-sgd7s-1r6a00a-s7s-amp-200w-a-p-amplifier ,
  https://automationdistribution.com/yaskawa-sgd7s-2r8a00a-s7s-amp-400w-a-p
- Panasonic MSMF042 ratings: https://industry.panasonic.com/ap/en/products/motor/fa-motor/ac-servo/number/msmf042l1t2
- Panasonic MSMF022 ratings: https://powermatic.net/part/panasonic/msmf022l1u2/2774006
- Panasonic MSMF042 price: https://www.e-motionsupply.com/Panasonic_AC_Servo_Motors_MSMF042L1U2M_p/msmf042l1u2m.htm
- Mitsubishi HG-KN specifications: https://us.mitsubishielectric.com/fa/en/products/drive-products/ac-servos-melservo/mrje/motor/specifications/

Note: StepperOnline T6 kits are now checked against their 5000 rpm maximum speed (previously
3000 rpm rated) so all servos are compared the same way.

## Market search additions (checked 2026-11-12)

More makers, so the app's "Cheapest that passes" and "Most robust that passes" picks come
from a wider field. Rated speed is 3000 rpm for every AC servo here.

| Motor | Drive | Rated / peak torque | Max speed | Rotor inertia | Price found |
|---|---|---|---|---|---|
| AutomationDirect SV2L-202N (200 W) | SV2A-2040 | 0.64 / 2.24 N·m | 6000 rpm | 0.25×10⁻⁴ kg·m² | Motor $315 (June 2025 guide) + drive $429 (current) = **$744** |
| AutomationDirect SV2L-202B (200 W, brake) | SV2A-2040 | 0.64 / 2.24 N·m | 6000 rpm | 0.28×10⁻⁴ kg·m² | Motor $521 + drive $429 = **$950** (both current) |
| AutomationDirect SV2L-204N (400 W) | SV2A-2040 | 1.27 / 3.96 N·m | 6000 rpm | 0.45×10⁻⁴ kg·m² | Motor $340 (2025 guide) + drive $429 = **$769** |
| AutomationDirect SV2L-207N (750 W) | SV2A-2075 | 2.39 / 7.86 N·m | 6000 rpm | 1.51×10⁻⁴ kg·m² | Motor $364 + drive $477 (2025 guide) = **$841** |
| Delta ECM-B3M-C20602 (200 W) | ASD-B3-0221 | 0.64 / 2.24 N·m | 6000 rpm | 0.141×10⁻⁴ kg·m² | Quote |
| Delta ECM-B3M-C20604 (400 W) | ASD-B3-0421 | 1.27 / 4.45 N·m | 6000 rpm | 0.254×10⁻⁴ kg·m² | Motor C$918.22 (DigiKey Canada); drive quote |
| Delta ECM-B3M-C20807 (750 W) | ASD-B3-0721 | 2.4 / 8.4 N·m | 6000 rpm | 1.07×10⁻⁴ kg·m² | Quote |
| Omron R88M-1M40030T (400 W) | R88D-1SN04H-ECT | 1.27 / 4.5 N·m | 6000 rpm | 0.44×10⁻⁴ kg·m² | Motor NZ$2,116.95 (RS New Zealand); drive quote |
| Leadshine ELM2H-0400LA60F (400 W) | EL7-EC400F | 1.27 / 3.81 N·m | 6500 rpm | 0.56×10⁻⁴ kg·m² | Quote |
| Teknic ClearPath CPM-SDSK-2321S (integrated) | built in | 0.7 / 3.5 N·m at 75 V DC | 3240 rpm | 0.2×10⁻⁴ kg·m² | **$315** (Teknic), 75 V DC supply extra |

Torque-speed shapes used by the app (approximate; the maker's curve is the authority):
- AutomationDirect: peak held to ~4000 rpm, ~30 % of peak at 6000 rpm; continuous 50 % of
  rated at 6000 rpm (read from the 230 V curves in ss2motors.pdf).
- Other 200 V servos: peak held to rated speed, 35 % of peak at max speed; continuous 50 %.
- ClearPath: DC-bus motor, torque falls steadily with speed (rated to ~1950 rpm, 60 % at max).
- CubeMars: rated torque held to the listed speed, peak falling to rated there.

Sources
- SureServo2 motor specs and curves: https://cdn.automationdirect.com/static/specs/ss2motors.pdf
- SureServo2 selection guide with list prices (June 2025): https://cdn.automationdirect.com/static/archive/specs/ss2selection-2025-06-11--01-30-34.pdf
- SV2L-202B current price: https://www.automationdirect.com/adc/shopping/catalog/motion_control/sureservo2_(sv2a_series)_servo_systems/115-z-230v_servo_motors,_drives,_motor_cables/sv2l-202b
- SV2A-2040 current price: https://www.automationdirect.com/adc/shopping/catalog/motion_control/sureservo2_(sv2a_series)_servo_systems/115-z-230v_servo_motors,_drives,_motor_cables/sv2a-2040
- Delta ASDA-B3 catalog: https://www.mouser.com/datasheet/2/632/DELTA_IA_ASDA_ASDA_B3_C_EN_20230523_web-3318784.pdf
- Delta C20604 price: https://www.digikey.ca/en/products/detail/delta-electronics-industrial-automation/ECM-B3M-C20604RS1/21852603
- Omron 1S 400 W: https://nz.rs-online.com/web/p/servo-motors/1362816
- Leadshine ELM2H-0400LA60F: https://www.leadshine.com/product-detail/ELM2H-0400LA60F.html
- Teknic ClearPath CPM-SDSK-2321S-RLN: https://teknic.com/model-info/CPM-SDSK-2321S-RLN/ and
  https://www.automationtechnologiesinc.com/products-page/servo-products/clearpath-cpm-sdsk-2321s-rln
