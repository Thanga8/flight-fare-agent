import unittest
from pathlib import Path


class WorkflowSafetyTests(unittest.TestCase):
    def test_monitor_workflow_is_gated_hosted_serialized_and_uses_shared_database(self):
        workflow = Path(__file__).parent / ".github" / "workflows" / "fare-monitor.yml"
        content = workflow.read_text(encoding="utf-8")
        self.assertIn("vars.FARE_MONITOR_ENABLED == 'true'", content)
        self.assertIn("runs-on: ubuntu-latest", content)
        self.assertIn("cancel-in-progress: false", content)
        self.assertIn("workflow_dispatch:", content)
        self.assertNotIn("DATABASE_URL:", content.split("jobs:", 1)[0])
        self.assertIn("timeout-minutes: 30", content)
        self.assertIn("SERPAPI_API_KEY: ${{ secrets.SERPAPI_API_KEY }}", content)
        self.assertNotIn("TELEGRAM_BOT_TOKEN:", content.split("- name: Require shared PostgreSQL configuration", 1)[0])
        self.assertNotIn("TELEGRAM_CHAT_ID:", content.split("- name: Require shared PostgreSQL configuration", 1)[0])
        self.assertIn("MAX_WEB_SERPAPI_BUDGET: \"50\"", content)
        self.assertIn("MONITOR_MAX_SERPAPI_BUDGET: \"50\"", content)
        self.assertNotIn("self-hosted", content)
        self.assertNotIn("ref: codex/", content)
        self.assertIn("flask --app webapp db-ready", content)
        self.assertIn("flask --app webapp run-due-monitors", content)


if __name__ == "__main__":
    unittest.main()
