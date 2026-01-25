---
applyTo: '*'
description: 'Code review standards and GitHub review guidelines for StreamVault'
---

# StreamVault Code Review Guidelines

Code reviews are essential for maintaining StreamVault's high security, performance, and quality standards. These guidelines ensure consistent, thorough, and constructive reviews.

## Code Review Philosophy

### Core Principles
- **Security first**: Every review prioritizes security implications
- **Quality assurance**: Maintain high code standards and best practices
- **Knowledge sharing**: Reviews are learning opportunities for everyone
- **Constructive feedback**: Focus on the code, provide actionable suggestions
- **Efficiency**: Reviews should be thorough but not block progress unnecessarily

### Review Objectives
1. **Prevent bugs**: Catch issues before they reach production
2. **Maintain security**: Ensure no vulnerabilities are introduced
3. **Preserve performance**: Avoid performance regressions
4. **Enforce standards**: Maintain consistent code quality
5. **Share knowledge**: Help team members learn and improve
6. **Document decisions**: Explain complex or non-obvious choices

## Review Process

### For Review Authors (PR Creators)

#### Pre-Review Checklist
Before requesting a review, ensure:
- [ ] **All tests pass**: `pytest tests/ -v` and `npm run build`
- [ ] **Code is self-reviewed**: You've reviewed your own changes
- [ ] **Description is complete**: Clear explanation of what and why
- [ ] **Security considerations**: Any security implications documented
- [ ] **Breaking changes noted**: Impact on existing functionality identified
- [ ] **Documentation updated**: Relevant docs updated for changes

#### PR Description Template
```markdown
## Summary
Brief description of the changes and their purpose.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Security Implications
- [ ] No security implications
- [ ] Security review required (explain why)
- [ ] New authentication/authorization logic
- [ ] File system access changes
- [ ] Database query modifications

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed
- [ ] Security testing performed

## Performance Impact
- [ ] No performance impact
- [ ] Performance improvement
- [ ] Potential performance regression (explain and justify)

## Additional Context
Any other context, screenshots, or relevant information.
```

### For Reviewers

#### Review Checklist

**Security Review (CRITICAL)**
- [ ] **Path traversal prevention**: All file operations use `validate_path_security()`
- [ ] **SQL injection prevention**: All database queries use ORM or parameterized statements
- [ ] **XSS prevention**: User input properly escaped in frontend
- [ ] **Authentication checks**: Protected endpoints require proper authentication
- [ ] **Input validation**: All user inputs validated and sanitized
- [ ] **Error handling**: No sensitive information leaked in error messages
- [ ] **HTTPS enforcement**: External API calls use secure connections

**Code Quality Review**
- [ ] **Type safety**: Proper TypeScript types and Python type hints
- [ ] **Error handling**: Comprehensive error handling with appropriate exceptions
- [ ] **Code organization**: Follows established patterns and conventions
- [ ] **Naming clarity**: Variables, functions, and classes have descriptive names
- [ ] **Documentation**: Complex logic is well-documented
- [ ] **No code duplication**: DRY principle followed
- [ ] **Performance considerations**: No obvious performance issues

**Testing Review**
- [ ] **Test coverage**: New functionality has appropriate tests
- [ ] **Test quality**: Tests cover edge cases and error conditions
- [ ] **Security tests**: Security-critical code has security tests
- [ ] **Integration tests**: Changes that affect multiple components have integration tests

#### Review Severity Levels

**🔴 Critical Issues (Request Changes)**
- Security vulnerabilities
- Data integrity risks  
- Breaking changes without proper migration
- Performance regressions > 20%
- Memory leaks or resource leaks

**🟡 Important Issues (Strong Suggestions)**
- Code quality violations
- Missing error handling
- Suboptimal algorithms
- Missing tests for new functionality
- Documentation gaps

**🔵 Suggestions (Nice to Have)**
- Code organization improvements
- Minor performance optimizations
- Better naming or comments
- Refactoring opportunities

## GitHub Review Workflow

### Using GitHub Review Features

#### Inline Comments
```markdown
**Issue**: Direct string formatting creates SQL injection vulnerability

**Problem**: 
```python
query = f"SELECT * FROM users WHERE name = '{user_input}'"
```

**Solution**: Use parameterized queries
```python
user = db.query(User).filter(User.name == user_input).first()
```

**Risk**: High - Could allow database access/modification
```

#### Review Summary Template
```markdown
## Review Summary

**Overall Assessment**: ✅ Approved / 🟡 Needs Minor Changes / 🔴 Major Issues

**Security Status**: 🔒 Secure / ⚠️ Concerns / 🚨 Vulnerabilities Found

**Performance Impact**: ⚡ Improved / ➡️ Neutral / 🐌 Regression

### Key Findings
- **Critical Issues**: [count] - Must be fixed before merge
- **Important Issues**: [count] - Should be addressed
- **Suggestions**: [count] - Consider for future improvements

### Specific Action Items
1. [Critical] Fix SQL injection vulnerability in user search
2. [Important] Add error handling for external API calls
3. [Suggestion] Consider extracting common validation logic

### Positive Feedback
- Excellent test coverage for new functionality
- Clear and well-structured code
- Good documentation of complex algorithms
```

### Review Comments Best Practices

#### Constructive Feedback Examples

**❌ Poor Feedback**
```
This is wrong.
Bad code.
Why did you do this?
```

**✅ Good Feedback**
```markdown
**Issue**: This approach could lead to N+1 query problems when loading many streams.

**Suggestion**: Consider using `selectinload()` to eagerly load the relationships:

```python
streams = db.query(Stream).options(
    selectinload(Stream.recordings)
).all()
```

**Benefit**: This reduces database queries from O(n) to O(1) for this operation.
```

#### Asking Questions vs Making Statements
```markdown
// ✅ Collaborative approach
"Could we use a more descriptive variable name here? Something like `recording_process_id` instead of `pid` might make the code more self-documenting."

// ❌ Demanding approach  
"Use a better variable name."
```

#### Explaining the "Why"
```markdown
**Security Concern**: Using `eval()` here creates a code injection vulnerability.

**Why it matters**: Attackers could execute arbitrary code by providing malicious input.

**Alternative**: Use `ast.literal_eval()` for safe evaluation of literals, or better yet, use JSON parsing:

```python
import json
config = json.loads(config_string)
```
```

## Review Turnaround Expectations

### Response Times
- **Critical security issues**: Same day
- **Regular PRs**: Within 2 business days
- **Draft PRs**: Within 1 week
- **Large architectural changes**: Schedule dedicated review session

### Re-review Process
- **Minor changes**: No re-review needed, trust the author
- **Addressing major issues**: Re-review required
- **New functionality added**: Full re-review needed

## Common Review Patterns

### Backend (Python) Reviews

#### Security Patterns to Catch
```python
# 🚨 PATH TRAVERSAL VULNERABILITY
@app.get("/files/{filename}")
async def get_file(filename: str):
    # VULNERABLE: Direct file access
    with open(f"uploads/{filename}", 'rb') as f:
        return f.read()

# ✅ SECURE: Validated path access
@app.get("/files/{filename}")
async def get_file(filename: str):
    safe_path = validate_path_security(filename, "read")
    with open(safe_path, 'rb') as f:
        return f.read()
```

#### Performance Patterns to Catch
```python
# 🚨 N+1 QUERY PROBLEM
def get_streamers_with_counts():
    streamers = db.query(Streamer).all()
    for streamer in streamers:
        # This creates N additional queries!
        streamer.recording_count = db.query(Recording).filter(
            Recording.streamer_id == streamer.id
        ).count()
    return streamers

# ✅ OPTIMIZED: Single query with aggregation
def get_streamers_with_counts():
    return db.query(
        Streamer,
        func.count(Recording.id).label('recording_count')
    ).outerjoin(Recording).group_by(Streamer.id).all()
```

### Frontend (Vue/TypeScript) Reviews

#### Security Patterns to Catch
```typescript
// 🚨 MISSING CREDENTIALS
const fetchRecordings = async () => {
  // VULNERABLE: Session cookie not sent
  const response = await fetch('/api/recordings');
  return response.json();
};

// ✅ SECURE: Includes session cookies
const fetchRecordings = async () => {
  const response = await fetch('/api/recordings', {
    credentials: 'include'  // Sends session cookies
  });
  return response.json();
};
```

#### Performance Patterns to Catch
```typescript
// 🚨 INEFFICIENT REACTIVITY
const expensiveComputed = computed(() => {
  // This runs on every reactive change!
  return recordings.value.map(r => 
    processComplexCalculation(r)
  );
});

// ✅ OPTIMIZED: Memoized with dependencies
const expensiveComputed = computed(() => {
  return recordings.value.map(r => 
    processComplexCalculation(r)
  );
});

// Even better: Use a ref with manual updates
const processedRecordings = ref([]);
watchEffect(() => {
  processedRecordings.value = recordings.value.map(r => 
    processComplexCalculation(r)
  );
});
```

## Review Tools and Automation

### GitHub Settings
```yaml
# .github/settings.yml
branches:
  - name: main
    protection:
      required_status_checks:
        strict: true
        contexts:
          - "Test Suite"
          - "Security Scan"
          - "Frontend Build"
      required_pull_request_reviews:
        required_approving_review_count: 2
        dismiss_stale_reviews: true
        require_code_owner_reviews: true
      enforce_admins: false
      restrictions: null
```

### Automated Checks
- **Lint checks**: Flake8, ESLint run automatically
- **Security scans**: Bandit, Safety, npm audit
- **Test coverage**: Ensure coverage doesn't decrease
- **Performance monitoring**: Flag significant regressions

### Review Assignments
```
# CODEOWNERS file
# Global owners
* @streamvault/core-team

# Security-sensitive areas require security team review
app/utils/security.py @streamvault/security-team
app/middleware/auth.py @streamvault/security-team

# Frontend architecture changes
app/frontend/src/composables/ @streamvault/frontend-team
app/frontend/src/stores/ @streamvault/frontend-team

# Database and performance critical code
app/models.py @streamvault/backend-team @streamvault/dba-team
app/services/ @streamvault/backend-team
```

## Handling Disagreements

### Escalation Process
1. **Discussion**: Have a respectful discussion in the PR
2. **Synchronous chat**: Move to video call if comments get long
3. **Team input**: Bring to team standup or Slack for input
4. **Tech lead decision**: Final call by technical lead if needed
5. **Documentation**: Document the decision for future reference

### Common Disagreement Areas
- **Performance vs. readability tradeoffs**
- **Security vs. usability balance**
- **Architectural approach differences**
- **Testing strategy and coverage**

## Continuous Improvement

### Review Metrics
- **Review turnaround time**: Target < 2 days
- **Defect escape rate**: Issues found in production that reviews missed
- **Review thoroughness**: Coverage of security, performance, quality concerns
- **Learning outcomes**: Knowledge shared and skills developed

### Regular Review Process Updates
- Monthly review of review guidelines
- Incorporate lessons learned from production issues
- Update checklists based on common findings
- Share knowledge from external security research

### Team Learning
- **Review showcase**: Share excellent reviews in team meetings
- **Common issues workshop**: Training on frequently missed issues
- **Security awareness**: Regular security review training
- **Tool training**: Keep up with GitHub features and review tools

Remember: Code reviews are not just about catching bugs—they're about building a stronger, more knowledgeable team and maintaining the high standards that make StreamVault reliable and secure.