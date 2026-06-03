
Create a git commit using conventional commit format.

## Format
```
<type>(<scope>): <subject>

<body>
```

## Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting/style changes
- `refactor`: Code restructuring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

## Rules
1. Subject line: max 50 characters, imperative mood
2. Body: wrapped at 72 characters, explain what and why
3. Reference issues when applicable (e.g., "Fixes #123")

## PowerShell Syntax

**IMPORTANT:** Use PowerShell here-strings, NOT bash HEREDOC (`<<EOF` doesn't work).

```powershell
git add file1.py file2.ts

@'
feat(api): add user authentication endpoint

Implement JWT-based authentication with refresh tokens.
Includes rate limiting and proper error handling.
'@ | git commit -F -
```

**Rules:**
- `@'` starts, `'@` ends (must be at line start)
- Pipe to `git commit -F -`
- ❌ Don't use: `git commit -m "$(cat <<'EOF' ...)"`


Review staged changes and create a commit following these conventions.
