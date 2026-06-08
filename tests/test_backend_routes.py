import unittest

from backend.main import app


class BackendRoutesTest(unittest.TestCase):
    def test_core_routes_remain_and_external_agent_routes_are_removed(self):
        paths = {route.path for route in app.routes}

        self.assertIn("/recommend", paths)
        self.assertIn("/chat", paths)
        self.assertIn("/user", paths)

        forbidden = {
            path
            for path in paths
            if "calendar" in path.lower()
            or "google" in path.lower()
            or "notification" in path.lower()
        }
        self.assertEqual(forbidden, set())


if __name__ == "__main__":
    unittest.main()
