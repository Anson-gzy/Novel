# Handoff: Love, Victor — Interactive Fiction (Data Preparation & Canon Audit)

**Date**: 2026-09-29  
**Workspace**: `l_victor/`  
**Transcript Archive**: `Love-Victor-Transcripts/` (3 Seasons, 28 Episodes, 603,768 characters)  
**Status**: Data Preparation & Canon Audit Completed. Novel drafting has **not yet started**.

---

## 1. Project Overview & Current State

The goal of this project is to adapt the complete television series *Love, Victor* (Hulu) into a high-fidelity, choice-driven interactive novel from Victor Salazar's first-person perspective, styled with the Vercel Geist Light design system.

### Current Status
- **Drafting Status**: **Not yet started**. All draft chapters, experimental outlines, and preliminary HTML templates have been cleared. The workspace `l_victor/` is clean and ready for the official opening.
- **Completed Work**: All focus in this initial phase was dedicated to **raw transcript scraping, data cleaning, and canonical scene-by-scene auditing**.

---

## 2. Prepared Assets & Verified Ground Truth

### 1. Complete Transcript Library
All 28 episodes across Seasons 1–3 were scraped, cleaned, and organized into structured Markdown files in:
`Love-Victor-Transcripts/`
- `Season 1/` (Episodes 1–10)
- `Season 2/` (Episodes 1–10)
- `Season 3/` (Episodes 1–8)

### 2. Verified Canonical Beats for Season 1, Episode 1 (`S01E01 - Welcome to Creekwood`)
The incoming agent must follow the verified transcript lines without skipping scenes or hallucinating actions:
1. **Intro Framing Voiceover**: Victor in his bedroom writing his raw Instagram message to Simon Spier (*"Dear Simon... today was my first day at Creekwood... and I just want to say screw you. Screw you for having the world's most perfect, accepting parents... 24 hours ago, I was actually looking forward to having a fresh start"*).
2. **24 Hours Earlier (Street Arrival)**: Salazars pull up on Brasstown Street. Armando boasts about middle management. Pilar sobs to her Texas boyfriend (*"My kidnappers are making me hang up. Send help"*). Adrian needs to pee. Felix Westen arrives from apartment 1B, introduces himself, and gives Victor the walkie-talkies (*"Where's your sense of whimsy?"*), setting a 7:00 AM walk.
3. **The Apartment & Texas Flashbacks**: Armando and Isabella admire the new home. Flashback to high school (friends teasing Ethan for ordering salad: *"Aunt Ethan"*) and church (Isabella talking to salon stylist, Armando calling him *"flojito"*). Next morning: Isabella looking for a place to hang the crucifix (*Pilar: "Probably not nailed to a cross"*), morning greetings, Felix knocks at 6:40 AM (waited 5 minutes outside door).
4. **Creekwood Morning**: Felix orientation. VP Ms. Albright (drama teacher promoted because former VP Mr. Worth was bit by a monkey in India and quarantined in Delhi; tells Victor the Simon carnival Ferris wheel legend). Lake Meriwether camera ambush for *Creek Secrets* (*"Are you cuffed?"*). Mia Brooks steps in to save Victor; Victor jokes about kneeling on the floor for the piano lesson flyer, making Mia blush. Felix's reaction. Benji compliments Victor's vintage Nike Cortezes.
5. **Gym & Basketball Tryouts**: Locker room casual homophobia. Andrew's shirtless tease (*"You like what you see?"*). Scrimmage jumper swish. Coach Ford (24 years, 0 championships) recruits Victor. Andrew claims starting point guard. The $500 fee sheet shock.
6. **Hallway Brawl & Escalation**: Pilar kicking vending machine (*"Dora in thrift store"*), Mia rescues snack and comforts Pilar. Random guy reveals Andrew's GoFundMe for the poor kid. Hallway fight: Victor slams Andrew into lockers. Benji pulls Victor away (*"Hey! You okay?"*). Lake posts on *Creek Secrets*. Victor snaps at Felix (*"We're not friends!"*).
7. **Evening Breakdown**: Home to parents screaming over Pilar's detention (shoved a girl into a brick wall). Victor covers up his bad day. Talk with mother about marriage struggles. Victor sends Simon the Instagram DM. Victor uses the walkie-talkie from his windowsill to apologize to Felix.
8. **Winter Carnival Climax**: Victor and Felix at carnival (cider & churros). Salazar family arrives. Simon's audio reply arrives (*"Maybe somewhere within the halls of that school, you'll find the person who will help you become who you are"*). Victor sees Benji with his boyfriend Derek. Victor asks Mia onto the Ferris wheel (*"Would you wanna ride the Ferris wheel with me?"*). Mia accepts.

---

## 3. Architecture & Delivery Constraints for Incoming Agents

1. **Strict 1:1 Transcript Fidelity**:
   - Zero hallucination. Do not alter locations, character actions, or skip canonical family moments (such as the crucifix scene or the India monkey quarantine joke).
2. **Modular Standalone Single-Page HTML**:
   - Each section must live in its own independent HTML file under the **Vercel Geist Light** design system (`#ffffff` background, `#fafafa` surface cards, `#eaeaea` 1px borders, Geist typography).
   - No backward recaps or redundant descriptions. Each section carries only the active scene beat.
3. **Diamond Branching Model (Convergence)**:
   - Provide meaningful choices at designated decision nodes (influencing Victor's mindset, internal monologues, dialogue tone, and relationship metrics).
   - Major plot milestones naturally converge back to canon events at pinch points (such as the Winter Carnival Ferris wheel climax).
4. **Hide Canonical Labels**:
   - Never mark or reveal which option is "canon" or "official script". Keep all choices neutral to protect player suspension of disbelief.
5. **Language & Pacing**:
   - Fast-paced, concise teenage American English (first-person POV: Victor Salazar). Avoid slow, repetitive scene padding.

---

## 4. Next Immediate Step

When the operator is ready, begin drafting the opening scene (**`section-1.1.html`**) from the clean workspace:
- Ground truth script: `Love-Victor-Transcripts/Season 1/S01E01 - Welcome to Creekwood.md`
- Target destination: `l_victor/`
- Start at Beat 1 & Beat 2 (The framing device and the Brasstown street arrival).

---

## 5. Suggested Skills

- **`interactive-fiction`**: For branch-and-bottle design, relationship state tracking, and choice node formatting.
- **`novel-writer`**: For authentic first-person POV control, natural teenage voice, and scene pacing.
- **`verceldesign`**: For strict compliance with the Geist Light aesthetic tokens (monochrome, high-contrast typography, minimal cards).
