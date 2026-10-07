# Mathematical & Kinematic Formulation Specification

## 1. Geodesic Separation (Haversine Formula)
To determine the geographic line-of-sight distance between two moving vehicles $(V_1, V_2)$ across the Earth's spherical surface:

$$\Delta\phi = \phi_2 - \phi_1, \quad \Delta\lambda = \lambda_2 - \lambda_1$$
$$a = \sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)$$
$$c = 2 \cdot \text{atan2}\left(\sqrt{a}, \sqrt{1-a}\right), \quad d = R \cdot c$$

*Where $R = 6,371,000 \text{ m}$ (mean Earth radius), and $\phi, \lambda$ represent Latitude and Longitude in radians.*

---

## 2. Navigational Compass Kinematics & Dynamic Closing Speed ($v_{close}$)
The relative velocity vector respects the navigational compass convention ($0^\circ = \text{North}, 90^\circ = \text{East}, 180^\circ = \text{South}, 270^\circ = \text{West}$):

$$v_{1x} = s_1 \cdot \sin(\theta_1), \quad v_{1y} = s_1 \cdot \cos(\theta_1)$$
$$v_{2x} = s_2 \cdot \sin(\theta_2), \quad v_{2y} = s_2 \cdot \cos(\theta_2)$$
$$rv_x = v_{1x} - v_{2x}, \quad rv_y = v_{1y} - v_{2y}$$

Converting spherical coordinates to local flat tangent displacement:
$$dx = (\lambda_2 - \lambda_1) \cdot 111320.0 \cdot \cos\left(\frac{\phi_1 + \phi_2}{2}\right), \quad dy = (\phi_2 - \phi_1) \cdot 111320.0$$
$$\text{posMag} = \sqrt{dx^2 + dy^2}$$
$$\text{Closing Speed } v_{close} = \frac{dx \cdot rv_x + dy \cdot rv_y}{\text{posMag}}$$

*If $v_{close} \le 0$, the vehicles are diverging or maintaining constant spacing, and the collision risk is zero.*

---

## 3. Time-To-Collision (TTC) & Threat Hierarchy
Time-To-Collision calculates the time window remaining before impact occurs:

$$\text{TTC} = \frac{d}{v_{close}} \quad (\text{for } v_{close} > 0.5 \text{ m/s})$$

| Risk Level | Threat Classification | TTC Threshold | Distance | System Response |
| :---: | :--- | :---: | :---: | :--- |
| **0** | **SAFE** | $\text{TTC} > 5.0\text{ s}$ | $> 100\text{ m}$ | Normal telemetry streaming; Green indicator. |
| **1** | **ADVISORY** | $3.5\text{ s} < \text{TTC} \le 5.0\text{ s}$ | $50\text{ m} - 100\text{ m}$ | Visual caution on OLED HUD; Yellow indicator. |
| **2** | **WARNING** | $2.5\text{ s} < \text{TTC} \le 3.5\text{ s}$ | $25\text{ m} - 50\text{ m}$ | Rapid audible beeping; Red HUD hazard flash. |
| **3** | **CRITICAL IMMINENT**| $\text{TTC} \le 2.5\text{ s}$ | $< 25\text{ m}$ | Continuous buzzer alarm; **AEB Relay Triggers Braking**. |
| **4** | **EMERGENCY VEHICLE**| N/A | $< 200\text{ m}$ | High-priority ambulance alert: **"Yield Right of Way"**. |

---

## 4. Highway Geofencing (Ray-Casting Algorithm)
Tests whether vehicle coordinate $(x, y)$ falls inside a polygon with vertices $(P_1, \dots, P_n)$:

$$\text{Ray Intersect Condition: } (y_i > y) \ne (y_j > y) \land \left(x < \frac{(x_j - x_i)(y - y_i)}{y_j - y_i} + x_i\right)$$
