# Submission acceptance checklist

Updated **2026-10-26, Asia/Singapore** (official rules reviewed October 25). This is a release gate, not a declaration of eligibility or an entry receipt. The entrant has selected the Nebius × NVIDIA event and will supply Nebius access. DeepSeek/GLM development calls cannot close the required-platform gate.

The deadline is **2026-10-31 01:00 SGT** (October 30, 10:00 PDT). Keep free judge access available through **2026-12-16 04:00 SGT** (December 15, noon PST). The [official rules](https://nebiusglobalaihackathon.devpost.com/rules) require working software, an NVIDIA open model on Nebius runtime, a public licensed source repository, a demo/test-build URL, a public YouTube video shorter than three minutes, English materials, feedback and disclosure of significant changes to pre-existing work. Entrant eligibility and ownership remain personal declarations.

| Gate | Required evidence | Current checkpoint |
|---|---|---|
| NVIDIA + Nebius execution | Actual NVIDIA-model inference through Token Factory, or qualifying Nebius compute; saved request/response and completed product workflow | Awaiting Nebius access; discovery alone is insufficient |
| Product behavior | Actual repair proposal, independent checks, corrupted repair rejection and completed tool task; installed-SDK controls | GLM and preliminary DeepSeek/Tavily development workflows plus SDK evidence executed; final required-platform run pending |
| English description | Reviewed product copy with exact model/platform roles and honest limits | `DEVPOST_SUBMISSION.md` prepared; live figures to be finalized |
| Public source | Final revision published, license visible and README sufficient; anonymous access tied to final commit | 0.5.0 development commit e3aa4bd published and anonymously verified; final required-platform run pending |
| Demo/test build | Public working demo or downloadable functional build with English judge instructions and free access | Development ZIP anonymously downloaded, byte-checked and relaunched; manifest records public URL |
| Video | Actual final file, <180 s, readable English, real runtime, spoken model/platform attribution, public YouTube link | 137-second English DeepSeek recorded-replay cut verified; final competition cut and public YouTube pending |
| Feedback | Specific observed platform/model use, strengths, limits, onboarding and reuse decision | Honest working draft; no invented findings |
| Existing work | Explain retained ACV baseline and significant in-period additions | `COMPETITION_CHANGELOG.md` exists |
| Entrant/form | Legitimate registration, eligibility/rights declarations, every actual required field and feedback entered | Authenticated form unavailable in public session |

The [official FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs) confirms that NVIDIA inference through Token Factory can satisfy the runtime requirement while the frontend runs elsewhere. Another provider does not replace that Nebius requirement. Do not change billing region to bypass onboarding restrictions. The [overview](https://nebiusglobalaihackathon.devpost.com/) and [feedback guidance](https://nebiusglobalaihackathon.devpost.com/updates/46205-how-to-build-a-winning-project) support the project-description, demo and platform-attribution packaging above.

## Deterministic local gate

Run from the repository root:

```bash
python scripts/submission_check.py --output evidence/submission/readiness.json
```

`submission-manifest.json` points to actual evidence. Missing records are JSON `null`, not fake URLs or placeholder success values. Exit **2 / BLOCKED** means required evidence is absent. Exit **1 / FAIL** means supplied evidence is malformed, inconsistent or does not meet its gate. Exit **0 / READY_FOR_ENTRANT_REVIEW** means the recorded package passes these local checks; it never means Devpost accepted the entry. The checker makes no network calls, spends no API credits and does not inspect credential files.

The checker binds runtime reports to canonical report hashes and each request record to its recorded canonical SHA-256. It rejects discovery-only evidence, GLM/DeepSeek substitutes, blocked/mocked provenance, missing payloads, absent completions, unverified repairs and incomplete fixture tasks. A valid hash proves local integrity, not provider authenticity.

## Recording the remaining evidence

Only update the manifest after the action actually occurred. Store sanitized records under `evidence/submission/`; never put tokens, private login credentials or personal identity documents in a public artifact.

| Manifest field | Evidence convention |
|---|---|
| `runtime_workflow` | Relative path to completed Nebius/NVIDIA `report.json`, alongside `manifest.json` and hash-bound request files |
| `source_commit` | Exact final 40-character Git commit, after local development is committed and published |
| `public_links.source`, `.demo`, `.youtube` | Each has a real `url` and a `verification` record path; null until actually published and checked |
| Public verification record | Exact `url`, `http_status: 200`, `access: anonymous`, dated `checked_at`, inspected `evidence_file`, its byte `evidence_sha256`, and `content_verified: true` |
| Source-specific record | The same final `commit`; verify source/license/setup instructions as an anonymous user |
| Demo-specific record | `functional_smoke_test: PASS` and `free_judge_access: true`, backed by the actual download/run or hosted interaction |
| YouTube-specific record | `visibility: public`; verify the actual final video while logged out |
| `video` | Actual `file`, video `manifest`, and completed `english_reviewed`, `competition_runtime_shown`, `spoken_platform_attribution` reviews; manifest stores actual duration, visual review and byte SHA-256 |
| `feedback_review` | Dated `reviewed_at`, byte hashes `document_sha256` and `runtime_report_sha256`, and reviewed `observations_backed_by_records: true` |
| `form_review` | Sanitized record of actual authenticated review; `kind: authenticated Devpost form review`, dated `reviewed_at`, and completed field/eligibility/rights/English/free-access declarations |

Form review booleans are `required_fields_reviewed`, `feedback_entered`, `entrant_eligibility_confirmed`, `ownership_and_licenses_confirmed`, `english_materials_reviewed`, and `free_judge_access_through_judging_confirmed`. These are recorded declarations by the entrant, not independent legal findings by the checker. Do not set them from an assumption or from the existence of this Markdown file.

## Actual Devpost form limitation

The [public submission-management page](https://devpost.com/submit-to/30790-nebius-x-nvidia-global-ai-hackathon/manage/submissions) was re-opened on October 25. It displays Join/Register and no editable entry fields in the available public session. Exact authenticated prompts, limits and required-field flags remain unverified. The entrant must inspect that form and adapt the prepared copy before final submission. Public development code and test assets have been published and verified separately. No Devpost login, entrant declaration, YouTube upload, external feedback message or final entry submission has been performed.
