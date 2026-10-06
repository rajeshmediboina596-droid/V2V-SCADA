import math
import time
from datetime import datetime
from backend.database import get_tollgates, log_tollgate_crossing

# State tracking per vehicle-tollgate pair
# Format: { (vid, toll_id): { "state": "APPROACHING"|"IN_ZONE"|"CROSSED", "last_dist": float, "min_dist": float, "last_event_time": float } }
toll_states = {}
CROSSING_COOLDOWN_SECONDS = 90.0

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000 # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class HighwayTollManager:
    def __init__(self):
        self._cached_tollgates = None
        self._last_cache_time = 0

    def get_all_tollgates(self):
        now = time.time()
        if not self._cached_tollgates or (now - self._last_cache_time > 30):
            try:
                self._cached_tollgates = get_tollgates()
                self._last_cache_time = now
            except Exception as e:
                print(f"[TollManager Error loading tollgates]: {e}")
                if not self._cached_tollgates:
                    self._cached_tollgates = []
        return self._cached_tollgates

    def evaluate_vehicle(self, vehicle_data):
        """
        Evaluates a vehicle against all highway tollgates.
        Returns:
            events: List of alert/notification dicts (e.g., tollgate_approach, tollgate_crossed)
            route_info: Route awareness metrics (next tollgate, distance, ETA)
        """
        vid = vehicle_data.get('vehicle_id')
        lat = vehicle_data.get('lat', 0.0)
        lon = vehicle_data.get('lon', 0.0)
        speed = vehicle_data.get('speed_kmph', 0.0)
        now = time.time()

        events = []
        nearest_tollgate = None
        nearest_dist = float('inf')
        last_crossed_toll = None

        tollgates = self.get_all_tollgates()

        for tg in tollgates:
            tg_id = tg['tollgate_id']
            tg_lat = tg['lat']
            tg_lon = tg['lon']
            radius = tg.get('detection_radius_m', 500.0)

            dist = haversine(lat, lon, tg_lat, tg_lon)

            # Track nearest tollgate for route awareness
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_tollgate = tg

            state_key = (vid, tg_id)
            state_data = toll_states.get(state_key, {
                "state": "OUTSIDE",
                "min_dist": dist,
                "last_dist": dist,
                "last_event_time": 0.0,
                "approach_notified": False
            })

            # Check cooldown
            time_since_event = now - state_data["last_event_time"]

            # State transition logic
            if dist <= radius:
                # Vehicle inside detection zone
                if state_data["state"] == "OUTSIDE" and time_since_event > CROSSING_COOLDOWN_SECONDS:
                    state_data["state"] = "IN_ZONE"
                    state_data["min_dist"] = dist
                    state_data["approach_notified"] = True

                    # Approach notification
                    events.append({
                        "type": "tollgate_approach",
                        "vehicle_id": vid,
                        "tollgate_id": tg_id,
                        "tollgate_name": tg['tollgate_name'],
                        "highway": tg['highway_name'],
                        "distance": round(dist, 1),
                        "speed_kmph": round(speed, 1),
                        "toll_phone": tg['toll_phone'],
                        "emergency_phone": tg['emergency_phone'],
                        "nearby_hospital": tg['nearby_hospital'],
                        "nearby_police": tg['nearby_police'],
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                elif state_data["state"] == "IN_ZONE":
                    # Update minimum distance to detect point of crossing
                    if dist < state_data["min_dist"]:
                        state_data["min_dist"] = dist

                    # If vehicle reached closest point (< 80m) and is now moving away (> min_dist + 20m)
                    # or is within ultra-close range (< 40m) and crossing:
                    if (state_data["min_dist"] < 80.0 and dist > state_data["min_dist"] + 25.0) or (dist < 40.0 and state_data["state"] != "CROSSED"):
                        state_data["state"] = "CROSSED"
                        state_data["last_event_time"] = now
                        last_crossed_toll = tg

                        # Record crossing to database
                        log_tollgate_crossing(vid, tg_id, round(speed, 1))

                        # Formal Tollgate Crossed Notification
                        events.append({
                            "type": "tollgate_crossed",
                            "vehicle_id": vid,
                            "tollgate_id": tg_id,
                            "tollgate_name": tg['tollgate_name'],
                            "highway": tg['highway_name'],
                            "location": f"{tg_lat:.4f}° N, {tg_lon:.4f}° E",
                            "speed_kmph": round(speed, 1),
                            "toll_phone": tg['toll_phone'],
                            "emergency_phone": tg['emergency_phone'],
                            "nearby_hospital": tg['nearby_hospital'],
                            "nearby_police": tg['nearby_police'],
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "crossing_banner": (
                                f"Tollgate Crossed\n"
                                f"Toll ID: {tg_id}\n"
                                f"Tollgate: {tg['tollgate_name']}\n"
                                f"Highway: {tg['highway_name']}\n"
                                f"Location: {tg_lat:.4f}° N, {tg_lon:.4f}° E\n"
                                f"Toll Contact: {tg['toll_phone']}\n"
                                f"Emergency Contact: {tg['emergency_phone']}\n"
                                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                        })
            else:
                # Vehicle is outside the detection radius
                if dist > radius + 100.0:
                    state_data["state"] = "OUTSIDE"
                    state_data["min_dist"] = dist
                    state_data["approach_notified"] = False

            state_data["last_dist"] = dist
            toll_states[state_key] = state_data

        # Route awareness computation
        route_info = {
            "current_highway": nearest_tollgate['highway_name'] if nearest_tollgate else "National Highway (NH-65)",
            "next_tollgate": nearest_tollgate['tollgate_name'] if nearest_tollgate else "Approaching Plaza",
            "next_tollgate_id": nearest_tollgate['tollgate_id'] if nearest_tollgate else "TG-001",
            "distance_to_next_m": round(nearest_dist, 1) if nearest_tollgate else 0.0,
            "toll_phone": nearest_tollgate['toll_phone'] if nearest_tollgate else "1033",
            "emergency_phone": nearest_tollgate['emergency_phone'] if nearest_tollgate else "112",
            "nearby_hospital": nearest_tollgate['nearby_hospital'] if nearest_tollgate else "General Hospital",
            "nearby_police": nearest_tollgate['nearby_police'] if nearest_tollgate else "Traffic Police (100)",
            "eta_seconds": round((nearest_dist / (max(speed, 20.0) / 3.6)), 0) if nearest_tollgate else 0
        }

        return events, route_info

# Global singleton
highway_toll_manager = HighwayTollManager()
