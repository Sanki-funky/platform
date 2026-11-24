# Repository setup

The everyday `clone` and `pull` examples are in the [README](../README.md). This page covers the initial GitHub setup.

## Create the repositories

The script reads the names and descriptions in [repositories.json](../repositories.json). It works on that list, rather than every repository in the organization.

From the platform folder, preview the commands:

```bash
python3 scripts/repos.py plan
```

To create missing repos:

```bash
python3 scripts/repos.py create --visibility private
```

Use `public` instead of `private` if that's what we want. You'll need permission to create repos in `Sanki-funky`. Existing repositories are skipped and keep their current settings. If creation stops partway through, fix the error and run it again.

Set the organization's default branch to `main` before creating service repos. They get an initial README. Platform is created empty so we can publish these local files as its first commit.

## Publish platform for the first time

If this folder isn't already in Git, and the remote platform repo is empty, run these commands inside it:

```bash
git init -b main
git add README.md .gitignore repositories.json scripts/ docs/
git commit -m "Add platform setup and project docs"
git remote add origin https://github.com/Sanki-funky/platform.git
git push -u origin main
```

If you're already in a Git checkout, use its normal commit/push workflow. If the remote has commits, clone it and copy these files into that checkout instead. See [folder structure](structure.md) for where the platform checkout should live.

## Clone, pull or push?

`clone` downloads a repository you don't have yet. Running it again leaves existing checkouts alone.

`pull` fetches every repository, platform included (it goes last), and fast-forwards whatever branch you have checked out. If you're on a feature branch, your local `main` is fast-forwarded too. Uncommitted changes stay put; Git only refuses when an incoming commit touches a file you've changed, and the script then tells you to commit or stash first. If a branch has diverged, never been pushed, or was deleted on GitHub, the script says so and suggests the command to run. It carries on with the other repos and exits unsuccessfully when something needs attention.

`push` shows what each repository would push, then asks before pushing anything. It pushes the branch you have checked out; a branch that isn't on GitHub yet is published with tracking set up, and you get a link to open a pull request. It never force-pushes, and it won't push a branch that is behind GitHub (pull first). Commits made directly on `main` are held back because we merge into `main` through reviewed PRs; it shows how to move them onto a branch, or use `--main` for the rare case you mean it.

`status` fetches and lists each repo's branch, commits to push or pull, and local changes. It changes nothing.

None of the commands switch branches, reset files, stash changes or create merge commits.

The default workspace is the parent of this platform folder. To use another location:

```bash
python3 scripts/repos.py clone --workspace ~/projects/sank
python3 scripts/repos.py pull --workspace ~/projects/sank
```

The script checks each existing checkout's `origin` against the expected Sanki-funky repo. If it reports an unexpected origin, check that you're pointing at the right workspace.

## Check the script locally

The pull tests use temporary Git repositories on your machine. They don't contact GitHub or update your services.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
```
