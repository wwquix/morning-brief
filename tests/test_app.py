import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

import app
import get_chat_id

ROOT = Path(__file__).resolve().parents[1]
CAT_URL = "https://cdn2.thecatapi.com/images/test.png"
PNG = b"\x89PNG\r\n\x1a\nfixture"


class BriefTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    def write_config(self, value=None):
        path = self.base / "config.json"
        path.write_text(json.dumps(self.config if value is None else value), encoding="utf-8-sig")
        return path

    def response(self, **overrides):
        response = MagicMock(status_code=200)
        response.__enter__.return_value = response
        response.headers = {"Content-Type": "image/png"}
        response.iter_content.return_value = [PNG]
        for key, value in overrides.items():
            setattr(response, key, value)
        return response

    def summary(self):
        return app.SummaryData("2026-10-05", "", "", app.WeatherReport("", "10 °C", "ясно"),
                               app.HolidayReport("", "праздников нет"), [], [])

    def test_valid_config_with_bom(self):
        self.assertEqual(app.load_config(self.write_config()), self.config)

    def test_invalid_config_values_rejected(self):
        cases = [("latitude", 91), ("latitude", True), ("longitude", float("nan")),
                 ("cat_images_count", "bad"), ("cat_images_count", -1), ("cat_images_count", 11),
                 ("cat_images_count", True), ("timezone", "Missing/Timezone"),
                 ("output_dir", ""), ("country_code", "../"), ("send_telegram", "false")]
        for key, value in cases:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                app.load_config(self.write_config({**self.config, key: value}))

    def test_config_requires_object(self):
        with self.assertRaises(ValueError):
            app.load_config(self.write_config([]))

    def test_env_preserves_process_values_and_reads_bom_quotes(self):
        path = self.base / ".env"
        path.write_text('TOKEN=local\nexport OTHER="hello=world"\nBAD KEY=no\n', encoding="utf-8-sig")
        with patch.dict(os.environ, {"TOKEN": "process"}, clear=True):
            app.load_env_file(path)
            self.assertEqual(os.environ["TOKEN"], "process")
            self.assertEqual(os.environ["OTHER"], "hello=world")
            self.assertNotIn("BAD KEY", os.environ)

    def test_pending_tasks_bom_completed_and_empty(self):
        path = self.base / "tasks.md"
        path.write_text('- [ ] First\n* [ ] Second\n- [x] Done\n- [ ]\n', encoding="utf-8-sig")
        self.assertEqual(app.read_pending_tasks(path), ["- First", "- Second"])

    def test_missing_or_invalid_tasks_report_error_without_losing_summary(self):
        for contents in (None, b"\xff"):
            with self.subTest(contents=contents), patch.object(app, "get_json", return_value=None):
                if contents:
                    (self.base / "tasks.md").write_bytes(contents)
                summary = app.build_summary(self.base, self.base, self.config)
                self.assertEqual(summary.tasks_error, app.TASKS_ERROR)
                self.assertIn(app.TASKS_ERROR, summary.markdown)
                self.assertIn(app.TASKS_ERROR, summary.html)
                self.assertEqual(app.build_brief_data(summary, self.config)["tasksError"], app.TASKS_ERROR)

    def test_timeout_and_invalid_json_return_unavailable(self):
        for error in (requests.Timeout(), ValueError("bad JSON")):
            with self.subTest(error=error), patch.object(app.requests, "get", side_effect=error):
                self.assertIsNone(app.get_json("https://example.invalid"))

    def test_missing_api_shapes_do_not_crash(self):
        for value in (None, {}, "oops", [None]):
            with self.subTest(value=value), patch.object(app, "get_json", return_value=value):
                self.assertEqual(app.fetch_weather(self.config).temperature, app.DATA_ERROR)

    def test_cat_count_zero_performs_no_request(self):
        with patch.object(app, "get_json") as request:
            self.assertEqual(app.fetch_cat_images({"cat_images_count": 0}, self.base, "2026-10-05"), [])
            request.assert_not_called()

    def test_untrusted_cat_urls_are_rejected_before_network(self):
        urls = ["http://cdn2.thecatapi.com/x", "https://localhost/x", "https://127.0.0.1/x",
                "file:///etc/passwd", "https://cdn2.thecatapi.com.evil.test/x",
                "https://user@cdn2.thecatapi.com/x", "https://cdn2.thecatapi.com:444/x", None]
        with patch.object(app.requests, "get") as request:
            for url in urls:
                with self.subTest(url=url):
                    self.assertFalse(app.is_allowed_cat_url(url))
                    self.assertIsNone(app.download_cat_image(url, self.base, "2026-10-05", 1))
            request.assert_not_called()

    def test_download_streams_and_embeds_local_image(self):
        response = self.response()
        with patch.object(app.requests, "get", return_value=response) as request:
            cat = app.download_cat_image(CAT_URL, self.base, "2026-10-05", 1)
        self.assertEqual(cat.local_path.read_bytes(), PNG)
        self.assertTrue(request.call_args.kwargs["stream"])
        self.assertFalse(request.call_args.kwargs["allow_redirects"])
        summary = self.summary()
        summary.cats = [cat]
        self.assertTrue(app.build_brief_data(summary, self.config)["cats"][0]["src"].startswith("data:image/png;base64,"))
        self.assertIn("data:image/png;base64,", app.render_cats_html([cat]))

    def test_download_rejects_redirect_type_and_size(self):
        responses = [self.response(status_code=302), self.response(headers={"Content-Type": "image/svg+xml"}),
                     self.response(headers={"Content-Type": "image/png", "Content-Length": "99"})]
        oversized = self.response()
        oversized.iter_content.return_value = [b"1234", b"56789"]
        responses.append(oversized)
        for response in responses:
            with self.subTest(response=response), patch.object(app, "MAX_IMAGE_BYTES", 8), patch.object(app.requests, "get", return_value=response):
                self.assertIsNone(app.download_cat_image(CAT_URL, self.base, "2026-10-05", 1))
        self.assertEqual(list(self.base.iterdir()), [])

    def test_failed_image_never_leaves_external_fallback(self):
        with patch.object(app, "fetch_cat_image_urls", return_value=[CAT_URL]), patch.object(app.requests, "get", side_effect=requests.Timeout()):
            self.assertEqual(app.fetch_cat_images(self.config, self.base, "2026-10-05"), app.CATS_ERROR)
        summary = self.summary()
        summary.cats = [app.CatImage(CAT_URL, CAT_URL)]
        self.assertEqual(app.build_brief_data(summary, self.config)["cats"], [])

    def test_script_json_round_trips_hostile_text_without_html_tokens(self):
        payload = {"tasks": ["</ScRiPt><script>alert(1)</script>", "<!--<script>", "\u2028&>"]}
        encoded = app.json_for_script(payload)
        self.assertNotIn("<", encoded)
        self.assertEqual(json.loads(encoded), payload)

    def test_fallback_escapes_task_html(self):
        summary = self.summary()
        summary.pending_tasks = ['- <img src=x onerror="alert(1)">']
        output = app.render_summary_html(summary, self.config)
        self.assertNotIn('<img src=x', output)
        self.assertIn('&lt;img', output)

    def test_telegram_requires_http_and_api_success_and_does_not_log_secrets(self):
        for http_ok, payload, expected in [(True, {"ok": True}, True), (True, {"ok": False}, False),
                                            (True, [], False), (False, {"ok": True}, False),
                                            (False, {"description": "SECRET"}, False)]:
            response = self.response(ok=http_ok)
            response.json.return_value = payload
            output = io.StringIO()
            with self.subTest(payload=payload), patch.object(app.requests, "post", return_value=response), contextlib.redirect_stdout(output):
                self.assertEqual(app.telegram_api_post("SECRET", "sendDocument", {}), expected)
            self.assertNotIn("SECRET", output.getvalue())

    def test_telegram_timeout_and_non_json_response(self):
        response = self.response(ok=True)
        response.json.side_effect = ValueError("SECRET")
        with patch.object(app.requests, "post", return_value=response):
            self.assertFalse(app.telegram_api_post("SECRET", "sendDocument", {}))
        with patch.object(app.requests, "post", side_effect=requests.Timeout("SECRET")):
            self.assertFalse(app.telegram_api_post("SECRET", "sendDocument", {}))

    def test_local_only_generates_files_without_notifications(self):
        self.write_config()
        (self.base / "tasks.md").write_text("- [ ] Test", encoding="utf-8")
        with patch.object(app, "get_json", return_value=None), patch.object(app, "send_telegram_summary") as telegram, patch.object(app, "send_clickable_notification") as toast:
            app.run_summary(self.base, local_only=True)
        telegram.assert_not_called()
        toast.assert_not_called()
        self.assertEqual(len(list((self.base / "output").glob("*.html"))), 1)
        self.assertEqual(len(list((self.base / "output").glob("*.md"))), 1)

    def test_cli_reports_failure_without_traceback_or_secrets(self):
        stderr = io.StringIO()
        with patch.object(app, "run_summary", side_effect=ValueError("SECRET")), contextlib.redirect_stderr(stderr):
            self.assertEqual(app.main(["--local-only"]), 1)
        self.assertNotIn("SECRET", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_chat_id_helper_loads_dotenv(self):
        with patch.object(get_chat_id, "load_env_file") as loader, patch.dict(os.environ, {}, clear=True), patch.object(get_chat_id.requests, "get") as request:
            get_chat_id.main()
        loader.assert_called_once()
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
