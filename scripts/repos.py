#!/usr/bin/env python3
"""Manage the Šank repositories: create, clone, status, pull and push. Standard library only."""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
ORG = "Sanki-funky"
MAIN = "main"


# Output ---------------------------------------------------------------------

STYLES = {
    "bold": "1", "dim": "2", "red": "31", "green": "32",
    "yellow": "33", "blue": "34", "cyan": "36",
}
# kind: (symbol, colour, summary label or None when the kind isn't counted)
KINDS = {
    "updated": ("✔", "green", "updated"),
    "pushed": ("↑", "green", "pushed"),
    "cloned": ("✔", "green", "cloned"),
    "ready": ("↑", "cyan", None),
    "same": ("·", "dim", "unchanged"),
    "info": ("○", "blue", "info"),
    "warn": ("!", "yellow", "need attention"),
    "fail": ("✖", "red", "failed"),
}


def use_color(stream):
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return stream.isatty() and os.environ.get("TERM") != "dumb"


def paint(text, *styles):
    styles = [style for style in styles if style]
    if not styles or not use_color(sys.stdout):
        return text
    return f"\033[{';'.join(STYLES[style] for style in styles)}m{text}\033[0m"


def plural(number, word):
    return f"{number} {word}{'' if number == 1 else 's'}"


class Report:
    """Prints one aligned, coloured line per repository and a summary at the end."""

    def __init__(self, names):
        self.width = max((len(name) for name in names), default=0)
        self.counts = {}

    def line(self, kind, name, branch, message, hint=None):
        symbol, colour, label = KINDS[kind]
        if label:
            self.counts[kind] = self.counts.get(kind, 0) + 1
        loud = colour if kind in ("warn", "fail") else None
        print(
            f"  {paint(symbol, colour, 'bold')} {paint(name.ljust(self.width), 'bold')}"
            f"  {paint((branch or '').ljust(16), 'dim')} {paint(message, loud)}",
            flush=True,
        )
        if hint:
            print(f"    {' ' * self.width}{paint('→ ' + hint, 'dim')}", flush=True)

    def summary(self):
        parts = [
            paint(f"{count} {KINDS[kind][2]}", KINDS[kind][1], "bold")
            for kind, count in self.counts.items()
        ]
        if parts:
            print("\n" + ", ".join(parts), flush=True)
        return any(kind in ("warn", "fail") for kind in self.counts)


def heading(text):
    print(paint(text, "bold"), flush=True)


# Git helpers ----------------------------------------------------------------

def run(args, *, capture=False):
    return subprocess.run(args, check=True, text=True, capture_output=capture)


def git(path, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(path), *args], check=check, text=True, capture_output=True
    )


def git_out(path, *args):
    return git(path, *args).stdout.strip()


def error_text(error):
    if isinstance(error, subprocess.CalledProcessError):
        lines = [line.strip() for line in (error.stderr or "").splitlines() if line.strip()]
        for line in lines:
            if line.startswith(("fatal:", "error:", "!")):
                return line
        return lines[-1] if lines else f"{shlex.join(error.cmd)} failed"
    return str(error)


def expected_origins(name):
    return (
        f"git@github.com:{ORG}/{name}.git",
        f"https://github.com/{ORG}/{name}.git",
        f"https://github.com/{ORG}/{name}",
        f"ssh://git@github.com/{ORG}/{name}.git",
    )


def check_checkout(path, name):
    if not (path / ".git").exists():
        raise ValueError(f"{path} exists but is not a Git checkout")
    # Read the configured URL, not the rewritten one, so url.*.insteadOf still works.
    origin = git(path, "config", "--get", "remote.origin.url", check=False).stdout.strip()
    if origin not in expected_origins(name):
        raise ValueError(f"origin is {origin or 'not set'}, expected github.com/{ORG}/{name}")


def ref_exists(path, ref):
    return git(path, "rev-parse", "--verify", "--quiet", ref, check=False).returncode == 0


def count(path, revisions):
    return int(git_out(path, "rev-list", "--count", revisions))


@dataclass
class State:
    branch: str  # empty when HEAD is detached
    upstream: str  # empty when the branch has never been pushed
    gone: bool  # the upstream branch was deleted on GitHub
    ahead: int
    behind: int
    dirty: bool


def read_state(path):
    branch = git_out(path, "branch", "--show-current")
    upstream = gone = ""
    if branch:
        upstream, track = git_out(
            path, "for-each-ref", "--format=%(upstream:short)|%(upstream:track)",
            f"refs/heads/{branch}",
        ).partition("|")[::2]
        gone = track == "[gone]"
    ahead = behind = 0
    if upstream and not gone:
        ahead, behind = map(
            int, git_out(path, "rev-list", "--left-right", "--count", f"HEAD...{upstream}").split()
        )
    dirty = bool(git_out(path, "status", "--porcelain"))
    return State(branch, upstream, bool(gone), ahead, behind, dirty)


def fetch(path):
    git(path, "fetch", "--prune", "--quiet", "origin")


def checkouts(repositories, workspace):
    """Yield (name, path) for each repository, platform last.

    Pulling platform last is safe: this script and repositories.json are already loaded.
    """
    for repository in sorted(repositories, key=lambda item: item["name"] == "platform"):
        yield repository["name"], workspace / repository["name"]


# Commands -------------------------------------------------------------------

def creation_command(repository, visibility):
    command = [
        "gh", "repo", "create", f"{ORG}/{repository['name']}",
        f"--{visibility}", "--description", repository["description"],
    ]
    # This local directory supplies platform's first commit. Avoid unrelated histories.
    if repository["name"] != "platform":
        command.append("--add-readme")
    return command


def create(repositories, visibility):
    # Stop on authentication/network errors; do not mistake them for missing repos.
    existing = set(
        run(
            ["gh", "api", "--paginate", f"orgs/{ORG}/repos?per_page=100", "--jq", ".[].name"],
            capture=True,
        ).stdout.splitlines()
    )
    for repository in repositories:
        if repository["name"] in existing:
            print(f"Exists: {ORG}/{repository['name']} (settings unchanged)", flush=True)
        else:
            run(creation_command(repository, visibility))


def clone(repositories, workspace):
    workspace.mkdir(parents=True, exist_ok=True)
    report = Report([repository["name"] for repository in repositories])
    heading(f"Cloning into {workspace}")
    for name, path in checkouts(repositories, workspace):
        try:
            if path.exists() or path.is_symlink():
                check_checkout(path, name)
                report.line("same", name, "", "already cloned (left unchanged)")
            else:
                run(["gh", "repo", "clone", f"{ORG}/{name}", str(path), "--", "--quiet"],
                    capture=True)
                report.line("cloned", name, MAIN, "cloned")
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            report.line("fail", name, "", error_text(error))
    return report.summary()


def sync_local_main(path, current_branch):
    """Fast-forward the local main branch while you work on another branch."""
    if (
        current_branch == MAIN
        or not ref_exists(path, f"refs/heads/{MAIN}")
        or not ref_exists(path, f"refs/remotes/origin/{MAIN}")
    ):
        return ""
    behind = count(path, f"{MAIN}..origin/{MAIN}")
    if not behind:
        return ""
    if count(path, f"origin/{MAIN}..{MAIN}"):
        return f"; local {MAIN} has diverged, left as is"
    # Refuses anything but a fast-forward, and refuses if main is checked out elsewhere.
    result = git(path, "fetch", "--quiet", ".", f"origin/{MAIN}:{MAIN}", check=False)
    return f"; {MAIN} +{behind}" if result.returncode == 0 else ""


def pull_one(path):
    """Return (branch, kind, message, hint). Never merges, rebases, stashes or switches."""
    fetch(path)
    state = read_state(path)
    main_note = sync_local_main(path, state.branch)
    if not state.branch:
        return "detached", "warn", "detached HEAD; fetched only" + main_note, f"git switch {MAIN}"
    if state.gone:
        return (state.branch, "warn", "branch was deleted on GitHub (merged?)" + main_note,
                f"git switch {MAIN} && git branch -d {state.branch}")
    if not state.upstream:
        return (state.branch, "info", "not on GitHub yet; nothing to pull" + main_note,
                "publish it with the push command")
    if state.behind == 0:
        message = "up to date"
        if state.ahead:
            message += f", {plural(state.ahead, 'local commit')} to push"
        return state.branch, "same", message + main_note, None
    if state.ahead:
        return (state.branch, "warn",
                f"diverged: {plural(state.ahead, 'local commit')}, {state.behind} on GitHub",
                f"cd {path.name} && git pull --rebase")
    result = git(path, "merge", "--ff-only", "--quiet", state.upstream, check=False)
    if result.returncode:
        if state.dirty:
            return (state.branch, "warn",
                    f"{plural(state.behind, 'new commit')} touch files you changed locally",
                    "commit or stash your changes, then pull again")
        raise subprocess.CalledProcessError(result.returncode, result.args, stderr=result.stderr)
    message = f"pulled {plural(state.behind, 'commit')}"
    if state.dirty:
        message += " (kept your uncommitted changes)"
    return state.branch, "updated", message + main_note, None


def pull(repositories, workspace):
    report = Report([repository["name"] for repository in repositories])
    heading(f"Pulling {len(repositories)} repositories in {workspace}")
    for name, path in checkouts(repositories, workspace):
        if not path.exists():
            report.line("warn", name, "", "missing locally", "run the clone command")
            continue
        try:
            check_checkout(path, name)
            branch, kind, message, hint = pull_one(path)
            report.line(kind, name, branch, message, hint)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            report.line("fail", name, "", error_text(error))
    return report.summary()


@dataclass
class PushPlan:
    name: str
    path: Path
    branch: str
    commits: int
    new: bool


def plan_push(name, path, allow_main):
    """Return (PushPlan or None, (kind, message, hint) describing the repo)."""
    fetch(path)
    state = read_state(path)
    local = " (uncommitted changes stay local)" if state.dirty else ""
    if not state.branch:
        return None, ("warn", "detached HEAD; nothing to push", "git switch <branch>")
    if state.gone:
        return None, ("warn", "branch was deleted on GitHub (merged?)",
                      f"git switch {MAIN}, or recreate it: git push -u origin {state.branch}")
    if state.upstream:
        if state.behind and state.ahead:
            return None, ("warn", f"diverged: {plural(state.ahead, 'local commit')}, "
                                  f"{state.behind} on GitHub", f"cd {name} && git pull --rebase")
        if state.behind:
            return None, ("warn", f"{plural(state.behind, 'new commit')} on GitHub",
                          "pull first")
        commits, new = state.ahead, False
    else:
        base = f"origin/{MAIN}"
        commits = count(path, f"{base}..HEAD" if ref_exists(path, base) else "HEAD")
        new = True
    if not commits:
        return None, ("same", "nothing to push" + local, None)
    if state.branch == MAIN and not allow_main:
        return None, ("warn", f"{plural(commits, 'commit')} on {MAIN}, not pushed",
                      f"move them: git switch -c feature/<name> && git branch -f {MAIN} "
                      f"origin/{MAIN}  (or rerun with --main)")
    target = "new branch on GitHub" if new else f"origin/{state.branch}"
    message = f"{plural(commits, 'commit')} → {target}{local}"
    return PushPlan(name, path, state.branch, commits, new), ("ready", message, None)


def push(repositories, workspace, *, allow_main=False, assume_yes=False):
    report = Report([repository["name"] for repository in repositories])
    heading(f"Checking {len(repositories)} repositories in {workspace}")
    plans = []
    for name, path in checkouts(repositories, workspace):
        if not path.exists():
            report.line("warn", name, "", "missing locally", "run the clone command")
            continue
        try:
            check_checkout(path, name)
            plan, (kind, message, hint) = plan_push(name, path, allow_main)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            report.line("fail", name, "", error_text(error))
            continue
        report.line(kind, name, plan.branch if plan else read_state(path).branch, message, hint)
        if plan:
            plans.append(plan)

    if not plans:
        print(paint("\nNothing to push.", "dim"))
        return report.summary()
    if not assume_yes:
        branches = "1 branch" if len(plans) == 1 else f"{len(plans)} branches"
        question = f"\nPush {branches} to GitHub? [y/N] "
        if not sys.stdin.isatty():
            print(paint("\nNot an interactive terminal; rerun with --yes to push.", "yellow"))
            return True
        if input(paint(question, "bold")).strip().lower() not in ("y", "yes"):
            print("Nothing pushed.")
            return report.summary()

    heading("\nPushing")
    for plan in plans:
        command = ["push", "--quiet", "--set-upstream"] if plan.new else ["push", "--quiet"]
        result = git(plan.path, *command, "origin", plan.branch, check=False)
        if result.returncode:
            error = subprocess.CalledProcessError(result.returncode, result.args, stderr=result.stderr)
            report.line("fail", plan.name, plan.branch, error_text(error))
            continue
        hint = None
        if plan.branch != MAIN:
            hint = f"open a PR: https://github.com/{ORG}/{plan.name}/pull/new/{plan.branch}"
        report.line("pushed", plan.name, plan.branch, f"pushed {plural(plan.commits, 'commit')}", hint)
    return report.summary()


def status(repositories, workspace):
    report = Report([repository["name"] for repository in repositories])
    heading(f"Status of {len(repositories)} repositories in {workspace}")
    for name, path in checkouts(repositories, workspace):
        if not path.exists():
            report.line("warn", name, "", "missing locally", "run the clone command")
            continue
        try:
            check_checkout(path, name)
            fetch(path)
            state = read_state(path)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            report.line("fail", name, "", error_text(error))
            continue
        parts, kind = [], "same"
        if not state.branch:
            parts, kind = ["detached HEAD"], "warn"
        elif state.gone:
            parts, kind = ["branch deleted on GitHub"], "warn"
        elif not state.upstream:
            parts, kind = ["not on GitHub yet"], "info"
        if state.ahead:
            parts.append(f"↑{state.ahead} to push")
            kind = "info" if kind == "same" else kind
        if state.behind:
            parts.append(f"↓{state.behind} to pull")
            kind = "warn" if state.ahead else ("info" if kind == "same" else kind)
        if state.dirty:
            parts.append("uncommitted changes")
            kind = "info" if kind == "same" else kind
        report.line(kind, name, state.branch or "detached", ", ".join(parts) or "clean, up to date")
    return report.summary()


def load_repositories():
    repositories = json.loads((ROOT / "repositories.json").read_text())
    names = set()
    for repository in repositories:
        name = repository["name"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or name in names:
            raise ValueError(f"Invalid or duplicate repository name: {name}")
        names.add(name)
    return repositories


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Print creation commands; no network or changes")
    plan.add_argument("--visibility", choices=["private", "public"], default="private")
    creation = commands.add_parser("create", help="Create missing GitHub repositories")
    creation.add_argument("--visibility", choices=["private", "public"], required=True)

    workspace = argparse.ArgumentParser(add_help=False)
    workspace.add_argument(
        "--workspace", type=Path, default=ROOT.parent,
        help="folder containing the checkouts (default: the folder around platform)",
    )
    commands.add_parser("clone", parents=[workspace],
                        help="Clone missing repos; never touch existing ones")
    commands.add_parser("status", parents=[workspace],
                        help="Show branch, commits to push/pull and local changes per repo")
    commands.add_parser("pull", parents=[workspace],
                        help="Fast-forward every repo's current branch (and local main)")
    pushing = commands.add_parser("push", parents=[workspace],
                                  help="Push every repo's current branch after confirming")
    pushing.add_argument("--main", action="store_true",
                         help=f"also push commits made directly on {MAIN}")
    pushing.add_argument("-y", "--yes", action="store_true", help="don't ask for confirmation")

    args = parser.parse_args()
    repositories = load_repositories()
    if args.command == "plan":
        for repository in repositories:
            print(shlex.join(creation_command(repository, args.visibility)))
        return False
    if args.command == "create":
        create(repositories, args.visibility)
        return False
    workspace = args.workspace.expanduser().resolve()
    if args.command == "clone":
        return clone(repositories, workspace)
    if args.command == "status":
        return status(repositories, workspace)
    if args.command == "pull":
        return pull(repositories, workspace)
    return push(repositories, workspace, allow_main=args.main, assume_yes=args.yes)


if __name__ == "__main__":
    if os.name == "nt":
        os.system("")  
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(errors="replace")  
    try:
        sys.exit(1 if main() else 0)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(paint(f"Stopped: {error_text(error)}", "red", "bold"), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
