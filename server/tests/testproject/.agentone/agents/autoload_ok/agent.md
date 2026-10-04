---
name: autoload_ok
description: >
  Tests the autoload block, loadGuidanceFileIndex and guidanceFileIndexLimit
  round-trip YAML→DB. Used by GuidanceFileLoaderTest.
autoload:
  files: [AGENTS.md, "**/extra.md"]
  maxFiles: 5
  maxChars: 10000
  maxCharsPerFile: 4000
loadGuidanceFileIndex: false
guidanceFileIndexLimit: 3
---
Autoload test agent
