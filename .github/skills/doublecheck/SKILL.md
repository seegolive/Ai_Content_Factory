 ---
name: doublecheck
description: 'Three-layer verification pipeline for AI output. Extracts verifiable claims, finds supporting or contradicting sources via web search, runs adversarial review for hallucination patterns, and produces a structured verification report with source links for human review.'
---

# Doublecheck

Run a three-layer verification pipeline on AI-generated output. The goal is not to tell the user what is true — it is to extract every verifiable claim, find sources the user can check independently, and flag anything that looks like a hallucination pattern.

## Activation

Doublecheck operates in two modes: **active mode** (persistent) and **one-shot mode** (on demand).

### Active Mode

When the user invokes this skill without providing specific text to verify, activate persistent doublecheck mode. Respond with:

> **Doublecheck is now active.** I'll verify factual claims in my responses before presenting them. Say "full report" on any response to get the complete three-layer verification. Turn it off anytime by saying "turn off doublecheck."

In active mode, after each substantive response, add a `Verification` section:

```
---
**Verification (N claims checked)**

- [VERIFIED] "Claim text" -- Source: [URL]
- [PLAUSIBLE] "Claim text" -- no specific source found
- [FABRICATION RISK] "Claim text" -- could not find this citation; verify before relying on it
```

### One-Shot Mode

When the user invokes this skill and provides specific text to verify, run the complete three-layer pipeline and produce a full verification report.

## Layer 1: Self-Audit

Re-read the target text with a critical lens. Extract every statement that asserts something verifiable:

| Category | Examples |
|----------|---------|
| **Factual** | "Python was created in 1991" |
| **Statistical** | "95% of enterprises use cloud services" |
| **Citation** | "Under Section 230 of the CDA..." |
| **Entity** | "OpenAI was founded by Sam Altman and Elon Musk" |
| **Temporal** | "Version 2.0 was released before the security patch" |

Check internal consistency — does the text contradict itself anywhere?

## Layer 2: Source Verification

For each extracted claim, search for external evidence. Provide URLs the user can visit to verify claims independently.

Citations are the highest-risk category for hallucinations. For any claim that cites a specific case, statute, paper, or standard:
1. Search for the exact citation
2. If you cannot find it at all, flag it as FABRICATION RISK

## Layer 3: Adversarial Review

Assume the output contains errors and actively try to find them. Check for these common hallucination patterns:

1. **Fabricated citations** — The text cites a specific case, paper, or statute that cannot be found
2. **Precise numbers without sources** — Statistics stated without indicating where the number comes from
3. **Confident specificity on uncertain topics** — Very specific claims where specifics are genuinely unknown or disputed
4. **Plausible-but-wrong associations** — Attributing a ruling to the wrong court, assigning a quote to the wrong person

## Confidence Ratings

| Rating | Meaning |
|--------|---------|
| **VERIFIED** | Supporting source found and linked |
| **PLAUSIBLE** | Consistent with general knowledge, no specific source found |
| **UNVERIFIED** | Could not find supporting or contradicting evidence |
| **DISPUTED** | Found contradicting evidence from a credible source |
| **FABRICATION RISK** | Matches hallucination patterns (e.g., unfindable citation) |

## Output Rules

- Provide links, not verdicts. The user decides what's true, not you.
- If a claim is unfalsifiable (too vague or subjective to verify), say so.
- Be explicit about what you could not check.
- Group findings by severity. Lead with the items that need the most attention.

**Limitations:** This tool accelerates human verification; it does not replace it.
