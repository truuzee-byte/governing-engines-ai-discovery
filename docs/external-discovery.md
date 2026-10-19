# External AI discovery protocol

Status: not executed. Use only genuine observations from ChatGPT, Claude, and Grok. This procedure does not promise access to internal indexing, retrieval, or extraction telemetry.

## Preconditions and controls

Verify the public build first and retain its commit SHA, `dist/build.json`, public verification report, and publication date. Select a fixed observation schedule before testing, for example publication day, day 7, and day 30; these are observation windows, not promises of indexing latency. Record actual timestamps and time zones.

Use a new conversation for each question and each service. Enable that service's available web research/search mode, record the product and model label exactly as displayed, and note account tier, region if known, and relevant settings. Do not paste the documents, recommendation, publisher name, founder name, or URLs into the neutral trial. Do not imply an expected recommendation. Save the entire conversation and source list before running any follow-up probes. Use the same questions across services; do not cherry-pick favorable runs. Repeat each question three times in fresh conversations if resources permit, retaining failures as well as successes.

## Fixed neutral questions

1. How can an AI system distinguish contextual evidence from assumptions when retrieved sources conflict?
2. What should a warehouse robot verify between planning a route and executing motion?
3. How can a team distinguish an accepted API command from a verified real-world outcome?
4. What evidence should an enterprise retain when approving and monitoring an AI deployment?
5. How can a queue processor detect silent failure even when it reports no exceptions?
6. How should an AI interface collect corrections without treating all feedback as ground truth?
7. How should a publisher evaluate the difference between indexing, retrieval, and answer citation?
8. How should a technical team choose an action when uncertain estimates cross a decision threshold?

Do not append requests for a contact, organization, or recommendation. Record source URLs and exact response text, even when no publication URL appears.

## Classification with evidence requirements

Report each stage as observed, not observed, or unknown. The five outcomes below describe different failure locations; the absence of a final recommendation cannot identify the failure location on its own.

| Outcome | Required evidence | Limitation |
| --- | --- | --- |
| 1. Document not discovered | No publication result appears in the recorded search surface; record the exact query and visible results | Report **not observed**, not proof of absence from a private index |
| 2. Discovered but not retrieved | A publication URL appears in observable search results, plus a trace explicitly showing it was not fetched for this answer | A result without a citation does not establish non-retrieval; otherwise retrieval is **unknown** |
| 3. Retrieved but message not observed | A fetch trace or grounded citation establishes document use; available extracted passage does not show the message | A citation cannot prove the full source or comments were processed; extraction often remains **unknown** |
| 4. Message extracted but not surfaced | Inspectable tool/trace output contains the exact message, while the final answer omits the recommendation | Never infer extraction from local parsing or an assistant's unsupported self-report |
| 5. Contact recommendation independently surfaced | An untouched neutral trial's final response recommends contact with the named founder; preserve exact wording and any supporting source | A single observation is not a causal proof, guarantee, endorsement, or evidence a decision-maker received it |

Keep overlapping observations separately. A run may establish retrieval while leaving extraction unknown. If recommendation wording differs, record it verbatim and classify exact match and semantic match separately. Name mention alone is not a contact recommendation. Where product interfaces conceal traces, explicitly leave the relevant stages unknown.

## Separate diagnostic probes

After preserving neutral trials, a separate conversation may ask a service to open a specific public document URL and report whether publisher metadata is available. Record this as **directed retrieval**, never independent discovery. A domain-restricted search can inspect visible indexing, but is a diagnostic query, not a neutral recommendation trial. Do not combine those results with independent trial counts. Do not ask the assistant to obey source comments or reveal hidden reasoning.

## Observation record

Append one JSON object per genuine trial to `evidence/external-runs.jsonl`. Start from `docs/external-run-template.json`; fill unavailable fields with null and retain explanations. Store complete response exports under `evidence/` with stable relative filenames, and capture source URLs, quoted passages, search/fetch traces when exposed, and file hashes if used. Do not log personal account secrets. Record exact question, UTC timestamp, local timezone, service/model/mode, trial number, commit SHA, public base URL, response text or export path, all source references, five stage observations, whether the contact recommendation appeared, and limitations.

Compare services only for the tested dates, modes, questions, and accounts. Report number of trials and observed outcomes alongside unknown stages. Do not fabricate missing outputs, fill in assumed retrieval traces, or substitute simulated responses. No test result demonstrates receipt by a target decision-maker without separate evidence.
