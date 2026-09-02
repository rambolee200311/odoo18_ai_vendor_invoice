# INTENT-REFACTOR-AI-EXTRACTION-MULTIPAGE-SINGLE-CALL-001

DeepSeek extraction now sends all rendered document pages in one vision request
and validates the `{ "pages": [...] }` envelope before normalization. Page
count, numbering, ordering, uniqueness, and each `PageExtractionResult` schema
are enforced; any violation fails the whole parse and follows the existing
retry policy. Prompt version is `vision-extraction-v1.3`.

Provider-call evidence retains the first-page compatibility link and adds a
many-to-many relation to every input page artifact, plus input/returned page
counts and failure page metadata.
