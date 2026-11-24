# Repository setup

The everyday commands are in the [README](../README.md). This page has the details.

The script works on the repositories named in [repositories.json](../repositories.json), not on every repository in the `Sanki-funky` organization. Each one lives in a folder of the same name next to platform. See [folder structure](structure.md).

## What each command does

`pull` clones any repository you don't have yet. It uses SSH if you cloned platform over SSH, otherwise HTTPS. Then it fetches every repository, platform included (it goes last), and fast-forwards whatever branch you have checked out. If you're on a feature branch, your local `main` is fast-forwarded too. Uncommitted changes stay put; Git only refuses when an incoming commit touches a file you've changed, and the script then tells you to commit or stash first. If a branch has diverged, never been pushed, or was deleted on GitHub, the script says so and suggests the command to run. It carries on with the other repos and exits unsuccessfully when something needs attention.

`push` shows what each repository would push, then asks before pushing anything. It pushes the branch you have checked out; a branch that isn't on GitHub yet is published with tracking set up, and you get a link to open a pull request. It never force-pushes, and it won't push a branch that is behind GitHub (pull first). Commits made directly on `main` are held back because we merge into `main` through reviewed PRs; it shows how to move them onto a branch, or use `--main` for the rare case you mean it.

`status` fetches and lists each repo's branch, commits to push or pull, and local changes. It changes nothing.

None of the commands switch branches, reset files, stash changes or create merge commits.

The script checks each existing checkout's `origin` against the expected `Sanki-funky` repo. If it reports an unexpected origin, check that you're pointing at the right workspace. The default workspace is the parent of the platform folder. To use another location:

```bash
python3 scripts/repos.py pull --workspace ~/projects/sank
```

## Add a repository

1. Create it in the `Sanki-funky` organization on GitHub, with `main` as the default branch and an initial README.
2. Add its name and a one-line description to [repositories.json](../repositories.json) and get that change merged into platform.
3. Everyone runs `pull`, which clones it.

## Check the script locally

The tests use temporary Git repositories on your machine. They don't contact GitHub or touch your checkouts.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
```
