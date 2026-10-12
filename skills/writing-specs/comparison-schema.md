# comparison.json reference

`comparison.json` is the input to stage 3 of an interactive spec. The coordinator writes it by hand from the approach tech specs and saves it beside `logic.json`; nothing generates it. `render_spec.py validate` and `render` check it against the rules below. For the workflow around it, see [Stage 3: compare approaches](interactive-logic-spec.md#stage-3-compare-approaches).

All prose fields are plain text and render as text, never HTML. The one exception is an approach's `specMarkdown`, which renders as Markdown.

## Top level

```text
{
  "kind": "quirk-approach-comparison",
  "schemaVersion": 1,
  "builtAgainst": { "signoffRenderId": str },     // logic.signoff.renderId when you built this
  "approaches": [Approach, ...],                  // 2..5; ids unique, one letter A-Z
  "scores": { "<REQ id>": { "<approach id>": Score } },
  "findings": [Finding, ...],                     // optional
  "pairings": [Pairing, ...],                     // optional
  "choices": [ { "question": str, "answers": { "<approach id>": str } } ],   // optional
  "keyDifferences": [str],                        // optional
  "example": { "scenario": str, "stages": [str] },// optional; stage labels every approach's trace shares
  "flowStages": [str],                            // optional; 3..8 stage names every approach's flow uses
  "guidance": Guidance                            // optional
}
```

`scores` needs an entry for every approach on every requirement whose scope is not `out`. Scores for unknown requirements or approaches are errors.

## Approach

```text
{
  "id": "A", "title": str, "overview": str,       // overview is coordinator-written
  "revision": str,                                // opaque; change it when the proponent's spec changes
  "anchors": [ { "repo": str, "commit": str } ], "readAt": "YYYY-MM-DD",
  "specMarkdown": str,                            // optional; the full tech spec
  "repos": [ { "name": str, "files": int } ],
  "schemaChange": str, "hotPaths": [str],
  "deploy": { "status": "stated" | "implied" | "not-stated", "steps": [str] },
  "criticalPath": str | null,
  "slices": [Slice, ...],
  "flow": [ { "stage": str, "lane": str, "text": str,
              "kind": "new" | "changed" | "reused", "focal": bool? } ],   // optional
  "sequence": { "participants": [str],
                "messages": [ { "from": str, "to": str, "label": str,
                                "kind": "call" | "return" | "async" | "focal" } ] },   // optional
  "schema": { "tables": [Table],
              "refs": [ { "from": [table, column], "to": [table, column], "kind": "fk" | "json" } ] },   // optional
  "exampleTrace": [str],                          // optional; one entry per example.stages
  "restsOn": [str],                               // optional
  "undo": { "flagOff": str, "hardToReverse": str, "cheapestNext": str },   // optional
  "rivalClaims": { "<other approach id>": [str] },   // optional; proponent advocacy
  "effortGaps": [str]                             // optional; coordinator notes shown on the Effort tab
}
```

## Slice, Table, Score, Finding, Pairing, Guidance

```text
Slice   { "id": str, "name": str, "size": SizeLabel, "band": "v1" | "fast-follow" | "optional",
          "area": str, "risk": str, "riskHeadline": str?, "lines": { "<repo>": [lo, hi] }? }

Table   { "name": str, "status": "new" | "changed" | "existing",
          "columns": [ { "name": str, "type": str, "chip": "PK" | "FK" | "UQ" | null?, "highlight": bool? } ],
          "moreColumns": str? }

Score   { "status": "met" | "met with workaround" | "very hard" | "not met", "qualifier": str?,
          "wording": str, "note": str, "citations": [str],
          "requirementHash": str, "requirementText": str,   // hash and signed text of the requirement when scored
          "check": str?,                                    // what you verified; absent means claimed
          "history": [ { "previous": { "status": ScoreStatus, "qualifier": str? },
                         "challenge": str, "reply": str,
                         "outcome": "revised" | "held" } ]? }

Finding { "requirementId": str, "approaches": [id, ...] | "all",
          "type": "disputes" | "same score, different design",
          "text": str, "citation": str }                    // citation is required and nonempty

Pairing { "name": str, "items": { "<approach id>": str }, "text": str }

Guidance { "intro": str,
           "steps": [ { "title": str, "body": str, "tab": TabKey } ],
           "questions": [str],
           "recommendation": { "approachId": str, "headline": str,
                               "confidence": "low" | "medium" | "high", "confidenceReason": str,
                               "why": [str], "costs": [str], "changeMyMind": [str] },
           "suggestedChallenges": [ { "requirementId": str, "approachId": str, "note": str, "want": ScoreStatus } ],
           "changeNote": str? }
```

- **ScoreStatus** is one of the four `Score.status` values.
- **TabKey** is one of `overview`, `approaches`, `effort`, `blast`, `tradeoffs`.
- `requirementHash` is the requirement's current hash in `logic.json`. Copy it when you score.
- `lines` spans are two non-negative integers with `lo <= hi`.

## Size labels

A slice `size` must be one of these labels. The page turns each into points for the effort bars.

| Label | Points |
|---|---|
| S | 2 |
| S-M | 2-3 |
| M | 3 |
| M-L | 3-5 |
| L | 5 |
| L-XL | 5-8 |
| XL | 8 |

## Hashed content

A challenge's `targetHash` covers only the content a reviewer argues with. Adding a `check` or a `history` entry never invalidates a reviewer's draft.

- **Score target:** `status`, `qualifier`, `wording`, `note`, `citations`, `requirementHash`.
- **Slice target:** `name`, `size`, `band`, `lines`.

The hash is the first 12 hex characters of the SHA-256 of the canonical JSON of those fields: keys sorted, `(",", ":")` separators, UTF-8, no ASCII escaping. A field that is absent is left out of the hashed object. Keep hashed content to strings, integers, booleans, arrays and objects with ASCII keys, so Python and the page compute the same hash.

## Stage-3 export

The reviewer exports challenges and stars from the page. The file has its own `kind` and no signature.

```text
{
  "kind": "quirk-approach-comparison-challenges", "schemaVersion": 1,
  "slug": str, "renderId": str, "comparisonId": str, "exportedAt": ISO 8601 date-time,
  "challenges": [ { "id": str,
                    "target": { "type": "score", "requirementId": str, "approachId": str }
                            | { "type": "slice", "approachId": str, "sliceId": str },
                    "note": str,                          // nonempty
                    "want": ScoreStatus | SizeLabel,      // ScoreStatus for a score, SizeLabel for a slice
                    "targetHash": str } ],
  "stars": [REQ id],
  "approachRevisions": { "<approach id>": str }
}
```

`comparisonId` is the first 12 hex characters of the SHA-256 of the canonical JSON of the whole comparison. Any edit to `comparison.json` changes it, which makes older exports stale.

## Validation

`validate` and `render` print each problem with a JSON pointer. Errors stop the command with exit 1. Warnings print to stderr only when there are no errors.

**Errors**
- Wrong `kind` or `schemaVersion`, or a missing required key.
- Fewer than 2 or more than 5 approaches; an approach id that is not one uppercase letter or is duplicated.
- An in-scope requirement with no score for some approach; a score for an unknown requirement or approach.
- A score status outside the four values.
- A finding without a `citation`, or one naming an unknown requirement or approach.
- A slice `size` outside the size labels; a duplicate slice id.
- `exampleTrace` length different from `example.stages`.
- `flowStages` outside 3 to 8 entries; a `flow` stage not in `flowStages`; two boxes in the same lane and stage.
- A sequence with more than 5 participants or 12 messages, or a message naming an unknown participant.
- A schema with more than 5 tables or 6 refs (`fk` and `json` count together), or a ref naming an unknown table or column.
- A guidance `tab` outside the TabKey values; a recommendation or suggested challenge naming an unknown approach or requirement.

**Warnings**
- `builtAgainst.signoffRenderId` differs from the spec's `signoff.renderId`.
- A score's `requirementHash` differs from the requirement's current hash. The page shows these cells as "scored against older text".
