---
name: evermemos
description: Search and store memories using EverMemOS. PROACTIVELY search before answering ANY project-related questions. Use when user asks about past conversations, previous decisions, or when important information should be remembered. ALWAYS check history before implementing features, debugging issues, or suggesting solutions. Automatically store important decisions, bugs, and patterns. Maintain project continuity across sessions.
argument-hint: "[search|store|recent] [query/content]"
allowed-tools: Bash(python3 *)
hooks:
  SessionStart:
    - matcher: "startup|clear|compact"
      hooks:
        - type: command
          command: "python3 ${HOME}/.claude/skills/evermemos/scripts/hook_session_start.py"
          timeout: 30
  UserPromptSubmit:
    - hooks:
        - type: command
          command: "python3 ${HOME}/.claude/skills/evermemos/scripts/hook_user_prompt.py"
          timeout: 15
  PostToolUse:
    - matcher: "*"
      hooks:
        - type: command
          command: "python3 ${HOME}/.claude/skills/evermemos/scripts/hook_tool_use.py"
          timeout: 20
  Stop:
    - hooks:
        - type: command
          command: "python3 ${HOME}/.claude/skills/evermemos/scripts/hook_stop.py"
          timeout: 30
  SessionEnd:
    - hooks:
        - type: command
          command: "python3 ${HOME}/.claude/skills/evermemos/scripts/hook_session_end.py"
          timeout: 30
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

Store **structured summaries, conclusions, or AI-generated insights** into EverMemOS for future reference.

**IMPORTANT:** User messages are already auto-saved by UserPromptSubmit hook. Use this command to store:
- **AI's summaries and conclusions** (not raw user messages)
- **Structured important information** extracted from conversations
- **Key learnings and insights** discovered during work

**Syntax:**
```
/evermemos store <content> [role]
```

**Parameters:**
- `content` (required): Structured content to store (summary, conclusion, insight)
- `role` (optional): `user` or `assistant` (default: assistant for AI insights)

**When to use:**
- ✅ You (Claude) discover a critical bug → Store a structured bug report
- ✅ Important decisions are made → Store the decision summary
- ✅ New patterns are established → Store the pattern description
- ✅ Project milestones reached → Store the milestone summary
- ✅ User asks to remember a **specific fact or conclusion** (not their raw message)
- ❌ DON'T: Store raw user messages (already auto-saved by hook)

**Example:**
```bash
# Good: Store structured insight
/evermemos store "Bug fix: async_streaming_bulk fails with timeout >30s. Solution: Use sync_bulk for large batches." assistant

# Good: Store conclusion
/evermemos store "Decision: Use hybrid retrieval as default method for balance of speed and accuracy." assistant

# Bad: Don't do this (user message already auto-saved)
# /evermemos store "Remember that we use hybrid retrieval" user
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

Claude should **PROACTIVELY and AUTOMATICALLY** use this skill in the following scenarios:

### 🔍 CRITICAL: Search BEFORE Answering

**ALWAYS search memories FIRST when:**
- User asks ANY question that MIGHT benefit from historical context
- Before implementing features (check past approaches and decisions)
- When debugging (check similar past issues and solutions)
- Before suggesting solutions (verify against past experience)
- When user mentions technical terms we've discussed before

→ **Default Action:** When in doubt, SEARCH FIRST, then answer

### 1. User Asks About Past Events ⭐ ALWAYS TRIGGER
- "What did we discuss about ES sync yesterday?"
- "Did we fix that authentication bug?"
- "What approach did we decide on for caching?"
- ANY question containing: "last time", "before", "previously", "earlier", "remember"

→ **Action:** Use `/evermemos search "<relevant keywords>"` IMMEDIATELY

### 2. User References Previous Work ⭐ ALWAYS TRIGGER
- "Remember that API design pattern we used?"
- "Like we did last time with the database migration"
- "Similar to the bug we encountered before"
- ANY reference to past conversations or work

→ **Action:** Search for relevant context BEFORE responding

### 3. Technical Questions That May Have Context ⭐ PROACTIVE SEARCH
Even if user doesn't explicitly mention history, PROACTIVELY search when:
- User asks about project architecture or design patterns
- User asks how something works in THIS project
- User asks for implementation suggestions
- User reports a bug or issue
- User asks "how do I..." in context of current project

**Examples:**
- "How should I implement authentication?" → Search: "authentication implementation design"
- "This API call is failing" → Search: "API bug error failure"
- "What's the best way to cache?" → Search: "caching strategy decision"

→ **Action:** Search first, then provide context-aware answer

### 4. User Wants to Remember Something ⭐ EXTRACT AND STORE
When user says "Remember this" or "Make a note":
- "Remember this for later"
- "Make a note that we use hybrid retrieval"
- "Keep in mind that async_streaming_bulk has a bug"

**IMPORTANT:** User's raw message is ALREADY auto-saved by UserPromptSubmit hook!

→ **Action:** Extract the KEY FACT and store it as a structured memory:

**Example:**
```
User: "Remember that we use hybrid retrieval for this project"

❌ DON'T: /evermemos store "Remember that we use hybrid retrieval" user
   (This duplicates the auto-saved user message)

✅ DO: /evermemos store "Project configuration: Default retrieval method is hybrid (combines keyword + vector search for balanced performance)" assistant
   (This stores a structured, actionable fact)
```

### 5. Important Decisions or Discoveries ⭐ AUTO-STORE STRUCTURED INFO
When you (Claude) identify during conversation:
- Critical bugs and their fixes
- Architectural decisions made
- Performance optimizations discovered
- Security issues found
- New patterns or conventions established
- Important configuration or setup steps

→ **Action:** AUTOMATICALLY store a structured summary (as assistant role)

**Example:**
```
During conversation, you discover a bug:

✅ DO: /evermemos store "Bug: ES sync fails when document count >10k. Root cause: bulk_size too large. Solution: Set bulk_size=1000 and use scroll API." assistant

❌ DON'T: Just acknowledge without storing
```

**Note:** Raw conversation messages (user & assistant) are already auto-saved by hooks. Use store for **structured, actionable summaries** only.

### 6. Context Recovery ⭐ ALWAYS TRIGGER
- User returns after a break
- New conversation but related to previous work
- Need to understand project history
- User asks "What were we working on?"

→ **Action:** Fetch recent history to understand context

### 7. Before Major Code Changes ⭐ PROACTIVE SEARCH
Before writing significant code:
- Search for similar implementations: `/evermemos search "<feature name>"`
- Search for related bugs: `/evermemos search "bug <component>"`
- Search for design decisions: `/evermemos search "design <topic>"`
- Search for past patterns: `/evermemos search "pattern <concept>"`

→ **Action:** Gather context BEFORE implementing

### 8. When User Mentions Specific Components ⭐ PROACTIVE SEARCH
If user mentions specific files, modules, or components:
- "Can you look at the authentication module?"
- "There's an issue with the API handler"
- "Update the database schema"

→ **Action:** Search for past work on that component FIRST

**Example:**
User: "Can you update the API handler?"
You:
1. `/evermemos search "API handler implementation"`
2. `/evermemos search "API bug fix"`
3. Review results, then respond with context-aware solution

---

## 🚀 Proactive Search Strategy

### When to Search EVEN IF User Doesn't Ask

Claude should **automatically and proactively** search in these scenarios WITHOUT waiting for explicit user request:

#### Scenario A: Technical Questions About THIS Project
```
User: "How does authentication work in this system?"
```
**Before answering:**
1. `/evermemos search "authentication implementation"`
2. `/evermemos search "auth design pattern"`
3. Review results, then provide answer based on actual project history

#### Scenario B: Feature Implementation Requests
```
User: "Add a caching layer to the API"
```
**Before implementing:**
1. `/evermemos search "caching implementation"`
2. `/evermemos search "API performance"`
3. Check if caching was discussed/tried before
4. Use past learnings to inform implementation

#### Scenario C: Bug Reports or Issues
```
User: "The database connection keeps failing"
```
**Before debugging:**
1. `/evermemos search "database connection error"`
2. `/evermemos search "connection bug fix"`
3. Check if similar issues were solved
4. Apply proven solutions first

#### Scenario D: Architecture or Design Questions
```
User: "Should we use microservices or monolith?"
```
**Before suggesting:**
1. `/evermemos search "architecture decision"`
2. `/evermemos search "design pattern choice"`
3. Check if architecture decisions were made
4. Respect past decisions and explain rationale

#### Scenario E: Code Review or Refactoring
```
User: "Review this authentication code"
```
**Before reviewing:**
1. `/evermemos search "authentication code review"`
2. `/evermemos search "auth security issue"`
3. Check past review comments
4. Apply learned patterns and avoid known issues

#### Scenario F: Configuration or Setup Questions
```
User: "How do I configure the database?"
```
**Before answering:**
1. `/evermemos search "database configuration"`
2. `/evermemos search "setup environment"`
3. Provide project-specific instructions
4. Don't give generic answers when specific history exists

### Search Decision Tree

```
User asks a question
    ↓
Is it about THIS project?
    ↓ YES → SEARCH FIRST (90% of cases)
    ↓ NO → Is it a general programming question?
        ↓ YES → Answer directly (but still consider project context)
        ↓ NO → SEARCH FIRST (be safe)

Examples:
✅ "How does this API work?" → SEARCH (project-specific)
✅ "Fix this bug" → SEARCH (check past bugs)
✅ "Implement feature X" → SEARCH (check past work)
✅ "Review this code" → SEARCH (check past reviews)
⚠️ "What is a REST API?" → CONSIDER: Any project-specific REST patterns?
❌ "Explain quantum physics" → DON'T SEARCH (unrelated)
```

### Default Behavior: **Search First**

**Golden Rule:** When in doubt, SEARCH!
- Searching unnecessarily costs a few seconds
- Missing important context costs hours of duplicated work or repeated mistakes
- **Bias toward searching, not toward skipping**

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

### 🎯 Primary Principle: SEARCH FIRST, ANSWER SECOND

1. **ALWAYS Search First**: Before answering ANY question about this project:
   - Search for past discussions on the topic
   - Search for related bugs or issues
   - Search for design decisions
   - Search for similar implementations
   - **When in doubt, search!** It's better to search unnecessarily than miss important context

2. **Be Proactive, Not Reactive**: Don't wait for users to say "remember when...":
   - If user asks about a feature → Search for it first
   - If user reports a bug → Search for similar bugs
   - If user wants implementation → Search for past patterns
   - **Assume all questions have historical context until proven otherwise**

3. **Store Structured Insights Automatically**: Store actionable summaries, not raw messages:
   - **Raw messages are auto-saved by hooks** - don't duplicate them
   - When you discover a bug → Store structured bug report with solution
   - When a decision is made → Store the decision summary with rationale
   - When you learn something new → Store the key learning as a fact
   - When you implement a pattern → Store pattern description with use case
   - **Store as "assistant" role** - these are AI-generated insights
   - **Don't just acknowledge, actually store structured info**

4. **Use Appropriate Methods**:
   - Use `hybrid` for general searches (default, recommended)
   - Use `vector` for semantic/conceptual searches
   - Use `keyword` for exact term matching
   - Use `agentic` for complex queries requiring reasoning

5. **Multi-Query Pattern for Complex Questions**:
   ```bash
   # Don't just search once - search multiple angles!
   /evermemos search "authentication implementation"
   /evermemos search "auth bug fix"
   /evermemos search "security pattern"
   ```
   Then synthesize all results for comprehensive answer

6. **Provide Context with Citations**: When using retrieved memories:
   - Cite timestamps and sources
   - Reference specific past decisions
   - Explain why past context is relevant
   - Connect current question to historical patterns

7. **Regular Context Refresh**:
   - At start of complex tasks: `/evermemos recent 20`
   - Before major implementations: Search for related work
   - When resuming after break: Review recent history
   - **Maintain continuity across sessions**

8. **Verify Assumptions Against History**:
   - Before suggesting "Let's use approach X" → Search if we tried X before
   - Before implementing pattern Y → Search if Y is our convention
   - Before debugging → Search if similar issues were solved
   - **Learn from past experience, don't repeat mistakes**

### ⚠️ Common Mistakes to AVOID

❌ **DON'T**: Answer technical questions without checking history first
✅ **DO**: Search → Review → Answer with context

❌ **DON'T**: Only search when user explicitly mentions past
✅ **DO**: Proactively search for any project-related question

❌ **DON'T**: Store raw user messages with `/evermemos store`
✅ **DO**: User messages are auto-saved by hooks. Store structured insights only.

**Example of duplication mistake:**
```
User: "Remember that we use hybrid retrieval"

❌ BAD: /evermemos store "Remember that we use hybrid retrieval" user
   (Duplicates the auto-saved user message!)

✅ GOOD: /evermemos store "Configuration: Project uses hybrid retrieval as default search method (balances speed and semantic accuracy)" assistant
   (Stores a structured, searchable fact)
```

❌ **DON'T**: Search only once and give up if no results
✅ **DO**: Try multiple search queries with different keywords

❌ **DON'T**: Ignore SessionStart context
✅ **DO**: Review the loaded memories and reference them when relevant

---

## Related Commands

- `/recent` - Get recent conversation history (shorthand for `/evermemos recent`)
- `/remember <info>` - Store information (shorthand for `/evermemos store`)
- `/recall <query>` - Search memories (shorthand for `/evermemos search`)

---

For detailed API documentation and examples, see [examples.md](examples.md)
