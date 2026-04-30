# Simple SOP — DAG-Ready Edition

## Purpose

A minimal SOP that exercises the regex extractor end-to-end without
introducing any of the revision loops that the real-world fixtures
include. Used by the API lifecycle test.

## SOP Architecture

Every task follows the standard node structure.

***

**NODE: SS-01**
**PHASE:** Intake
**TASK NAME:** Receive Request
**TRIGGER:** Inbound request
**ACTOR:** Coordinator
**ACTION:**
1. Acknowledge request within 1 hour
2. Capture client name and request type
**OUTPUT:** Acknowledgment recorded
**DECISION GATE:** Is the request urgent?
→ YES: SS-02
→ NO: SS-03
**NEXT NODE(S):** SS-02
**TIMELINE:** 1 hour
**PARALLEL:** No

***

**NODE: SS-02**
**PHASE:** Triage
**TASK NAME:** Fast Track
**TRIGGER:** Urgent request
**ACTOR:** Coordinator
**ACTION:**
1. Skip queue
2. Hand off to on-call specialist
**OUTPUT:** Specialist engaged
**NEXT NODE(S):** SS-04
**TIMELINE:** 30 minutes
**PARALLEL:** No

***

**NODE: SS-03**
**PHASE:** Triage
**TASK NAME:** Standard Queue
**TRIGGER:** Non-urgent request
**ACTOR:** Coordinator
**ACTION:**
1. Add to standard queue
**OUTPUT:** Queued
**NEXT NODE(S):** SS-04
**TIMELINE:** 4 hours
**PARALLEL:** No

***

**NODE: SS-04**
**PHASE:** Resolution
**TASK NAME:** Close Case
**TRIGGER:** Specialist completes work
**ACTOR:** Coordinator
**ACTION:**
1. Confirm completion with client
2. Close ticket
**OUTPUT:** Case closed
**TIMELINE:** Same day
**PARALLEL:** No
