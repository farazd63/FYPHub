# Llama summary availability repair — 2026-11-12

## Follow-up: full-source multipass and missing review details

The compliance-summary route now partitions large full-source prompts into lossless UTF-8 segments of at most 8,000 bytes, reads every segment, reduces intermediate notes hierarchically when necessary, and synthesizes the final narrative. The segment size is a per-call processing budget, not a document-size rejection limit. Smaller prompts use one call. A failed segment prevents saving a partially completed summary. All original recorded findings, scores and statuses are still copied from the full source report by the application, independently of the narrative synthesis. Intermediate AI notes are a lossy narrative aid; they do not replace the stored proposal or recorded findings. Cache report version was advanced so earlier summaries are regenerated.

The live 79% report has 19 passed checks, zero failed checks and five **UNVERIFIABLE** academic-consistency checks. The reasons reference undetected problem/objectives/methodology/purpose/solution/outcomes/scope fields. This means the engine could not verify those relationships, not that it proved five contradictions. Previously CSS hid the partial counter and the detailed panel showed only failed violations. The page now shows partial/unverifiable counts, the score calculation and each unresolved check's expected value, detected value, location and recorded evidence. The downloadable report includes these details as well. The scoring formula was not changed.

Follow-up validation: 18 focused backend tests passed; frontend server-render regression for the 19/24 case passed; frontend build/typecheck and lint passed (14 existing warnings). The actual 138,477-byte report source was partitioned into 18 segments, maximum 8,000 bytes each, and reconstructs byte-for-byte. These tests verify the source-routing, failure and rendering logic; an entire 18-part inference against the live CPU model was not run to completion. Long requests can still be constrained by processing time, service availability and hardware. The model's physical context capacity has not been made infinite.

## Observed causes

Ollama returned HTTP 500 while loading a 60,416-token context. Its logs reported failure to fit the model into system memory followed by `llama-server process has terminated: signal: killed`. Docker has approximately 9.8 GiB available. The tag-list health check continued to pass even though inference failed.

The backend also rejected a 138,477-byte full report prompt as exceeding 131,072 tokens. Bytes are a conservative upper bound, not a measured token count: the runner logged only 36,176 input tokens for this document.

## Changes deployed

- Enable Flash Attention and q4_0 KV caching, one parallel request and one loaded model. Keep the model resident for 30 minutes and retain the existing restart policy. Quantized caching trades some numerical precision for lower memory use; recorded compliance findings and scores remain application-owned.
- Cap the requested context at the model's native 128K-token capacity rather than refusing requests solely on UTF-8 byte size. Send the complete prompt unchanged. Reject results whose reported prompt-token usage reaches the context boundary, instead of saving a potentially truncated report.
- Use a 512-token processing batch and allow 30 minutes for detailed compliance inference, with a matching 1,900-second proxy read timeout.
- Keep existing authentication, compliance rules, findings, score ownership and successful-summary caching.

The active model remains **llama3.1:8b**. A smaller-model download was investigated but stopped because of slow network throughput; it is not configured as the active model. The machine's RTX 3050 was detected, but Docker GPU startup failed because `libnvidia-ml.so.1` was unavailable. The attempted GPU configuration was reverted, and the CPU service was restored.

## Verification and limits

- Backend and frontend images rebuilt and deployed; all running application services healthy.
- 13 focused provider/compliance-summary tests passed, covering full input preservation, byte-size versus token-size handling, context saturation, response validation and failure behavior.
- A real Llama 3.1 8B request completed in 17.02 seconds and returned a valid generated summary preserving the supplied 15% / Not Compliant result.
- Large full-report prompts loaded and began processing without the previous memory kill. A complete large-report inference was **not** verified: diagnostic restarts interrupted those runs. Do not interpret the short live inference test as an end-to-end large-report acceptance test.
- Large reports can take many minutes on CPU. Model capacity and available hardware still impose limits; these changes cannot guarantee permanent availability or unlimited document size.

Existing failed summaries are retried through the report's **Retry AI summary** control. Successfully generated summaries continue to be stored in the report and reused when the source/report fingerprint matches.

References: [Ollama cache configuration](https://github.com/ollama/ollama/blob/main/docs/faq.mdx), [Docker GPU support](https://docs.docker.com/compose/how-tos/gpu-support/).
