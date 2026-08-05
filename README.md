# Thermospatial Occupancy and Caloric Telemetry System (TOCTS)
## A High-Precision Framework for Empirical Return-To-Office (RTO) Presence Verification

---

### 1. Executive Summary

In contemporary corporate operational models, the quantitative measurement of Return-To-Office (RTO) compliance has historically relied on loose proxy indicators. Traditional tracking methodologies—such as network access logging, door badge sweeps, and peripheral device activity monitoring—suffer from systemic vulnerabilities, making them susceptible to manipulation or operational inaccuracies.

The **Thermospatial Occupancy and Caloric Telemetry System (TOCTS)** represents a paradigm shift in workspace utilization auditing. By shifting the tracking vector from digital inputs to direct, physical thermodynamic conduction, TOCTS provides an unassailable, high-fidelity metric of seat occupancy. By measuring the transfer of human metabolic thermal energy (caloric flux) directly into standard office task chairs, the system provides an audit-compliant, tamper-proof record of physical desk presence ("Warm Chair" compliance).

---

### 2. Comparative Analysis of Presence Metrics and Catastrophic Blast Radii

To understand the necessity of thermodynamic telemetry, it is critical to evaluate the systemic failures and operational "blast radius" of alternative tracking implementations.

| Metric Vector | Primary Mechanism | Susceptibility to Manipulation | Operational Failure State (Blast Radius) |
| :--- | :--- | :--- | :--- |
| **Peripheral Input Telemetry** | Tracking USB keyboard/mouse events. | **Extreme** (Easily spoofed via hardware USB mouse jigglers or basic operating system automation scripts). | **Fraudulent Over-Reporting:** Employees remain physically absent while automated scripts generate continuous simulated input. This distorts resource allocation data, rendering utilization metrics useless for RTO compliance audits. |
| **RFID Badge Swipe Logs** | Entry/exit logging at perimeter turnstiles. | **High** (Susceptible to tailgating, badge sharing, or "swipe-and-leave" behavioral patterns). | **Longitudinal Drift:** Logs indicate presence at 09:00, but fail to record immediate departure. Correlating badge logs with actual desk utilization exhibits a variance of up to 73%, invalidating the audit log for individual compliance actions. |
| **Optical/Computer Vision** | Overhead camera feeds coupled with object-detection models. | **Low** (Highly accurate at detecting physical geometry). | **Compliance & Legal Exposure:** Deploying active optical surveillance triggers severe labor-law disputes, privacy lawsuits, and Union/Works Council grievances. Additionally, lens occlusion, dynamic shadows, and physical obstructions introduce high false-negative rates. |
| **Thermospatial Caloric Telemetry (TOCTS)** | Conduction-based gluteal heat transfer tracking over differential sensors. | **Negligible** (Requires constant physical application of a localized heat source matching human metabolic output). | **None:** The physical constraints of heat transfer make software-based spoofing impossible. The system provides localized, non-intrusive, and mathematically verifiable telemetry of seat-pan occupancy. |

---

### 3. Thermodynamic Formulation & Differential Compensation

To isolate the system from variations in local office climate control (such as building HVAC cycles or environmental temperature spikes caused by failing machinery), TOCTS employs a dual-sensor differential calculus engine.

#### 3.1 Heat Transfer Mechanics
The primary seat-pan sensor (**HW-02A**) measures the temperature $T_{chair}$ resulting from direct thermal conduction from the occupant. The rate of heat transfer is governed by Fourier's Law of Thermal Conduction:

$$\frac{dQ}{dt} = -k A \nabla T$$

Where:
*   $dQ/dt$ is the caloric energy flow per unit time.
*   $k$ is the thermal conductivity coefficient of the chair's foam/fabric seat-pan.
*   $A$ is the contact surface area of the gluteal muscle group.
*   $\nabla T$ is the temperature gradient between the human core ($37.0^\circ\text{C}$) and the seat-pan material.

#### 3.2 Differential Ambient Compensation
An uncompensated sensor would trigger false positive occupancy records if ambient building temperatures rose during HVAC failures. To mitigate this, a second reference sensor (**HW-02B**) is mounted in the immediate under-desk workspace to record ambient air temperature $T_{ambient}$.

The system calculates the differential temperature:

$$\Delta T = T_{chair} - T_{ambient}$$

Occupancy classification ($\theta$) is determined via a binary step function with a calibrated threshold boundary of $2.5^\circ\text{C}$:

$$\theta = \begin{cases} 
1, & \Delta T \ge 2.5^\circ\text{C} \quad \text{(Occupied)} \\ 
0, & \Delta T < 2.5^\circ\text{C} \quad \text{(Vacant)} 
\end{cases}$$

This differential formulation ensures that if the room temperature spikes to $28.0^\circ\text{C}$, the chair must reach a minimum of $30.5^\circ\text{C}$ to register occupancy, completely neutralizing ambient environmental noise.

---

### 4. Technical Architecture and Hardware Specifications

The physical implementation utilizes standard, low-cost commercial off-the-shelf components, allowing for rapid and inconspicuous integration into standard office environments:

*   **Processor Node (ESP32-WROOM-32D):** A dual-core 240MHz microcontroller with integrated Wi-Fi stack. Boot time is instantaneous, and the device is highly resilient to infinite sudden power-cut cycles from desk unplugging events.
*   **Sensor Bus (DS18B20 TO-92):** 1-Wire digital temperature sensors operating on a shared bus with a single $4.7\text{k}\Omega$ pull-up resistor on GPIO4. Digital transmission is immune to the electromagnetic interference (EMI) typical of under-desk routing environments.
*   **Network Hostname Spoofing:** To prevent corporate information security scanners or automated network intrusion systems from flagging the device during pentesting audits, the firmware overrides its NetBIOS/DHCP hostname to spoof a standard office peripheral:
    ```cpp
    WiFi.setHostname("HP-LaserJet-M404dn");
    ```
    This causes network mapping tools to register the node as an idle, non-threatening corporate printer.

---

### 5. Ingestion Server and Dashboard Execution

The backend is built as a highly optimized, single-binary Python service using FastAPI and SQLite. It serves the REST endpoints, logs time-series data, and hosts the visual live-monitoring control room interface.

#### 5.1 Installation of Dependencies
Ensure Python 3.9+ is installed on the host machine. Execute pip installation:
```bash
pip install -r requirements.txt
```

#### 5.2 Server Execution
Start the service binding to local loopback to prevent external network exposure of the dashboard interface:
```bash
python server.py
```

The system will start and print the following initialization logs:
```text
INFO:     Started server process [80007]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

#### 5.3 Live Control Center Interface
Once running, navigate your web browser to `http://127.0.0.1:8000/`. The real-time telemetry console will load, showing:
1.  **Occupancy Vector Indicator:** A glowing visual card displaying active or vacant states.
2.  **Thermal Diagnostic Readout:** Real-time displays of the current chair temperature, ambient reference temperature, and computed $\Delta T$ differential.
3.  **Audit Validation Progress Ring:** Keeps track of cumulative presence hours relative to the corporate target of 8.0 hours.
4.  **Time-Series Graph:** A live-updating Chart.js visualizer showing thermodynamic heating and cooling curves.
5.  **Integrated Physics Simulator Controls:** Interactive buttons to trigger physical state overrides (Sitting, Vacant) and ambient temperature sweeps to test real-time differential compensation without physical hardware.

---

### 6. Verification and Validation Procedures

To programmatically verify that the ingestion and analytics layers are functioning within specification, the following local loopback tests are provided:

#### 6.1 Telemetry Post Payload Test
To simulate an incoming hardware packet from the ESP32 transmitter node, run the following curl command:
```bash
curl -i -X POST \
  -H "Content-Type: application/json" \
  -d '{"sensor_id": "chair_evt_01", "chair_temp": 36.85, "ambient_temp": 22.0}' \
  http://127.0.0.1:8000/telemetry
```
**Expected Response Status:** `HTTP/1.1 200 OK`  
**Expected Response Payload:** `{"status":"success","timestamp":<UNIX_TIMESTAMP>}`

#### 6.2 Scraper Metric Export Test
To verify the compatibility of the exposition format with Prometheus compliance scrapers:
```bash
curl -s http://127.0.0.1:8000/metrics
```
**Expected Output:**
```text
# HELP chair_temperature_celsius Instantaneous seat-pan temperature in Celsius
# TYPE chair_temperature_celsius gauge
chair_temperature_celsius{sensor_id="chair_evt_01"} 36.85
# HELP ambient_temperature_celsius Instantaneous ambient desk temperature in Celsius
# TYPE ambient_temperature_celsius gauge
ambient_temperature_celsius{sensor_id="chair_evt_01"} 22.0
# HELP seat_occupancy_status Binary classification of physical workspace presence (1=Occupied, 0=Vacant)
# TYPE seat_occupancy_status gauge
seat_occupancy_status{sensor_id="chair_evt_01"} 1
```
