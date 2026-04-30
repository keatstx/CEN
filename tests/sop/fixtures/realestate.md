# Residential Real Estate Transaction SOP
## Listing Agent & Buyer's Agent — DAG-Ready Workflow Edition

**Document Version:** 1.0
**Effective Date:** April 2026
**Scope:** Residential Real Estate Transactions — Both Sides of the Transaction
**AI Operability:** Designed for Direct Acyclic Generation (DAG) workflow and logic automation

***

## Purpose of This SOP

This Standard Operating Procedures (SOP) document provides both Listing Agents and Buyer's Agents with a comprehensive, step-by-step operational guide for every phase of a residential real estate transaction. It is structured to ensure consistency, compliance, and client satisfaction across all transactions. Each procedure block is written to support automated AI Operating Procedures via **Direct Acyclic Generation (DAG)**, enabling workflow orchestration, conditional logic, parallel task execution, and status-gate enforcement.[^1][^2]

**How to Use This Document:**
- Each numbered task is a discrete **DAG Node**
- Each node contains: Trigger, Action, Output, and Next Node(s)
- Decision points are marked **[DECISION GATE]** — these are branching nodes in the DAG
- Parallel-executable tasks are marked **[PARALLEL]**
- All communications should provide full details and anticipate the next question the client might ask[^1]
- End every client communication with what to expect next and when[^1]

***

## SOP Architecture: DAG Node Schema

Every task in this SOP follows this standard node structure to enable AI automation:

```
NODE ID:        [LA-##] or [BA-##]
PHASE:          [Phase Name]
TASK NAME:      [Human-readable task label]
TRIGGER:        [What initiates this task]
ACTOR:          [Listing Agent | Buyer's Agent | Both | Third Party]
ACTION:         [Step-by-step instructions]
OUTPUT:         [Document, communication, or system update produced]
DECISION GATE:  [Yes/No condition that routes to different next nodes]
NEXT NODE(S):   [Downstream task(s)]
TIMELINE:       [SLA or expected completion window]
PARALLEL:       [Yes/No — can run concurrently with other nodes]
```

***

## Part I: Listing Agent SOP (Seller's Side)

### Overview

The Listing Agent represents the seller throughout the transaction. The 90 tasks below are organized into six phases. Each task is structured as a DAG node for AI workflow generation.[^2]

***

### Phase 1: Pre-Listing Preparation (Nodes LA-01 through LA-20)

***

**NODE: LA-01**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Prepare Listing Presentation for Sellers
**TRIGGER:** Initial seller inquiry received (phone, email, or referral)[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Research seller's property address and pull tax records
2. Pull comparable sold properties (comps) within 0.5–1 mile radius, last 6 months
3. Determine average days on market (DOM) for the submarket
4. Compile market conditions summary
5. Build presentation deck with value proposition and brokerage benefits
**OUTPUT:** Listing Presentation Package (PDF/Digital)
**DECISION GATE:** Is the seller ready to meet? → YES: proceed to LA-02 | NO: schedule follow-up in CRM
**NEXT NODE(S):** LA-02
**TIMELINE:** 24–48 hours after inquiry
**PARALLEL:** No

***

**NODE: LA-02**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Research Sellers Property Tax Info
**TRIGGER:** LA-01 complete; presentation preparation underway[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Access county tax assessor records
2. Confirm current assessed value, tax rate, and annual taxes
3. Confirm lot size and legal description from county records
**OUTPUT:** Property Tax Summary (internal file)
**NEXT NODE(S):** LA-03 [PARALLEL with LA-03, LA-04]
**TIMELINE:** Same session as LA-01
**PARALLEL:** YES — runs concurrently with LA-03, LA-04

***

**NODE: LA-03**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Research Comparable Sold Properties
**TRIGGER:** LA-01 initiated[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Pull MLS data: sold comps, active listings, pending
2. Adjust for square footage, lot size, condition, upgrades
3. Arrive at suggested list price range
**OUTPUT:** Comparative Market Analysis (CMA) Report
**NEXT NODE(S):** LA-05
**TIMELINE:** Concurrent with LA-02
**PARALLEL:** YES

***

**NODE: LA-04**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Determine Average Days on Market
**TRIGGER:** LA-01 initiated[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Pull MLS statistics for ZIP code/submarket
2. Document average DOM, list-to-sale price ratio
3. Note seasonal market trends
**OUTPUT:** Market Statistics Summary
**NEXT NODE(S):** LA-05
**TIMELINE:** Concurrent with LA-02 and LA-03
**PARALLEL:** YES

***

**NODE: LA-05**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Gather Info From Sellers About Their Home
**TRIGGER:** LA-02, LA-03, LA-04 complete[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Send seller pre-meeting questionnaire (upgrades, age of systems, HOA, warranty info)
2. Confirm: mortgage balance, loan type, payoff amount
3. Gather details on inclusions/exclusions
**OUTPUT:** Seller Property Profile (internal file)
**NEXT NODE(S):** LA-06
**TIMELINE:** Before first meeting
**PARALLEL:** No

***

**NODE: LA-06**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Meet With Sellers at Their Home
**TRIGGER:** LA-05 complete; meeting scheduled[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Tour entire home; take notes on condition, upgrades, features
2. Identify deferred maintenance or items needing attention
3. Walk exterior and lot
**OUTPUT:** Agent Property Notes (internal)
**NEXT NODE(S):** LA-07
**TIMELINE:** Scheduled meeting
**PARALLEL:** No

***

**NODE: LA-07**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Get To Know Their Home & Present Listing Presentation
**TRIGGER:** LA-06 complete[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Present CMA with suggested list price range
2. Discuss current market conditions
3. Share value proposition and brokerage benefits
4. Present marketing options (MLS, social, video, 3D tour, drone)[^2]
5. Explain buyer & seller agency relationships
6. Describe the buyer pre-screening process
**OUTPUT:** Seller briefed; verbal go/no-go decision
**DECISION GATE:** Seller agrees to list? → YES: proceed to LA-08 | NO: follow up in 30 days, log in CRM
**NEXT NODE(S):** LA-08
**TIMELINE:** At property meeting (LA-06)
**PARALLEL:** No

***

**NODE: LA-08**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Advise on Repairs and/or Upgrades
**TRIGGER:** LA-07 approved; seller agrees to list[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Identify items that will negatively impact value or buyer objections
2. Prioritize by ROI (paint, carpet, curb appeal, staging)
3. Discuss seller's budget and timeline for pre-list repairs
**OUTPUT:** Pre-Listing Repair/Upgrade Recommendation List
**NEXT NODE(S):** LA-09, LA-10 [PARALLEL]
**TIMELINE:** At or within 24 hours of meeting
**PARALLEL:** No

***

**NODE: LA-09**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Provide Home Seller To-Do Checklist
**TRIGGER:** LA-08 complete[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Distribute branded seller checklist (declutter, deep clean, depersonalize)
2. Set expected timeline for readiness
**OUTPUT:** Seller To-Do Checklist (PDF, emailed to seller)
**NEXT NODE(S):** LA-11
**TIMELINE:** Within 24 hours of meeting
**PARALLEL:** YES — runs with LA-10

***

**NODE: LA-10**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Discuss Seller's Goals & Financing Landscape
**TRIGGER:** LA-07 complete[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Confirm seller's desired closing date and timeline
2. Discuss different types of buyer financing (conventional, FHA, VA, cash)
3. Explain the appraisal process and common pitfalls
**OUTPUT:** Seller Goals & Timeline Document (internal)
**NEXT NODE(S):** LA-11
**TIMELINE:** At or within 24 hours of meeting
**PARALLEL:** YES

***

**NODE: LA-11**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Create Internal File for Transaction
**TRIGGER:** Seller committed to list[^1][^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Open transaction file in CRM/transaction management platform
2. Input all property data, seller contact info, key dates
3. Assign transaction coordinator if applicable
**OUTPUT:** Active Transaction File (CRM/system)
**NEXT NODE(S):** LA-12
**TIMELINE:** Same day as seller commitment
**PARALLEL:** No

***

**NODE: LA-12**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Get Listing Agreement & Disclosures Signed
**TRIGGER:** LA-11 complete[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Present listing agreement (duration, commission, terms)
2. Obtain seller's signature on listing agreement via e-sign platform
3. Provide seller's disclosure form for completion
4. Determine need for lead-based paint disclosure (pre-1978 homes)
**OUTPUT:** Signed Listing Agreement; Seller Disclosure Form issued
**DECISION GATE:** All signatures obtained? → YES: LA-13 | NO: follow up within 24 hours
**NEXT NODE(S):** LA-13
**TIMELINE:** Within 48 hours of seller commitment
**PARALLEL:** No

***

**NODE: LA-13**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Property Due Diligence Bundle [PARALLEL GROUP]
**TRIGGER:** LA-12 complete[^2]
**ACTOR:** Listing Agent
**ACTION (all run in parallel):**
- Verify interior room sizes
- Confirm lot size from county tax records (cross-reference LA-02)
- Investigate any unrecorded property easements
- Verify HOA fees and obtain copy of HOA bylaws
- Gather transferable warranties (appliances, HVAC, roof)
- Verify security system ownership (leased vs. owned)
- Determine property inclusions and exclusions
- Obtain current mortgage loan information / payoff statement
**OUTPUT:** Property Due Diligence Checklist (complete)
**NEXT NODE(S):** LA-14
**TIMELINE:** 3–5 business days
**PARALLEL:** YES — all sub-tasks run concurrently

***

**NODE: LA-14**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Agree on Repairs / Discuss Showing Protocol
**TRIGGER:** LA-13 complete[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Finalize which repairs will be made before listing
2. Establish showing instructions (lockbox, appointment only, etc.)
3. Agree on showing times with sellers
4. Discuss video recording devices and privacy during showings
**OUTPUT:** Showing Instructions Document; Repair Agreement (written)
**NEXT NODE(S):** LA-15 [PARALLEL with LA-16, LA-17]
**TIMELINE:** 1–2 days
**PARALLEL:** No

***

**NODE: LA-15**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Schedule Staging Consultation & House Cleaners
**TRIGGER:** LA-14 complete[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Contact preferred stager; schedule walkthrough
2. Confirm staging recommendations with seller
3. Schedule professional house cleaners for pre-photo day
**OUTPUT:** Staging and cleaning appointments confirmed
**NEXT NODE(S):** LA-16
**TIMELINE:** 1 week before photo shoot
**PARALLEL:** YES — runs with LA-16

***

**NODE: LA-16**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Install Lockbox & Yard Sign
**TRIGGER:** Listing Agreement signed (LA-12)[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Install electronic lockbox on front door
2. Install branded yard sign
3. Have extra keys made for lockbox
4. Set up showing services platform (CSS, ShowingTime, etc.)
**OUTPUT:** Property access infrastructure in place
**NEXT NODE(S):** LA-17
**TIMELINE:** 3–5 days before go-live
**PARALLEL:** YES

***

**NODE: LA-17**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Set-Up Photo, Video & 3D Tour Shoot
**TRIGGER:** Home cleaned and staged (LA-15 complete)[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Schedule professional photographer
2. Schedule drone shoot (if applicable)
3. Schedule 3D/Matterport tour shoot
4. Meet photographer at property; prepare home for shoot
5. Review and approve all photos, video, and tour materials
**OUTPUT:** Approved photo gallery, video, and 3D tour assets
**NEXT NODE(S):** LA-18
**TIMELINE:** Completed before MLS input
**PARALLEL:** No (sequential after staging)

***

**NODE: LA-18**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Get Seller's Approval of All Marketing Materials
**TRIGGER:** LA-17 complete[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Present all photos, video edits, and 3D tour to seller
2. Present draft MLS listing copy for review
3. Create property flyer draft
4. Obtain written/email approval from seller on all materials
**OUTPUT:** Approved Marketing Package
**DECISION GATE:** Seller approves? → YES: LA-19 | NO: revise and resubmit
**NEXT NODE(S):** LA-19
**TIMELINE:** Within 48 hours of shoot
**PARALLEL:** No

***

**NODE: LA-19**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Input Property Listing Into the MLS
**TRIGGER:** LA-18 approved[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Enter all property data into MLS (rooms, features, disclosures, showing instructions)
2. Upload approved photos (ordered by best first)
3. Attach virtual tour link and 3D tour
4. Have listing proofread before activating
5. Set MLS status to Active
6. Verify listing data appears correctly on Zillow, Realtor.com, and Trulia
**OUTPUT:** Live MLS listing; property syndicated to 3rd party portals
**NEXT NODE(S):** LA-20
**TIMELINE:** Same-day activation after approval
**PARALLEL:** No

***

**NODE: LA-20**
**PHASE:** Pre-Listing Preparation
**TASK NAME:** Launch Active Marketing
**TRIGGER:** MLS listing live (LA-19)[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Distribute property flyer (digital and print)
2. Post to social media platforms
3. Send to agent network / top buyer agents
4. Set up showing services with automated confirmation and feedback requests
5. Help owners coordinate initial showings
**OUTPUT:** Active marketing in market
**NEXT NODE(S):** LA-21 (Phase 2)
**TIMELINE:** Same day as MLS go-live
**PARALLEL:** No

***

### Phase 2: Active Marketing & Showings (Nodes LA-21 through LA-38)

***

**NODE: LA-21**
**PHASE:** Active Marketing & Showings
**TASK NAME:** Manage Showings & Gather Feedback
**TRIGGER:** First showing confirmed[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Help owners coordinate showings (notify sellers per showing instructions)
2. Track all showing activity in showing platform and CRM
3. Send automated feedback requests to showing agents after each visit
4. Compile and summarize feedback for seller
**OUTPUT:** Showing Activity Report; Buyer Feedback Log
**NEXT NODE(S):** LA-22 [PARALLEL with LA-23]
**TIMELINE:** Ongoing — daily during active listing
**PARALLEL:** YES

***

**NODE: LA-22**
**PHASE:** Active Marketing & Showings
**TASK NAME:** Schedule Weekly Update Calls with Seller
**TRIGGER:** Listing Active; weekly cadence[^1][^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Review showing activity, feedback trends, and market changes
2. Discuss price reduction strategy if DOM exceeds market average
3. Provide updated comps if market has shifted
4. Confirm seller's readiness and availability
**OUTPUT:** Weekly Seller Update Call Notes (CRM log)
**NEXT NODE(S):** LA-22 (repeat weekly) | LA-23
**TIMELINE:** Every 7 days from listing activation
**PARALLEL:** YES

***

**NODE: LA-23**
**PHASE:** Active Marketing & Showings
**TASK NAME:** Update MLS Listing as Needed
**TRIGGER:** Price change, status update, or material change[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Update price, photos, or description in MLS as directed
2. Confirm changes syndicate to 3rd party sites
3. Document all changes with dates in transaction file
**OUTPUT:** Updated MLS Listing; Change Log
**NEXT NODE(S):** LA-21 (loop back), LA-24 (when offer received)
**TIMELINE:** Within 24 hours of approved change
**PARALLEL:** YES

***

### Phase 3: Offer Management & Negotiation (Nodes LA-24 through LA-38)

***

**NODE: LA-24**
**PHASE:** Offer Management & Negotiation
**TASK NAME:** Receive and Evaluate Offers
**TRIGGER:** Offer submitted by buyer's agent[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Prepare "Net Sheet" for each offer (seller net proceeds after all costs)
2. Obtain pre-approval letter from buyer's agent
3. Examine and verify buyer's qualifications and lender credibility
4. Present all offers to seller with agent's recommendation
**OUTPUT:** Offer Net Sheet(s); Buyer Qualification Summary
**DECISION GATE:** Acceptable offer received? → YES: LA-25 | NO: counter or reject, loop to LA-21
**NEXT NODE(S):** LA-25
**TIMELINE:** Within 2–4 hours of offer receipt
**PARALLEL:** No

***

**NODE: LA-25**
**PHASE:** Offer Management & Negotiation
**TASK NAME:** Negotiate All Offers
**TRIGGER:** Seller reviews offer(s)[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Advise seller on negotiation strategy (counter, accept, reject)
2. Draft and deliver counter-offer if applicable via e-sign
3. Track all counter-offer deadlines
4. Confirm mutual acceptance of final terms
**OUTPUT:** Executed Purchase Agreement (all parties signed)
**DECISION GATE:** Contract executed? → YES: LA-26 | NO: return to offer loop
**NEXT NODE(S):** LA-26
**TIMELINE:** Per contract deadline (typically 24–48 hours)
**PARALLEL:** No

***

**NODE: LA-26**
**PHASE:** Offer Management & Negotiation
**TASK NAME:** Under Contract — Open Escrow [PARALLEL LAUNCH]
**TRIGGER:** Purchase agreement fully executed[^1][^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Send fully executed contract to title/escrow company
2. Check buyer's agent has received all signed copies
3. Change property status in MLS to "Under Contract" or "Pending"
4. Deliver copies of contract/addendum to seller
5. Keep track of copies for office file
**OUTPUT:** Open escrow; MLS status updated; all parties notified
**NEXT NODE(S):** LA-27, LA-28, LA-29 [PARALLEL GROUP]
**TIMELINE:** Within 24 hours of execution
**PARALLEL:** No (initiates parallel group)

***

### Phase 4: Under Contract — Inspection & Appraisal (Nodes LA-27 through LA-52)

***

**NODE: LA-27**
**PHASE:** Under Contract — Inspection
**TASK NAME:** Coordinate Inspections with Sellers
**TRIGGER:** LA-26 complete; inspection period begins[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Confirm inspection date/time with seller and buyer's agent
2. Ensure seller vacates property during inspection
3. Ensure all utilities are on
4. Refer trustworthy contractors to sellers in advance if repairs are anticipated
**OUTPUT:** Inspection Scheduled; Seller Access Confirmed
**NEXT NODE(S):** LA-28
**TIMELINE:** Per contract inspection deadline
**PARALLEL:** YES — runs with LA-29

***

**NODE: LA-28**
**PHASE:** Under Contract — Inspection
**TASK NAME:** Receive & Respond to Buyer's Inspection Objections
**TRIGGER:** Buyer submits inspection objection/repair request[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Review buyer's inspection objection document in full
2. Explain buyer's objections to seller clearly
3. Determine seller's resolution strategy (repair, credit, reject)
4. Get all repair agreements in writing via addendum
5. Refer trusted contractors if seller is making repairs
**OUTPUT:** Inspection Resolution Addendum (signed by all parties)
**DECISION GATE:** Agreement reached? → YES: LA-29 | NO: negotiate or contract may terminate
**NEXT NODE(S):** LA-29
**TIMELINE:** Per contract inspection objection deadline
**PARALLEL:** No

***

**NODE: LA-29**
**PHASE:** Under Contract — Appraisal
**TASK NAME:** Manage Appraisal Process
**TRIGGER:** Inspection period resolved; lender orders appraisal[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Meet appraiser at the property (provide comps, upgrade list, recent sale data)
2. Advocate for property value by presenting supporting documentation
3. Monitor appraisal status with buyer's agent
**OUTPUT:** Appraisal Report received
**DECISION GATE:** Appraisal at or above contract price? → YES: LA-30 | NO: negotiate (LA-29b)

***

**NODE: LA-29b**
**PHASE:** Under Contract — Appraisal
**TASK NAME:** Negotiate Unsatisfactory Appraisal [DECISION BRANCH]
**TRIGGER:** Appraisal comes in below contract price[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Review appraisal report for errors or missed comps
2. File appraisal dispute/rebuttal with supporting comps if warranted
3. Negotiate with buyer: price reduction, buyer pays gap, or terminate
**OUTPUT:** Appraisal Resolution Addendum or Contract Termination
**NEXT NODE(S):** LA-30 (if resolved) | Contract Termination (if not)

***

**NODE: LA-30**
**PHASE:** Under Contract — Pre-Closing
**TASK NAME:** Pre-Closing Coordination [PARALLEL GROUP]
**TRIGGER:** Clear-to-Close received from buyer's lender[^2]
**ACTOR:** Listing Agent
**ACTION (all run in parallel):**
- Confirm clear-to-close (CTC) with buyer's agent and lender
- Coordinate closing date, time, and location with all parties
- Verify title company has all required documents
- Remind sellers to transfer/cancel utilities on closing day
- Make sure all parties are notified of closing time
- Resolve any title issues before closing
- Confirm all agreed-upon repairs have been completed
**OUTPUT:** Closing Confirmation; All Pre-Close Checklist Items Complete
**NEXT NODE(S):** LA-31
**TIMELINE:** 5–7 days before closing
**PARALLEL:** YES

***

### Phase 5: Closing (Nodes LA-31 through LA-38)

***

**NODE: LA-31**
**PHASE:** Closing
**TASK NAME:** Review Closing Documents
**TRIGGER:** Closing disclosure received from title/escrow[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Receive and carefully review closing disclosure (CD) and HUD-1/settlement statement
2. Verify all line items: sales price, commissions, credits, prorations, payoffs
3. Review closing figures with seller and answer all questions
4. Resolve any last-minute issues or discrepancies
**OUTPUT:** Seller-Reviewed Closing Statement; All Issues Resolved
**DECISION GATE:** Closing docs correct? → YES: LA-32 | NO: contact title to correct
**NEXT NODE(S):** LA-32
**TIMELINE:** 24–48 hours before closing
**PARALLEL:** No

***

**NODE: LA-32**
**PHASE:** Closing
**TASK NAME:** Attend Seller's Closing
**TRIGGER:** All pre-close tasks complete; closing day[^2]
**ACTOR:** Listing Agent
**ACTION:**
1. Attend closing with seller (in-person or remote/mail-away)
2. Confirm seller brings valid ID and any required items (keys, garage openers, HOA docs)
3. Witness signing of all closing documents
4. Confirm disbursement of funds to seller
**OUTPUT:** Transaction Closed; Seller Receives Net Proceeds
**NEXT NODE(S):** LA-33
**TIMELINE:** Closing day
**PARALLEL:** No

***

### Phase 6: Post-Closing (Nodes LA-33 through LA-38)

***

**NODE: LA-33**
**PHASE:** Post-Closing
**TASK NAME:** Post-Closing Wrap-Up [PARALLEL GROUP]
**TRIGGER:** Closing complete[^1][^2]
**ACTOR:** Listing Agent
**ACTION (all run in parallel):**
- Pick up lockbox and yard sign from property
- Change MLS status to "Sold" (input final sale price and closing date)
- Close out seller's file with brokerage (submit all required documents)
- Send closing gift and thank-you to seller
- Request online review/referral from seller
- Update CRM with closed transaction data
**OUTPUT:** File Closed; MLS Updated; Brokerage Records Complete
**TIMELINE:** Within 48 hours of closing
**PARALLEL:** YES

***

## Part II: Buyer's Agent SOP (Buyer's Side)

### Overview

The Buyer's Agent represents the buyer throughout the transaction. The 90 tasks below are organized into six phases. Each task is structured as a DAG node.[^2]

***

### Phase 1: Buyer Onboarding & Pre-Approval (Nodes BA-01 through BA-18)

***

**NODE: BA-01**
**PHASE:** Buyer Onboarding
**TASK NAME:** Schedule Time to Meet Buyers
**TRIGGER:** Buyer inquiry received (phone, email, referral, website)[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Respond to inquiry within 30–60 minutes with confirmation[^1]
2. Schedule in-person or virtual buyer consultation
3. Send calendar invite with agenda and pre-meeting prep materials
**OUTPUT:** Consultation Meeting Scheduled
**NEXT NODE(S):** BA-02
**TIMELINE:** Within 24 hours of inquiry
**PARALLEL:** No

***

**NODE: BA-02**
**PHASE:** Buyer Onboarding
**TASK NAME:** Prepare Buyers Guide & Presentation
**TRIGGER:** BA-01 complete; meeting scheduled[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Compile buyer's guide (process overview, timeline, key milestones)
2. Prepare current market conditions summary
3. Include overview of different financing options
4. Include information on earnest money deposits, inspection process, home warranties
**OUTPUT:** Buyer's Guide & Presentation Package (PDF)
**NEXT NODE(S):** BA-03
**TIMELINE:** Before consultation meeting
**PARALLEL:** No

***

**NODE: BA-03**
**PHASE:** Buyer Onboarding
**TASK NAME:** Conduct Buyer Consultation
**TRIGGER:** BA-02 complete; meeting occurs[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Discuss buyers' goals, needs, wants, and timeline
2. Explain buyer and seller agency relationships
3. Explain agent's value proposition and brokerage benefits
4. Discuss different types of financing options
5. Address foreclosures and short sales as applicable
6. Explain school districts' effect on home values
7. Discuss recording devices during showings
8. Learn all buyer goals and make a plan
**OUTPUT:** Buyer Goals & Search Criteria Document; Buyer Representation Agreement Signed
**DECISION GATE:** Buyer signs representation agreement? → YES: BA-04 | NO: follow up, re-engage
**NEXT NODE(S):** BA-04
**TIMELINE:** At consultation meeting
**PARALLEL:** No

***

**NODE: BA-04**
**PHASE:** Buyer Onboarding
**TASK NAME:** Help Buyers Find a Mortgage Lender & Obtain Pre-Approval
**TRIGGER:** BA-03 complete; representation agreement signed[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Provide 2–3 trusted lender referrals if buyer does not have one
2. Explain the pre-approval vs. pre-qualification difference
3. Follow up with buyer and lender until pre-approval letter is received
4. Review pre-approval letter for accuracy (amount, loan type, expiration)
**OUTPUT:** Buyer Pre-Approval Letter on File
**DECISION GATE:** Pre-approval received? → YES: BA-05 | NO: hold search; assist buyer in resolving barriers
**NEXT NODE(S):** BA-05
**TIMELINE:** 2–5 business days
**PARALLEL:** No

***

**NODE: BA-05**
**PHASE:** Buyer Onboarding
**TASK NAME:** Create Internal File for Buyers Records
**TRIGGER:** BA-04 complete; pre-approval received[^1][^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Open buyer transaction file in CRM/transaction platform
2. Input buyer contact information, pre-approval details, target criteria
3. Set up automated MLS search based on buyer criteria
4. Send buyers homes within their criteria immediately upon setup
**OUTPUT:** Active Buyer File (CRM); Automated MLS Alerts Active
**NEXT NODE(S):** BA-06
**TIMELINE:** Same day as pre-approval receipt
**PARALLEL:** No

***

### Phase 2: Property Search & Showings (Nodes BA-06 through BA-17)

***

**NODE: BA-06**
**PHASE:** Property Search & Showings
**TASK NAME:** Start Showing Buyers Homes [PARALLEL ONGOING LOOP]
**TRIGGER:** BA-05 complete; buyer criteria confirmed[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Schedule and organize all showings
2. Gather showing instructions for each listing
3. Send showing schedule to buyers in advance
4. Show up early; prepare for first showing
**OUTPUT:** Showing Schedule Confirmed
**NEXT NODE(S):** BA-07
**TIMELINE:** Ongoing until home identified
**PARALLEL:** YES — all showing management runs in parallel loop

***

**NODE: BA-07**
**PHASE:** Property Search & Showings
**TASK NAME:** Conduct Showings & Manage Buyer Experience
**TRIGGER:** BA-06; each showing appointment[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Look for possible repair issues while showing (roof, foundation, HVAC, etc.)
2. Share knowledge and insight about each home
3. Guide buyers through their emotional journey
4. Discuss HOA, utilities, transferable warranties, water source
5. Estimate expected utility usage costs
6. Keep records of all showings in CRM
7. Update listing agents with buyer's feedback
**OUTPUT:** Showing Notes (per property); Buyer Feedback Log
**NEXT NODE(S):** BA-08 [PARALLEL]
**TIMELINE:** At each showing
**PARALLEL:** No (sequential per showing)

***

**NODE: BA-08**
**PHASE:** Property Search & Showings
**TASK NAME:** Ongoing Buyer Communication & Search Management [PARALLEL]
**TRIGGER:** Active showing phase[^1][^2]
**ACTOR:** Buyer's Agent
**ACTION (ongoing parallel tasks):**
- Update buyers when new homes hit the market
- Update buyers on any price drops on watchlisted properties
- Discuss MLS data with buyers at showings
- Inform buyers of their showing activity weekly
- Update buyer pre-approval letter if market search extends >60 days
- Provide updated housing market data to buyers
**OUTPUT:** Weekly Buyer Status Updates; CRM Logs
**TIMELINE:** Weekly cadence; continuous during active search
**PARALLEL:** YES

***

**NODE: BA-09**
**PHASE:** Property Search & Showings
**TASK NAME:** Identify Target Home & Pre-Offer Preparation
**TRIGGER:** Buyer identifies preferred home[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Confirm property inclusions and exclusions
2. Verify listing data is correct (MLS vs. physical)
3. Review comps with buyers to determine fair market value
4. Discuss multiple offer situation strategy if applicable
5. Create practice offer to help buyers prepare
6. Determine need for lead-based paint disclosure
7. Explain home warranty options
8. Discuss loan objection deadlines and contract contingencies
9. Choose a target closing date
**OUTPUT:** Pre-Offer Strategy Document; Buyer Decision Confirmed
**NEXT NODE(S):** BA-10
**TIMELINE:** 24–48 hours before submitting offer
**PARALLEL:** No

***

### Phase 3: Offer Submission & Negotiation (Nodes BA-10 through BA-20)

***

**NODE: BA-10**
**PHASE:** Offer Submission & Negotiation
**TASK NAME:** Prepare & Submit Buyer's Offer
**TRIGGER:** BA-09 complete; buyer is ready[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Update buyer's pre-approval letter (amount matching offer)
2. Prepare sales contract with all terms, contingencies, and deadlines
3. Educate buyers on all contract options before signing
4. Obtain buyer's signatures via e-sign
5. Submit offer to listing agent
**OUTPUT:** Executed Buyer Offer Package (contract + pre-approval + earnest money instructions)
**DECISION GATE:** Offer submitted within deadline? → YES: BA-11 | NO: escalate immediately
**NEXT NODE(S):** BA-11
**TIMELINE:** Per offer deadline
**PARALLEL:** No

***

**NODE: BA-11**
**PHASE:** Offer Submission & Negotiation
**TASK NAME:** Negotiate Buyer's Offer
**TRIGGER:** Listing agent responds to offer[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Receive counter-offer from listing agent
2. Present counter-offer to buyers with recommendation
3. Draft buyer's counter-counter if needed
4. Track all counter deadlines in CRM
5. Confirm mutual acceptance
**OUTPUT:** Fully Executed Purchase Agreement
**DECISION GATE:** Contract executed? → YES: BA-12 | NO: continue negotiation or move to next property
**NEXT NODE(S):** BA-12
**TIMELINE:** Per counter-offer deadlines (typically 24–48 hours)
**PARALLEL:** No

***

**NODE: BA-12**
**PHASE:** Offer Submission & Negotiation
**TASK NAME:** Execute Contract & Open Escrow [PARALLEL LAUNCH]
**TRIGGER:** Purchase agreement fully executed[^1][^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Send fully executed contract to title/escrow company
2. Coordinate earnest money drop-off (wire or cashier's check within deadline)
3. Deliver copies to mortgage lender
4. Obtain copy of seller's disclosure for buyers
5. Deliver copies of contract/addendum to buyers
6. Obtain a copy of HOA bylaws (if applicable)
7. Keep track of copies for office file
**OUTPUT:** Open Escrow; Earnest Money Deposited; All Parties Have Contract Copies
**NEXT NODE(S):** BA-13, BA-14, BA-15 [PARALLEL GROUP]
**TIMELINE:** Within 24 hours of execution; earnest money per contract deadline
**PARALLEL:** No (initiates parallel group)

***

### Phase 4: Under Contract — Inspection, Appraisal & Loan (Nodes BA-13 through BA-28)

***

**NODE: BA-13**
**PHASE:** Under Contract — Inspection
**TASK NAME:** Coordinate & Attend Inspection
**TRIGGER:** BA-12 complete; inspection period begins[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Hire qualified home inspector (recommend 2–3 options to buyer)
2. Coordinate inspection with sellers/listing agent
3. Meet inspector at the property
4. Walk through entire home with inspector
5. Review home inspection report in detail with buyers
**OUTPUT:** Inspection Report; Buyer Review Complete
**NEXT NODE(S):** BA-14
**TIMELINE:** Within inspection period (typically 5–10 days)
**PARALLEL:** YES — runs with BA-15

***

**NODE: BA-14**
**PHASE:** Under Contract — Inspection
**TASK NAME:** Negotiate Inspection Objections
**TRIGGER:** Buyer reviews inspection report[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Prepare inspection objection/repair request document
2. Prioritize requests: health & safety first, material defects second, cosmetic last
3. Submit to listing agent within inspection objection deadline
4. Negotiate response from seller
5. Get all agreed-upon repair items in writing via addendum
**OUTPUT:** Inspection Resolution Addendum (signed by all parties)
**DECISION GATE:** Agreement reached? → YES: BA-15 | NO: escalate or exercise termination right
**NEXT NODE(S):** BA-15
**TIMELINE:** Per contract inspection objection deadline
**PARALLEL:** No

***

**NODE: BA-15**
**PHASE:** Under Contract — Loan & Title
**TASK NAME:** Loan & Title Management [PARALLEL ONGOING]
**TRIGGER:** BA-12 complete; runs through closing[^2]
**ACTOR:** Buyer's Agent
**ACTION (ongoing parallel):**
- Check in with lender weekly to verify loan status
- Verify any existing lease agreements on property
- Check on appraisal date and coordinate access
- Ensure all loan documents requested by lender are submitted promptly
- Solve any title problems before closing
**OUTPUT:** Loan Status Updates (CRM); Title Issues Resolved
**TIMELINE:** Weekly check-ins from contract to CTC
**PARALLEL:** YES

***

**NODE: BA-16**
**PHASE:** Under Contract — Appraisal
**TASK NAME:** Monitor & Manage Appraisal
**TRIGGER:** Lender orders appraisal[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Confirm appraisal date with listing agent
2. Ensure appraiser has access to property
3. Receive appraisal results from lender
**OUTPUT:** Appraisal Report (to lender and parties)
**DECISION GATE:** Appraisal at or above contract price? → YES: BA-17 | NO: BA-16b
**NEXT NODE(S):** BA-17 or BA-16b

***

**NODE: BA-16b**
**PHASE:** Under Contract — Appraisal
**TASK NAME:** Negotiate Unsatisfactory Appraisal [DECISION BRANCH]
**TRIGGER:** Appraisal below contract price[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Present appraisal results to buyer with options
2. Negotiate with listing agent: price reduction, buyer pays gap, split difference, or terminate
3. Document resolution in signed addendum
**OUTPUT:** Appraisal Resolution Addendum or Contract Termination
**NEXT NODE(S):** BA-17 (if resolved) | Contract Termination

***

### Phase 5: Pre-Closing & Closing (Nodes BA-17 through BA-24)

***

**NODE: BA-17**
**PHASE:** Pre-Closing
**TASK NAME:** Pre-Closing Coordination [PARALLEL GROUP]
**TRIGGER:** Clear-to-Close (CTC) issued by lender[^2]
**ACTOR:** Buyer's Agent
**ACTION (all run in parallel):**
- Coordinate closing date, time, and location with all parties
- Make sure all documents are fully signed
- Verify title company has everything needed
- Remind buyers to schedule utility transfers (electric, gas, water, internet)
- Make sure all parties are notified of closing time and location
- Confirm sellers have completed all agreed-upon repairs
**OUTPUT:** Closing Confirmation; Pre-Close Checklist Complete
**TIMELINE:** 5–7 days before closing
**PARALLEL:** YES

***

**NODE: BA-18**
**PHASE:** Pre-Closing
**TASK NAME:** Review Closing Documents
**TRIGGER:** Closing disclosure received from title/escrow[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Receive and review closing disclosure (CD) in full
2. Verify all line items: purchase price, credits, lender fees, prorations
3. Review closing figures with buyers; answer all questions
4. Resolve any last-minute issues or discrepancies with title
**OUTPUT:** Buyer-Reviewed Closing Statement; All Issues Resolved
**DECISION GATE:** Closing docs correct? → YES: BA-19 | NO: contact title to correct immediately
**NEXT NODE(S):** BA-19
**TIMELINE:** 24–48 hours before closing
**PARALLEL:** No

***

**NODE: BA-19**
**PHASE:** Pre-Closing
**TASK NAME:** Perform Final Walk-Through with Buyers
**TRIGGER:** Day before or morning of closing[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Walk through entire property with buyers
2. Verify sellers have vacated and property is in agreed condition
3. Confirm all agreed-upon repairs have been completed
4. Test appliances, doors, windows, garage doors, HVAC, plumbing
5. Document any outstanding issues; contact listing agent immediately
**OUTPUT:** Final Walk-Through Sign-Off
**DECISION GATE:** Property condition acceptable? → YES: BA-20 | NO: resolve before proceeding to closing
**NEXT NODE(S):** BA-20
**TIMELINE:** Day before or morning of closing
**PARALLEL:** No

***

**NODE: BA-20**
**PHASE:** Closing
**TASK NAME:** Attend Closing with Buyers
**TRIGGER:** All pre-close tasks complete; closing day[^2]
**ACTOR:** Buyer's Agent
**ACTION:**
1. Confirm buyer has valid ID, cashier's check or wire confirmation, and any required items
2. Get CDA (Commission Disbursement Authorization) signed by brokerage
3. Attend closing — in-person or remote
4. Witness buyers signing all closing documents
5. Confirm title transfer and key exchange
**OUTPUT:** Transaction Closed; Title Transferred to Buyers
**NEXT NODE(S):** BA-21
**TIMELINE:** Closing day
**PARALLEL:** No

***

### Phase 6: Post-Closing (Nodes BA-21 through BA-24)

***

**NODE: BA-21**
**PHASE:** Post-Closing
**TASK NAME:** Post-Closing Handoff & File Closure [PARALLEL GROUP]
**TRIGGER:** Closing complete[^1][^2]
**ACTOR:** Buyer's Agent
**ACTION (all run in parallel):**
- Provide home warranty paperwork to buyers
- Give all keys, garage openers, mailbox keys, and accessories to buyers
- Close out buyer's file with brokerage (submit all required documents)
- Send closing gift and thank-you to buyers
- Request online review/referral from buyers
- Update CRM with closed transaction data
- Follow up at 30/60/90 days post-closing to check in
**OUTPUT:** File Closed; Buyers Have All Property Materials; Brokerage Records Complete
**TIMELINE:** Within 48 hours of closing
**PARALLEL:** YES

***

## Part III: DAG Workflow Logic Reference

### Transaction Phase Map

| Phase | Listing Agent Nodes | Buyer's Agent Nodes | Key Decision Gates |
|-------|--------------------|--------------------|-------------------|
| Phase 1: Pre-Engagement | LA-01 – LA-05 | BA-01 – BA-05 | Seller agrees to list; Buyer has pre-approval |
| Phase 2: Pre-Listing / Search | LA-06 – LA-20 | BA-06 – BA-09 | Marketing approved; Target home identified |
| Phase 3: Offer | LA-24 – LA-26 | BA-10 – BA-12 | Offer accepted; Contract executed |
| Phase 4: Under Contract | LA-27 – LA-30 | BA-13 – BA-16 | Inspection resolved; Appraisal passed; CTC |
| Phase 5: Closing | LA-31 – LA-32 | BA-17 – BA-20 | Docs correct; Walk-through approved |
| Phase 6: Post-Closing | LA-33 | BA-21 | File closed |

### DAG Execution Rules

The following rules govern AI agent workflow orchestration when generating automated operating procedures from this SOP:

1. **Sequential Gates:** Nodes marked with `DECISION GATE` must be resolved before downstream nodes are activated. AI agents must evaluate the gate condition and route accordingly.[^1]
2. **Parallel Execution:** Nodes marked `[PARALLEL]` may be dispatched simultaneously by the AI orchestrator. A join node (the next sequential node) waits for all parallel tasks to complete before proceeding.
3. **Loopback Nodes:** Nodes that reference themselves (e.g., LA-22 repeating weekly, BA-08 continuous) represent scheduled or event-triggered loops. The AI agent should use time-based or event-based triggers to re-invoke these nodes.
4. **Error Handling / Branch Termination:** Decision branches that resolve to contract termination (LA-29b, BA-16b) should trigger a Termination Workflow: notify all parties, release earnest money per contract terms, update MLS/CRM, and close file.
5. **Communication Standard:** Every outbound communication node should append: *"Here is what to expect next and when..."* This is a required output attribute for all client-facing communication nodes.[^1]
6. **File Integrity:** All document nodes must verify completeness before passing to the next node. Missing signatures or documents trigger a hold state until resolved.[^1]
7. **Timeline SLA Enforcement:** AI agents should flag any node that exceeds its defined timeline and escalate to the supervising agent/broker.

### Parallel Node Groups Summary

| Group ID | Nodes | Phase | Join Condition |
|----------|-------|-------|---------------|
| PG-LA-01 | LA-02, LA-03, LA-04 | Pre-Listing Research | All three complete before LA-05 |
| PG-LA-02 | LA-09, LA-10 | Post-Meeting Prep | Both complete before LA-11 |
| PG-LA-03 | LA-13 sub-tasks | Due Diligence | All due diligence complete before LA-14 |
| PG-LA-04 | LA-15, LA-16 | Pre-Photo Staging | Both complete before LA-17 |
| PG-LA-05 | LA-27, LA-28, LA-29 | Under Contract | All resolved before LA-30 |
| PG-LA-06 | LA-33 sub-tasks | Post-Closing | All complete; file closed |
| PG-BA-01 | BA-13, BA-14, BA-15 | Under Contract | All resolved before BA-17 |
| PG-BA-02 | BA-17 sub-tasks | Pre-Closing | All complete before BA-18 |
| PG-BA-03 | BA-21 sub-tasks | Post-Closing | All complete; file closed |

***

## Part IV: Roles, Responsibilities & Escalation

### Agent Roles & Accountability

| Role | Primary Responsibility | Key Accountability |
|------|----------------------|-------------------|
| Listing Agent | Represent seller's interests; market property; negotiate sale | All LA nodes; seller communication; MLS accuracy |
| Buyer's Agent | Represent buyer's interests; identify and secure property | All BA nodes; buyer communication; contract deadlines |
| Transaction Coordinator (TC) | Manage file, documents, and timelines post-contract | Document completeness; deadline tracking |
| Broker/Supervising Broker | License holder; compliance; dispute escalation | Override authority; E&O compliance |
| Title/Escrow Officer | Clear title; disburse funds | Title commitment; closing disclosure |
| Lender | Qualify buyer; issue loan | Pre-approval; CTC issuance |
| Inspector | Identify property defects | Inspection report |
| Appraiser | Determine property value | Appraisal report |

### Escalation Matrix

| Issue Type | First Contact | Escalation | Final Authority |
|-----------|--------------|------------|----------------|
| Contract deadline missed | Transaction Coordinator | Listing/Buyer Agent | Broker |
| Inspection dispute unresolved | Buyer's Agent + Listing Agent | Broker mediation | Contract terms / Attorney |
| Appraisal below purchase price | Both Agents | Lender | Mutual negotiation |
| Title defect | Title Officer | Real Estate Attorney | Court (if necessary) |
| Client complaint | Agent | Broker | State RE Commission |

***

## Part V: Communication Standards

### Response Time SLAs

Adapted from Proforma CSR SOP communication standards:[^1]

| Communication Type | Response SLA | Channel |
|-------------------|-------------|---------|
| Client inquiry (phone/email) | 30–60 minutes for acknowledgment | Phone, Email, Text |
| Offer received | 2–4 hours for presentation to client | In-person, Phone, Email |
| Contract counter-offer | Per deadline (typically 24 hours) | E-sign platform + Phone |
| Inspection objection response | Per contract deadline | E-sign + Email |
| Weekly client update | Every 7 days | Phone call + Email summary |
| General client question | Same business day | Email or phone |

### Communication Principles

- End every communication with what to expect next and when[^1]
- No surprises — communicate all changes, issues, and new information proactively[^1]
- We do what we say we are going to do, when we say we are going to do it, and how we said we would do it[^1]
- Never ask a client for information you already have — check the file first[^1]
- Anticipate the client's next question and answer it before they ask[^1]
- All agreements must be in writing — verbal commitments are insufficient

### Error Correction Protocol

Adapted from Proforma COE (Correction of Errors) framework:[^1]

When an error occurs in any transaction node:
1. Acknowledge the issue with the affected party promptly
2. Provide a COE document: what happened, why it happened, and the corrective action taken
3. Update the SOP node to prevent recurrence
4. Document the error in the transaction file
5. Notify broker if error has legal or financial consequences

***

## Part VI: Tools & Technology Reference

| Tool Category | Purpose | Used In Nodes |
|--------------|---------|--------------|
| MLS Platform | Listing input, status updates, comp research | LA-03, LA-19, LA-23, LA-33 |
| CRM / Transaction Management | File management, deadlines, communication logs | LA-11, BA-05, all phases |
| E-Sign Platform (DocuSign/DotLoop) | Contract execution, addenda, disclosures | LA-12, BA-10, BA-12 |
| Showing Management (ShowingTime) | Appointment scheduling, feedback automation | LA-16, LA-21, BA-06 |
| MLS Search Alerts | Automated buyer property matching | BA-05, BA-08 |
| Title/Escrow Platform | Closing document management | LA-26, BA-12, BA-17 |
| Photography/3D Tour Tools | Marketing asset creation | LA-17 |
| Appraisal Management System | Appraisal ordering and tracking | LA-29, BA-16 |
| Lender Portal | Loan status, document submission | BA-04, BA-15 |

***

## Appendix A: Document Checklist — Listing Side

| Document | When Required | Node |
|----------|--------------|------|
| Listing Agreement | Pre-listing | LA-12 |
| Seller's Disclosure | Pre-listing | LA-12 |
| Lead-Based Paint Disclosure | Pre-1978 homes | LA-12 |
| HOA Bylaws & Financials | Pre-listing | LA-13 |
| Transferable Warranties | Pre-listing | LA-13 |
| Earnest Money Receipt | Under contract | LA-26 |
| Inspection Resolution Addendum | Under contract | LA-28 |
| Appraisal Report | Under contract | LA-29 |
| Closing Disclosure (CD) | Pre-closing | LA-31 |
| CDA (Commission Disbursement Authorization) | Closing day | LA-32 |

## Appendix B: Document Checklist — Buyer's Side

| Document | When Required | Node |
|----------|--------------|------|
| Buyer Representation Agreement | Pre-search | BA-03 |
| Pre-Approval Letter | Pre-offer | BA-04 |
| Seller's Disclosure | Post-contract | BA-12 |
| HOA Bylaws | Post-contract | BA-12 |
| Home Inspection Report | Under contract | BA-13 |
| Inspection Objection/Resolution | Under contract | BA-14 |
| Appraisal Report | Under contract | BA-16 |
| Closing Disclosure (CD) | Pre-closing | BA-18 |
| Final Walk-Through Sign-Off | Day of closing | BA-19 |
| Home Warranty Certificate | Post-closing | BA-21 |

***

*This SOP is a living document. Any agent who identifies an outdated or incorrect procedure is responsible for notifying the supervising broker. The broker is responsible for maintaining this document and communicating all revisions to the agent team.*[^3]

---

## References

1. [ProForma-SOP-CSR-internal-6.8.22.docx](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/55954620/22d64e4b-2fd4-499c-8dab-a8208a7dac3f/ProForma-SOP-CSR-internal-6.8.22.docx?AWSAccessKeyId=ASIA2F3EMEYERPWO4HSJ&Signature=scR3GvuodFMk9fVWRE0XZz%2F3VF8%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEIz%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJHMEUCIARxEJ4ffoRqxNKkRXGtn97yjUI0JwyiINrPCd%2Fr0Bh%2FAiEAwGVoy4r6q3Y9x%2Fs69J6lHtlz29iAXP6NtOvHbpWJxB8q8wQIVRABGgw2OTk3NTMzMDk3MDUiDLWIs%2FDxNjLFbzAIYirQBKDi1YapR9Tk7t431AhW%2FqEqXGLdWnflw0QJ0c1QIOYRkyt%2Fl4Zqx3YyFtdZjWJHxvR%2F4KIFAbqCBOorx1HTHAMC%2FQW%2FZrGlDQGJs3y%2FA6n%2BNeDsZrNMbWbOxjb9PTkQbl33gUQNuu9UhL4iuQLdUdeQlHzUET%2FOsJxvXoqSXIuelKa6BZsnPi6jpq484gY9pDk50te7HLj0yBB7h4eL%2BLZrhBXntzfrFzcvrZ4WWV3gTL53DTQvASAw6tlXhxkKAU%2F3wIxr28dwAFbb%2BO%2F1sLZ%2Bk%2FWtaJPt3Sg9s4AlOVEU%2FJ9%2F5OCVAcPnafXUJ60utFnusnI3Nulv8uAObK4WiheumMJ34NCFFo4VU2whlbqL66DIcJhtdNQ89kYUp2eWPV%2Blih2ZgeypIMwIZ0O%2FwzzbMY%2FTwn7VZmacakG71xfpZc2byCjBp0igZc2ZVEyzFqmSlA6N4S9HVcskMuvUiEPZ%2F3ALIcCMdRXe%2FCh1HiVOInsmcSnRVG3crYcg4OXE79Wldqrzy5sg3OATK7bTVG8mGvKpPZ92wd0fykjTYlv9He60xFZ9LxXTNSu9mHZJBlpQhU7WHjQkuAzwk3n1fq2Tg3H%2FCIbBkUcoZQxzSplKp2%2Br1yjVd6P6kAjMi%2BX3WDwoTELNqIK3vP4eQckBbl4Y8s5sa7GgOZ8f3eAzKQ4O1Yq2T4LFZZQKjSgMESfXwe2aJueZivaRioEQHTzN7GX09Yn%2FIKfcPFou%2Bn%2B654O6Y%2FmWhyVCD%2BLHrARRwPJeepSnsmvQXX1JAnQKfZlponMwqMmkzwY6mAEribmE6uzicwC%2FioauE0mgTJjkYX3rV7ZruO61Er%2FvUtrcLX1BDStUMngrTCilBfnsIgc%2F2bVLySTz2kp2Fdi8Up%2FDgDqyitG56oaTlSC2IgbeR2NimoYEd%2B1q%2FWvGWJa961P2BAVi3w0dYMPrsuW7IsB1Gw4Mni7u%2BccKDHm7BZnx9NH8rBpbNOt4or2%2F8pMQO3oRPCuXKA%3D%3D&Expires=1776890491) - Client Request (E-mail or Phone)

-   Response within 30 minutes to an hour with expectation

-   12...

2. [Real-Estate-RE-detailed-agent-tasks.docx](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/55954620/3826cd8a-a172-4e4d-8d15-8f0748487931/Real-Estate-RE-detailed-agent-tasks.docx?AWSAccessKeyId=ASIA2F3EMEYERPWO4HSJ&Signature=ZPbf4EyfeO96ecnAkkBW%2FM3vNvA%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEIz%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJHMEUCIARxEJ4ffoRqxNKkRXGtn97yjUI0JwyiINrPCd%2Fr0Bh%2FAiEAwGVoy4r6q3Y9x%2Fs69J6lHtlz29iAXP6NtOvHbpWJxB8q8wQIVRABGgw2OTk3NTMzMDk3MDUiDLWIs%2FDxNjLFbzAIYirQBKDi1YapR9Tk7t431AhW%2FqEqXGLdWnflw0QJ0c1QIOYRkyt%2Fl4Zqx3YyFtdZjWJHxvR%2F4KIFAbqCBOorx1HTHAMC%2FQW%2FZrGlDQGJs3y%2FA6n%2BNeDsZrNMbWbOxjb9PTkQbl33gUQNuu9UhL4iuQLdUdeQlHzUET%2FOsJxvXoqSXIuelKa6BZsnPi6jpq484gY9pDk50te7HLj0yBB7h4eL%2BLZrhBXntzfrFzcvrZ4WWV3gTL53DTQvASAw6tlXhxkKAU%2F3wIxr28dwAFbb%2BO%2F1sLZ%2Bk%2FWtaJPt3Sg9s4AlOVEU%2FJ9%2F5OCVAcPnafXUJ60utFnusnI3Nulv8uAObK4WiheumMJ34NCFFo4VU2whlbqL66DIcJhtdNQ89kYUp2eWPV%2Blih2ZgeypIMwIZ0O%2FwzzbMY%2FTwn7VZmacakG71xfpZc2byCjBp0igZc2ZVEyzFqmSlA6N4S9HVcskMuvUiEPZ%2F3ALIcCMdRXe%2FCh1HiVOInsmcSnRVG3crYcg4OXE79Wldqrzy5sg3OATK7bTVG8mGvKpPZ92wd0fykjTYlv9He60xFZ9LxXTNSu9mHZJBlpQhU7WHjQkuAzwk3n1fq2Tg3H%2FCIbBkUcoZQxzSplKp2%2Br1yjVd6P6kAjMi%2BX3WDwoTELNqIK3vP4eQckBbl4Y8s5sa7GgOZ8f3eAzKQ4O1Yq2T4LFZZQKjSgMESfXwe2aJueZivaRioEQHTzN7GX09Yn%2FIKfcPFou%2Bn%2B654O6Y%2FmWhyVCD%2BLHrARRwPJeepSnsmvQXX1JAnQKfZlponMwqMmkzwY6mAEribmE6uzicwC%2FioauE0mgTJjkYX3rV7ZruO61Er%2FvUtrcLX1BDStUMngrTCilBfnsIgc%2F2bVLySTz2kp2Fdi8Up%2FDgDqyitG56oaTlSC2IgbeR2NimoYEd%2B1q%2FWvGWJa961P2BAVi3w0dYMPrsuW7IsB1Gw4Mni7u%2BccKDHm7BZnx9NH8rBpbNOt4or2%2F8pMQO3oRPCuXKA%3D%3D&Expires=1776890491) - SO...YOU WANT TO BE A REALTOR

There is a lot of talk in the news about real estate agent commission...

3. [SOP_Template.doc](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/55954620/696b13c0-3b75-4bb6-b9f7-78dcc618e09b/SOP_Template.doc?AWSAccessKeyId=ASIA2F3EMEYERPWO4HSJ&Signature=j3R6L2j0jgYFo6as%2BMkjt%2BZbdP4%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEIz%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJHMEUCIARxEJ4ffoRqxNKkRXGtn97yjUI0JwyiINrPCd%2Fr0Bh%2FAiEAwGVoy4r6q3Y9x%2Fs69J6lHtlz29iAXP6NtOvHbpWJxB8q8wQIVRABGgw2OTk3NTMzMDk3MDUiDLWIs%2FDxNjLFbzAIYirQBKDi1YapR9Tk7t431AhW%2FqEqXGLdWnflw0QJ0c1QIOYRkyt%2Fl4Zqx3YyFtdZjWJHxvR%2F4KIFAbqCBOorx1HTHAMC%2FQW%2FZrGlDQGJs3y%2FA6n%2BNeDsZrNMbWbOxjb9PTkQbl33gUQNuu9UhL4iuQLdUdeQlHzUET%2FOsJxvXoqSXIuelKa6BZsnPi6jpq484gY9pDk50te7HLj0yBB7h4eL%2BLZrhBXntzfrFzcvrZ4WWV3gTL53DTQvASAw6tlXhxkKAU%2F3wIxr28dwAFbb%2BO%2F1sLZ%2Bk%2FWtaJPt3Sg9s4AlOVEU%2FJ9%2F5OCVAcPnafXUJ60utFnusnI3Nulv8uAObK4WiheumMJ34NCFFo4VU2whlbqL66DIcJhtdNQ89kYUp2eWPV%2Blih2ZgeypIMwIZ0O%2FwzzbMY%2FTwn7VZmacakG71xfpZc2byCjBp0igZc2ZVEyzFqmSlA6N4S9HVcskMuvUiEPZ%2F3ALIcCMdRXe%2FCh1HiVOInsmcSnRVG3crYcg4OXE79Wldqrzy5sg3OATK7bTVG8mGvKpPZ92wd0fykjTYlv9He60xFZ9LxXTNSu9mHZJBlpQhU7WHjQkuAzwk3n1fq2Tg3H%2FCIbBkUcoZQxzSplKp2%2Br1yjVd6P6kAjMi%2BX3WDwoTELNqIK3vP4eQckBbl4Y8s5sa7GgOZ8f3eAzKQ4O1Yq2T4LFZZQKjSgMESfXwe2aJueZivaRioEQHTzN7GX09Yn%2FIKfcPFou%2Bn%2B654O6Y%2FmWhyVCD%2BLHrARRwPJeepSnsmvQXX1JAnQKfZlponMwqMmkzwY6mAEribmE6uzicwC%2FioauE0mgTJjkYX3rV7ZruO61Er%2FvUtrcLX1BDStUMngrTCilBfnsIgc%2F2bVLySTz2kp2Fdi8Up%2FDgDqyitG56oaTlSC2IgbeR2NimoYEd%2B1q%2FWvGWJa961P2BAVi3w0dYMPrsuW7IsB1Gw4Mni7u%2BccKDHm7BZnx9NH8rBpbNOt4or2%2F8pMQO3oRPCuXKA%3D%3D&Expires=1776890491) - **ABC Company Support Center**

**Table of Contents
**

5
General Information

5
Purpose of Standard...

