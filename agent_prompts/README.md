# Agent Prompts - Multi-Agent Orchestration

This directory contains ready-to-copy-paste prompts for running multiple Claude Code agents concurrently on QuizWeaver.

## Quick Start

### Option 1: Launch All 4 Agents (Maximum Parallelization)
1. Open 4 separate Claude Code sessions
2. In Session 1: Copy-paste **agent_a_testing_docs.txt**
3. In Session 2: Copy-paste **agent_b_web_ui.txt**
4. In Session 3: Copy-paste **agent_c_agent_polish.txt**
5. In Session 4: Copy-paste **agent_d_demo_prep.txt**

All agents will work concurrently with minimal conflicts.

### Option 2: Launch 2 Agents (Recommended for Workshop)
Best for time-constrained scenarios:

**Session 1: Testing Polish** (30-60 min)
- Copy-paste **agent_a_testing_docs.txt**
- Adds edge case tests, updates documentation

**Session 2: Demo Prep** (30-60 min)
- Copy-paste **agent_d_demo_prep.txt**
- Creates demo materials for workshop presentation

These won't conflict (different file areas).

## Agent Overview

| Agent | Focus Area | Files Modified | Conflicts With | Time Estimate |
|-------|------------|----------------|----------------|---------------|
| **Agent A** | Testing & Docs | tests/*, docs/*, README.md | Low conflict | 2-3 hours |
| **Agent B** | Web UI | app/*, templates/*, static/* | Low conflict | 3-4 hours |
| **Agent C** | Agent Logic | src/agents.py, src/cost_tracking.py | Medium conflict with A | 2-3 hours |
| **Agent D** | Demo Content | demo_data/*, *.md files | No conflicts | 2-3 hours |

## Conflict Risk Matrix

```
         A (Testing)  B (Web UI)  C (Agent)  D (Demo)
A (Testing)    -        Low        Medium     Low
B (Web UI)    Low        -         Low        Low
C (Agent)    Medium     Low         -         Low
D (Demo)      Low       Low        Low         -
```

**Low conflict**: Agents work on different files
**Medium conflict**: Agents may touch same files (coordinate commits)

## Coordination Strategy

### Before Starting
Each agent should:
```bash
git pull
git log --oneline -20  # See what others did
python -m pytest       # Verify tests pass
```

### During Work
- **Commit frequently**: After each task (not after all tasks)
- **Pull before push**: Always `git pull` before `git push`
- **Check for conflicts**: `git status` before committing

### Create PROGRESS.md
Create a shared progress tracker:

```markdown
# Multi-Agent Progress Tracker

## Agent A (Testing & Docs)
- [x] Run full test suite (202 tests pass)
- [ ] Add edge case tests
Last updated: 2026-02-06 15:00 UTC

## Agent B (Web UI)
- [ ] Quiz generation page
Last updated: 2026-02-06 15:10 UTC

## Agent C (Agent Polish)
- [ ] Verify lesson context
Last updated: 2026-02-06 15:05 UTC

## Agent D (Demo)
- [x] Created demo_data/
Last updated: 2026-02-06 15:15 UTC
```

## File Ownership

### Agent A Owns
- `tests/*` (new test files)
- `docs/*`
- `README.md`

### Agent B Owns
- `app/*`
- `templates/*`
- `static/*`
- `tests/test_app*.py`

### Agent C Owns
- `src/agents.py`
- `src/cost_tracking.py`
- `prompts/*.txt`
- `tests/test_agents.py`
- `tests/test_cost_tracking.py`

### Agent D Owns
- `demo_data/*`
- `demo_script.md`
- `workshop_slides.md`
- `docs/DEMO.md`

### Shared (Coordinate Before Changing)
- `main.py` (CLI routing - all agents read, coordinate before modifying)
- `config.yaml` (read-only for most agents)
- `src/database.py` (stable, avoid changes)

## Example Workflow (2 Agents)

### Scenario: Testing + Demo (Recommended)

**Agent A Session:**
```bash
# Terminal 1
git pull
python -m pytest -v > test_results.txt
# Copy-paste agent_a_testing_docs.txt
# Agent starts working on tests and docs
```

**Agent D Session:**
```bash
# Terminal 2
git pull
python main.py list-classes
# Copy-paste agent_d_demo_prep.txt
# Agent starts creating demo materials
```

**Expected Timeline:**
- 0:00 - Both agents start (git pull)
- 0:15 - Agent A commits first test improvement
- 0:30 - Agent D commits demo_script.md
- 0:45 - Agent A commits documentation update
- 1:00 - Agent D commits sample data
- 1:30 - Both agents done, workshop ready!

## Troubleshooting

### Merge Conflict
```bash
git pull  # Shows conflict
# Resolve conflict in editor
git add <file>
git commit -m "fix: Resolve merge conflict with Agent X"
git push
```

### Agent Stuck
If an agent is waiting for approval or stuck:
1. Check the agent's output
2. Answer any prompts (yes/no questions)
3. If blocked, stop agent and manually fix issue

### Test Failures
If an agent breaks tests:
1. `git log -1` to see what changed
2. `git revert HEAD` to undo last commit
3. Fix the issue
4. Recommit

## Success Metrics

After all agents complete:
- [ ] All tests pass: `python -m pytest`
- [ ] No merge conflicts: `git status`
- [ ] Documentation updated
- [ ] Demo materials ready
- [ ] Web UI enhanced (if Agent B ran)
- [ ] Agent improvements committed (if Agent C ran)

## Tips for Success

1. **Start with 2 agents** (Testing + Demo) before attempting 4
2. **Use PROGRESS.md** to track who's doing what
3. **Pull often** (every 15 minutes) to avoid drift
4. **Commit small** (after each task, not after all tasks)
5. **Communicate via git commits** (descriptive messages)
6. **Check test suite** before and after your changes

## Time Estimates by Combination

| Combination | Time to Complete | Conflicts | Workshop Ready? |
|-------------|------------------|-----------|-----------------|
| A + D | 1.5-2 hours | Very low | ✅ Yes |
| B + D | 2-3 hours | Very low | ✅ Yes (with UI demo) |
| A + B + D | 2-3 hours | Low | ✅✅ Excellent |
| All 4 | 3-4 hours | Medium | ✅✅✅ Comprehensive |

## Next Steps

1. Decide how many agents to run (recommend: 2)
2. Choose agent combination (recommend: A + D for workshop)
3. Open Claude Code sessions (1 per agent)
4. Copy-paste prompts from .txt files
5. Let agents work!
6. Monitor PROGRESS.md
7. Merge results when done

Good luck with your agentic SDLC workshop! 🚀
