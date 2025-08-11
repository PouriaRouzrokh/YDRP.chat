# Commit History

## commit 1 (8/11/2025 - 20:00)

- Chat rendering refined for agent HTML output:
  - Sanitize while preserving class and data attributes used by streamed chunks.
  - Render sanitized HTML directly inside `div.chat-html`.
  - Tailwind/typography list styles enabled; bullets and spacing visible.
  - Added spacing between streamed chunks using `.html-chunk-sep` and `[data-chunk="1"]`.

## commit 0 (4/21/2025 - 22:01)

Updated agent system prompt.

