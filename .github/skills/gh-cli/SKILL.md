 ---
name: gh-cli
description: GitHub CLI (gh) comprehensive reference for repositories, issues, pull requests, Actions, projects, releases, gists, codespaces, organizations, extensions, and all GitHub operations from the command line.
---

# GitHub CLI (gh)

Comprehensive reference for GitHub CLI (gh) — work seamlessly with GitHub from the command line.

## Prerequisites

```bash
# Install
sudo apt update && sudo apt install gh

# Authentication
gh auth login
gh auth status
```

## Common Workflows

### Create PR from Issue

```bash
# Create branch from issue
gh issue develop 123 --branch feature/issue-123

# Make changes, commit, push
git add .
git commit -m "fix: resolve issue #123"
git push

# Create PR linking to issue
gh pr create --title "Fix #123" --body "Closes #123"
```

### Issues

```bash
# Create issue
gh issue create --title "Bug: Login not working" --body "Steps to reproduce..." --labels bug

# List open issues
gh issue list
gh issue list --labels bug --assignee @me

# View issue
gh issue view 123 --comments

# Close issue
gh issue close 123 --comment "Fixed in PR #456"
```

### Pull Requests

```bash
# Create PR
gh pr create --title "Feature: Add new functionality" --base main --draft

# List PRs
gh pr list --state open
gh pr list --author @me

# View PR
gh pr view 123 --web

# Merge PR
gh pr merge 123 --squash --delete-branch

# Approve PR
gh pr review 123 --approve --body "LGTM!"

# Request changes
gh pr review 123 --request-changes --body "Please fix these issues"
```

### GitHub Actions

```bash
# List workflow runs
gh run list --workflow "ci.yml" --branch main

# Watch run in real-time
gh run watch 123456789

# Rerun failed run
gh run rerun 123456789

# View run logs
gh run view 123456789 --log

# Trigger workflow manually
gh workflow run ci.yml --ref develop
```

### Repositories

```bash
# Clone repository
gh repo clone owner/repo

# Fork repository
gh repo fork owner/repo --clone

# Create repository
gh repo create my-repo --public --description "My awesome project"

# View repository
gh repo view --web

# Sync fork
gh repo sync
```

### Releases

```bash
# Create release
gh release create v1.0.0 --notes "Release notes here"

# List releases
gh release list

# Download release assets
gh release download v1.0.0
```

## Output Formatting

```bash
# JSON output with jq
gh pr list --json number,title,state --jq '.[] | select(.state == "OPEN")'

# Custom template
gh repo view --template '{{.name}}: {{.description}}'
```

## Best Practices

1. **Set default repository**: `gh repo set-default owner/repo`
2. **JSON Parsing**: Use `--json` + `--jq` for scripting
3. **Pagination**: Use `--paginate` for large result sets
4. **Auth automation**: `export GH_TOKEN=$(gh auth token)`

## Getting Help

```bash
gh --help
gh pr --help
gh issue create --help
```

**Official Manual:** https://cli.github.com/manual/
