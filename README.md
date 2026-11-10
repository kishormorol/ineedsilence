# ineedsilence

**Three AIs review your paper. Then they review each other. You get it back when they finally stop talking.**

![Three AI judges go from "12 issues" to "Judge B is wrong" to green](assets/hero.png)

Reviewer 2 has been automated. Unfortunately, so have Reviewers 1 and 3.

`ineedsilence` is a skill for [Claude Code](https://claude.com/claude-code). It hands your draft to
Claude, GPT and Gemini separately (or to any panel you choose: add DeepSeek, Kimi, Qwen, a local
model, four judges, five), merges what they find, fixes it, and then makes the three of
them argue with each other until nobody has anything left to say. That last part is the silence.

## Try it in two minutes

Out of the box you need Claude Code, the Codex CLI (`codex`) and the Antigravity CLI (`agy`), each
signed in. Don't have one of them? [Pick your own judges](#pick-your-judges-as-many-as-you-like):
DeepSeek, Kimi, Qwen, a local model, or any agent CLI.

```sh
git clone https://github.com/kishormorol/ineedsilence ~/.claude/skills/ineedsilence
python3 ~/.claude/skills/ineedsilence/scripts/panel.py doctor
```

`doctor` asks each judge a ten-second question. You want to see this:

```
  claude  Claude Fable 5.2                  4s  ok
  gpt     GPT-6 Astra (Codex)              10s  ok
  gemini  Gemini 4 Argon (Antigravity)     17s  ok
ALL 3 JUDGES READY
```

If a judge fails, it tells you why in plain words: not signed in, model name not accepted, out of
usage, or not installed.

Then open Claude Code and say:

```
/ineedsilence path/to/my-paper-folder
```

Go make tea. A round takes 5 to 30 minutes.

## What happens while you drink the tea

**Round 1: everyone reads alone.** No judge sees another's notes. Each returns up to 25 issues,
and every one must come with a location and an exact quote from your text. No "consider improving
clarity". No praise either.

**Intermission: the cleanup.** Claude Code merges the duplicates, checks every issue against your
actual text (judges do sometimes complain about things that are not there), fixes what is real,
and writes down exactly what it changed.

**Round 2: cross-examination.** Each judge gets the revised text and one shared list of every
issue, with the others' opinions attached. The names are hidden: they only see "judge A" and
"judge B", so nobody defers to a famous model. For each item they answer *resolved*, *still open*,
or *not an issue*.

**Round 3: sign-off.** Green or red. A green means "I would put my name to this text."

If someone is still red, you get one more round. After that the tool stops and tells you who is
unhappy and why, instead of grinding on forever.

## A real argument

This is round 4 from the tool's first full run. Two judges were happy. The third had spotted a real
bug that the *previous round's fix* had introduced:

```
$ panel.py verdict skills.silence
round 4: claude=green  gpt=red  gemini=green
NOT SILENT
  - gpt: still open ['I7']
  - gpt: new blocker/major issues: ['Baseline comparison can leave the requested change undone']
```

Some numbers from that run, so you know what to expect:

| | |
|---|---|
| Issues raised in round 1 | 62 |
| Distinct issues after merging | 28 |
| Issues a judge invented | 1 (it insisted two real model names did not exist) |
| Times a judge dropped its own objection after reading the others | at least once |
| Rounds until silence | 5 |

## The rule that makes it honest

`panel.py verdict` prints `SILENCE` only if **all** of this is true:

- it is round 3 or later;
- every judge on the panel said green;
- nobody left a single item "still open";
- nobody raised a new serious issue;
- every judge answered every item on the list;
- the text has not changed by one character since they read it.

It reads the judges' own saved replies. You cannot get there by editing the list, and neither can
the AI running the show. Touch the paper after sign-off and the greens are void.

## Please read this part

**Your whole document goes to three companies.** Anthropic, OpenAI and Google, plus Mistral or Meta
if a stand-in steps in. Do not use this on a paper you are *refereeing* or on anything you are not
allowed to share. Ask your co-authors first.

**It eats quota.** Each round is one long, careful review per judge, and a full run is three to
five rounds. In the first run, one vendor's weekly allowance for its best model was gone after a
single round.

**Silence is not truth.** It means three models ran out of objections. Research on AI debate keeps
finding that models can agree on wrong answers together, and that extra rounds can invent problems
([Choi et al.](https://arxiv.org/abs/2508.17536),
[Batra et al.](https://arxiv.org/abs/2610.35930),
[Song](https://arxiv.org/abs/2603.16244)). The judges also read only your document: they do not
check your novelty against the literature or whether your citations exist. Treat this as a tough
pre-submission read, not a guarantee.

**Check your plans' terms.** The script drives each vendor's command-line tool without a human at
the keyboard. Whether your subscription allows that is between you and the vendor.

## When a judge runs out of quota

It will. The script then seats a stand-in by itself, in this order:

1. the same vendor's other model (say, a Flash model for the flagship), so that vendor stays on the
   panel;
2. another vendor: Mistral through `vibe`, then Meta through `muse`.

It only does this for a usage limit, never for the Claude seat, and the final verdict names every
stand-in. Read that line. In the first run the one judge still objecting ran out of quota before
the last round, so the final green for its seat came from a stand-in. The tool said so. A tool that
hid it would be worse than no tool.

Prefer the run to stop instead? Delete `alternates` and `fallbacks` from `assets/judges.json`.

## Pick your judges (as many as you like)

The panel is whatever `assets/judges.json` lists. Three ship by default. Add a fourth and a fifth,
swap one out, or run a different set per paper:

```sh
/ineedsilence my-paper                                            # everyone in judges.json
panel.py init my-paper --judges claude,gpt,deepseek,qwen,kimi    # or pick for this run
```

Every judge has a `type`, and two of the types cover almost anything:

| Type | What it is | Good for |
|---|---|---|
| `claude`, `codex`, `agy` | the three built-in agent CLIs | Claude, GPT, Gemini on your subscriptions |
| `vibe`, `muse` | two more built-in CLIs | Mistral, Meta |
| `api` | any OpenAI-compatible `/chat/completions` endpoint | **DeepSeek, Kimi, Qwen**, OpenRouter, a local Ollama model |
| `command` | any program that prints the JSON reply | whatever agent CLI you already use |

An API judge, with the key kept in an environment variable and never in the file:

```json
{"name": "deepseek", "type": "api", "base_url": "https://api.deepseek.com",
 "model": "<a DeepSeek model id>", "key_env": "DEEPSEEK_API_KEY", "label": "DeepSeek"}
```

A fully local judge, which sends your paper nowhere:

```json
{"name": "local", "type": "api", "base_url": "http://localhost:11434/v1",
 "model": "qwen2.5:3b", "max_chars": 60000, "label": "Local model (Ollama)"}
```

Any other command-line agent:

```json
{"name": "mine", "type": "command", "model": "<model>",
 "run": ["my-agent", "--model", "{model}", "--prompt-file", "{prompt_file}"]}
```

`assets/judges.example.json` has ready-to-copy entries for DeepSeek, Kimi, Qwen, OpenRouter, Ollama
and opencode. Base URLs and model names change, so check each provider's page.

Things worth knowing before you seat five judges:

- **More judges, more quota, less silence.** Every judge has to go green on the same text. Five
  fussy readers agree less often than three.
- **Two is allowed, three is the point.** Two models can agree on the same mistake. The script
  warns you and carries on.
- **An API judge has no eyes.** It gets the text files pasted into its prompt, so it cannot look
  at a figure, and a very large project may not fit (`max_chars`, refused instead of silently cut).
- **Small models make noisy judges.** A 3B local model will find the obvious and invent some of
  the rest. Fine as a fourth opinion, weak as one of three.
- **What has actually been run:** the three built-ins, `vibe` and `muse` on real documents; the
  `api` type against a local Ollama model in a real round; the `command` type with opencode up to
  its free-tier limit. DeepSeek's, Kimi's, Qwen's and OpenRouter's endpoints were reached at the
  addresses in the examples file and answered "no key" as expected (10 Nov 2026), so the addresses
  and paths are right. A full review through them has not been run by the author, who has no keys
  for them: a report of what happens on yours is welcome.

## Not only papers

```sh
panel.py init my-skills --kind skill --focus "a/SKILL.md, b/SKILL.md"
panel.py init my-report --kind document
```

`--kind skill` asks the judges to review instructions written for AI agents: contradictions,
missing cases, steps nobody could check. `--focus` says which files to judge when the folder holds
more.

For a paper, point it at the **LaTeX folder**. With only a PDF the judges can complain, but nothing
can be fixed, so there is nothing to sign off.

## Questions people ask

**Do they really disagree?** Yes. In the first run two judges gave opposite advice on the same
step, and on another point a judge withdrew its own objection in round 2 after reading the
reasoning against it.

**Can I use just two judges?** You can, and the script will say what it thinks of that. Two can be
wrong together and feel great about it.

**Can I use five?** Yes. Bring snacks.

**Will it make my paper get accepted?** No. It makes your paper survive three fussy readers who
never get tired. Human reviewers know your field's literature; these three only know your PDF.

**Does it invent results to fix a weak claim?** It is told never to. When a claim outruns the
evidence, it narrows the claim or states the gap, and lists every claim it touched so you can
disagree.

**Why is it called that?** Because after the third round of "Judge B is wrong", silence is all
anyone wants.

## What a run leaves behind

Everything, so you can check the tool's work:

```
paper.silence/
  issues.json           the shared list: every issue, what was done, who thinks what
  seats.json            which stand-ins sat where, if any
  round-N/
    paper/              the exact copy the judges read
    <judge>.prompt.txt  exactly what each judge was told
    <judge>.json        exactly what it answered
    <judge>.raw.txt     the tool's full output
```

## It learns

The skill keeps a private notebook of what went wrong on your runs (`LESSONS.md`) and reads it
before the next one. A mistake you correct, or one it makes twice, gets written into the skill
itself. The notebook stays on your machine. [LEARNING.md](LEARNING.md) has the rules, including
the important one: nothing a reviewed document says can become a lesson.

## For tinkerers

- Python 3.9 or later, standard library only. Nothing to `pip install`.
- `pdftotext` (poppler) if you want the judges to read a compiled PDF.
- 30 tests run offline and never call a real judge: `python3 -m unittest discover -s tests -v`
- The prompts live at the top of `scripts/panel.py`. They are short. Argue with them.

Version 0.1: one full five-round run and one toy run so far. It has not been measured on documents
with known, planted errors, so nobody knows yet how often it goes silent on a text that still has
a bug. That would make a good experiment. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence and citation

MIT. If it helps your research, cite it with [CITATION.cff](CITATION.cff).
