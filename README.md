# Text-to-Cypher on a quality-management knowledge graph: Graph RAG, Neo4j-MCP and Agent Skills

This repository holds the evaluation harness, configurations, questions and scored results for a study submitted
for publication; the reference will be added here once it is published. The study compares ways of giving a large language model what it needs to
write Cypher queries for a concrete-block factory's quality-management knowledge graph: the schema and few-shot
examples in the prompt (Graph RAG), a Model Context Protocol server (Neo4j-MCP), and Agent Skills (a generic skill
and a domain-specific skill), all run through one harness so that only the configuration changes.

## What is here

| Folder | Contents |
|---|---|
| `harness/` | The harness: prompt building, the episode loop, model clients (Claude, GPT), database back ends (Neo4j driver, MCP server), skill tools, run planning and recording |
| `configurations/` | One YAML file per configuration (C0–C7t) and `models.yaml` (pinned model versions and request settings) |
| `prompts/` | Base prompt, few-shot examples, output notes, skill and domain texts, placebo text; `prompts/original/` holds the schema texts the configurations read |
| `skills/concrete-qm-graph/` | The domain-specific skill (instructions, reference files, query patterns and `validate.py`) |
| `data/` | The question sets: `questions_original.jsonl` (20 original questions) and `questions_v2.jsonl` (60 questions in 46 information needs, with ground-truth queries and expected answers); `needs.md` lists the needs. In this copy the header's `source` field in `questions_original.jsonl` is a relative path; the questions are unchanged |
| `scoring/` | Automatic scores (LA, EAA, EA_S) and the rescoring script |
| `analysis/` | The contrast analysis (`analysis_contrasts.py`) and its test |
| `runs/main/` | The main run's scores per episode (`runs_scored.csv`), the analysis output (`contrast_results*.csv`) and the session records |
| `tests/` | Tests for every harness module |
| `scripts/view_run.py` | Writes a readable HTML page of a run folder's episodes |

The raw episode records (every conversation, prompt and query result) and the manual ratings are not included
because of their size; they are available from the corresponding author on request.

## Configurations

| ID | Mechanism |
|---|---|
| C0 | No schema (schema-blind baseline) |
| C1 | Graph RAG: full schema and few-shot examples, query run through the Neo4j driver |
| C2 | As C1 with the MCP server's schema text |
| C3, C3n | Neo4j-MCP, with and without examples |
| C4, C4w, C4p | Generic skill content as plain instructions; reworded; placebo text of the same length |
| C5, C6, C6n | Generic skill loaded by the harness; offered to the model (with and without examples) |
| C7, C7f, C7n | Domain skill offered to the model; loaded by the harness; offered without examples |
| C7t | Domain skill content as plain instructions |

The full design of each configuration is given in Table 6 of the paper.

## Requirements

- Python 3.11 (tested with 3.11.9) and the packages in `requirements.txt`
- Neo4j with the APOC plugin (the study used Neo4j Enterprise 2026.01.3 and APOC 2026.01.3); the study database
  must be named `qmsoriginal`
- Node.js (tested with v26.12.0) for the MCP server in `mcp-server/`
- API keys for Anthropic (Claude) and/or OpenAI (GPT)

```bash
python -m pip install -r requirements.txt
```

## Setup

1. **Database.** The study graph is `docs/backup.json` (an APOC JSON export of the graph as it was during the
   original runs: 170 nodes and 411 relationships). Restore it into a database named `qmsoriginal`:
   - add `apoc.import.file.enabled=true` to the DBMS's `conf/apoc.conf` and restart the DBMS;
   - copy `docs/backup.json` into the DBMS's import folder;
   - fill in the Neo4j connection in `.env` (step 4), then run

   ```bash
   python scripts/restore_original_db.py --check
   python scripts/restore_original_db.py
   ```

   The first command only checks that everything is ready; the second creates and fills the database and checks
   it against the JSON (counts, labels, relationship types and property keys). Creating a second database needs
   Neo4j Enterprise Edition (included in Neo4j Desktop). The harness only reads the database (read-only
   sessions).
2. **MCP server** (configurations C2–C7t). The server is in `mcp-server/` (see its README); install its packages
   with `npm ci` in that folder. The harness starts it itself.
3. **Generic skill** (C4–C6). The generic skill is the `neo4j-query` skill by Ori Nachum
   (https://github.com/OriNachum/autonomous-intelligence, MIT License; see `THIRD_PARTY_NOTICES.md`). It is not
   included here; download the version used in the study (commit `ee572176aca3`) to `skills/neo4j-query/SKILL.md`:

   ```bash
   mkdir -p skills/neo4j-query
   curl -L -o skills/neo4j-query/SKILL.md https://raw.githubusercontent.com/OriNachum/autonomous-intelligence/ee572176aca3b6a280a2276a14e6826f4cb9c9e0/qq/.agent/skills/neo4j-query/SKILL.md
   ```

   The file should have SHA-256 `f32083f1259e6123781918f5f361bac5e905420dc5a286fa68c44cfe1d03ab2e`. C4 and C4w use
   its text from `prompts/skill_body.txt` and `prompts/skill_body_reworded.txt`; C5 and C6 load the file.
4. **Settings.** Copy `.env.example` to `.env` and fill in the API keys and the Neo4j connection.

## Running

Check the plan first, then run (one episode at a time; finished episodes are skipped on restart):

```bash
python -m harness.run configurations --runs 5 --out runs/my_run --questions-file data/questions_v2.jsonl --dry-run
python -m harness.run configurations --runs 5 --out runs/my_run --questions-file data/questions_v2.jsonl
```

The harness refuses to start with uncommitted changes to tracked files, so that every record names the code that
produced it. Then score the run (each recorded query is rerun through the driver):

```bash
python -m scoring.rescore runs/my_run --questions-file data/questions_v2.jsonl
```

The main run used 5 runs of all 60 questions: 15 configurations with Claude Sonnet 4.6
(`claude-sonnet-4-6`) and 11 with GPT-5.4 (`gpt-5.4-2026-03-05`), 7,800 episodes in total.

## Reproducing the analysis

The paper's estimates, intervals and classifications can be reproduced from the published scores without running
any model:

```bash
python analysis/analysis_contrasts.py runs/main/runs_scored.csv --gpt gpt --out contrast_results.csv
```

The output should match `runs/main/contrast_results.csv`.

## Tests

Each test file runs on its own and prints PASS/FAIL per check:

```bash
python tests/test_config.py
```

`test_backends.py`, `test_skill_tools.py` and `test_validate.py` need the database (and the MCP server). The
others need neither; `test_models.py` and `test_gpt.py` use fake clients, so no API call is made.

## Licence

MIT License (see `LICENSE`), except third-party material: the generic skill text in `prompts/skill_body.txt` and `prompts/skill_body_reworded.txt` is derived
from the `neo4j-query` skill by Ori Nachum (https://github.com/OriNachum/autonomous-intelligence, MIT License); see
`THIRD_PARTY_NOTICES.md`.

## Citation

The paper is under review; its reference will be added here once it is published. Until then, please cite this
repository: Sangdean, T. (2026). *Text-to-Cypher on a quality-management knowledge graph: Graph RAG, Neo4j-MCP and
Agent Skills* [Computer software]. https://github.com/Thanyalak-San/text2cypher-qm-kg
