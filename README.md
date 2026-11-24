# Šank platform

Šank lives across several repositories. This folder is our shared starting point: the project docs and the scripts we use to get everything onto our machines.

The services each have their own code and release cycle. Platform holds the things we need across the project. As we build out the app, the local Docker Compose setup and shared cloud configuration will live here too. For now, we have the repo script and the docs below.

## Get the repositories

You'll need Python 3.9+, Git and the GitHub CLI (`gh`). Sign in once if you haven't already:

```bash
gh auth login
```

Run these commands **inside the platform folder**:

```bash
python3 scripts/repos.py clone
```

This downloads the repositories listed in [repositories.json](repositories.json), next to this folder. It skips anything you've already cloned.

Day to day you'll use three commands:

```bash
python3 scripts/repos.py status   # what's ahead, behind or uncommitted in each repo
python3 scripts/repos.py pull     # get everyone's latest changes
python3 scripts/repos.py push     # push what you've committed, after a preview
```

On Windows (PowerShell), use `python .\scripts\repos.py pull` and so on.

`pull` updates every repo on whatever branch you have checked out and keeps your local `main` current too. Your uncommitted changes stay where they are. When a repo needs you (diverged branch, files you changed also changed on GitHub, a branch deleted after its PR was merged) the script says what to run and carries on with the others.

`push` pushes each repo's current branch after you confirm. New branches are published and you get a link to open a PR. Commits made directly on `main` are held back, since changes reach `main` through reviewed PRs; add `--main` if you really mean to push them. It never force-pushes.

Typical flow: `git switch -c feature/menu-prices` in the repo you're changing, commit, then `push` and open the PR from the link. After it's merged, `git switch main` and `pull`.

### Run it from any folder

The script always works on the folder around platform, wherever you run it from. To avoid typing the path, add an alias once.

macOS/Linux, in `~/.zshrc` or `~/.bashrc` (use your own path):

```bash
alias sank='python3 "$HOME/path/to/PROJECT/platform/scripts/repos.py"'
```

Windows, in your PowerShell profile (`notepad $PROFILE`):

```powershell
function sank { python "C:\path\to\PROJECT\platform\scripts\repos.py" @args }
```

Then `sank status`, `sank pull` and `sank push` work in `PROJECT/`, `PROJECT/platform`, inside any service, anywhere.

The output is coloured when you run it in a terminal. Set `NO_COLOR=1` to turn that off.

## Other script commands

```bash
# See which GitHub repositories would be created. Changes nothing.
python3 scripts/repos.py plan

# Create any missing repositories in Sanki-funky.
python3 scripts/repos.py create --visibility private

# Clone into a different workspace.
python3 scripts/repos.py clone --workspace ~/projects/sank
```

Use `--visibility public` if you want public repositories. Existing repos keep their current settings. `status`, `pull` and `push` also accept `--workspace`.

The script handles repositories only. It doesn't start services or deploy the app. [Repository setup](docs/repository-setup.md) covers the one-time publishing steps and a couple of common questions.

## Project docs

- [Folder structure](docs/structure.md): where things go and what belongs in platform.
- [Microservices](docs/services.md): what each service owns and how they work together.
- [Development](docs/development.md): the onion structure and what to build first.
- [Deployment](docs/deployment.md): the plan for CI/CD, Helm and Azure.
- [Course requirements](docs/project-requirements.md): what the course asks for and what we've chosen to build.
