# GatherAI case study

Status: working local MVP with fictional data. No users, customers or revenue. The founder should add their own motivation and validation results.

## Problem
Organizers of community gatherings juggle chats, spreadsheets and calls. One cancellation can undo a whole ride plan.

## Hypothesis (unverified)
Organizers will trust an assistant to fix logistics if it reads live data, shows its reasoning and unresolved items, and changes nothing without approval.

## Key product decisions
- Proposals rather than autonomous actions, because a wrong ride assignment has real consequences.
- Rules enforced by code, not by the model, so capacity limits hold even if the model is wrong.
- Showing what could not be solved, which is often the most useful part of a plan.
- A WhatsApp-style simulator first, to test the conversation before the cost and approval process of the official platform.

## Architecture
React front end, FastAPI service, relational database. The model works through permission-checked tools. Approval claims a proposal atomically, compares a fingerprint of current data, revalidates, and applies changes in one transaction.

## Verification
Automated tests cover capacity, tenant isolation, role limits, duplicate and stale approvals, and injection attempts. See `TEST_PLAN.md`.

## Validation experiments to run
1. Time three organizers rebuilding a ride plan after a cancellation, with a spreadsheet and with GatherAI.
2. Measure the share of AI proposals approved without edits on a real event.
3. Interview organizers on which actions they would never delegate.

## AI-assisted development
The code and documents were generated with Claude Code under the founder's product direction.
