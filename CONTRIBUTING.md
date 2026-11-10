# Contributing

Issues and pull requests are welcome. The parts most open to argument are the judges' prompts, the
round structure, and how stand-ins are chosen.

## Set up

```sh
git clone https://github.com/kishormorol/ineedsilence
cd ineedsilence
python3 -m unittest discover -s tests -v
```

There is nothing to install: the script and the tests use the Python standard library, and the
tests never call a judge.

## Changing something

- **The script** (`scripts/panel.py`): add or update a test in `tests/test_panel.py`. If you touch
  how a judge is run, also run `panel.py doctor` once normally and once with a deliberately wrong
  model name in `assets/judges.json`, because the failure path is not exercised when all three
  judges answer.
- **A prompt** (`BRIEF`, `ROUND1`, `ROUND1_SKILL`, `ROUNDN` in `panel.py`): say in the pull request
  what the old wording got wrong, with the judge's reply that showed it if you have one. The judges
  read files in different ways: Codex reads through a read-only shell, Antigravity refuses any
  command in plan mode. A rule that helps one can stop another from reading at all, so
  tool-specific rules belong in `run_judge`, not in the shared brief.
- **A new judge**: most need no code. An OpenAI-compatible endpoint is a `type: api` entry and any
  agent CLI is a `type: command` entry in `assets/judges.json`; add a checked example to
  `assets/judges.example.json` and say in the pull request that you ran `doctor` with it. A new
  built-in type is a branch in `run_judge` and an entry in `LOGIN`, for a CLI that needs flags the
  `command` type cannot express.
- **The instructions** (`SKILL.md`): explain the reason for a rule in the text, as the rest of the
  file does.

Do not commit `lessons.jsonl`, `LESSONS.md` or any `*.silence/` folder: they describe your own
runs and may hold text from your documents. They are in `.gitignore`.

## Reporting a bug

Include the command, what it printed, and the last lines of the relevant
`round-N/<judge>.raw.txt` with anything from your document removed.

## Pull requests

One purpose per pull request, with the tests passing. Say what changed, why, and how you checked
it.
