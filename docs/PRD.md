# GatherAI product requirements

## Problem
Organizers of 20 to 100 person gatherings coordinate through chat groups, spreadsheets and calls. Information scatters, cancellations break logistics, and tasks get lost.

## Hypothesis (unvalidated)
An assistant that reads live event state and proposes validated changes for human approval saves organizers meaningful coordination time compared with spreadsheets.

## Personas
Primary organizer, participant (no account), co-organizer (event-scoped), platform administrator (least privilege).

## MVP scope
Accounts and organizations; event creation; public registration; participant, ride, accommodation and task management; a database-backed dashboard; an AI assistant with tools and approval workflow; a labeled WhatsApp-style simulator; fictional demo data.

## Out of MVP
Live WhatsApp sending, outbound and return ride separation, route time calculation, payments.

## Core acceptance story: driver cancellation
Given a driver with assigned passengers, when the organizer asks to reorganize rides, then the assistant identifies affected people, proposes a capacity-valid plan, states what remains unresolved, and changes nothing until approval. On approval the state is revalidated, changes run in one transaction, messages are drafted and an audit entry is written. A stale or repeated approval changes nothing.

## Success measures (to be measured, none collected yet)
Organizer time saved, manual actions reduced, share of logistics requests resolved, share of valid AI proposals, cancellation resolution time, organizer satisfaction.
