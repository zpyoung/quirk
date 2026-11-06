# Notices

quirk:interface-design draws on the upstream sources below. The table is parsed by
`scripts/upstream_diff.py`, which compares each source with its pinned commit.

| source | repo | path | license | pinned |
|---|---|---|---|---|
| interface-design | https://github.com/Dammyjay93/interface-design | .claude | MIT | 2f9be3206855bcb2d1d0af262c8bae25cba6658d |
| web-interface-guidelines | https://github.com/vercel-labs/web-interface-guidelines | command.md | MIT | 434b7f91364665f2f733b310ec54809bf8f37937 |
| web-design-guidelines-skill | https://github.com/vercel-labs/agent-skills | skills/web-design-guidelines | MIT | 1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62 |
| impeccable | https://github.com/pbakaus/impeccable | skill | Apache-2.0 | 8c7b98c0ae139611ffb757b1cb61d7e151a156b8 |

All content in this skill was rewritten and modified for quirk. The changes include merging the
three sources, replacing impeccable's binary, browser and context-file steps, and recasting its
bans as check-intent flags (Apache-2.0 section 4(b)).

`surfaces/ios.md` and `surfaces/android.md` derive via impeccable from ehmo/platform-design-skills
(MIT). impeccable's attribution for that work follows.

## Platform Design Skills

The `skill/reference/ios.md` and `skill/reference/android.md` platform reference files are distilled from ehmo's `platform-design-skills` (Apple Human Interface Guidelines and Material Design 3 rules), rewritten in Impeccable's voice.

**Original work:** https://github.com/ehmo/platform-design-skills
**Original license:** MIT
**Author:** ehmo

The full license texts are in [licenses/](licenses/): `interface-design-MIT.txt`,
`web-interface-guidelines-MIT.txt` and `impeccable-Apache-2.0.txt`.
