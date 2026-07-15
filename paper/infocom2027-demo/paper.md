# INFOCOM 2027 Demo — Handoff / Progress Notes

> Self-contained handoff so any Claude session can continue without the original chat.
> Last updated: 2026-07-15. Author: labry@etri.re.kr (ETRI).

## 0. TL;DR
We are writing a **2-page IEEE INFOCOM 2027 *demo-track* abstract**. Headline idea =
**"Cross-Domain Conflict Guard"** on the existing NCOF prototype. Draft (LaTeX/IEEEtran, with
two TikZ figures) is at [`conflict-guard-abstract.tex`](./conflict-guard-abstract.tex) in this
folder. Mental model: **it's a DEMO — acceptance comes from a working live system + crisp story +
one fresh sliver + correct framing, NOT from a big experiment / metrics table.**

## 1. Venue & deadline
- **IEEE INFOCOM 2027, Demo track** (a.k.a. posters/demos). 2-page IEEE abstract, **single-blind**
  (author names required), **in-person mandatory** (no virtual/substitute), accepted demos go to
  IEEE Xplore.
- Deadline **~January 2027** (2026 cycle was Jan 8–15; 2027 CFP not posted yet — re-check
  `infocom2027.ieee-infocom.org`). Conf ~May 2027, Honolulu.
- Main track was ruled out: its deadline was end-July 2026 and ~19% accept — too heavy for a
  "simple idea + simple experiment".

## 2. The idea (headline): Cross-Domain Conflict Guard
NCOF (an NWDAF-extended analytics **+ control** function) drives **two heterogeneous closed loops
from one signal**: RAN energy (gNB2 `DEEP_SLEEP`/`ACTIVE` via RICF) and core QoS
(`gbrDl`/`mbrDl` via PCF). Because both decisions originate in one function and hit the **same
cell**, they can conflict: *you cannot guarantee QoS on a cell you are simultaneously putting to
sleep* — a live SLA-violation window between the two commands.

**The Guard** = two lightweight stages around the existing decision path:
1. **Subscribe-time semantic check (LLM):** reads each new subscription + existing ones + a
   1-paragraph summary of what each drives → conflict verdict + rationale + suggested precedence.
   Catches antagonism no exact/schema match can (the RAN-power and QoS subscriptions share no
   field; the incompatibility is *semantic*).
2. **Pre-actuation predicate:** a guard between decision engine and notification senders keeps a
   pending-action table keyed by cell; a predicate over `{power_action, qos_action}` flags
   collisions; resolver applies declared precedence (defer sleep until the gbr grant lapses) via a
   **deferred-action queue**. ~150 lines between existing components.

**Why it's the pick** (chosen by an area-chair analysis over 8 candidate ideas): best exploits the
platform's one genuinely unique asset — two cross-domain loops from ONE function — which is the
under-occupied sliver. Most visceral, hardest-to-fake booth hook. Small build (loops/models/engine
already exist).

## 3. Fallback headline: SemDedup
LLM lens detecting **subscription↔subscription semantic overlap** across consumers, collapsing N
redundant collection+inference pipelines into 1, proven **behavior-preserving** live via the two
loops. Cleanest unpublished sliver; more defensible if reviewers push back on conflict-mitigation
crowding. Same substrate → build both partially at low marginal cost. Keep as co-strong fallback.
Supporting panels (tiny build, optional): Analytics-Cost Meter, WhyNCOF.
Do **not** submit "Two-Domain Transaction (atomic rollback)" alongside Conflict Guard — reviewers
see them as one idea.

## 4. Why this direction (from 2 verified research passes + adversarial review)
- **All candidate ideas are *incremental*, not fresh-method.** Demo track does not trade on method
  novelty → **claim systems/integration novelty + live proof**, and say so.
- **Avoid as headline (crowded/preempted):** RL/DRL base-station/cell **sleeping** for energy
  saving (ToN'21; a 2024 IEEE survey; O-RAN energy DRL demo arXiv:2410.14021; live RL xApp REAL
  arXiv:2502.00715; and **ETRI's own** ETRI Journal 2024, Park et al.). LLM **intent→subscription
  generation** (LLM-Enabled NWDAF arXiv:2606.11877; IntAgent arXiv:2601.13114).
- **Fresh-ish slivers we aim at:** cross-domain (RAN power + core QoS) coordination from one
  analytics function; subscription↔subscription semantic dedup; **behavior-preserving** proofs via
  live downstream loops.

## 5. Framing musts (accept-or-die points — put these in the paper)
1. **NCOF is NOT a standardized term** (ETRI-coined). Map it to **NWDAF** (analytics) /
   O-RAN RIC rApp-xApp (control) / OAM-SON. Pre-empt "why not NWDAF + an O-RAN ES rApp?".
2. **Cite & differentiate:**
   - 3GPP **DCCF** (TS 23.288 / TS 29.574): exact/rule-based *data-collection* dedup; cannot see a
     cross-domain conflict that lives only in subscription semantics.
   - **O-RAN conflict mitigation** (Wadud arXiv:2411.03326, 2024 — RAN-only, sim; PACIFISTA, IEEE
     TMC 2025): within-RAN, among RAN apps. Ours is cross-domain, in the CN analytics function.
   - **LLM-for-NWDAF** (arXiv:2606.11877): intent→subscription; we run the inverse.
3. **"Why LLM, not schema/ontology match?"** — the two subscriptions share no comparable field;
   show cases (synonymy/paraphrase/cross-vocabulary) that string/schema matching provably misses.
4. **Behavior-preserving:** the guard changes only *timing* of conflicting commands, not the
   control outcome; the two live loops are the proof (they keep actuating).
5. Lead with the **QoS-violation window**, not the arbitration mechanism.
6. **Re-run the novelty web search before submission** (slivers were open only as of mid-2026).

## 6. The running platform ("두두원 시나리오")
`두두원` = partner company **㈜두두원**; the running energy-saving closed-loop PoC is the scenario
used for the 두두원 integration. Repo layout: `prototype/` (servers + Vue UI), `generated/`
(OpenAPI FastAPI stubs), `gym_for_ncof/` (RL).
- **5 servers** (see `prototype/README.md`): NCOF `:8000` (`nncof-server`), SMF/UPF `:8001`
  (`nsmf-server`), AF `:8002` + RICF `:8003` (`nnef-server`, NEF mock = AF+RICF), PCF `:8004`
  (`callback-server`). Subscription injection via `prototype/api-clients/`.
- **Two live loops:** (1) gNB2 `DEEP_SLEEP`↔`ACTIVE` when WLAN DL throughput crosses ~500 Mbps →
  RICF echoes `cell_power_state`; (2) `qosParamSet` (`gbrDl`/`mbrDl`) to PCF.
- **Engine hot-swap:** `NCOF_DECISION_ENGINE=rule|rl` (default `rule`). RL = PPO policy JSON from
  `gym_for_ncof` (`models/gnb2_policy.json`); reward economics make optimal threshold ≈500 Mbps, so
  RL re-learns the rule from reward alone.
- **Dashboard:** `prototype/nncof-ui/` = SignalViz (Vue3+Vite, dev `:5173`, proxies to NCOF `:8000`,
  WebSocket `/api/ws`).

## 7. Template papers (real, verified, INFOCOM demo-track)
- **PRIMARY — INFOCOM'26:** *"A Live Demo of Real-Time Congestion Detection and QoD Control for
  Holographic XR Traffic"*, AbdelNabi et al. (i2CAT/UV/Ericsson), IEEE INFOCOM 2026 (DOI
  10.1109/INFOCOM59046.2026.11571471, pp.1878–1879). PDF was downloaded to repo root:
  `A_Live_Demo_of_Real-Time_Congestion_Detection_and_QoD_Control_for_Holographic_XR_Traffic.pdf`.
  - Closest match: closed-loop **PCF `AsSessionWithQoS` + 5QI slice switching** (= our QoS loop),
    a detection fn subscribing to per-UE KPIs, Grafana dashboard with "CONGESTION DETECTED!!" +
    before/after panels. Staging trick we copied: **QoD activation deliberately delayed to expose
    the impact** (= our Guard OFF→ON).
  - Structure: Abstract → I. Intro (related work folded in) → II. System Architecture (Fig.1) →
    III. Demo Description and Results (Fig.2 = testbed + rendered shot + dashboard screenshot,
    results woven in) → Conclusion → Refs. Two figures do the heavy lifting; no separate
    related-work / evaluation / requirements section.
- **SECONDARY — INFOCOM'25:** *"Interactive Explanation and Steering of DRL Agents ... with
  SymbXRL"* (IMDEA). Open PDF at IMDEA dspace. Borrow its **`Technical Setup`** (doubles as
  requirements) and its **second-person booth walkthrough** with an interactive **steering toggle**
  (parallels our conflict-inducing toggle), and its numbered figure-callout convention.
- (3rd: BeGREEN, INFOCOM'25 WKSHPS demo, arXiv:2606.05000 — same i2CAT style; superseded by the two above.)

## 8. Current abstract state
File: [`conflict-guard-abstract.tex`](./conflict-guard-abstract.tex) (IEEEtran conference, restructured to the XR'26 template).
- Sections: Abstract → Index Terms (incl. `Demo`) → I. Introduction (motivation + "Relation to
  prior work" folded in) → II. System Architecture (Fig.1, numbered callouts 1–5; LLM+predicate =
  our novel content lives here) → III. Demo Description and Results (A. Technical setup /
  B. Dashboard flow and control [OFF = deliberately-delayed exposure, ON = replay] / C. What the
  demo shows) → Conclusion → References (6).
- **Fig.1** = architecture (TikZ, `figure*`, 2-col span). **Fig.2** = SignalViz conflict-timeline
  OFF/ON (TikZ; **placeholder** — a `\includegraphics` line is commented in for a real screenshot).
- Two synced copies (keep both in sync when editing):
  - main workspace: `/home/labry/git/ncof_generated/paper/infocom2027-demo/conflict-guard-abstract.tex`
  - worktree (branch `claude/ncof-llm-nwdaf-overlap-b5aff0`): `.claude/worktrees/ncof-llm-nwdaf-overlap-b5aff0/paper/infocom2027-demo/`

## 9. Remaining tasks (prioritized)
**Paper polish**
- [ ] Fill `[Author Names]`.
- [ ] Replace Fig.2 schematic with a **real SignalViz screenshot** (uncomment `\includegraphics`);
      demo track rewards a real screenshot.
- [ ] Add `\section*{Acknowledgment}` (funding).
- [ ] **Compile** (`pdflatex` ×2; needs IEEEtran.cls + tikz) and verify it fits **≤2 pages** and
      both TikZ figures render. If it overflows, trim §II/§III prose or make Fig.1 single-column.
      (No LaTeX in the last working env, so this was NOT yet verified.)

**Build (this is what actually raises accept odds — it's a demo)**
- [ ] Implement the **~150-line guard lens**: pending-action table (keyed by cell) + compatibility
      predicate over `{power_action, qos_action}` + deferred-action queue + precedence policy,
      inserted between the decision engine output and the RICF/PCF notification senders.
- [ ] **LLM subscribe-time checker** module (new+existing subscriptions → conflict verdict);
      pin/cache outputs + human-approve gate for on-floor determinism.
- [ ] SignalViz **conflict panel** (registry + conflict timeline + OFF/ON toggle) and a
      subscription-injection path for the conflict.
- [ ] **Conflict-case set**: same-cell sleep-vs-QoS collisions + semantic cases string/schema match
      misses (for the "why LLM" defense).
- [ ] Rehearse the WLAN-drag + premium-QoS-click choreography; keep injected subs in a reconcilable
      family so behavior-preservation actually holds live.

## 10. Key citations (with URLs)
- 3GPP TS 23.288 (NWDAF/DCCF) — https://www.tech-invite.com/3m23/toc/tinv-3gpp-23-288_h.html ; DCCF Ndccf TS 29.574.
- Wadud et al., "xApp-Level Conflict Mitigation in O-RAN...", arXiv:2411.03326 (2024) — https://arxiv.org/abs/2411.03326
- Brach del Prever et al., "PACIFISTA: Conflict Evaluation and Management in Open RAN", IEEE TMC 2025.
- 3GPP TR 38.864 (NES, Rel-18) — https://www.tech-invite.com/3m38/toc/tinv-3gpp-38-864_a.html
- Daniel et al., "LLM-Enabled NWDAF...", arXiv:2606.11877 (2026) — https://arxiv.org/abs/2606.11877
- Template PRIMARY: XR QoD demo, IEEE INFOCOM 2026, pp.1878–1879 (PDF in repo root).
- Template SECONDARY: SymbXRL demo, IEEE INFOCOM 2025 — IMDEA dspace open PDF.
- BeGREEN demo, INFOCOM'25 WKSHPS — https://arxiv.org/pdf/2606.05000

## 11. Pointers
- Repo: `ncof_generated`. Current branch: `claude/ncof-llm-nwdaf-overlap-b5aff0` (paper is untracked; not committed).
- Auto-memory (same machine): `~/.claude/projects/-home-labry-git-ncof-generated/memory/infocom2027-demo-conflict-guard.md`.
