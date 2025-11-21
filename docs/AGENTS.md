# StreamVault Custom Agents

This repository uses **GitHub Copilot Custom Agents** for specialized task handling. Each agent is optimized for specific types of work with tailored instructions, tool access, and domain expertise.

## 📋 Available Agents

### 1. 🐛 bug-fixer
**Specialization:** Fixing bugs and crashes  
**Profile:** `.github/agents/bug-fixer.md`  
**Best For:**
- Production crashes and errors
- Import errors and missing dependencies
- Type errors and undefined names
- Runtime failures and exceptions

**Tools:** Read, search, edit, build, test  
**Limitations:** Cannot modify architecture or add new features

---

### 2. 🗄️ database-expert
**Specialization:** Database migrations and schema changes  
**Profile:** `.github/agents/database-expert.md`  
**Best For:**
- Creating database migrations
- Adding indexes and constraints
- Schema refactoring
- Performance optimization queries

**Tools:** Read, search, edit, database tools  
**Limitations:** Must follow migration numbering convention

---

### 3. 📝 docs-writer
**Specialization:** Technical documentation  
**Profile:** `.github/agents/docs-writer.md`  
**Best For:**
- API documentation
- README files
- Architecture documentation
- Issue templates and documentation

**Tools:** Read, search, create, edit (documentation only)  
**Limitations:** Cannot modify code files

---

### 4. ✨ feature-builder
**Specialization:** New features and enhancements  
**Profile:** `.github/agents/feature-builder.md`  
**Best For:**
- Multi-proxy system implementation
- H.265/AV1 codec support
- Recording features
- Backend/frontend feature development

**Tools:** Full access (read, search, edit, build, test, deploy)  
**Limitations:** Must follow existing architecture patterns

---

### 5. 📱 mobile-specialist
**Specialization:** Mobile responsiveness and PWA features  
**Profile:** `.github/agents/mobile-specialist.md`  
**Best For:**
- Mobile-responsive UI components
- Touch target optimization
- PWA features (offline, install prompts)
- Responsive design fixes

**Tools:** Read, search, edit, frontend build tools  
**Limitations:** Frontend only (no backend changes)

---

### 6. ♻️ refactor-specialist
**Specialization:** Code quality and refactoring  
**Profile:** `.github/agents/refactor-specialist.md`  
**Best For:**
- Extracting magic numbers to constants
- Optimizing N+1 database queries
- Eliminating code duplication
- Performance improvements

**Tools:** Read, search, edit, static analysis tools  
**Limitations:** Must maintain existing functionality

---

### 7. 🔒 security-auditor
**Specialization:** Security vulnerabilities and hardening  
**Profile:** `.github/agents/security-auditor.md`  
**Best For:**
- Path traversal prevention
- Input validation
- SQL injection fixes
- Authentication/authorization issues

**Tools:** Read, search, edit, security scanning tools  
**Limitations:** Cannot disable security features

---

### 8. 🧪 test-specialist
**Specialization:** Test coverage and quality  
**Profile:** `.github/agents/test-specialist.md`  
**Best For:**
- Writing unit tests
- Integration tests
- Test coverage improvements
- Fixing flaky tests

**Tools:** Read, search, edit, test runners  
**Limitations:** Test files only (no production code)

---

## 🎯 How to Use Custom Agents

### 1. Assign an Issue to Copilot

```bash
# Tag an issue with agent recommendation
gh issue create \
  --title "Fix import error in models.py" \
  --body "Application crashes on startup..." \
  --label "type:bug,priority:critical,agent:bug-fixer"
```

### 2. Use Agent in Comments

When commenting on PRs, you can request a specific agent:

```markdown
@copilot with agent bug-fixer: Fix the NameError on line 470
```

### 3. Use Agent in Slash Commands

```
/agent bug-fixer fix import error in app/models.py
```

## 📊 Agent Selection Guide

| Task Type | Recommended Agent | Estimated Time |
|-----------|-------------------|----------------|
| Production crash | `bug-fixer` | 5-30 min |
| Missing import | `bug-fixer` | 2-5 min |
| Database migration | `database-expert` | 15-60 min |
| New feature | `feature-builder` | 2-8 hours |
| Mobile UI fix | `mobile-specialist` | 30-120 min |
| Code quality | `refactor-specialist` | 1-4 hours |
| Security fix | `security-auditor` | 30-120 min |
| Test coverage | `test-specialist` | 1-3 hours |
| Documentation | `docs-writer` | 30-90 min |

## 🔧 Agent Configuration

Each agent has:

1. **Specialized Instructions** - Domain-specific guidelines and patterns
2. **Tool Access Control** - Limited to relevant tools for safety
3. **Example Prompts** - Pre-defined patterns for common tasks
4. **Validation Rules** - Checks before marking tasks complete

### Example Agent Profile Structure

```markdown
---
name: bug-fixer
description: Specialized agent for fixing bugs and crashes
tools:
  - read
  - search
  - edit
  - build
  - test
limitations:
  - Cannot modify architecture
  - Cannot add new features
---

# Bug Fixer Agent

[Instructions...]
```

## 🚀 Best Practices

### ✅ DO

- Assign clear, well-scoped issues to agents
- Include acceptance criteria in issue description
- Mention affected files in issue body
- Use @copilot mentions for iterations
- Review agent changes before merging

### ❌ DON'T

- Assign broad, multi-domain tasks to single agent
- Give security-critical tasks without review
- Assign tasks requiring deep domain knowledge
- Use agents for learning/exploratory work
- Skip manual testing of agent changes

## 📈 Agent Performance

Track agent effectiveness:

```bash
# List issues by agent
gh issue list --label "agent:bug-fixer"

# View agent success rate
gh pr list --label "copilot-generated" --state merged
```

## 🛠️ Creating New Agents

To create a new custom agent:

1. Create profile: `.github/agents/new-agent.md`
2. Define specialization and tools
3. Add to this AGENTS.md file
4. Test with sample issue
5. Document patterns and examples

See `.github/agents/README.md` for detailed guide.

## 📚 Related Documentation

- [GitHub Copilot Custom Agents](https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-agents)
- [Agent Profiles](.github/agents/README.md)
- [Repository Instructions](.github/copilot-instructions.md)
- [Path-Specific Instructions](.github/instructions/)

---

**Last Updated:** November 13, 2025  
**Total Agents:** 8  
**Average Task Completion Time:** 30-120 minutes
