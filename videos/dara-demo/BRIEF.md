---
workflow: product-launch-video
flow: automation
storyboard: no
message: "Govern AI media before spend, preserve every attempt, and verify the exact delivered bytes"
destination: youtube
aspect: 1920x1080
language: en
audience: "Backblaze Generative Media Hackathon judges and AI media builders"
length: 165s
angle: "Evidence-first product tour: problem, generate, govern, verify, regenerate, then prove the one-bucket B2 architecture"
narration: yes
capture: yes
vo_mode: restructured
---

## Intent

Show Dara as it actually works, using its own production screens and recorded evidence.
The piece starts with the operational cost/provenance problem, then demonstrates the
zero-spend QA replay, a pre-provider policy block, trusted-file verification, regeneration
lineage, and the DuckDB-over-Parquet ledger. It should feel precise, calm, and credible,
not like a generic SaaS commercial.

## Assets

- `https://usedara.xyz` — public judge deployment
  for the production Studio, Ledger, Verify, and Assets routes.
- `../../docs/assets/tour-studio.jpg` — fallback production Studio capture.
- `../../docs/assets/tour-ledger.jpg` — fallback live Ledger capture.
- `../../docs/assets/tour-verify.jpg` — fallback trusted-match Verify capture.

## Customizations

- Feature Dara's own captured screens as the primary visual material.
- Follow the beat order in `docs/SUBMISSION.md`: problem, definition, generate, govern,
  verify, regenerate, B2 architecture, close on ledger outcomes.
- Use readable captions and restrained callouts for exact proof terms such as
  `zero provider calls`, `published_sha256`, `parent_run_id`, and `DuckDB over B2`.

## Notes

- Hard limit: under 3:00; target 2:45.
- No copyrighted music. Use narration without a music bed.
- Do not imply adversarial authenticity or byte-deterministic regeneration.
- Do not claim provider-reported image cost; label the live amount as estimated.
- Do not invent a live provider failover. The visible QA replay is explicitly a
  deterministic fixture; production OpenAI/B2 records are shown separately.
- No live provider call during capture.
