 ---
name: secret-scanning
description: 'Guide for configuring and managing GitHub secret scanning, push protection, custom patterns, and secret alert remediation. Use this skill when enabling secret scanning, setting up push protection, defining custom patterns, triaging alerts, resolving blocked pushes, or when an agent needs to scan code for secrets before committing.'
---

# Secret Scanning

This skill provides procedural guidance for configuring GitHub secret scanning — detecting leaked credentials, preventing secret pushes, defining custom patterns, and managing alerts.

## When to Use This Skill

Use this skill when the request involves:

- Enabling or configuring secret scanning for a repository or organization
- Setting up push protection to block secrets before they reach the repository
- Defining custom secret patterns with regular expressions
- Resolving a blocked push from the command line
- Triaging, dismissing, or remediating secret scanning alerts
- Scanning local code changes for secrets before committing

## How Secret Scanning Works

Secret scanning automatically detects exposed credentials across:

- Entire Git history on all branches
- Issue descriptions, comments, and titles (open and closed)
- Pull request titles, descriptions, and comments
- Wikis and secret gists

## Core Workflow — Enable Secret Scanning

### Step 1: Enable Secret Protection

1. Navigate to repository **Settings** → **Advanced Security**
2. Click **Enable** next to "Secret Protection"

### Step 2: Enable Push Protection

Push protection blocks secrets during the push process — before they reach the repository.

1. Navigate to repository **Settings** → **Advanced Security**
2. Enable "Push protection" under Secret Protection

### Step 3: Configure Exclusions (Optional)

Create `.github/secret_scanning.yml` to auto-close alerts for specific directories:

```yaml
paths-ignore:
  - "docs/**"
  - "test/fixtures/**"
  - "**/*.example"
```

### Step 4: Enable Additional Features (Optional)

- **Non-provider patterns** — detect private keys, connection strings, generic API keys
- **AI-powered generic secret detection** — uses Copilot to detect unstructured secrets like passwords
- **Validity checks** — verify if detected secrets are still active

## Core Workflow — Resolve Blocked Pushes

When push protection blocks a push from the command line:

### Option A: Remove the Secret

```bash
# Remove the secret from the file, then amend the commit
git commit --amend --all
git push
```

### Option B: Bypass Push Protection

1. Visit the URL returned in the push error message
2. Select a bypass reason: "It's used in tests", "It's a false positive", or "I'll fix it later"
3. Click **Allow me to push this secret**
4. Re-push within 3 hours

## Alert Management

### Remediation Priority

1. **Rotate the credential immediately** — this is the critical action
2. Review the alert for context (location, commit, author)
3. Check validity status: `active` (urgent), `inactive` (lower priority), `unknown`
4. Remove from Git history if needed

### Dismissing Alerts

Dismiss with a documented reason:
- **False positive** — detected string is not a real secret
- **Revoked** — credential has already been revoked
- **Used in tests** — secret is only in test code

## Custom Patterns

Define organization-specific secret patterns using regular expressions.

1. Settings → Advanced Security → Custom patterns → **New pattern**
2. Enter pattern name and regex for secret format
3. Add a sample test string
4. Click **Save and dry run** to test
5. Review results for false positives
6. Click **Publish pattern**
