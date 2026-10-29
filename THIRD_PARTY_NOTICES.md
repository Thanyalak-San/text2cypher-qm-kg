# Third-party notices

## neo4j-query skill (Ori Nachum)

The generic skill used in configurations C4, C4w, C5 and C6 is the `neo4j-query` skill from

- Repository: https://github.com/OriNachum/autonomous-intelligence
- Path: `qq/.agent/skills/neo4j-query/SKILL.md`
- Version: downloaded on 12 February 2026; the file's latest commit at that date is `ee572176aca3b6a280a2276a14e6826f4cb9c9e0` (5 February 2026); the file at that commit is byte-identical to the copy used
- SHA-256 of the downloaded `SKILL.md`: `f32083f1259e6123781918f5f361bac5e905420dc5a286fa68c44cfe1d03ab2e`

Files in this repository derived from it:

| File | Used by | Relation to the original |
|---|---|---|
| `prompts/skill_body.txt` | C4 | The body of `SKILL.md` without its YAML header, unchanged |
| `prompts/skill_body_reworded.txt` | C4w | The same content reworded and reordered for the wording control (headings, order of sections and queries, and prose changed; all content kept) |

Both files keep the skill's own default connection details (including the password `refinerypass`, for the skill
author's Docker container); they are not credentials for this study's database.

The skill is distributed under the MIT License:

```
MIT License

Copyright (c) 2025 Ori Nachum

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
