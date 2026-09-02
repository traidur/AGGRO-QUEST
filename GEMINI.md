# Read CLAUDE.md

Always read and strictly follow the instructions and rules in `CLAUDE.md` before answering questions or working on tasks in this project, just as if they were your own native instructions.

# Native Tools Only
**File Operations:** Never use terminal commands (`cat`, `grep`, `ls`, `dir`, `Get-Content`, `Select-String`, or ad-hoc python/node scripts) for file operations, as they trigger permission prompts and block execution. Strictly use native tools (`view_file`, `grep_search`, `list_dir`, `replace_file_content`) or MCP tools for all file viewing and editing. Do not script your way around this boundary.

## Communication Rules
- Never write code blocks or modify project files on the first turn.
- Always propose a textual explanation or implementation plan first.
- Wait for explicit user confirmation before executing any actions.

# Cross-Agent Handoffs
When asked to update AI_HANDOFF.md, you MUST read its internal 'RULES - READ FIRST' section before making any edits. The handoff file is strictly for process/status and second opinions, NEVER for logging design decisions or rules. Always insert new entries at the top (reverse chronological) and prune aggressively.
