"""Exercise status, pull and push against local Git repositories; no GitHub access.

Each checkout keeps a real github.com origin URL, and `url.<local>.insteadOf` makes
Git talk to a bare repository in a temporary folder instead.
"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import tempfile
import unittest

import repos


class WorkspaceTestCase(unittest.TestCase):
    def git(self, directory, *args):
        return subprocess.run(
            ["git", "-C", str(directory), *args],
            check=True, text=True, capture_output=True,
        ).stdout.strip()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sank-repos-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.remotes = {}

    def configure(self, directory):
        for key, value in (
            ("user.name", "Repos test"), ("user.email", "test@example.invalid"),
            ("commit.gpgsign", "false"), ("core.hooksPath", "/dev/null"),
        ):
            self.git(directory, "config", key, value)

    def remote(self, name):
        """Create a bare 'GitHub' repo with one commit on main and a writer clone."""
        bare = self.root / "github" / f"{name}.git"
        writer = self.root / "writers" / name
        bare.mkdir(parents=True)
        writer.mkdir(parents=True)
        self.git(bare, "init", "--bare", "--initial-branch=main")
        self.git(writer, "init", "--initial-branch=main")
        self.configure(writer)
        self.git(writer, "remote", "add", "origin", str(bare))
        self.remotes[name] = (bare, writer)
        self.publish(name, "first")
        return bare

    def publish(self, name, content, filename="changes.txt", branch="main"):
        writer = self.remotes[name][1]
        if self.git(writer, "branch", "--show-current") != branch:
            self.git(writer, "fetch", "origin")
            self.git(writer, "checkout", "-B", branch, f"origin/{branch}")
        (writer / filename).write_text(content)
        self.git(writer, "add", filename)
        self.git(writer, "commit", "-m", content)
        self.git(writer, "push", "origin", branch)

    def checkout(self, name="catalog-service"):
        bare = self.remotes.get(name, (None,))[0] or self.remote(name)
        destination = self.workspace / name
        self.git(self.workspace, "clone", "--quiet", str(bare), str(destination))
        self.configure(destination)
        url = f"https://github.com/{repos.ORG}/{name}.git"
        self.git(destination, "remote", "set-url", "origin", url)
        self.git(destination, "config", f"url.{bare}.insteadOf", url)
        return destination

    def commit(self, checkout, filename, content):
        (checkout / filename).write_text(content)
        self.git(checkout, "add", filename)
        self.git(checkout, "commit", "-m", content)

    def head(self, directory, ref="HEAD"):
        return self.git(directory, "rev-parse", ref)

    def call(self, command, names, **options):
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            attention = command([{"name": name} for name in names], self.workspace, **options)
        return attention, output.getvalue()


class PullTests(WorkspaceTestCase):
    def test_clean_main_gets_latest_commit_and_can_run_twice(self):
        checkout = self.checkout()
        self.publish("catalog-service", "second")
        attention, output = self.call(repos.pull, ["catalog-service"])
        self.assertFalse(attention)
        self.assertIn("pulled 1 commit", output)
        attention, output = self.call(repos.pull, ["catalog-service"])
        self.assertIn("up to date", output)
        self.assertEqual((checkout / "changes.txt").read_text(), "second")

    def test_output_has_no_colour_codes_when_not_a_terminal(self):
        self.checkout()
        self.assertNotIn("\033[", self.call(repos.pull, ["catalog-service"])[1])

    def test_unrelated_local_changes_are_kept_while_pulling(self):
        checkout = self.checkout()
        (checkout / "notes.txt").write_text("untracked work")
        self.publish("catalog-service", "second")
        attention, output = self.call(repos.pull, ["catalog-service"])
        self.assertFalse(attention)
        self.assertIn("kept your uncommitted changes", output)
        self.assertEqual((checkout / "changes.txt").read_text(), "second")
        self.assertEqual((checkout / "notes.txt").read_text(), "untracked work")

    def test_conflicting_local_changes_are_left_untouched(self):
        checkout = self.checkout()
        before = self.head(checkout)
        (checkout / "changes.txt").write_text("my unfinished changes")
        self.publish("catalog-service", "second")
        attention, output = self.call(repos.pull, ["catalog-service"])
        self.assertTrue(attention)
        self.assertIn("touch files you changed locally", output)
        self.assertEqual(self.head(checkout), before)
        self.assertEqual((checkout / "changes.txt").read_text(), "my unfinished changes")

    def test_feature_branch_is_pulled_and_local_main_kept_current(self):
        checkout = self.checkout()
        self.git(checkout, "switch", "-c", "feature/recipes")
        self.commit(checkout, "recipe.txt", "recipe")
        self.git(checkout, "push", "--quiet", "-u", "origin", "feature/recipes")
        self.publish("catalog-service", "teammate on feature", "recipe.txt", "feature/recipes")
        self.publish("catalog-service", "teammate on main", branch="main")
        attention, output = self.call(repos.pull, ["catalog-service"])
        self.assertFalse(attention)
        self.assertEqual(self.git(checkout, "branch", "--show-current"), "feature/recipes")
        self.assertEqual((checkout / "recipe.txt").read_text(), "teammate on feature")
        self.assertEqual(self.head(checkout, "main"), self.head(checkout, "origin/main"))
        self.assertIn("main +1", output)

    def test_detached_head_and_unpublished_branch_are_reported(self):
        checkout = self.checkout()
        self.git(checkout, "checkout", "--quiet", "--detach")
        self.assertIn("detached HEAD", self.call(repos.pull, ["catalog-service"])[1])
        self.git(checkout, "switch", "-c", "feature/new")
        self.assertIn("not on GitHub yet", self.call(repos.pull, ["catalog-service"])[1])

    def test_diverged_repo_is_left_alone_and_other_repos_still_update(self):
        catalog = self.checkout()
        sales = self.checkout("sales-service")
        self.commit(catalog, "local.txt", "local commit")
        before = self.head(catalog)
        self.publish("catalog-service", "second")
        self.publish("sales-service", "second")
        attention, output = self.call(repos.pull, ["catalog-service", "sales-service"])
        self.assertTrue(attention)
        self.assertIn("diverged", output)
        self.assertEqual(self.head(catalog), before)
        self.assertEqual(self.git(catalog, "status", "--porcelain"), "")
        self.assertEqual(self.head(sales), self.head(self.remotes["sales-service"][1]))

    def test_wrong_remote_is_rejected_before_fetch(self):
        checkout = self.checkout()
        self.git(checkout, "remote", "set-url", "origin", "https://github.com/other/repo.git")
        self.publish("catalog-service", "second")
        attention, output = self.call(repos.pull, ["catalog-service"])
        self.assertTrue(attention)
        self.assertIn("expected github.com", output)
        self.assertNotEqual(self.head(checkout, "origin/main"),
                            self.head(self.remotes["catalog-service"][1]))

    def test_missing_checkout_is_reported(self):
        attention, output = self.call(repos.pull, ["catalog-service"])
        self.assertTrue(attention)
        self.assertIn("missing locally", output)

    def test_platform_is_pulled_last(self):
        self.checkout("platform")
        self.checkout("sales-service")
        output = self.call(repos.pull, ["platform", "sales-service"])[1]
        self.assertLess(output.index("sales-service"), output.index("platform"))


class PushTests(WorkspaceTestCase):
    def remote_head(self, name, branch):
        return self.git(self.remotes[name][0], "rev-parse", branch)

    def test_new_feature_branch_is_published_with_upstream(self):
        checkout = self.checkout()
        self.git(checkout, "switch", "-c", "feature/menu")
        self.commit(checkout, "menu.txt", "menu")
        (checkout / "draft.txt").write_text("not committed")
        attention, output = self.call(repos.push, ["catalog-service"], assume_yes=True)
        self.assertFalse(attention)
        self.assertIn("uncommitted changes stay local", output)
        self.assertIn("pull/new/feature/menu", output)
        self.assertEqual(self.remote_head("catalog-service", "feature/menu"), self.head(checkout))
        self.assertEqual(self.git(checkout, "rev-parse", "--abbrev-ref", "@{u}"),
                         "origin/feature/menu")

    def test_commits_on_main_need_the_main_flag(self):
        checkout = self.checkout()
        before = self.remote_head("catalog-service", "main")
        self.commit(checkout, "hotfix.txt", "hotfix")
        attention, output = self.call(repos.push, ["catalog-service"], assume_yes=True)
        self.assertTrue(attention)
        self.assertIn("--main", output)
        self.assertEqual(self.remote_head("catalog-service", "main"), before)
        attention, _ = self.call(repos.push, ["catalog-service"], assume_yes=True,
                                 allow_main=True)
        self.assertFalse(attention)
        self.assertEqual(self.remote_head("catalog-service", "main"), self.head(checkout))

    def test_branch_behind_github_is_not_pushed(self):
        checkout = self.checkout()
        self.commit(checkout, "local.txt", "local")
        self.publish("catalog-service", "teammate")
        before = self.remote_head("catalog-service", "main")
        attention, output = self.call(repos.push, ["catalog-service"], assume_yes=True,
                                      allow_main=True)
        self.assertTrue(attention)
        self.assertIn("diverged", output)
        self.assertEqual(self.remote_head("catalog-service", "main"), before)

    def test_nothing_to_push(self):
        self.checkout()
        attention, output = self.call(repos.push, ["catalog-service"], assume_yes=True)
        self.assertFalse(attention)
        self.assertIn("Nothing to push", output)


class StatusTests(WorkspaceTestCase):
    def test_reports_ahead_behind_and_local_changes(self):
        checkout = self.checkout()
        self.commit(checkout, "local.txt", "local")
        self.publish("catalog-service", "teammate")
        (checkout / "draft.txt").write_text("draft")
        attention, output = self.call(repos.status, ["catalog-service"])
        self.assertTrue(attention)
        for text in ("↑1 to push", "↓1 to pull", "uncommitted changes"):
            self.assertIn(text, output)


if __name__ == "__main__":
    unittest.main()
