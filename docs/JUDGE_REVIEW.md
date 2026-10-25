# Independent judge-experience review

Reviewed 2026-10-24 (Asia/Shanghai) by a separate review agent using the README, generated outputs, and an actual headless browser. **The offline developer demonstration is usable. The competition submission is not ready.**

## Commands independently executed

From the repository root:

| Command | Observed result |
|---|---|
| `python -m patchcourt demo --output outputs/judge-check` | Exit 0; 16 cases: 3 PASS, 11 FAIL, 1 INCONCLUSIVE, 1 NEEDS_REVIEW; live inference false |
| `python -m patchcourt serve outputs/judge-check --port 8766` | Launched by the browser QA script; loopback page and report loaded successfully; owned process stopped afterward |
| `python -m unittest discover -s outputs/judge-check -p test_regression.py` | One exported regression test passed |
| `python -m patchcourt --help` | CLI commands and scope described successfully |
| `python -m patchcourt check examples/upgrade/baseline.json examples/upgrade/candidate.json --output outputs/judge-example-failure` | FAIL, expected exit 1 |
| `python -m patchcourt check examples/upgrade/baseline.json examples/upgrade/baseline.json --output outputs/judge-example-control` | PASS, exit 0 |
| `python -m patchcourt inspect patchcourt --dependency langchain-nvidia-ai-endpoints --from-version 1.4.2 --to-version 1.4.3 --output outputs/judge-check/inspection.json` | NEEDS_REVIEW, native Python exit 2; inspection does not invent a defect from a version change |
| `python -m patchcourt verify outputs/judge-check` | Integrity PASS; explicitly does not authenticate provenance |
| `node tests/browser_viewer_check.cjs` | 14 browser checks passed; saved screenshots and results |

The demo FAIL verdicts describe deliberately reproduced defects and mutations; they are not demo-command failures. Source-boundary repair verification is separate from that verdict. The screenshot/exported report is genuine output from this local execution, not a fabricated UI fixture.

## Browser integration and visual review

Used installed Chrome in headless mode at desktop 1440×1100 and mobile 390×844. No package/browser installation or visible window was required. The native Node HTTP client was used after the initial fetch-based QA client hit a Node/Undici assertion; the failing harness attempt was not classified as a product defect. A sandboxed loopback attempt was unavailable; the successful run used approved local execution permissions.

The 14 checks covered real report auto-loading, all 16 case entries, declared summary counts, first source case selection, visible offline qualification, repair/replay value 21, explicit non-model repair origin, switching cases and finding panes, BLOCKED lab state, 16 acceptance gates, desktop/mobile horizontal overflow, file upload, JSON export preserving the run ID, and absence of runtime exceptions. [Machine-readable results](../evidence/browser/qa-results.json) identify the exact exported report and browser version.

Reviewed [desktop protocol](../evidence/browser/desktop-protocol.png), [desktop repair](../evidence/browser/desktop-repair.png), and [mobile findings](../evidence/browser/mobile-findings.png) screenshots. The initial desktop layout stretched the evidence panel to the full 16-case list height, leaving excessive empty space. This was fixed with a scrollable case list and independent panel height, and the browser checks were rerun successfully.

The headline communicates a concrete failure quickly. Protocol, findings, repair/replay, and provenance are separately accessible. The viewer does not initiate provider requests. Payload differences are explicitly distinguished from semantic-defect classifications. JSON values are rendered as text; earlier synthetic DOM checks additionally confirmed HTML/event-handler strings remain inert and malformed/deep report inputs are rejected.

## Review findings and disposition

| Finding | Disposition |
|---|---|
| Original README did not introduce PatchCourt | Fixed: current README leads with the product, runnable demo, and limitations while retaining ACV instructions |
| README example-trace link initially targeted a missing directory | Fixed: actual example files and their README were added; failure/control commands above both executed correctly |
| Unverified integration between generated report and viewer | Resolved for this offline report by actual Chrome loading, interactions, upload, and export |
| Desktop panel height grew with the entire case list | Fixed and visually rechecked |
| Full NVIDIA SDK evidence differs from bundled inert-type demo evidence | Properly distinguished in README and evidence/full-sdk/README.md; this reviewer inspected those records but did not repeat package installation or the full-SDK experiment |
| Keyboard and assistive-technology behavior | Native controls, focus styling, labels and status region exist; complete keyboard/screen-reader traversal remains untested |
| Fresh machine installation and published judge access | Not independently verified in this review |

## Unresolved competition blockers

- No genuine NVIDIA/Nemotron response through Nebius is evidenced by this offline run.
- No live Nemotron-generated test or model repair contribution is established.
- No actual Nebius reliability experiments or evidence-backed platform feedback findings are established.
- Tavily functionality/benefit is not live demonstrated.
- Authenticated Devpost field requirements and final feedback-field completion remain unverified.
- Public YouTube video and durable public judge-accessible release URL were not supplied to this reviewer.
- Personal eligibility and final entry approval are outside this local review.

These are acceptance blockers, not reasons to mislabel the offline product as broken. Continue to show blocked live gates honestly. The browser result establishes usability of this static test build; it does not establish competition eligibility, universal adapter coverage, model quality, or award likelihood.
