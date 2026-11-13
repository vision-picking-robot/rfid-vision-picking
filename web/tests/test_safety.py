"""Work-area safety webcam: warning beep -> robot hold -> "안전구역 확보" resume, only while picking."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.safety import DEFAULT_ZONES, SafetyMonitor, near


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = Clock()
        self.phase = None
        self.holds = []
        self.m = SafetyMonitor(Path(self.temp.name) / "safety.json", Settings(camera_autostart=False),
                               phase_fn=lambda: self.phase, hold_fn=lambda hold, msg: self.holds.append((hold, msg)),
                               clock=self.clock)

    def tick(self, seconds, persons=None, steps=10):
        for _ in range(steps):
            self.clock.t += seconds / steps
            self.m.step(persons)
        return self.m.state

    def kinds(self):
        return [a["kind"] for a in self.m.status()["announcements"]]

    def test_person_near_the_picked_zone_warns_then_holds_then_resumes(self):
        person_at_zone2 = [[0.6, 0.1, 0.8, 0.45, 0.9]]
        self.phase = {"active": True, "zone": 2, "product": "canned_meat"}
        self.assertEqual(self.tick(0.5, []), "clear")
        self.assertEqual(self.tick(1.0, person_at_zone2), "warning")
        self.assertEqual(self.holds, [])  # 1st stage: warning only
        self.assertEqual(self.tick(2.5, person_at_zone2), "hold")  # still there after 3 s -> stop
        self.assertEqual(self.holds[-1][0], True)
        self.assertIn("구역 2", self.holds[-1][1])
        self.assertEqual(self.tick(2.0, []), "hold")  # gone for 2 s: not yet
        self.assertEqual(self.tick(1.5, []), "clear")  # gone for 3 s -> release
        self.assertEqual(self.holds[-1], (False, "안전구역 확보. 로봇을 다시 가동합니다."))
        self.assertEqual(self.kinds(), ["warning", "hold", "resume"])

    def test_stage_changes_are_reported_for_the_phone(self):
        reported = []
        self.m.state_fn = lambda state, zone, message: reported.append((state, zone, message))
        self.phase = {"active": True, "zone": 2}
        person = [[0.6, 0.1, 0.8, 0.45, 0.9]]
        self.tick(0.5, [])
        self.tick(1.0, person)
        self.tick(2.5, person)
        self.tick(4.0, [])
        stages = [s for s, _, _ in reported]
        self.assertEqual(stages, ["clear", "warning", "hold", "clear"])  # each change once, not every step
        self.assertIn("3초", reported[1][2])
        self.assertEqual(reported[2][1], 2)
        self.assertEqual(reported[3][2], "안전구역 확보. 로봇을 다시 가동합니다.")

    def test_no_warning_while_carrying_to_the_box_or_idle(self):
        person_everywhere = [[0.0, 0.0, 1.0, 1.0, 0.9]]
        self.phase = None  # carrying to the box / idle
        self.assertEqual(self.tick(5.0, person_everywhere), "idle")
        self.assertEqual((self.holds, self.kinds()), ([], []))

    def test_person_far_from_the_zone_or_leaving_in_time_does_not_stop(self):
        self.phase = {"active": True, "zone": 1}
        far = [[0.75, 0.75, 0.95, 0.99, 0.9]]  # by zone 3, not zone 1
        self.assertEqual(self.tick(5.0, far), "clear")
        near_zone1 = [[0.1, 0.1, 0.3, 0.4, 0.9]]
        self.assertEqual(self.tick(1.5, near_zone1), "warning")
        self.assertEqual(self.tick(1.0, []), "clear")  # left within the warning
        self.assertEqual(self.holds, [])
        self.assertEqual(self.kinds(), ["warning", "warning_cleared"])

    def test_hold_outlasts_the_pick_phase_until_the_zone_is_clear(self):
        self.phase = {"active": True, "zone": 4}
        self.m.simulate(True)
        self.assertEqual(self.tick(4.0), "hold")
        self.phase = None  # robot cycle stopped reporting the phase: still held while the person stays
        self.assertEqual(self.tick(5.0), "hold")
        self.m.simulate(False)
        self.assertEqual(self.tick(3.5), "idle")
        self.assertEqual([h for h, _ in self.holds], [True, False])

    def test_zone_geometry_and_persistence(self):
        self.assertTrue(near([0.45, 0.2, 0.55, 0.3], DEFAULT_ZONES["2"]))
        self.assertFalse(near([0.0, 0.8, 0.1, 0.95], DEFAULT_ZONES["2"]))
        self.m.set_zone(3, [[0.2, 0.2], [0.4, 0.2], [0.4, 0.4], [0.2, 0.4]])
        again = SafetyMonitor(Path(self.temp.name) / "safety.json", Settings(camera_autostart=False),
                              phase_fn=lambda: None, hold_fn=lambda *a: None)
        self.assertEqual(again.zones["3"][0], [0.2, 0.2])


class ApiTests(unittest.TestCase):
    def test_endpoints_and_robot_hold_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            app = create_app(Settings(camera_autostart=False), state_root=temp)
            with TestClient(app) as c:
                monitor = app.state.safety
                monitor.warn_s = monitor.clear_s = 0.3
                self.assertEqual(c.get("/api/safety/status").json()["state"], "idle")
                self.assertEqual(c.get("/api/safety/frame.jpg").status_code, 204)  # no webcam yet
                c.get("/api/v1/mobile/status", params={"robot": "remote_rfid"})  # robot heartbeat
                c.post("/api/v1/mobile/safety-phase", json={"active": True, "zone": 1, "product": "wet_wipes"})
                c.post("/api/safety/simulate", json={"person": True})
                for _ in range(16):
                    monitor.step()
                    __import__("time").sleep(0.06)
                self.assertTrue(c.get("/api/v1/mobile/status").json()["safety_hold"])
                self.assertEqual(c.get("/api/v1/mobile/status").json()["safety_state"]["state"], "hold")
                c.post("/api/safety/simulate", json={"person": False})
                for _ in range(16):
                    monitor.step()
                    __import__("time").sleep(0.06)
                status = c.get("/api/v1/mobile/status").json()
                self.assertFalse(status["safety_hold"])
                self.assertEqual(status["safety_message"], "안전구역 확보. 로봇을 다시 가동합니다.")
                bad = c.post("/api/safety/zones", json={"zone": 2, "points": [[0, 0], [2, 0], [1, 1]]})
                self.assertEqual(bad.status_code, 422)
                ok = c.post("/api/safety/zones", json={"zone": 2, "points": [[0.5, 0.0], [0.9, 0.0], [0.9, 0.4], [0.5, 0.4]]})
                self.assertEqual(ok.json()["zones"]["2"][1], [0.9, 0.0])
                self.assertEqual(c.delete("/api/safety/zones").json()["zones"], DEFAULT_ZONES)


if __name__ == "__main__":
    unittest.main()
