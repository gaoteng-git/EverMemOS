# EverMemOS Skill - Usage Examples

This document provides detailed examples of using the EverMemOS skill in various real-world scenarios.

## Table of Contents

1. [Basic Operations](#basic-operations)
2. [Context-Aware Coding](#context-aware-coding)
3. [Bug Tracking & Resolution](#bug-tracking--resolution)
4. [Project Knowledge Management](#project-knowledge-management)
5. [Code Review with Memory](#code-review-with-memory)
6. [Team Collaboration](#team-collaboration)
7. [Advanced Patterns](#advanced-patterns)

---

## Basic Operations

### Example 1: Simple Search

**Scenario:** User asks about a past discussion

```
User: What did we talk about regarding the database migration?

Claude:
Let me search our conversation history...

[Executes: /evermemos search "database migration" hybrid 5]

Based on our previous discussions:

📁 Database Migration Discussion (2026-01-28)
  - We decided to use Alembic for schema migrations
  - Identified need for zero-downtime migration strategy
  - Discussed rolling back failed migrations safely

Would you like me to elaborate on any of these points?
```

---

### Example 2: Storing Information

**Scenario:** User wants to remember a decision

```
User: Remember that we're using PostgreSQL 15 with TimescaleDB extension for time-series data

Claude:
I'll store that for future reference.

[Executes: /evermemos store "Project uses PostgreSQL 15 with TimescaleDB extension for time-series data" user]

✅ Remembered! I've stored this information and will recall it when discussing:
- Database configuration
- Time-series data handling
- Performance optimization
```

---

### Example 3: Fetching Recent History

**Scenario:** User returns after a break

```
User: What were we working on earlier today?

Claude:
Let me check our recent conversation history...

[Executes: /evermemos recent 20]

📜 Today's work summary:

1. **Morning (09:00-11:00)**
   - Fixed ES sync bug by replacing async_streaming_bulk
   - Implemented raw ES client API workaround
   - Tested data synchronization across MongoDB/ES/Milvus

2. **Afternoon (14:00-16:00)**
   - Integrated EverMemOS with Claude Code
   - Created skill-based integration approach
   - Documented usage examples

We were just finishing the skill documentation. Ready to continue?
```

---

## Context-Aware Coding

### Example 4: Implementing Similar Features

**Scenario:** Building a feature similar to past work

```
User: I need to add a new API endpoint for user preferences

Claude:
Let me check our previous API implementations...

[Executes: /evermemos search "API endpoint implementation" hybrid 8]

Based on past work, here's the pattern we follow for this project:

1. **Controller Layer** (src/infra_layer/adapters/input/api/)
   - Use FastAPI with Pydantic models
   - Follow RESTful naming conventions
   - Return standardized JSON responses

2. **Service Layer** (src/application/services/)
   - Business logic validation
   - DI container integration

3. **Repository Layer** (src/infra_layer/adapters/out/persistence/)
   - MongoDB for primary storage
   - ES for search indexing
   - Milvus for vector storage

I'll implement the endpoint following these established patterns.

[After implementation]

[Executes: /evermemos store "Created user preferences API endpoint following project patterns: FastAPI controller, service layer validation, MongoDB persistence with ES/Milvus sync" assistant]
```

---

### Example 5: Learning from Past Mistakes

**Scenario:** Preventing known issues

```
User: I'm going to use elasticsearch's async_streaming_bulk for this sync operation

Claude:
⚠️ Wait! Let me check our history with that function...

[Executes: /evermemos search "async_streaming_bulk bug" hybrid 3]

I found an important issue we discovered previously:

⚠️ **Known Bug (2026-02-03)**:
- elasticsearch's async_streaming_bulk has a bug where it hangs after bulk operations complete
- The async for loop never exits despite successful HTTP requests
- Solution: Use raw es_client.bulk() API instead

Here's the working approach we developed:

```python
# Don't use this (hangs):
async for ok, info in async_streaming_bulk(client, actions):
    pass

# Use this instead (works):
body = [...]  # Build bulk request body
response = await es_client.bulk(body=body)
```

Would you like me to implement it using the working approach?
```

---

## Bug Tracking & Resolution

### Example 6: Documenting a Bug Discovery

**Scenario:** Discovering and fixing a new bug

```
User: The authentication token expires too quickly, users are getting logged out

Claude:
Let me help investigate this issue.

[After debugging]

Found the issue! The JWT token expiration is set to 15 minutes in config/auth.py:245, but the refresh logic only triggers after 20 minutes.

I'll fix this and document it.

[Executes: /evermemos store "Bug: JWT token expires after 15min but refresh triggers after 20min, causing premature logouts. Fix: Changed refresh trigger to 10min in frontend/auth.js:89" assistant]

✅ Bug fixed and documented. Future reference: config/auth.py:245
```

---

### Example 7: Tracking Related Issues

**Scenario:** New bug similar to previous one

```
User: Users can't upload files larger than 10MB

Claude:
Let me check if we've encountered similar issues...

[Executes: /evermemos search "file upload limit" hybrid 5]

I found a related issue we fixed before:

📁 Previous Upload Issue (2026-01-15)
  - Problem: Large file uploads timing out
  - Cause: Nginx proxy_timeout set to 60s
  - Solution: Increased to 300s in /etc/nginx/sites-available/app

For your current 10MB limit, this is likely a different setting. Let me check:

[Searches codebase]

Found it! The limit is in:
1. Backend: max_upload_size in config/app.py (currently 10MB)
2. Nginx: client_max_body_size (currently 10m)

Would you like me to increase both to support larger files?
```

---

## Project Knowledge Management

### Example 8: Onboarding to a New Module

**Scenario:** Working on unfamiliar code area

```
User: I need to modify the memory retrieval logic but I'm not familiar with it

Claude:
Let me gather the context from our previous work in this area...

[Executes: /evermemos search "memory retrieval" hybrid 10]
[Executes: /evermemos search "retrieval methods" hybrid 5]

Here's what I found from our past discussions:

📚 **Memory Retrieval System Overview**

1. **Architecture** (src/application/services/memory/)
   - `MemoryRetrievalService`: Main entry point
   - Supports 5 retrieval methods: keyword, vector, hybrid, rrf, agentic
   - Hybrid method is recommended default

2. **Storage Backends**
   - MongoDB: Primary storage, keyword search
   - Elasticsearch: Full-text search
   - Milvus: Vector similarity search

3. **Past Decisions**
   - We chose hybrid retrieval for balance of speed + accuracy
   - RRF (Reciprocal Rank Fusion) combines rankings from multiple methods
   - Vector search uses cosine similarity with threshold 0.7

4. **Known Issues**
   - ES async_streaming_bulk hangs (use raw API)
   - Milvus requires dense vectors (768 dims)

What specific changes do you need to make?
```

---

### Example 9: Design Pattern Reference

**Scenario:** Choosing implementation approach

```
User: How should I structure this new feature for real-time notifications?

Claude:
Let me check our architectural patterns and past decisions...

[Executes: /evermemos search "architecture pattern" hybrid 5]
[Executes: /evermemos search "real-time" hybrid 5]

Based on our project conventions:

📐 **Established Patterns**

1. **Layered Architecture** (we follow this consistently)
   - API Layer: FastAPI controllers
   - Application Layer: Service interfaces
   - Domain Layer: Business models
   - Infrastructure Layer: External adapters

2. **Real-time Communication** (from past websocket work)
   - Use FastAPI WebSocket support
   - Implement ConnectionManager pattern
   - Store connections in Redis for horizontal scaling

3. **Event Pattern** (from event logging system)
   - Event emitter in domain layer
   - Subscribers in infrastructure layer
   - Async event processing with queues

For notifications, I recommend:

```
api/notification_controller.py  → WebSocket endpoint
services/notification_service.py → Business logic
events/notification_emitter.py   → Event generation
adapters/notification_sender.py  → WebSocket delivery
```

This follows our established patterns. Shall I implement it?

[After implementation]

[Executes: /evermemos store "Real-time notifications implemented using WebSocket + event pattern. ConnectionManager in adapters layer, NotificationService in application layer. Follows layered architecture." assistant]
```

---

## Code Review with Memory

### Example 10: Reviewing with Historical Context

**Scenario:** Reviewing code changes

```
User: Can you review this pull request?

Claude:
Let me review the changes and check against our established patterns...

[Reads PR diff]
[Executes: /evermemos search "code review guidelines" hybrid 5]
[Executes: /evermemos search "security best practices" hybrid 5]

🔍 **Code Review Findings**

✅ **Good Practices** (aligns with our conventions):
- Follows layered architecture pattern
- Uses DI container for dependencies
- Includes unit tests with >80% coverage

⚠️ **Issues Found**:

1. **SQL Injection Risk** (line 145)
   ```python
   # Current (vulnerable):
   query = f"SELECT * FROM users WHERE id = {user_id}"

   # Should be (parameterized):
   query = "SELECT * FROM users WHERE id = ?"
   params = (user_id,)
   ```

   📝 **Reference**: We documented SQL injection prevention patterns on 2026-01-20

2. **Missing Error Handling** (line 203)
   No try-catch around external API call

   📝 **Reference**: Our error handling policy requires wrapping all external calls

3. **Performance Issue** (line 178)
   Loading all records into memory

   📝 **Reference**: Similar issue in PR #234, we fixed with pagination

Would you like me to suggest fixes for these issues?

[After review]

[Executes: /evermemos store "PR #456 review: Found SQL injection risk, missing error handling, and pagination issue. Follows architecture patterns but needs security fixes." assistant]
```

---

## Team Collaboration

### Example 11: Handoff Between Sessions

**Scenario:** Different team member continues work

```
User: I'm taking over the ES sync bug fix from my colleague

Claude:
Let me get you up to speed on that work...

[Executes: /evermemos search "ES sync bug" hybrid 10]
[Executes: /evermemos recent 30]

📋 **ES Sync Bug - Work Summary**

**Problem Identified** (2026-02-03):
- Backend exits after ES bulk insert
- async_streaming_bulk hangs indefinitely
- HTTP request succeeds but loop never exits

**Root Cause**:
- Bug in elasticsearch Python library's async helpers
- The async for loop over async_streaming_bulk doesn't complete

**Solution Implemented**:
- Replaced async_streaming_bulk with raw es_client.bulk() API
- Manual bulk body construction
- Manual response parsing

**Files Modified**:
- `src/core/validation/es_data_validator.py:441-497`

**Current Status**:
- ✅ Fix implemented and working
- ✅ Backend starts successfully
- ⏳ Pending: More testing with large datasets

**What's Left**:
1. Test with 10k+ document sync
2. Verify performance metrics
3. Update documentation

Ready to continue from here?
```

---

### Example 12: Cross-Project Learning

**Scenario:** Applying patterns from different projects

```
User: We're starting a new microservice. What patterns should we follow?

Claude:
Let me check best practices from our previous projects...

[Executes: /evermemos search "microservice architecture" hybrid 8]
[Executes: /evermemos search "project setup patterns" hybrid 8]

📚 **Microservice Patterns from Past Projects**

**From Project Alpha** (2025-12):
- ✅ Use API gateway for routing
- ✅ Service discovery with Consul
- ✅ Circuit breaker pattern for resilience

**From EverMemOS Project** (current):
- ✅ Layered architecture (API → Application → Domain → Infrastructure)
- ✅ DI container for loose coupling
- ✅ Dual storage (MongoDB + ES + Milvus)

**From Project Beta** (2026-01):
- ✅ Health check endpoints at /health
- ✅ Structured logging with correlation IDs
- ✅ OpenAPI/Swagger documentation

**Recommended Stack** (based on our successes):
- Framework: FastAPI (proven in EverMemOS)
- Database: PostgreSQL with async driver
- Cache: Redis for session/temp data
- Message Queue: RabbitMQ for async tasks
- Monitoring: Prometheus + Grafana

Would you like me to generate a project template following these patterns?
```

---

## Advanced Patterns

### Example 13: Multi-Step Investigation

**Scenario:** Complex debugging requiring historical context

```
User: The memory search is returning irrelevant results

Claude:
Let me investigate this systematically using our historical context...

**Step 1**: Check retrieval method being used

[Executes: /evermemos search "retrieval method configuration" hybrid 5]

Found: We default to `hybrid` method which combines keyword + vector search.

**Step 2**: Check past issues with search quality

[Executes: /evermemos search "search quality issue" hybrid 5]
[Executes: /evermemos search "irrelevant results" hybrid 5]

Found: Similar issue on 2026-01-25
- Cause: Vector embeddings not properly normalized
- Fix: Added L2 normalization in embedding generation

**Step 3**: Check current vector configuration

[Reads code: src/infra_layer/adapters/out/vector/embedder.py]

❌ Found the issue!

The L2 normalization we added in January is commented out (line 87):
```python
# embedding = embedding / np.linalg.norm(embedding)  # TODO: causing errors
```

Someone commented it out during debugging but never re-enabled it!

**Step 4**: Verify this is the cause

Let me check the TODO reference...

[Executes: /evermemos search "normalization error" hybrid 3]

Found: There was a NaN error when vectors had zero magnitude. The proper fix is:

```python
norm = np.linalg.norm(embedding)
if norm > 0:
    embedding = embedding / norm
else:
    embedding = np.zeros_like(embedding)
```

Should I apply this fix?

[After fix]

[Executes: /evermemos store "Fixed vector search quality issue: Re-enabled L2 normalization with zero-check to prevent NaN errors. This was accidentally commented out causing irrelevant search results." assistant]
```

---

### Example 14: Predictive Assistance

**Scenario:** Anticipating needs based on context

```
User: I'm about to deploy the new API changes to production

Claude:
Before you deploy, let me check our deployment checklist from previous releases...

[Executes: /evermemos search "production deployment" hybrid 5]
[Executes: /evermemos search "deployment issues" hybrid 5]

⚠️ **Pre-Deployment Checklist** (from past experience):

✅ **Required Steps** (we learned these the hard way):

1. **Database Migrations** ⚠️
   - Run: `alembic upgrade head`
   - Test rollback: `alembic downgrade -1 && alembic upgrade head`
   - Past issue (2026-01-10): Forgot migration, caused 500 errors

2. **Environment Variables** ⚠️
   - Verify all new env vars in `.env.production`
   - Past issue (2025-12-15): Missing API_KEY caused auth failures

3. **Dependencies** ✅
   - Run: `pip freeze > requirements.txt`
   - Check for security vulnerabilities: `pip-audit`

4. **Tests** ⚠️
   - Run full test suite: `pytest`
   - Load test critical endpoints
   - Past issue (2026-01-28): Didn't load test, deployment crashed under load

5. **Rollback Plan** ⚠️
   - Tag current release: `git tag v1.2.3`
   - Document rollback steps
   - Past issue (2025-12-20): No rollback plan, 4-hour downtime

6. **Monitoring** ✅
   - Set up alerts for error rates
   - Monitor logs in real-time during deployment

Have you completed all these checks?

[After deployment]

[Executes: /evermemos store "Production deployment v1.3.0 successful. New API endpoints deployed. Followed full pre-deployment checklist. No issues encountered." assistant]
```

---

### Example 15: Pattern Evolution Tracking

**Scenario:** Documenting architecture evolution

```
User: Why do we use Milvus instead of just Elasticsearch for vector search?

Claude:
Great question! Let me trace our architectural evolution...

[Executes: /evermemos search "vector search implementation" hybrid 8]
[Executes: /evermemos search "Milvus decision" hybrid 5]
[Executes: /evermemos search "Elasticsearch vector" hybrid 5]

📜 **Vector Search Architecture Evolution**

**Phase 1: Elasticsearch Only** (2025-11)
- Used ES vector search (kNN)
- Simple setup, single backend
- ❌ Problem: Slow for large datasets (>100k docs)
- ❌ Problem: High memory usage

**Phase 2: Evaluation Period** (2025-12)
- Tested Milvus, Pinecone, Weaviate
- Benchmarked performance:
  - ES: ~500ms for 100k docs
  - Milvus: ~50ms for 100k docs
  - Milvus: 10x faster! 🚀

**Phase 3: Dual Storage** (2026-01 - current)
- ES for keyword/full-text search
- Milvus for vector similarity
- Hybrid retrieval combines both
- ✅ Best of both worlds

**Decision Factors**:
1. **Performance**: Milvus 10x faster
2. **Scalability**: Milvus handles billions of vectors
3. **Specialization**: Purpose-built for vector search
4. **Cost**: Milvus more memory efficient

**Trade-offs**:
- ❌ More complex (two systems to maintain)
- ✅ But worth it for performance gains

So we use:
- **Milvus**: Vector similarity (semantic search)
- **Elasticsearch**: Keyword matching (exact terms)
- **Hybrid**: Combines rankings from both

This architecture gives us the speed of Milvus with the flexibility of ES.
```

---

## Tips for Effective Memory Usage

### 1. Be Specific in Searches
```bash
❌ Bad:  /evermemos search "error"
✅ Good: /evermemos search "authentication error token expiration"
```

### 2. Store Context, Not Just Facts
```bash
❌ Bad:  "Bug fixed"
✅ Good: "Fixed authentication bug where JWT token expiration (15min) didn't align with refresh trigger (20min). Solution: Changed refresh to 10min in auth.js:89"
```

### 3. Use Appropriate Retrieval Methods
```bash
# Conceptual questions → vector/hybrid
/evermemos search "how does authentication work" hybrid

# Exact terms → keyword
/evermemos search "async_streaming_bulk" keyword

# Best of both → hybrid (default)
/evermemos search "database migration strategy" hybrid
```

### 4. Tag Important Information
```bash
# Include keywords for future findability
/evermemos store "IMPORTANT: async_streaming_bulk has bug, use raw es_client.bulk() API instead. elasticsearch library issue." assistant
```

### 5. Regular Context Refresh
```bash
# At start of session
/evermemos recent 20

# Before major changes
/evermemos search "similar feature name" hybrid 10
```

---

## Conclusion

The EverMemOS skill transforms Claude Code into a context-aware assistant that learns from every interaction. By automatically searching for relevant context and storing important information, it ensures continuity across sessions and helps avoid repeating past mistakes.

For more details, see the main [SKILL.md](SKILL.md) documentation.
