---
name: evermemos
description: Search and store memories using EverMemOS. Use when user asks about past conversations, previous decisions, or when important information should be remembered. Also use to recall project context and historical knowledge.
argument-hint: "[search|store|recent] [query/content]"
allowed-tools: Bash(python3 *)
---

# EverMemOS Memory Integration

This skill enables Claude Code to use EverMemOS as a persistent memory backend, allowing you to search past conversations, store important information, and fetch recent history.

## Available Commands

### 🔍 Search Memories

Search for relevant memories based on a query. Use this to recall past conversations, decisions, bugs, or any historical context.

**Syntax:**
```
/evermemos search <query> [method] [top_k]
```

**Parameters:**
- `query` (required): Search query text
- `method` (optional): Retrieval method - `keyword`, `vector`, `hybrid` (default), `rrf`, or `agentic`
- `top_k` (optional): Maximum results to return (default: 5)

**When to use:**
- User asks "What did we discuss about X?"
- User references past work: "Remember that bug we fixed?"
- Need project context before implementing features
- Recall past decisions or approaches

**Example:**
```bash
python3 ~/.claude/skills/evermemos/scripts/evermemos_client.py search "$ARGUMENTS[1]" "${2:-hybrid}" "${3:-5}"
```

---

### 💾 Store Memory

Store important information from the current conversation into EverMemOS for future reference.

**Syntax:**
```
/evermemos store <content> [role]
```

**Parameters:**
- `content` (required): Message content to store
- `role` (optional): `user` or `assistant` (default: user)

**When to use:**
- User explicitly says "Remember this:"
- Important decisions are made
- Bugs are discovered and documented
- New patterns or conventions are established
- Project milestones are reached

**Example:**
```bash
python3 ~/.claude/skills/evermemos/scripts/evermemos_client.py store "$ARGUMENTS[1]" "${2:-user}"
```

---

### 📜 Recent History

Fetch recent conversation history from EverMemOS to understand current context.

**Syntax:**
```
/evermemos recent [limit]
```

**Parameters:**
- `limit` (optional): Number of recent memories to fetch (default: 10)

**When to use:**
- User asks "What were we working on?"
- Need to recap recent activities
- Resuming work after a break
- Understanding conversation flow

**Example:**
```bash
python3 ~/.claude/skills/evermemos/scripts/evermemos_client.py recent "${1:-10}"
```

---

## Automatic Usage Guidelines

Claude should **automatically** use this skill in the following scenarios:

### 1. User Asks About Past Events
- "What did we discuss about ES sync yesterday?"
- "Did we fix that authentication bug?"
- "What approach did we decide on for caching?"

→ **Action:** Use `/evermemos search "<relevant keywords>"`

### 2. User References Previous Work
- "Remember that API design pattern we used?"
- "Like we did last time with the database migration"
- "Similar to the bug we encountered before"

→ **Action:** Search for relevant context before responding

### 3. User Wants to Remember Something
- "Remember this for later"
- "Make a note that we use hybrid retrieval"
- "Keep in mind that async_streaming_bulk has a bug"

→ **Action:** Use `/evermemos store "<content>" "user"`

### 4. Important Decisions or Discoveries
When you (Claude) identify:
- Critical bugs and their fixes
- Architectural decisions
- Performance optimizations
- Security issues
- New patterns or conventions

→ **Action:** Store the information for future reference

### 5. Context Recovery
- User returns after a break
- New conversation but related to previous work
- Need to understand project history

→ **Action:** Fetch recent history to understand context

---

## Configuration

The skill uses environment variables (can be set in Claude Code settings or shell):

```bash
export EVERMEMOS_BASE_URL="http://localhost:1995"      # API endpoint
export EVERMEMOS_USER_ID="claude_code_user"            # User identifier
export EVERMEMOS_GROUP_ID="session_2026"               # Session/project identifier
```

---

## Usage Examples

### Example 1: Search for Past Discussions

User: "What did we discuss about the ES sync bug?"

```bash
/evermemos search "ES sync bug" hybrid 5
```

Claude will:
1. Execute the search command
2. Parse the results
3. Summarize relevant past conversations
4. Provide context-aware response

---

### Example 2: Store Important Information

User: "Remember that we're using hybrid retrieval for this project"

```bash
/evermemos store "Project uses hybrid retrieval method for memory search" user
```

Claude confirms the information is stored for future reference.

---

### Example 3: Fetch Recent Context

User: "What were we working on earlier?"

```bash
/evermemos recent 15
```

Claude will:
1. Fetch the last 15 memories
2. Analyze the conversation flow
3. Summarize recent activities and tasks

---

### Example 4: Context-Aware Bug Fix

User: "There's a similar bug in the authentication module"

Claude should:
1. **Search:** `/evermemos search "authentication bug" hybrid 5`
2. Recall previous similar bugs and fixes
3. Apply learned patterns to the new issue
4. **Store:** Save the new bug and fix for future reference

---

### Example 5: Project Onboarding

User: "What's the architecture of this project?"

Claude should:
1. **Search:** `/evermemos search "architecture design patterns" hybrid 10`
2. **Search:** `/evermemos search "project structure" hybrid 10`
3. Synthesize information from past discussions
4. Provide comprehensive overview

---

## Workflow Integration

### Before Implementing Features
1. Search for related past work: `/evermemos search "<feature name>"`
2. Check for previous decisions: `/evermemos search "design decision <topic>"`
3. Look for known issues: `/evermemos search "bug <related area>"`

### After Completing Work
1. Store important decisions made
2. Document bugs discovered and fixed
3. Record new patterns or approaches used

### During Code Review
1. Search for related past reviews
2. Check for known issues in similar code
3. Apply lessons from previous feedback

---

## Technical Details

### Memory Types
- `episodic_memory`: Conversation messages and interactions
- `event_log`: System events and actions
- `foresight`: Future plans and predictions

### Retrieval Methods
- `keyword`: Traditional text search (fast, exact matches)
- `vector`: Semantic similarity search (understands meaning)
- `hybrid`: Combines keyword + vector (balanced, recommended)
- `rrf`: Reciprocal Rank Fusion (advanced ranking)
- `agentic`: AI-powered intelligent retrieval

---

## Troubleshooting

### Connection Issues
If you see "Connection Error", check:
1. EverMemOS backend is running: `curl http://localhost:1995`
2. Correct `EVERMEMOS_BASE_URL` is set
3. Network/firewall settings

### No Results Found
- Try different search terms
- Use `hybrid` or `vector` method for semantic search
- Increase `top_k` to get more results
- Verify data exists for the current `user_id` and `group_id`

### Permission Errors
- Ensure the Python script is executable: `chmod +x ~/.claude/skills/evermemos/scripts/evermemos_client.py`
- Check Python 3 is installed: `python3 --version`

---

## Advanced Usage

### Multi-Query Search Pattern

For complex questions, perform multiple searches:

```bash
# Search for feature
/evermemos search "user authentication" hybrid 5

# Search for related bugs
/evermemos search "auth bug fix" hybrid 5

# Search for design decisions
/evermemos search "auth design pattern" hybrid 5
```

Then synthesize all results to provide comprehensive answer.

---

### Session-Specific Groups

Change `GROUP_ID` to organize memories by project or session:

```bash
export EVERMEMOS_GROUP_ID="project_alpha"     # For project Alpha
export EVERMEMOS_GROUP_ID="bugfix_session"    # For bug fixing session
export EVERMEMOS_GROUP_ID="feature_dev"       # For feature development
```

This allows context isolation between different work streams.

---

## Best Practices

1. **Search First**: Before answering questions about past work, always search memories
2. **Store Important Info**: Don't just acknowledge user requests to remember - actually store them
3. **Use Appropriate Methods**:
   - Use `hybrid` for general searches (default)
   - Use `vector` for semantic/conceptual searches
   - Use `keyword` for exact term matching
4. **Provide Context**: When using retrieved memories, cite timestamps and sources
5. **Regular Recall**: Periodically search for project context to maintain continuity

---

## Related Commands

- `/recent` - Get recent conversation history (shorthand for `/evermemos recent`)
- `/remember <info>` - Store information (shorthand for `/evermemos store`)
- `/recall <query>` - Search memories (shorthand for `/evermemos search`)

---

For detailed API documentation and examples, see [examples.md](examples.md)
