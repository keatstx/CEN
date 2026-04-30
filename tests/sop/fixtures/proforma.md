# Proforma One Solution
## Consolidated CSR & Operations SOP — DAG-Ready Edition

**Document Version:** 3.0 (Consolidated)
**Effective Date:** April 2026
**Supersedes:** CSR Internal SOP 6.8.22, CSR Internal SOP 02.28.2023, Client-Facing SOP 3.6.25, Billing Step-by-Step SOP
**Scope:** CSR Order Management, Promotional Items, Printed Items, Billing & Invoicing, Credit Card Processing, Art Library
**AI Operability:** Structured for Direct Acyclic Generation (DAG) workflow and logic automation

***

## Purpose of This SOP

This document consolidates all Proforma One Solution Standard Operating Procedures into a single, comprehensive, DAG-ready reference. It replaces four prior SOP documents and serves as the authoritative source of truth for CSR operations, billing, and client communications. Every procedure is structured as a discrete DAG node to support automated AI Operating Procedures and workflow orchestration.

**How to Use This Document:**
- Each numbered task is a discrete **DAG Node**
- Each node contains: Trigger, Actor, Action, Output, Decision Gate, Next Node(s), Timeline, and Parallel flag
- Decision points are marked **[DECISION GATE]** — these are branching nodes in the DAG
- Tasks that can run at the same time are marked **[PARALLEL]**
- All client communications must follow the Communication Standards in Part IV

***

## SOP Architecture: DAG Node Schema

Every task follows this standard node structure:

```
NODE ID:        [PF-##]
PHASE:          [Phase Name]
TASK NAME:      [Human-readable task label]
TRIGGER:        [What initiates this task]
ACTOR:          [CSR | Billing | Manager | System]
ACTION:         [Step-by-step instructions]
OUTPUT:         [Document, communication, or system update produced]
DECISION GATE:  [Condition that routes to different next nodes]
NEXT NODE(S):   [Downstream task(s)]
TIMELINE:       [SLA or expected completion window]
PARALLEL:       [Yes/No]
```

***

## Part I: Client Request & Intake

***

**NODE: PF-01**
**PHASE:** Client Request & Intake
**TASK NAME:** Receive & Acknowledge Client Request
**TRIGGER:** Inbound client request via email or phone
**ACTOR:** CSR
**ACTION:**
1. Receive request — note channel (email or phone), date, time, and client name
2. Send acknowledgment confirmation to client within 30–60 minutes of receipt
3. In the acknowledgment, provide a realistic response expectation:
   - Promotional and apparel projects: 1–2 business days
   - Basic printed projects: 1–3 business days; complex or larger jobs may be longer
4. All communication must provide full details and multiple options
5. Anticipate the client's next question and answer it proactively — aim to be 2 steps ahead
**OUTPUT:** Acknowledgment email sent to client with timeline expectation
**DECISION GATE:** Is this a Promotional/Apparel order or a Printed order?
→ Promotional/Apparel: proceed to PF-02A
→ Printed: proceed to PF-02B
→ Both: run PF-02A and PF-02B in parallel
**NEXT NODE(S):** PF-02A and/or PF-02B
**TIMELINE:** Acknowledgment within 30–60 minutes of receipt
**PARALLEL:** No

***

## Part II: Sourcing & Proposal

### Phase 2A — Promotional & Apparel Items

***

**NODE: PF-02A**
**PHASE:** Sourcing & Proposal — Promotional/Apparel
**TASK NAME:** Source Promotional Products & Build Proposal
**TRIGGER:** PF-01 complete; order type confirmed as Promotional or Apparel
**ACTOR:** CSR
**ACTION:**
1. Access ESP (or internal promotional database) to source products based on client information
2. If details are unknown, begin with a Good / Better / Best search framework
3. Ask client for key details if not yet provided: quantity, budget, audience, in-hand date
4. Mark up setup fees as well as the unit cost of the product
5. **Do not check inventory** until the client has narrowed down their choices
6. Refine search if initial results do not meet client's target product or price point
7. Compile PDF Proposal including all details, lead time (if available), and price options
8. Email PDF Proposal to client
9. Request client input to determine which samples to order for approval — **size and color are critical**
10. **Do not place an order without the client receiving a sample of the size and color item they are interested in**
**OUTPUT:** PDF Proposal emailed to client; sample request initiated if applicable
**DECISION GATE:** Does client approve proposal?
→ YES: proceed to PF-03 (Order Acceptance)
→ NO: revise proposal, refine search, re-submit
**NEXT NODE(S):** PF-03
**TIMELINE:** Response within 1–2 business days of intake
**PARALLEL:** YES — can run concurrently with PF-02B if order includes both types

***

### Phase 2B — Printed Items

***

**NODE: PF-02B**
**PHASE:** Sourcing & Proposal — Printed Items
**TASK NAME:** Source Print Vendors & Build Printed Proposal
**TRIGGER:** PF-01 complete; order type confirmed as Printed
**ACTOR:** CSR
**ACTION:**
1. Determine print capability and capacity required (local, national, or global)
2. Access the distribution list for print vendors with the specific capability required
3. BCC all qualifying suppliers with the same specs, details, and required in-hand date simultaneously
4. Build a custom proposal using the Word Document Custom Template (city-specific where applicable) including:
   - Quantity
   - All print specifications
   - Pricing
   - Lead time from final art approval
5. Approved orders must receive hard copy proofs (except digital-only jobs)
6. Where applicable, arrange for paper dummies
7. Email proposal to client
**OUTPUT:** Print Proposal emailed to client; vendor quotes received
**DECISION GATE:** Does client approve proposal?
→ YES: proceed to PF-03
→ NO: revise specs, requote, re-submit
**NEXT NODE(S):** PF-03
**TIMELINE:** Response within 1–3 business days; complex jobs may be longer
**PARALLEL:** YES — can run concurrently with PF-02A

***

## Part III: Order Management

### Phase 3 — Order Acceptance

***

**NODE: PF-03**
**PHASE:** Order Acceptance
**TASK NAME:** Receive & Enter Approved Order
**TRIGGER:** Client approves proposal via signed proposal or email notification
**ACTOR:** CSR
**ACTION:**
1. Receive email confirmation or signed proposal from client
2. Enter the order into ProVision2 (PV2) with all details for repeat and future use
3. Record: client name, order date, quantity, product specs, pricing, delivery date, in-hand date, and any special instructions
**OUTPUT:** Order entered and active in ProVision2
**DECISION GATE:** Is all order information complete and confirmed?
→ YES: proceed to PF-04
→ NO: contact client to resolve missing details before proceeding
**NEXT NODE(S):** PF-04
**TIMELINE:** Same day as client approval
**PARALLEL:** No

***

**NODE: PF-04**
**PHASE:** Order Acceptance
**TASK NAME:** Send Order Acknowledgement & Purchase Order [PARALLEL]
**TRIGGER:** PF-03 complete; order entered in PV2
**ACTOR:** CSR
**ACTION:**
1. Send Order Acknowledgement (OA) to client that mirrors the proposal exactly — all details and lead time must match
2. Send Purchase Order (PO) to supplier with all job details and delivery requirements
3. Input all details and dates for both the OA and PO into PV2
4. End acknowledgment email with: *"Here is what you can expect next and when..."*
**OUTPUT:** OA sent to client; PO sent to supplier; both logged in PV2
**NEXT NODE(S):** PF-05
**TIMELINE:** Same day as order entry (PF-03)
**PARALLEL:** YES — OA to client and PO to supplier sent simultaneously

***

### Phase 4 — Proof & Proof Approval

***

**NODE: PF-05**
**PHASE:** Proof & Proof Approval
**TASK NAME:** Request & Manage Proof from Supplier
**TRIGGER:** PF-04 complete; PO acknowledged by supplier
**ACTOR:** CSR
**ACTION:**
1. Contact supplier to request proof submission (not required for embroidery)
2. **All orders — including repeat orders — must be marked for proof and proof approval**
3. Upon receipt of proof from supplier, forward to client for approval
4. Receive client response: approval or revision requests
5. If revisions requested: submit revisions to supplier; request revised proof; repeat until approved
6. Upon client approval: submit approved proof to plant/supplier
7. Request estimated ship date from plant upon proof approval
**OUTPUT:** Approved proof on file; estimated ship date received from plant
**DECISION GATE:** Client approves proof?
→ YES: log approval; proceed to PF-06
→ NO: submit revisions, request new proof, loop back to step 4
**NEXT NODE(S):** PF-06
**TIMELINE:** Per supplier lead time; manage proactively
**PARALLEL:** No (sequential approval loop)

***

### Phase 5 — Production & Client Updates

***

**NODE: PF-06**
**PHASE:** Production & Client Updates
**TASK NAME:** Manage Production Timeline & Communicate Ship Date
**TRIGGER:** PF-05 complete; proof approved; estimated ship date received
**ACTOR:** CSR
**ACTION:**
1. Communicate estimated ship date to client via email
2. Add a calendar reminder or task in ProCSR for 2–3 days before estimated ship date
3. 2–3 days before estimated ship date: follow up with plant to confirm ship date is on track
4. If ship date changes: notify client immediately with updated timeline — no surprises
5. Day after shipment: obtain tracking number from plant
6. Send tracking number and link to client via email
7. End every update with: *"Here is what you can expect next and when..."*
**OUTPUT:** Client notified of ship date and tracking; CRM/calendar reminders set
**DECISION GATE:** Did order ship on time and without issues?
→ YES: proceed to PF-07 (Invoicing)
→ NO: proceed to PF-10 (Order Issues)
**NEXT NODE(S):** PF-07 or PF-10
**TIMELINE:** Ongoing through shipment; tracking sent day after ship
**PARALLEL:** No

***

## Part IV: Billing & Invoicing

### Phase 6 — Standard Invoicing

***

**NODE: PF-07**
**PHASE:** Billing & Invoicing
**TASK NAME:** Post Vendor Invoice & Create Client Bill
**TRIGGER:** Order ships; vendor invoice received in invoice email
**ACTOR:** CSR / Billing
**ACTION:**

**Step 1 — Log In to ProVision2:**
1. Navigate to: https://provision.proforma.com/Provision/#/
2. Log in with username and password
3. Open the Invoice email account: invoices.onesolution@proforma.com

**Step 2 — Vendor-Specific Timing Rules:**
- **SanMar invoices** (apparel vendor): Wait 1–2 weeks before posting
- **CBI invoices** (decorator/ships to client): Back-date CBI invoices by 10 days when posting

**Step 3 — Locate the Order in PV2:**
1. Click on "Orders" in PV2 navigation
2. Click the Orders icon
3. In the Customer Reference box, enter the Customer Reference # from the open orders report
4. Hit Search; then click on the Order #

**Step 4 — Post Vendor Invoice:**
1. From the order pop-up screen, locate the yellow eye icon next to the plus sign under "Vendor Invoice"
2. Click the yellow eye to open the Post Vendor Invoice screen
3. Green indicator = all invoices entered; yellow/red = incomplete
4. Select the vendor from the drop-down box
5. Locate the invoice in the invoices email (some may be in the CSR email)
6. Enter from the invoice: Invoice #, invoice date, and amount for each line item
7. **Double-check that all prices match the invoice exactly**
8. **CHECK YOUR TOTALS TO MAKE SURE THEY MATCH before clicking Post**
9. Click the Post button; repeat for all invoices in the drop-down

**Step 5 — Create Client Bill:**
1. Click the plus sign under "Bill" to create the bill
2. Click OK on the confirmation pop-up
3. The Create Customer Bill screen will open
4. **Review overview notes and follow steps for owned items**
5. If pro-freight is present and should be zero: zero it out
6. Click "Preview Bill" to review before finalizing
7. Verify: line-items total, freight amount, and tax are correct
8. Note: not all bills will have taxes — refer to applicable state tax laws
9. Click "Create Bill" to finalize
10. Click "Return to Prior Screen" after creation
11. Refer to ProStore overview for each company as configurations differ

**Step 6 — Input Client Invoice Details:**
1. Input all details and differences into ProVision2
2. Submit information for supplier invoice to be paid
3. Release client invoice — batches mail the day after submission

**OUTPUT:** Vendor invoice posted in PV2; client invoice released
**DECISION GATE:** Were totals verified and matched?
→ YES: proceed to PF-08
→ NO: do not post; resolve discrepancy before proceeding
**NEXT NODE(S):** PF-08
**TIMELINE:** Per vendor invoice receipt; timing rules apply (SanMar, CBI)
**PARALLEL:** No

***

**NODE: PF-08**
**PHASE:** Billing & Invoicing
**TASK NAME:** Monthly Unbilled/Partial Bill Audit
**TRIGGER:** Monthly — calendar-triggered
**ACTOR:** CSR / Billing
**ACTION:**
1. Log in to PV2
2. Navigate to Reports
3. Run the **Unbilled/Partial Bill Report** to see the status of all open orders
4. Review all orders with unbilled or partial-bill status
5. Identify and resolve any orders that should have been billed but were not
6. Document findings and corrective actions in internal notes
**OUTPUT:** Monthly Unbilled Report reviewed; all open items resolved or flagged
**DECISION GATE:** Are there orders identified as unbilled or partially billed?
→ YES: resolve each item (post vendor invoice and create bill); loop to PF-07
→ NO: close audit for the month; log in CRM
**NEXT NODE(S):** PF-07 (for any unbilled orders) or PF-09 (close)
**TIMELINE:** Once per month
**PARALLEL:** No

***

### Phase 7 — Credit Card Payment Processing

***

**NODE: PF-09**
**PHASE:** Credit Card Payment Processing
**TASK NAME:** Process Credit Card Payment
**TRIGGER:** Credit card is used to pay a vendor invoice
**ACTOR:** CSR
**ACTION:**

**Step 1 — Obtain & Verify Receipt:**
1. Confirm client receives a receipt/invoice that matches the credit card charge amount exactly
2. Verify the charge amount against the invoice before posting

**Step 2 — Post in PV2:**
1. Post the credit card payment in ProVision2 immediately after the card is charged
2. The invoice receipt must be posted to PV2 as soon as the CC is charged — do not delay
3. **Do not mark the order as PBO (Paid by Owner) until the vendor invoice is posted**

**Step 3 — Update CC Tracking Spreadsheet:**
Enter all required information into the PBO CC Spreadsheet immediately after use:
- CC Paid Date
- Customer / File Name
- Order Date
- Sales Order #
- Vendor Name
- Invoice #
- Amount Paid
- Payment Type
- Order Description
- Ordered By

**Step 4 — Add Internal Note in PV2:**
Add a note in PV2 Internal Notes containing:
- Date the credit card was used
- Which CSR used the card
- Amount charged on that date
- **Do not mark as PBO until vendor invoice is posted**

**OUTPUT:** CC payment posted in PV2; CC tracking spreadsheet updated; internal note added
**DECISION GATE:** Is the vendor invoice posted before PBO is marked?
→ YES: mark as PBO; proceed to PF-07 (standard billing flow)
→ NO: hold PBO status until vendor invoice is posted
**NEXT NODE(S):** PF-07
**TIMELINE:** Immediate — all CC entries must be made same day as charge
**PARALLEL:** No

***

## Part V: Order Issues & Error Resolution

***

**NODE: PF-10**
**PHASE:** Order Issues & Error Resolution
**TASK NAME:** Handle Order Issues & Issue Correction of Errors (COE)
**TRIGGER:** Client reports a problem with an order, or CSR identifies an error
**ACTOR:** CSR + Manager (as needed)
**ACTION:**

**Step 1 — Client Communication:**
1. Thank the client for bringing it to your attention and for the opportunity to make things right
2. **Do not apologize** — express gratitude and ownership instead
3. Acknowledge the issue and set a timeline for resolution response

**Step 2 — Investigate & Document:**
1. Review the full order file: original request, proposal, PO, proofs, approvals, and shipping records
2. Identify what happened, how it happened, and at what step the error occurred
3. Determine who was responsible (CSR, supplier, carrier, or client)

**Step 3 — Issue Correction of Errors (COE) Document:**
Provide a formal COE to all relevant parties that includes:
- What happened and how it happened (root cause)
- The corrective action taken to resolve this specific instance
- The changes made to the SOP or process to prevent recurrence
- How the error changed our standard operating procedure going forward

**Step 4 — Resolve the Order:**
1. Coordinate reorder, replacement, credit, or refund as appropriate
2. Get written client confirmation of resolution acceptance
3. Document resolution in PV2 order notes

**Step 5 — Update the SOP:**
1. Notify the SOP owner of the required update
2. Update the relevant SOP node with the process improvement
3. Communicate the SOP change to all CSR team members

**OUTPUT:** Client notified; COE document issued; SOP updated; order resolved
**DECISION GATE:** Is the error resolved to client satisfaction?
→ YES: close the issue; log in CRM; return to normal order flow
→ NO: escalate to manager; re-engage with client
**NEXT NODE(S):** Return to active order phase (PF-06 or PF-07) or Manager Escalation
**TIMELINE:** Initial response within 2–4 hours of issue identification; full COE within 24 hours
**PARALLEL:** No

***

## Part VI: Art Library & Digital Asset Management

***

**NODE: PF-11**
**PHASE:** Art Library & Digital Asset Management
**TASK NAME:** Access & Use the Art Library
**TRIGGER:** CSR needs to retrieve client artwork, logos, or documents for an order
**ACTOR:** CSR
**ACTION:**

**Step 1 — Log In to Art Library:**
1. Navigate to: provision.proforma.com
2. Log in with username and password
3. Click the "Customer" tab at the top of the screen
4. Click the "Art Library" icon

**Step 2 — Search for Client Artwork:**
1. In the Art Library, enter the customer name in the Customer Search Bar (e.g., "Lerch Bates")
2. Press Enter — all artwork and documents for that client will display
3. Never ask a client for artwork you may already have — search exhaustively first

**Step 3 — Download Content:**
1. Click on the logo or document needed
2. Click the download icon in the top-right of the screen
3. File downloads to your local drive for use

**Step 4 — Proforma One Solution Resources:**
Access Proforma One Solution through the Art Library as a customer to find:
- Distribution List of Print Vendors
- Standard Operating Procedures (Prostore Build, Samples SOP, CSR SOP, client-specific SOPs)
- Company Store Documents (Store Testing Checklist, User Template, Prostore Product Spreadsheet, Prostores Implementation Checklist)

**OUTPUT:** Artwork or document retrieved; order proceeds with correct assets
**DECISION GATE:** Is the needed artwork available in the Art Library?
→ YES: download and proceed with order
→ NO: request artwork from client; save to Art Library upon receipt for future use
**NEXT NODE(S):** Return to active order phase (PF-02A, PF-02B, or PF-05)
**TIMELINE:** Immediate during active order work
**PARALLEL:** YES — can run concurrently with any sourcing or production phase

***

## Part VII: DAG Workflow Logic Reference

### End-to-End Process Flow Map

| Phase | Node(s) | Actor | Key Output | Decision Gate |
|-------|---------|-------|-----------|---------------|
| Client Intake | PF-01 | CSR | Acknowledgment sent | Promo vs. Print vs. Both |
| Sourcing — Promo | PF-02A | CSR | PDF Proposal | Client approves? |
| Sourcing — Print | PF-02B | CSR | Print Proposal | Client approves? |
| Order Acceptance | PF-03 | CSR | Order in PV2 | All info complete? |
| OA & PO | PF-04 | CSR | OA to client; PO to supplier | — |
| Proof Approval | PF-05 | CSR | Approved proof; ship date | Client approves proof? |
| Production Updates | PF-06 | CSR | Tracking sent to client | Shipped on time? |
| Billing — Standard | PF-07 | CSR/Billing | Vendor posted; client billed | Totals match? |
| Monthly Audit | PF-08 | CSR/Billing | Unbilled/partial resolved | Unbilled orders found? |
| Credit Card | PF-09 | CSR | CC logged; PV2 updated | Vendor invoice posted before PBO? |
| Order Issues | PF-10 | CSR/Manager | COE issued; SOP updated | Resolved? |
| Art Library | PF-11 | CSR | Artwork retrieved | Asset available? |

### Parallel Node Groups

| Group ID | Nodes | Condition | Join Point |
|----------|-------|-----------|------------|
| PG-01 | PF-02A + PF-02B | Order includes both Promo and Print | Both proposals complete before PF-03 |
| PG-02 | PF-04 (OA + PO) | Single node; OA to client and PO to supplier sent simultaneously | Both confirmed before PF-05 |
| PG-03 | PF-11 + any sourcing/production node | Art retrieval can run alongside sourcing | Art available when needed |

### DAG Execution Rules

1. **Sequential Gates:** All `[DECISION GATE]` nodes must be evaluated before downstream nodes are activated. The AI orchestrator must route based on the gate condition.
2. **Parallel Execution:** Nodes marked `[PARALLEL]` may be dispatched simultaneously. The join node waits for all parallel tasks to complete before proceeding.
3. **Loopback Nodes:** Proof approval (PF-05) and proposal revision (PF-02A/PF-02B) are loopback nodes — the AI agent re-invokes the node upon receiving a revision request until approval is obtained.
4. **Error Branch:** Any node that identifies a quality, shipping, or billing error routes to PF-10 (Order Issues). PF-10 always returns to the active phase after resolution or escalates to Manager.
5. **Hold States:** The PBO hold in PF-09 (Credit Card) is a mandatory hold state — the AI agent must not mark PBO until the vendor invoice condition is satisfied.
6. **Monthly Trigger:** PF-08 (Monthly Audit) is a time-triggered node. The AI scheduler must invoke this node on the first business day of each month.
7. **File Integrity Rule:** Never ask a client for information or artwork already on file. The AI agent must query PV2 and the Art Library before generating a client request.

***

## Part VIII: Communication Standards

### Response Time SLAs

| Communication Type | Response SLA | Channel |
|-------------------|-------------|---------|
| Initial client inquiry acknowledgment | 30–60 minutes | Email or Phone |
| Promotional/apparel proposal | 1–2 business days | Email (PDF Proposal) |
| Printed items proposal | 1–3 business days | Email (PDF Proposal) |
| Order acknowledgment | Same day as client approval | Email |
| Proof delivery to client | Per supplier lead time | Email |
| Ship date confirmation follow-up | 2–3 days before estimated ship | Phone/Email |
| Tracking number to client | Day after shipment | Email with tracking link |
| Order issue initial response | 2–4 hours | Phone + Email |
| COE document delivery | Within 24 hours of issue | Email |

### The Five Communication Principles

Every CSR communication must reflect these principles:

1. **End every communication with what to expect next and when** — clients should never have to wonder what happens next
2. **No surprises from presentation to invoice** — communicate all extra charges, delays, or changes proactively along the way
3. **Do what we say, when we say it, how we said we would do it** — consistency builds trust
4. **We are the experts** — it is our job to inform the client and make it as easy as possible to do business with us; create as little friction as possible
5. **Never ask a client for something you already have** — exhaust your search of emails, PV2, and the Art Library before making any request of the client

***

## Part IX: Roles & Responsibilities

| Role | Primary Responsibilities | Key Nodes |
|------|------------------------|-----------|
| CSR | Client intake, sourcing, proposals, order entry, proof management, client updates, basic billing | PF-01 through PF-09, PF-11 |
| Billing / CSR-Billing | Vendor invoice posting, client bill creation, monthly audit, CC processing | PF-07, PF-08, PF-09 |
| CSR Manager | Order issue escalation, COE review, SOP updates, supplier escalations | PF-10 (escalation path) |
| Supplier/Plant | Proof submission, production, shipment | PF-05, PF-06 (external actor) |

***

## Appendix A: ProVision2 Key Functions Reference

| Function | Navigation Path | Node Used |
|----------|----------------|-----------|
| Enter new order | Orders → Orders Icon → Search/Select | PF-03 |
| Post vendor invoice | Orders → Order # → Yellow Eye under Vendor Invoice | PF-07 |
| Create client bill | Orders → Order # → Plus under Bill | PF-07 |
| Preview client bill | Create Bill Screen → Preview Bill button | PF-07 |
| Run unbilled/partial bill report | Reports → Unbilled/Partial Bill Report | PF-08 |
| Add internal note | Order Record → Internal Notes field | PF-09 |
| Access Art Library | Customer Tab → Art Library Icon | PF-11 |
| Access Proforma One Solution | Art Library → Customer Search: "Proforma One Solution" | PF-11 |

***

## Appendix B: Vendor-Specific Billing Rules

| Vendor | Rule | Node |
|--------|------|------|
| SanMar (apparel vendor) | Wait 1–2 weeks after receipt before posting invoice | PF-07 |
| CBI (decorator, ships to client) | Back-date all CBI invoices by 10 days when posting | PF-07 |
| All other vendors | Post upon receipt; verify totals match before clicking Post | PF-07 |

***

## Appendix C: Credit Card Tracking Spreadsheet — Required Fields

All fields are mandatory when a credit card is used to pay a vendor invoice:

| Field | Description |
|-------|-------------|
| CC Paid Date | Date the card was charged |
| Customer / File Name | Client name and associated file |
| Order Date | Original order date |
| Sales Order # | PV2 order number |
| Vendor Name | Supplier charged |
| Invoice # | Vendor invoice number |
| Amount Paid | Dollar amount charged |
| Payment Type | Credit card type / last four digits |
| Order Description | Brief description of what was ordered |
| Ordered By | Name of the CSR who placed the order |

***

## Appendix D: Order Issue COE Template

When completing a Correction of Errors (COE), the document must address all four sections:

| Section | Required Content |
|---------|----------------|
| What Happened | Objective description of the error or issue |
| How It Happened | Root cause — step, system, or person where breakdown occurred |
| Corrective Action | Specific steps taken to resolve this instance |
| SOP Update | Exact change made to the SOP to prevent recurrence |

***

*This SOP is a living document. Any CSR who identifies an outdated or incorrect procedure is responsible for notifying the CSR Manager. The Manager is responsible for maintaining this document and communicating all revisions to the full team.*