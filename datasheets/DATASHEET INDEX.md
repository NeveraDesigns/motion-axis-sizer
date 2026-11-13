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
