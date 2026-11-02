# Issue #22 — usability and keyboard accessibility

**Status: implementation, keyboard checks and participant trials recorded (P1, P2, P4
passed; P3 failed and was retested by P4). Not committed or pushed. Remaining: commit,
open the PR and merge. Do not close #22
until that is done.**

## Acceptance evidence

| Requirement | Evidence | Status |
| --- | --- | --- |
| Dataset → Pipeline → Model → Run → Results | Shared stage navigation, one `aria-current="step"`; rendered route tests | Automated pass |
| Visible current stage | Stage word and current-step semantics, glyphs plus colour; 5 ordered stages on workflow pages | Markup pass; visual check pending |
| Labelled keyboard controls | Native inputs/selects/radios/buttons; invalid controls reference existing error/help elements; focusable error summaries and skip destination | Automated/source pass; live Tab test pending |
| Meaning beyond colour | Text status/column types, stage names and glyphs, matrix captions and correct-cell text | Source pass; visual/AT check pending |
| Numeric equivalent for every chart | Comparison chart references the numeric table containing the same scores | Automated pass |
| Three participants finish in under five minutes | Blank trial record below | Pending |
| Findings recorded with linked defects | Issues #44 and #45 below | Recorded; local fixes await publication |

## Defects and local fixes

- [#44 — Form error associations and keyboard focus indicators](https://github.com/team5-ml-model-evaluator/SE-Mini-Project/issues/44):
  associate errors and help with upload/pipeline/model/comparison/auth controls;
  link comparison and registration summaries to controls; make main focusable;
  ensure button focus outlines override framework resets and enlarge comparison
  checkbox targets. Normal Tab order is preserved; `tabindex=-1` adds no extra stop.
- [#45 — Focus lost when training results update](https://github.com/team5-ml-model-evaluator/SE-Mini-Project/issues/45):
  when an element has focus, offer **View updated results** instead of reloading;
  preserve that focus and announce readiness. Run polling stops at a terminal
  state and ignores stale terminal responses and late errors.

## Verification boundary

Automated checks use Django-rendered HTML and Node simulated DOM/network/timers.
They verify relationships, route semantics and update logic, not browser rendering,
actual keyboard focus movement, screen-reader announcements or user task speed.
Browser and keyboard checks are recorded separately below. No WCAG conformance claim is made.

Three independent code reviews checked semantics, Python/rendered forms, and
JavaScript focus/async behavior. These are code reviews, not trial participants.

Verified locally: **159 pytest tests and 54 subtests passed (plus 36 in `webui/tests.py`,
which the default pytest patterns skip); 13 Node tests passed.**
All three code reviews have no outstanding findings after the late-error fix.

Run checks:

```sh
python manage.py test webui.test_accessibility
node --test tests/focus_refresh.test.cjs tests/run_polling.test.cjs tests/batch_polling.test.cjs tests/target_marker.test.cjs
python -m pytest -q webui/tests.py   # not collected by the default pytest patterns
python -m pytest -q
```

## Automated browser keyboard run (2026-11-01, Chrome, local server)

Run through browser automation against the local build as the `demo` user.
This is a partial facilitator check, **not** a participant trial and not a WCAG claim.
Browser version and macOS keyboard setting were not recorded.

| Check | Result |
| --- | --- |
| Tab 1 reaches Skip to main content, visible outline; Enter then Tab lands in main | Pass |
| Empty upload submit: focus on error summary, input `aria-invalid`, described by help and error | Pass |
| Upload `docs/fixtures/usability-classification.csv` and submit with Enter | Pass |
| Pipeline: empty submit focuses error summary; select has `aria-invalid` and error description | Pass |
| Pipeline: error summary links to the select | Pass; an earlier "no link" note used a wrong selector and is retracted (`webui/tests.py` covers `href="#id_target"`) |
| Select target by typeahead; arrow keys switch Feature/Excluded radios | Pass |
| Algorithm select by typeahead, Review settings, Start run with Enter | Pass |
| Focus on a link while training: no reload, focus kept, announcement, **View updated results** shown; Enter shows completed run | Pass |
| Stage list: text status plus glyph, 5 ordered stages, current stage marked | Pass |
| Comparison chart references numeric table; table has caption; scroll regions focusable | Pass |
| Layout at 320 px (about 400% zoom) and 375 px: dataset list, upload, pipeline, model, run, comparison | Pass: no page-level horizontal overflow. Measured by rendering each page in a sized frame, not in a real zoomed browser window |
| Space toggles comparison checkboxes (two toggled by keyboard, focus stays correct); each checkbox target is 24x24 px | Pass |
| Light theme: contrast computed from the stylesheet colours (text pairs 5.50:1 to 17.14:1, focus ring 4.55:1 and 5.12:1) | Pass by calculation; not viewed in a light-mode browser |
| Screen reader (VoiceOver) | Not run in the automated run. Facilitator reported it working; no browser or macOS version recorded |
| Light theme in a real light-mode browser | Facilitator reported it working; no version recorded |

One single run (logistic regression, 40 rows) finished in 8 s with Accuracy 100.00%.
That timing comes from automation driving the page and does not count toward the 5-minute
participant criterion.

## Manual keyboard check (facilitator)

Use the current full local build in Downloads/SE-Mini-Project. On macOS ensure the
browser permits Tab navigation to links and all controls. Record browser/version,
OS and any keyboard setting; do not claim a pass when controls cannot be reached.

1. Tab to **Skip to main content**, press Enter, and confirm the next Tab reaches
   main-content controls. Check the focus ring is visible on links, buttons,
   selects, checkboxes, radio options and scrollable tables.
2. Submit upload/model/pipeline forms empty. Confirm focus reaches the error
   summary; follow its links to the relevant control/group. If a screen reader is
   available, confirm labels, error descriptions and invalid states are read.
3. Upload the supplied CSV using the file picker. Select the target and use
   arrow keys to switch Feature/Excluded radios; Space toggles comparison choices.
4. Complete a single training run. While it runs, focus a control. Completion
   must preserve that control and expose **View updated results**; activate it
   with Enter/Space. Also check ordinary automatic refresh with focus on the page.
5. Compare completed runs using the keyboard. Reach the scroll region, scroll
   horizontally, select a chart metric and verify its scores in the numeric table.
   Repeat the focus/update check on an active batch if using the optional dashboard.
6. Check narrow width/400% zoom and light/dark themes: readable stage names and
   controls, no clipped focus ring, no page-wide horizontal overflow except tables.
7. Check labels, stage/status text and matrix explanations without relying on colour.

## Three-participant walkthrough

Provide only the task card below and `docs/fixtures/usability-classification.csv`.
Use three people who have not read the documentation or watched a demonstration.
They may be classmates or colleagues. Do not coach or choose controls for them.
Use one participant at a time; keep accounts/data isolated when practical.
Have the local server running and start each trial signed in on the dataset list.
Record this starting condition. Test login separately if it is part of your study.

**Task card (give this, not the facilitator checklist):**

> Upload the provided customer CSV. Train a model to predict `purchased` using the
> other fields, then find the model's accuracy and explain what that score means.
> Use only the application's interface. Tell the facilitator when you are finished.

Start a stopwatch when the participant receives the task card. Stop when they
show the completed run's accuracy and give a correct basic interpretation (the
proportion of held-out predictions that were correct). Include upload, training
wait and metric review in elapsed time. Record any assistance or documentation
use; such a trial does not meet the unassisted criterion. If blocked, record the
block and elapsed time, fix the defect, and repeat with an unfamiliar participant.

| Participant (anonymous) | Date / build | Browser / input method | Upload complete | Training complete | Accuracy reviewed | Total time | No docs/assistance | Outcome / observations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 2026-10-31, build not recorded | Chrome, version not recorded | — | — | — | 3:42 | Yes | **Pass.** Briefly paused at "target column", then continued independently. Per-stage times not recorded. |
| P2 | 2026-10-31, build not recorded | Chrome, version not recorded | — | — | — | 4:18 | Yes | **Pass.** Took extra time choosing an algorithm. Per-stage times not recorded. |
| P3 | 2026-10-31, build not recorded | Safari, version not recorded | — | — | — | 5:12 | No | **Fail.** Asked which column to predict; confused about target versus features. Over 5:00 and assisted. |
| P4 (retest for P3) | 2026-11-01, build with the target-row fix | Chrome, version not recorded | — | — | — | 4:23 | Yes | **Pass.** Briefly reviewed the target-column description, then completed independently. Facilitator-reported; per-stage times not recorded. |

Result: P1 and P2 passed. P3 failed on both time and assistance. Per the retest rule
below, P4 (a new, unfamiliar participant) repeated the trial on the fixed build and
passed in 4:23 with no help, so three participants have now completed it unassisted
in under 5:00. Caveat: P1 and P2 used the build from before the target-row fix, and
all timings and observations were supplied by the facilitator.

P3 defect, fixed locally and retested by P4: after choosing the
target, its row still showed Feature ticked. The target row now says in words
"Target. The model predicts this column. It is never used as a feature." and its
Feature/Excluded choice is hidden; it updates when the target changes
(`tests/target_marker.test.cjs`, `PipelineFormTests`). Checked in Chrome on the
local build. Defect issue: [#46](https://github.com/team5-ml-model-evaluator/SE-Mini-Project/issues/46),
linked to #22. The light theme, VoiceOver and checkbox Space checks are
recorded in the table above.

Acceptance requires **all three** to finish in **less than 5:00** with no
consultation of documentation or assistance. Record actual times; never substitute
automated runs, test duration, invented participants or averages for this evidence.
Create an issue for each new defect, link it to #22, and add its URL and retest
result here. Record no personal identifiers or passwords.
