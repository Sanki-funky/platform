"""Create or clone the explicit Sank repository list. Standard library only."""

import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
ORG = "Sanki-funky"


def run(args, *, capture=False):
    return subprocess.run(args, check=True, text=True, capture_output=capture)


def load_repositories():
    repositories = json.loads((ROOT / "repositories.json").read_text())
    names = set()
    for repository in repositories:
        name = repository["name"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or name in names:
            raise ValueError(f"Invalid or duplicate repository name: {name}")
        names.add(name)
    return repositories


def creation_command(repository, visibility):
    command = [
        "gh",
        "repo",
        "create",
        f"{ORG}/{repository['name']}",
        f"--{visibility}",
        "--description",
        repository["description"],
    ]
    # This local directory supplies platform's first commit. Avoid unrelated histories.
    if repository["name"] != "platform":
        command.append("--add-readme")
    return command


def create(repositories, visibility):
    # Stop on authentication/network errors; do not mistake them for missing repos.
    existing = set(
        run(
            [
                "gh",
                "api",
                "--paginate",
                f"orgs/{ORG}/repos?per_page=100",
                "--jq",
                ".[].name",
            ],
            capture=True,
        ).stdout.splitlines()
    )
    for repository in repositories:
        if repository["name"] in existing:
            print(
                f"Exists: {ORG}/{repository['name']} (settings unchanged)", flush=True
            )
        else:
            run(creation_command(repository, visibility))


def clone(repositories, workspace):
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    for repository in repositories:
        name = repository["name"]
        destination = workspace / name
        if destination.resolve() == ROOT:
            print(f"Using local platform directory: {ROOT}", flush=True)
            continue
        if destination.exists() or destination.is_symlink():
            if not (destination / ".git").exists():
                raise ValueError(f"Existing path is not a checkout: {destination}")
            origin = run(
                [
                    "git",
                    "-C",
                    str(destination),
                    "remote",
                    "get-url",
                    "origin",
                ],
                capture=True,
            ).stdout.strip()
            expected = (
                f"git@github.com:{ORG}/{name}.git",
                f"https://github.com/{ORG}/{name}.git",
                f"https://github.com/{ORG}/{name}",
                f"ssh://git@github.com/{ORG}/{name}.git",
            )
            if origin not in expected:
                raise ValueError(f"Unexpected origin for {destination}: {origin}")
            print(f"Already cloned: {name} (working tree unchanged)", flush=True)
        else:
            run(["gh", "repo", "clone", f"{ORG}/{name}", str(destination)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser(
        "plan", help="Print creation commands; no network or changes"
    )
    plan.add_argument("--visibility", choices=["private", "public"], default="private")
    creation = commands.add_parser("create", help="Create missing GitHub repositories")
    creation.add_argument("--visibility", choices=["private", "public"], required=True)
    cloning = commands.add_parser(
        "clone", help="Clone missing repos; never pull/reset existing ones"
    )
    cloning.add_argument("--workspace", type=Path, default=ROOT.parent)
    args = parser.parse_args()
    repositories = load_repositories()
    if args.command == "plan":
        for repository in repositories:
            print(shlex.join(creation_command(repository, args.visibility)))
    elif args.command == "create":
        create(repositories, args.visibility)
    else:
        clone(repositories, args.workspace)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        sys.exit(1)
