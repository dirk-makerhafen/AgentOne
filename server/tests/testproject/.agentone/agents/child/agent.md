---
name: child
description: >
  Tests agent inheritance via extends. Inherits fs.* from base, adds compiler.*
  via + merge. Used by LoaderTest.
extends: base
tools: [+, compiler.*]
---
Child test agent (extends base)
