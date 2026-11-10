"""Offline tests for panel.py. No judge CLI is called: where a judge would run, a stand-in function
returns a canned reply. Run with:  python3 -m unittest discover -s tests -v"""
import http.server
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import panel  # noqa: E402

GREEN = {"verdict": "green", "summary": "fine", "issues": [], "responses": []}


def issue(sev="major"):
    return {"title": "t", "severity": sev, "location": "§1", "quote": "q", "problem": "p", "fix": "f", "needs": "edit"}


class Replies(unittest.TestCase):
    def test_a_complete_reply_is_valid(self):
        self.assertIsNone(panel.valid(GREEN))
        self.assertIsNone(panel.valid({**GREEN, "verdict": "red", "issues": [issue()]}))

    def test_a_reply_missing_a_key_or_with_a_bad_stance_is_rejected(self):
        self.assertIn("missing", panel.valid({"verdict": "green"}))
        self.assertIn("verdict", panel.valid({**GREEN, "verdict": "amber"}))
        bad = {**GREEN, "responses": [{"id": "I1", "stance": "maybe", "reason": "r"}]}
        self.assertIn("stance", panel.valid(bad))

    def test_json_is_found_inside_surrounding_prose(self):
        self.assertEqual(panel.extract_json('Here you go:\n{"verdict": "green"}\nThanks'), {"verdict": "green"})
        self.assertIsNone(panel.extract_json("no json here"))


class Diagnosis(unittest.TestCase):
    def diagnose(self, text, cmd="codex"):
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d) / "x.raw.txt"
            raw.write_text(text)
            return panel.diagnose("gpt", raw, {"cmd": cmd, "model": "some-model"})

    def test_usage_limits_are_recognised_in_each_vendors_words(self):
        self.assertIn("usage limit", self.diagnose("ERROR: You've hit your usage limit. Try again later."))
        self.assertIn("usage limit", self.diagnose("RESOURCE_EXHAUSTED (code 429): Individual quota reached", "agy"))

    def test_a_rejected_model_name_is_not_called_a_login_problem(self):
        self.assertIn("was not accepted", self.diagnose("model some-model is not recognized as a known model", "agy"))

    def test_a_field_named_credential_does_not_mean_signed_out(self):
        text = '{"result": "boom", "credential_expires_at": "2030-01-01"}\n--- stderr\nsomething odd'
        self.assertIn("unrecognised", self.diagnose(text, "claude"))

    def test_the_hosted_providers_bad_key_replies_are_recognised(self):
        # The replies DeepSeek, Kimi, Qwen and OpenRouter gave to a request with no key, 10 Nov 2026.
        for reply in ("HTTP 403: Authentication Fails (governor)",
                      'HTTP 403: {"error":{"message":"Incorrect API key provided"}}',
                      "HTTP 403: You didn't provide an API key.",
                      "HTTP 403: No cookie auth credentials found"):
            with tempfile.TemporaryDirectory() as d:
                raw = Path(d) / "x.raw.txt"
                raw.write_text("--- stderr\n" + reply)
                why = panel.diagnose("deepseek", raw, {"cmd": "api", "model": "m", "key_env": "MY_KEY"})
            self.assertIn("MY_KEY", why, reply)

    def test_a_real_sign_in_error_says_how_to_sign_in(self):
        self.assertIn("codex login", self.diagnose("Error: not logged in. Please log in."))


class Panel(unittest.TestCase):
    """A panel folder built by hand, as three finished rounds would leave it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.paper = base / "paper"
        self.paper.mkdir()
        (self.paper / "main.tex").write_text("\\documentclass{article}\\begin{document}Hello.\\end{document}\n")
        self.root = base / "paper.silence"
        with redirect_stdout(io.StringIO()):
            panel.cmd_init(type("A", (), {"paper": str(self.paper), "out": str(self.root), "venue": "",
                                          "pdf": None, "kind": "paper", "focus": None, "judges": None})())
        self.conf = panel.cfg(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def write_round(self, n, replies):
        rdir = self.root / f"round-{n}"
        rdir.mkdir()
        for judge, reply in replies.items():
            (rdir / f"{judge}.json").write_text(json.dumps(reply))
        (rdir / "meta.json").write_text(json.dumps({"paper_hash": panel.paper_hash(self.conf), "judges": {}}))

    def verdict(self):
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                panel.cmd_verdict(type("A", (), {"dir": str(self.root)})())
                code = 0
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()

    def test_three_greens_in_round_three_on_unchanged_text_is_silence(self):
        self.write_round(3, {j: GREEN for j in panel.names(self.root)})
        code, out = self.verdict()
        self.assertEqual(code, 0, out)
        self.assertIn("SILENCE", out)

    def test_greens_before_round_three_are_not_enough(self):
        self.write_round(2, {j: GREEN for j in panel.names(self.root)})
        code, out = self.verdict()
        self.assertEqual(code, 1)
        self.assertIn("three are required", out)

    def test_one_red_judge_breaks_the_silence(self):
        self.write_round(3, {"claude": GREEN, "gpt": {**GREEN, "verdict": "red"}, "gemini": GREEN})
        code, out = self.verdict()
        self.assertEqual(code, 1)
        self.assertIn("gpt: RED", out)

    def test_a_green_judge_with_an_open_item_or_a_new_major_issue_does_not_count(self):
        open_item = {**GREEN, "responses": [{"id": "I1", "stance": "still_open", "reason": "r"}]}
        self.write_round(3, {"claude": open_item, "gpt": {**GREEN, "issues": [issue("major")]}, "gemini": GREEN})
        code, out = self.verdict()
        self.assertEqual(code, 1)
        self.assertIn("still open ['I1']", out)
        self.assertIn("new blocker/major", out)

    def test_editing_the_paper_after_the_round_voids_the_greens(self):
        self.write_round(3, {j: GREEN for j in panel.names(self.root)})
        (self.paper / "main.tex").write_text("changed\n")
        code, out = self.verdict()
        self.assertEqual(code, 1)
        self.assertIn("the paper changed", out)

    def test_every_ledger_item_needs_an_answer_from_every_judge(self):
        ledger = [{"id": "I1", "title": "t", "severity": "major", "location": "§1", "problem": "p",
                   "raised_by": ["gpt"], "status": "fixed", "resolution": "done", "positions": {}}]
        (self.root / "issues.json").write_text(json.dumps(ledger))
        answered = {**GREEN, "responses": [{"id": "I1", "stance": "resolved", "reason": "r"}]}
        self.write_round(3, {"claude": answered, "gpt": answered, "gemini": GREEN})
        code, out = self.verdict()
        self.assertEqual(code, 1)
        self.assertIn("gemini: gave no response on ['I1']", out)

    def test_the_ledger_hides_which_model_raised_what(self):
        ledger = [{"id": "I1", "title": "t", "severity": "major", "location": "§1", "problem": "p",
                   "raised_by": ["gpt", "claude"], "status": "disputed", "resolution": "",
                   "positions": {"gemini": "it is fine"}}]
        (self.root / "issues.json").write_text(json.dumps(ledger))
        text = panel.ledger_text(self.root, "gpt")
        self.assertIn("raised by: you, judge A", text)
        self.assertIn("position of judge B: it is fine", text)
        for name in ("claude", "gemini", "gpt"):
            self.assertNotIn(name, text.replace("raised by", ""))

    def test_round_one_and_later_rounds_get_different_briefs(self):
        (self.root / "issues.json").write_text("[]")
        first = panel.build_prompt(self.root, self.conf, 1, "claude", ["main.tex"])
        later = panel.build_prompt(self.root, self.conf, 3, "claude", ["main.tex"])
        self.assertIn("independent review", first)
        self.assertNotIn("LEDGER", first)
        self.assertIn("final sign-off", later)
        self.assertIn("LEDGER", later)


class StandIns(unittest.TestCase):
    def setUp(self):
        panel._RESERVED.clear()
        self._which = panel.shutil.which
        panel.shutil.which = lambda cmd: "/usr/bin/" + cmd       # pretend every CLI is installed
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        panel.shutil.which = self._which
        self.tmp.cleanup()

    def test_the_same_vendors_other_model_is_tried_before_another_vendor(self):
        first = panel.take_fallback(self.root, "gemini", set())
        self.assertTrue(first["name"].startswith("model:"))
        self.assertEqual(first["cmd"], "agy")
        second = panel.take_fallback(self.root, "gemini", {first["name"]})
        self.assertEqual(second["name"], "vibe")

    def test_two_seats_never_get_the_same_stand_in(self):
        gpt_alts = {"model:" + a["model"] for a in panel.judges_file()["by"]["gpt"]["alternates"]}
        gem_alts = {"model:" + a["model"] for a in panel.judges_file()["by"]["gemini"]["alternates"]}
        a = panel.take_fallback(self.root, "gpt", gpt_alts)
        b = panel.take_fallback(self.root, "gemini", gem_alts)
        self.assertEqual({a["name"], b["name"]}, {"vibe", "muse"})

    def test_a_judge_marked_fallback_false_has_no_stand_in(self):
        self.assertIsNone(panel.take_fallback(self.root, "claude", set()))

    def test_a_seated_stand_in_keeps_the_seat_and_says_whom_it_replaces(self):
        fb = panel.take_fallback(self.root, "gemini", set())
        panel.seat_given(self.root, "gemini", fb)
        conf = panel.judges_conf(self.root)
        self.assertEqual(conf["gemini"]["model"], fb["model"])
        self.assertEqual(conf["gemini"]["stands_in_for"], panel.judges_file()["by"]["gemini"]["label"])
        self.assertNotIn("stands_in_for", conf["claude"])


FIVE = {"judges": [
    {"name": "claude", "type": "claude", "model": "m1", "fallback": False},
    {"name": "gpt", "type": "codex", "model": "m2"},
    {"name": "gemini", "type": "agy", "model": "m3"},
    {"name": "deepseek", "type": "api", "base_url": "http://127.0.0.1:1/v1", "model": "m4", "key_env": "TEST_PANEL_KEY"},
    {"name": "geese", "type": "command", "run": ["true"], "model": "m5"},
], "fallbacks": []}


class AnyNumberOfJudges(unittest.TestCase):
    """The panel is whatever judges.json lists, and a run may pick a subset."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "judges.json").write_text(json.dumps(FIVE))
        os.environ["INEEDSILENCE_JUDGES"] = str(base / "judges.json")
        self.paper = base / "doc"
        self.paper.mkdir()
        (self.paper / "note.md").write_text("A note.\n")
        self.root = base / "doc.silence"

    def tearDown(self):
        os.environ.pop("INEEDSILENCE_JUDGES", None)
        self.tmp.cleanup()

    def init(self, judges=None):
        out = io.StringIO()
        with redirect_stdout(out):
            panel.cmd_init(type("A", (), {"paper": str(self.paper), "out": str(self.root), "venue": "",
                                          "pdf": None, "kind": "document", "focus": None, "judges": judges})())
        return out.getvalue()

    def finish_round(self, n, replies):
        rdir = self.root / f"round-{n}"
        rdir.mkdir()
        for judge, reply in replies.items():
            (rdir / f"{judge}.json").write_text(json.dumps(reply))
        (rdir / "meta.json").write_text(json.dumps({"paper_hash": panel.paper_hash(panel.cfg(self.root)), "judges": {}}))

    def verdict(self):
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                panel.cmd_verdict(type("A", (), {"dir": str(self.root)})())
                return 0, out.getvalue()
            except SystemExit as e:
                return e.code, out.getvalue()

    def test_by_default_every_listed_judge_sits(self):
        self.init()
        self.assertEqual(panel.names(self.root), ["claude", "gpt", "gemini", "deepseek", "geese"])

    def test_five_judges_all_have_to_be_green(self):
        self.init()
        five = panel.names(self.root)
        self.finish_round(3, {j: GREEN for j in five[:4]})
        code, out = self.verdict()
        self.assertEqual(code, 1)
        self.assertIn("geese: no report", out)
        (self.root / "round-3" / "geese.json").write_text(json.dumps(GREEN))
        code, out = self.verdict()
        self.assertEqual(code, 0, out)
        self.assertIn("all 5 judges are green", out)

    def test_a_run_can_pick_its_own_judges(self):
        self.init("gpt,deepseek")
        self.assertEqual(panel.names(self.root), ["gpt", "deepseek"])
        self.finish_round(3, {"gpt": GREEN, "deepseek": GREEN})
        self.assertEqual(self.verdict()[0], 0)

    def test_two_judges_are_allowed_with_a_warning_and_one_is_not(self):
        self.assertIn("only two judges", self.init("gpt,claude"))
        with self.assertRaises(SystemExit):
            self.init("gpt")
        with self.assertRaises(SystemExit):
            self.init("gpt,nobody")

    def test_issue_tags_stay_unique_when_names_share_letters(self):
        tag = panel.tags(["claude", "gpt", "gemini", "geese", "deepseek"])
        self.assertEqual(len(set(tag.values())), 5)
        self.assertEqual(tag["claude"], "c")
        self.assertEqual((tag["gemini"], tag["geese"]), ("gem", "gee"))

    def test_with_five_judges_the_ledger_uses_four_letters(self):
        self.init()
        ledger = [{"id": "I1", "title": "t", "severity": "minor", "location": "x", "problem": "p",
                   "raised_by": ["claude", "gpt", "gemini", "deepseek", "geese"], "status": "open",
                   "resolution": "", "positions": {}}]
        (self.root / "issues.json").write_text(json.dumps(ledger))
        self.assertIn("raised by: judge A, you, judge B, judge C, judge D", panel.ledger_text(self.root, "gpt"))
        self.assertIn("one of 5 independent judges",
                      panel.build_prompt(self.root, panel.cfg(self.root), 1, "gpt", ["note.md"]))


class OtherKindsOfJudge(unittest.TestCase):
    """An API judge against a local stand-in server, and a command judge that is a tiny script."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "schema.json").write_text(json.dumps(panel.SCHEMA))
        self.rdir = base / "round-1"
        self.stage = self.rdir / "paper"
        self.stage.mkdir(parents=True)
        (self.stage / "note.md").write_text("The sky is green.\n")
        (self.stage / "figure.png").write_bytes(b"\x89PNG\x00\x00")
        self.seen = {}
        test = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                test.seen.update(path=self.path, auth=self.headers.get("Authorization"), body=body)
                if body["model"] == "broke":
                    self.send_response(429)
                    self.end_headers()
                    self.wfile.write(b'{"error": {"message": "Rate limit exceeded"}}')
                    return
                reply = {"choices": [{"message": {"content": "Sure.\n" + json.dumps(GREEN)}}]}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(reply).encode())

            def log_message(self, *args):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        os.environ["TEST_PANEL_KEY"] = "sk-test"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        os.environ.pop("TEST_PANEL_KEY", None)
        self.tmp.cleanup()

    def api(self, **over):
        conf = {"name": "deepseek", "cmd": "api", "base_url": self.url, "model": "good",
                "key_env": "TEST_PANEL_KEY", "label": "DeepSeek", **over}
        return conf, panel.run_judge("deepseek", conf, "Judge this.", self.stage, self.rdir, 20)

    def test_an_api_judge_gets_the_files_in_the_prompt_and_the_key_from_the_environment(self):
        _, status = self.api()
        self.assertTrue(status["ok"], status)
        self.assertEqual(self.seen["path"], "/v1/chat/completions")
        self.assertEqual(self.seen["auth"], "Bearer sk-test")
        sent = self.seen["body"]["messages"][0]["content"]
        self.assertIn("===== FILE: note.md =====", sent)
        self.assertIn("The sky is green.", sent)
        self.assertNotIn("figure.png", sent)
        self.assertEqual(json.loads((self.rdir / "deepseek.json").read_text())["verdict"], "green")

    def test_an_api_judge_out_of_quota_is_diagnosed_as_a_usage_limit(self):
        conf, status = self.api(model="broke")
        self.assertFalse(status["ok"])
        self.assertIn("usage limit", panel.diagnose("deepseek", self.rdir / "deepseek.raw.txt", conf))

    def test_a_missing_key_is_reported_with_the_variable_to_set(self):
        os.environ.pop("TEST_PANEL_KEY")
        conf, status = self.api()
        self.assertFalse(status["ok"])
        why = panel.diagnose("deepseek", self.rdir / "deepseek.raw.txt", conf)
        self.assertIn("TEST_PANEL_KEY", why)
        self.assertIsNone(self.seen.get("path"), "nothing may be sent without a key")

    def test_material_too_large_for_an_api_judge_is_refused_not_truncated(self):
        conf, status = self.api(max_chars=5)
        self.assertFalse(status["ok"])
        self.assertIn("max_chars", panel.diagnose("deepseek", self.rdir / "deepseek.raw.txt", conf))

    def test_a_command_judge_is_any_program_that_prints_the_json(self):
        script = Path(self.tmp.name) / "judge.py"
        script.write_text("import sys, json, pathlib\n"
                          "prompt = pathlib.Path(sys.argv[1]).read_text()\n"
                          "assert 'matching this JSON Schema' in prompt and sys.argv[2] == 'mymodel'\n"
                          "print(json.dumps({'verdict': 'red', 'summary': pathlib.Path('note.md').read_text().strip(),"
                          " 'issues': [], 'responses': []}))\n")
        conf = {"name": "local", "cmd": "command", "model": "mymodel", "label": "Local",
                "run": [sys.executable, str(script), "{prompt_file}", "{model}"]}
        status = panel.run_judge("local", conf, "Judge this.", self.stage, self.rdir, 20)
        self.assertTrue(status["ok"], (self.rdir / "local.raw.txt").read_text())
        reply = json.loads((self.rdir / "local.json").read_text())
        self.assertEqual((reply["verdict"], reply["summary"]), ("red", "The sky is green."))


if __name__ == "__main__":
    unittest.main()
