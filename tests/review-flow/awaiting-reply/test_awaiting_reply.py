"""Tests for plugins/review-flow/scripts/awaiting-reply.py.

One test per row of the plan's I/O & Edge-Case Matrix.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "plugins/review-flow/scripts/awaiting-reply.py"
_spec = importlib.util.spec_from_file_location("awaiting_reply", SCRIPT)
ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ar)

T0, T1, T2 = "2026-10-01T10:00:00Z", "2026-10-02T10:00:00Z", "2026-10-03T10:00:00Z"


def user(login, bot=False):
    return {"login": login, "__typename": "Bot" if bot else "User"}


def c(author, at, body="text", db=1):
    return {"author": author, "body": body, "createdAt": at,
            "url": f"https://x/c{db}", "databaseId": db}


def thread(comments, resolved=False, outdated=False, line=5, original=5, more=False):
    return {"id": "T_1", "isResolved": resolved, "isOutdated": outdated, "path": "a.ts",
            "line": line, "originalLine": original,
            "comments": {"nodes": comments, "pageInfo": {"hasNextPage": more}}}


def review(author, at, body="please fix", state="COMMENTED", db=9):
    return {"databaseId": db, "author": author, "state": state, "body": body,
            "submittedAt": at, "url": f"https://x/r{db}"}


def page(conn, nodes):
    return {"data": {"repository": {"pullRequest": {conn: {"nodes": nodes}}}}}


class ThreadTests(unittest.TestCase):
    def test_open_thread_reviewer_last(self):
        out = ar.awaiting([thread([c(user("rev"), T1, db=7)])], [], [], "me")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "thread")
        self.assertEqual(out[0]["reply_to"], 7)
        self.assertEqual(out[0]["conversation"], [{"author": "rev", "body": "text"}])

    def test_resolved_thread_excluded(self):
        t = thread([c(user("rev"), T1)], resolved=True)
        self.assertEqual(ar.awaiting([t], [], [], "me"), [])

    def test_viewer_spoke_last(self):
        t = thread([c(user("rev"), T1), c(user("me"), T2)])
        self.assertEqual(ar.awaiting([t], [], [], "me"), [])

    def test_viewer_opened_reviewer_replied(self):
        t = thread([c(user("me"), T1, db=1), c(user("rev"), T2, db=2)])
        out = ar.awaiting([t], [], [], "me")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["author"], "me")
        self.assertEqual(out[0]["last_author"], "rev")

    def test_outdated_falls_back_to_original_line(self):
        t = thread([c(user("rev"), T1)], outdated=True, line=None, original=12)
        out = ar.awaiting([t], [], [], "me")[0]
        self.assertTrue(out["outdated"])
        self.assertEqual(out["line"], 12)

    def test_truncated_thread(self):
        out = ar.awaiting([thread([c(user("rev"), T1)], more=True)], [], [], "me")[0]
        self.assertTrue(out["truncated"])

    def test_thread_without_comments(self):
        self.assertEqual(ar.awaiting([thread([])], [], [], "me"), [])

    def test_deleted_user_is_ghost(self):
        out = ar.awaiting([thread([c(None, T1)])], [], [], "me")[0]
        self.assertEqual(out["author"], "ghost")

    def test_bot_author(self):
        out = ar.awaiting([thread([c(user("bot[bot]", bot=True), T1)])], [], [], "me")[0]
        self.assertTrue(out["bot"])

    def test_login_case_insensitive(self):
        t = thread([c(user("rev"), T1), c(user("me"), T2)])
        self.assertEqual(ar.awaiting([t], [], [], "ME"), [])


class ConversationTests(unittest.TestCase):
    def test_review_with_empty_body(self):
        self.assertEqual(ar.awaiting([], [review(user("rev"), T1, body="  ")], [], "me"), [])

    def test_review_answered_by_link(self):
        reply = c(user("me"), T2, body="See https://github.com/o/r/pull/1#pullrequestreview-9")
        self.assertEqual(ar.awaiting([], [review(user("rev"), T1)], [reply], "me"), [])

    def test_review_answered_by_quote(self):
        reply = c(user("me"), T2, body="> please fix\n\nFixed in abc123.")
        self.assertEqual(ar.awaiting([], [review(user("rev"), T1)], [reply], "me"), [])

    def test_unrelated_newer_comment_does_not_answer(self):
        out = ar.awaiting([], [review(user("rev"), T1)], [c(user("me"), T2, body="rebased")], "me")
        self.assertEqual([(i["kind"], i["state"]) for i in out], [("review", "COMMENTED")])

    def test_link_to_another_item(self):
        reply = c(user("me"), T2, body="#pullrequestreview-90")
        self.assertEqual(len(ar.awaiting([], [review(user("rev"), T1)], [reply], "me")), 1)

    def test_answer_predates_item(self):
        reply = c(user("me"), T1, body="> please fix\n\nok")
        out = ar.awaiting([], [review(user("rev"), T2)], [reply], "me")
        self.assertEqual(len(out), 1)

    def test_review_by_viewer(self):
        self.assertEqual(ar.awaiting([], [review(user("me"), T1)], [], "me"), [])

    def test_top_level_comment_answered_and_not(self):
        cs = [c(user("rev"), T0, db=3), c(user("rev"), T0, db=4),
              c(user("me"), T2, body="done, see #issuecomment-3", db=5)]
        out = ar.awaiting([], [], cs, "me")
        self.assertEqual([i["id"] for i in out], ["comment:4"])

    def test_viewer_never_commented(self):
        cs = [c(user("rev"), T1, db=3)]
        out = ar.awaiting([], [review(user("rev"), T1)], cs, "me")
        self.assertEqual(sorted(i["kind"] for i in out), ["comment", "review"])

    def test_several_pages(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.json"
            p.write_text(json.dumps([
                page("reviewThreads", [thread([c(user("rev"), T1)])]),
                page("reviewThreads", [dict(thread([c(user("rev"), T2)]), id="T_2")])]))
            nodes = ar.load(str(p), "reviewThreads")
        self.assertEqual(len(nodes), 2)
        self.assertEqual(len(ar.awaiting(nodes, [], [], "me")), 2)

    def test_output_sorted_by_at(self):
        t = thread([c(user("rev"), T2)])
        out = ar.awaiting([t], [review(user("rev"), T0)], [c(user("rev"), T1, db=3)], "me")
        self.assertEqual([i["at"] for i in out], [T0, T1, T2])


class CliTests(unittest.TestCase):
    def run_cli(self, threads, reviews, comments):
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for name, data in (("t", threads), ("r", reviews), ("c", comments)):
                p = Path(d) / f"{name}.json"
                p.write_text(json.dumps(data))
                paths.append(str(p))
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--viewer", "me", "--threads", paths[0],
                 "--reviews", paths[1], "--comments", paths[2]],
                capture_output=True, text=True)

    def test_pr_not_found(self):
        bad = [{"data": {"repository": {"pullRequest": None}}}]
        r = self.run_cli(bad, [page("reviews", [])], [page("comments", [])])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("pull request not found in", r.stderr)

    def test_not_an_array(self):
        r = self.run_cli({"data": {}}, [page("reviews", [])], [page("comments", [])])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("expected the --slurp array of pages", r.stderr)

    def test_end_to_end(self):
        r = self.run_cli([page("reviewThreads", [thread([c(user("rev"), T1)])])],
                         [page("reviews", [])], [page("comments", [])])
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(json.loads(r.stdout)), 1)


if __name__ == "__main__":
    unittest.main()
