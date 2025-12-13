You are generating a changelog for a GitHub Release page.

Project: Supex - Modern SketchUp integration through Model Context Protocol (MCP).
Components: Python MCP driver (CLI + server), Ruby SketchUp extension (runtime), Ruby standard library.
Users: Developers integrating AI agents with SketchUp for 3D modeling and woodworking.

Task: Generate changelog for version {VERSION}
Commit range: {RANGE}

Explore the commits in the given range using git commands. Decide yourself how much detail you need - you can look at commit messages, full descriptions, or actual diffs if something is unclear.

Output format:
## What's New
- User-facing feature descriptions

## Improvements
- Enhancements to existing features

## Bug Fixes
- Fixed issues

Rules:
1. Only include user-facing changes (skip internal refactors, CI, docs unless significant)
2. Group similar changes together - when aggregating, include all relevant commit hashes
3. Write in past tense ("Added X" not "Add X")
4. Be concise - one line per change
5. Include commit hash(es) at the end of each item in parentheses, e.g.: "Added feature X (a1b2c3d, e4f5g6h)"
6. If a section would be empty, omit it entirely
7. Focus on WHAT changed for users, not HOW it was implemented

Output ONLY the changelog markdown, no explanations.
