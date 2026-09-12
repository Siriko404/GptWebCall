# FinProdLine handbook protocol

The handbook is a required output line, and it **lags production**.

A phase becomes eligible for handbook production only after that phase's Method, Data and Execution
gates are 100% passed. The handbook never teaches provisional, unresolved or probably-correct
content. If a passed phase is later invalidated by a late defect, its handbook sections are
superseded, not quietly patched.

> **Standing operator ruling.** Audience testing is **not** required. The line does not wait for, and
> does not require, real learners. Teachability is an audited judgment against the learner contract
> in §4, performed by fresh bounded handbook auditors. The consequence is recorded and accepted:
> the teachability verdict is model-assessed rather than measured on real learners.

---

## 1. Learner contract

At project initialization the operator is asked for their handbook preference. If no preference is
supplied, the default learner is **an absolute beginner from zero**.

The learner contract must state, explicitly and before any content is designed:

- **assumed knowledge** — what the learner is taken to know already: accounting, financial
  statements, FP&A, FX, Excel, statistics, or none of these;
- **excluded assumptions** — anything the handbook needs but does not list as a prerequisite must be
  taught before it is first used;
- **observable job-performance outcomes** — stated as things the learner can *do*. "Understand FP&A"
  is not an outcome. "Trace a transaction into a monthly result", "explain a material variance using
  supported evidence", "distinguish actual from planning information" are outcomes.

The completion test for the contract: an actual zero-experience learner in the declared class can
enter the handbook without hitting a hidden prerequisite.

---

## 2. Production lag

1. A phase passes Method, Data and Execution at 100%.
2. Only then does the phase become handbook-eligible.
3. The handbook covers every 100%-passed phase. A phase with no handbook coverage keeps the final
   gate open.
4. A phase that loses its pass loses its handbook coverage until re-passed.

---

## 3. Production pipeline

For each eligible phase:

1. A **handbook planner** worker maps the accepted phase into learning outcomes and a lesson
   architecture, producing a Handbook Plan.
2. The Handbook Plan receives its own independent audit loop under [AUDIT_PROTOCOL.md](AUDIT_PROTOCOL.md).
3. A **handbook author** worker produces or updates the tutorial artifact.
4. Handbook audits run independently from finance execution audits, with their own Audit Planner,
   replicas and integrator.
5. Defects are repaired by fresh workers, followed by a fresh full handbook audit round.
6. Repeat until the handbook acceptance contract passes.

---

## 4. Handbook QA — three separate verdicts

Keep three verdicts, never merged:

- **finance correctness** — factual and method fidelity to the 100%-passed phase, checked against
  the phase's accepted method, data and artifacts;
- **teachability** — whether the handbook actually develops the declared outcomes for the declared
  learner, checked against the learner contract and the tests in §5;
- **control fidelity** — provenance, policy, release and version accuracy, and traceability.

One population of reviewer cannot substitute for another. Each dimension has its own auditors and
its own sign-off.

---

## 5. Teachability tests

These are checkable tests, not aspirations. Each is audited and each produces pass or a finding.

**Design**
1. The learner and its assumed knowledge are defined before the content.
2. Observable performance outcomes are defined before the content, and every chapter exists because
   it develops one or more of them.
3. A coherent big-picture mental model comes before detail — what the business does, how money
   flows, where the discipline enters, what the end-to-end process looks like.
4. The curriculum is organized around authentic whole tasks, not a glossary. The learner is doing
   recognizable work from near the beginning.
5. A meaningful, small, real success happens early in the first session.
6. Complexity is sequenced simple to complex, and every new complication rests on knowledge already
   acquired.
7. Pretraining is minimal and immediately useful. A term introduced before it is used must be needed
   imminently.
8. Most terminology is introduced just in time, at the point of need. No page lists unrelated
   concepts merely because they share a technical category.
9. One concept has one stable name and one meaning. No unexplained synonym changes, no local
   redefinitions, no invented vocabulary where standard industry language works.
10. Tutorial, explanation, reference and control/audit material are separated and never mixed
    sentence by sentence. Provenance strings and registry identifiers never interrupt the learner's
    reasoning unless they are themselves the object being taught.
11. Guidance for novices is explicit: the learner always knows what to look at, what to do, why, and
    what result to expect.
12. Early instruction offers one canonical path. "You could also…" branches are excluded during
    initial skill acquisition unless the distinction is essential.
13. Worked examples precede independent practice for every important analytical skill, with the
    expert reasoning exposed: what I notice, what I compare, what evidence I inspect, what I may
    conclude, what I may **not** conclude.
14. Guidance fades: worked example, then partially completed example, then guided problem, then
    independent problem.
15. Every substantive lesson follows a repeatable architecture: where we are in the workflow, what
    problem we are solving, one concrete example, only the needed explanation, a small learner
    action, the expected result, a comprehension check, the connection to the next step.
16. Complex material is segmented into learner-paced units. One section has one primary teaching
    purpose; if the author cannot state that purpose in one sentence, the section splits.
17. Extraneous load is ruthlessly reduced. Every sentence, table and visual answers "what learning
    function does this serve?"
18. Visual signaling tells the learner where to look: headings, arrows, highlighting, numbered
    overlays, callouts.
19. Explanations sit beside the visual element they explain.
20. Every screenshot is pedagogical: cropped to the relevant area, legible, with the exact elements
    to inspect annotated and what to notice stated. No postage-stamp screenshots.
21. Concrete cases come before abstract generalizations. Core abstractions each carry at least one
    concrete case.
22. Correct-versus-wrong analyst examples are used selectively, and a wrong example always explains
    why the reasoning fails. No misconception is left unresolved.
23. Navigation and headings are predictable and say what the section helps the learner do or
    understand. The table of contents alone gives a beginner a picture of the journey.
24. Layout meets a readability specification: line length around 50–75 characters, substantial white
    space, clear grouping, logical visual hierarchy, roughly 40–50% white space. No wall-of-text
    pages, no microscopic captions.
25. When the format is PDF, the PDF is genuinely accessible: tagged, semantic heading structure,
    image alternatives, table markup, bookmarks, logical reading order. Accessibility is tested
    technically, not inferred from the document looking clean.

**Learning**
26. The learner retrieves and uses knowledge rather than rereading it. Chapters contain genuine
    recall and application opportunities whose answers are not visible immediately above.
27. Feedback is explanatory. A wrong answer identifies the misconception or missing step and says
    what to do differently. Revealing a letter is not feedback.
28. Retrieval is cumulative and distributed. Later exercises deliberately require earlier concepts.
29. Problems vary and transfer. Passing cannot be achieved by memorizing the worked example's
    numbers or screen locations.
30. Assessment is aligned with the real skill and resembles the job more than a trivia quiz.
31. The handbook culminates in an unseen authentic case: new but controlled evidence, from which the
    learner independently produces the required output.
32. Learner performance against the declared outcomes is evaluated and recorded as audit evidence.
    Under the standing ruling this is evaluated against the artifact and the outcomes, not by
    running human test subjects.

**Provenance and honesty**
33. Source integrity is preserved through layered provenance: a small unobtrusive source marker in
    the teaching layer, mapped to exact hashes, anchors, controls and evidence lineage in an
    appendix or reference layer. An auditor can trace every claim precisely while a learner reads
    the lesson without decoding provenance syntax.
34. Completeness is not confused with instructional quality. Omissions from the core tutorial are
    deliberate deferrals to later lessons or reference material, never missing controls.
35. Instruction adapts to prior knowledge, task complexity and demonstrated progress — never to
    "learning styles". Multimedia is chosen because the content benefits from that representation.
36. The handbook is treated as a product that can fail. Correct facts are necessary but not
    sufficient: if the declared learner cannot follow it, forms wrong mental models, needs an
    instructor to translate it, or can pass only by memorizing labels, the artifact has failed and
    the audit must say so.

---

## 6. Change replay

When a pinned release changes, the affected handbook sections are revalidated as one end-to-end
experience: screenshots, numbers, exercises, expected outputs and answer explanations together. A
handbook section is never assumed still-valid because the underlying phase still passes; a release
change is its own trigger for a handbook audit round.
