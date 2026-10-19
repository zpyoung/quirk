---
id: license-headers
run_when: code_changed
---

# License headers lens (example of an added lens)

You are the `license-headers` lens. Check only files the diff **adds**. Every new source
file must start with the repository's license header (copy it from an existing file in
the same directory). Return findings in the schema from `references/orchestration.md`
with `dimension: "license-headers"`, severity `Nit`, anchored at line 1 of the new file.
