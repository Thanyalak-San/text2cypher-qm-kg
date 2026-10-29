"""The tools each configuration offers the model (guide, Appendix A), in the neutral format of
harness/models/base.py.

- Driver configurations (C0–C2): no tools; the query comes as a ```cypher block in the reply.
- MCP configurations: the query tool, with the one-line definition the published MCP and skill scripts
  sent (docs/audit.md, "Harness settings"); `validate_cypher` is not offered.
- Schema on request (C3r, C3rn; exploratory, added after the main run): also `get_schema`, which returns the
  configuration's schema text, the same text the other MCP configurations have in the prompt.
- A skill offered or loaded (C5, C6, C7): also `load_skill`. C5 needs it because the harness load is a
  tool call, and the API requires a tool to exist before a tool call can appear in the history.
- The domain skill (C7) also gets `read_skill_file` and `run_skill_script`, for the files and the
  validator script its instructions name.

The skill tools' descriptions are written once and used for both models.
"""

from __future__ import annotations

from harness.config import Config

QUERY_TOOL = {
    "name": "execute_cypher_query",
    "description": "Execute a Cypher query against the Neo4j concrete factory knowledge graph.",
    "parameters": {"type": "object",
                   "properties": {"query": {"type": "string", "description": "Cypher query to execute"}},
                   "required": ["query"]},
}
GET_SCHEMA_TOOL = {
    "name": "get_schema",
    "description": "Get the schema of the Neo4j concrete factory knowledge graph: node labels with their properties, and relationship types.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
LOAD_SKILL_TOOL = {
    "name": "load_skill",
    "description": "Load the full instructions of the skill listed under Available skill, using the name given there.",
    "parameters": {"type": "object",
                   "properties": {"name": {"type": "string", "description": "Name of the skill to load"}},
                   "required": ["name"]},
}
READ_FILE_TOOL = {
    "name": "read_skill_file",
    "description": "Read a file of the skill listed under Available skill, using the file name given in the skill's instructions.",
    "parameters": {"type": "object",
                   "properties": {"path": {"type": "string", "description": "Name of the file to read"}},
                   "required": ["path"]},
}
RUN_SCRIPT_TOOL = {
    "name": "run_skill_script",
    "description": ("Run a script of the skill listed under Available skill, using the script name given in the "
                    "skill's instructions. The input text is passed to the script, and its output is returned."),
    "parameters": {"type": "object",
                   "properties": {"script": {"type": "string", "description": "Name of the script to run"},
                                  "input": {"type": "string",
                                            "description": "Text passed to the script (for example, the query to check)"}},
                   "required": ["script", "input"]},
}
SKILL_FILES_OK = {"SKILL.md"}        # a skill folder with anything else gets the file and script tools


def skill_has_files(config: Config) -> bool:
    if config.skill is None:
        return False
    return any(f.is_file() and f.name not in SKILL_FILES_OK and "__pycache__" not in f.parts
               for f in config.skill.rglob("*"))


def tools_for(config: Config) -> list[dict]:
    if config.interface == "driver":
        return []
    tools = [QUERY_TOOL] + ([GET_SCHEMA_TOOL] if config.schema_delivery == "on_request" else [])
    tools += [LOAD_SKILL_TOOL] if config.skill is not None else []
    if skill_has_files(config):
        tools += [READ_FILE_TOOL, RUN_SCRIPT_TOOL]
    return tools
