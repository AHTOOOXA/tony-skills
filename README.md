# tony-skills

Skills for [Claude Code](https://claude.com/claude-code) (and any agent that
reads `SKILL.md`). One skill so far.

| Skill | What it does |
|---|---|
| [`pishi/`](pishi/) | Russian prose for a human reader — messages to a CTO, ops instructions, tickets, PR bodies, explanations, cover letters, how-tos for parents. Infostyle method + Russian AI-tell removal + your own house rules, with a zero-dependency linter that scores a draft 0–100. |

## pishi — «Пиши, сокращай» для агента

Claude's Russian is grammatically clean and still reads as machine output: twice
as long as needed, opens with a preamble, cites numbers that are not in the
source, formats a chat answer as a document with headers. `pishi` fixes that
layer first, then the language layer (stop-words, bureaucratese, passive,
vagueness, AI-tells).

**Order of work** (this order, because it matches how people actually correct
machine Russian): reader / action / channel / length → facts only from the
source → first line is the point → structure = the reader's question → eight
stop-word groups → verbs and one thought per sentence → AI-tells → one linter
pass → deliver.

**Linter** — `pishi/scripts/check.py`, stdlib only:

```bash
python3 pishi/scripts/check.py draft.txt
python3 pishi/scripts/check.py draft.txt --source notes.md --max-words 180 --no-greeting
echo "текст" | python3 pishi/scripts/check.py -
```

Prints hits by category with line numbers and a `ЧИСТОТА: N/100` score.
`--source` flags every number in the draft that does not appear in the source
material — the «цифры непонятно откуда» detector. Exit code 1 on `--max-words`,
`--no-greeting`, `--min-score` or foreign-number failures, so it works in evals.

**House rules** — the skill reads `~/.claude/pishi/house-rules.md` before every
task if it exists. That file is where *your* repeated corrections live (quote →
rule), plus your team's formats. Template: `pishi/references/house-rules.example.md`.
Keep it out of public repos.

**Benchmark** — `pishi/evals/`: six tasks on fictional data with mechanical
checks. On the author's private set of real tasks (iteration 1, Opus, 5 tasks ×
with/without skill): assertion pass rate 100 % vs 77 %; mean output length −29 %;
linter scores were 96–100 in both arms — the wins are all in length, format and
facts-from-source, not in vocabulary.

## Install

```bash
git clone https://github.com/AHTOOOXA/tony-skills ~/tony-skills
ln -s ~/tony-skills/pishi ~/.claude/skills/pishi          # user scope: every project
# or project scope:
ln -s ~/tony-skills/pishi <repo>/.claude/skills/pishi
mkdir -p ~/.claude/pishi && cp ~/tony-skills/pishi/references/house-rules.example.md ~/.claude/pishi/house-rules.md
```

Restart Claude Code. The skill triggers on Russian writing requests («напиши»,
«объясни по-русски», «сократи», «сообщение для…», «тикет», «PR на русском»).

## Credits

The editing method is the information style of Максим Ильяхов and Людмила
Сарычева («Пиши, сокращай»), paraphrased; examples here are original. The
Russian AI-tell list draws on public work such as
[humanizer-ru](https://github.com/ilyautov/humanizer-ru) and the
[LLM Writing Quality by Language](https://peterkaminski.ai/research/llm-writing-quality-by-language/)
survey.

MIT.
