# RPU upstream MSG review — 2026-10-24

Source issue: https://github.com/munument1/Fallout2-RPU-Korean-Edition/issues/1

## Comparison scope

- Translation baseline: RPU 2.4.34, upstream `2c5aff7c4132`.
- Issue snapshot: upstream `98f93309ff2a` (2026-10-23).
- On 2026-10-24, upstream advanced to `a23ef4675cca`; the intervening four commits did not change English MSGs, but did change Swedish translation files.
- This is a **draft compatibility patch**, not a validated translation upgrade to all of upstream master. Do not merge upstream wholesale or publish this overlay as an updated RPU release.

## Changes included in this draft

| Priority | Korean file | Review outcome |
| --- | --- | --- |
| P0 | `dialog/dcrebecc.msg` | Translate IDs 1230–1234, invoked by the new upstream `scripts_src/den/dcrebecc.ssl` door-tamper event. |
| P0 | `dialog/zclvillrat.msg` | Reuse original `vilrat.msg` IDs 100, 101, 102, 200 verbatim. Corresponding upstream `data/scripts/scripts.lst` moved `vilrat.int` to `zclvillrat.int`. Retain old `vilrat.msg` as a harmless compatibility file. |
| P1 | `game/combat.msg` | Update **second MSG field only** for 65 entries: `female_pc` (38), `female_npc` (27). English visible text was unchanged; keep Korean text and format specifiers unchanged. |
| P1 | `game/editor.msg` | Update metadata field for ID 304 to `editor`; Korean text unchanged. |
| P1 | `dialog/ectrappr.msg` | Change ID 102 possessive description to match revised English wording. |
| P1 | `dialog/epac6.msg` | In IDs 280 and 300, use "창고" for updated `storage shed` references. |

Manifest: `korean/manifest.json` updates hashes and sizes for changed files, and adds `zclvillrat.msg`.

## Existing translations retained / not blindly deleted

- `containr.msg` and `door.msg`: seven lock-breaking message changes in each; existing translations already convey the updated action.
- `dcrebdor.msg`: no changed MSG IDs, but upstream script behavior changed and needs gameplay QA.
- `pro_scen.msg`: 11 modified, 63 removed; existing changed-ID Korean lines are present, and the modified bullet-proof-glass descriptions largely match.
- `pro_tile.msg`: 45 modified, 76 removed; existing translations for `Roof`, `Floor tile`, and `Roof Pipes` already exist.
- `pro_wall.msg`: 47 removed in English upstream; no blanket deletion until prototype / .lst references are independently checked.
- `combat.msg` IDs are **not** 65 new Korean sentences: the changes are in the gender tag field.

## Upstream code / installation risks still open

1. New Den door-tamper warnings require actual updated scripts and the event path; this MSG-only patch cannot cause new events to exist on the original 2.4.34 scripts.
2. `data/scripts/scripts.lst` renames the Village Monster script. Confirm the updated INT/prototype uses `zclvillrat.msg` in-game.
3. Scenery / tile / wall .lst and prototypes may depend on the 186 removed `pro_*.msg` IDs. Inspect references before removing any Korean translations.
4. Upstream `extra/package/translations.sh` now uses DAT3 rather than DAT2, but this project's translation-only ZIP builder is separate. Check install paths and load order on a disposable modern RPU copy.
5. No Korean text renderer, patched game executable or upstream scripts are included in the translation-only ZIP.

## Verified / outstanding

- Run `python -m unittest discover -s korean/tests -v`.
- Run `python korean/build_overlay.py`; then validate the ZIP file list and SHA-256 against the 1,341-entry manifest.
- **Outstanding:** in-game Den/Becky door warning, new Village Monster script, male/female combat, save/load, overlay restore, modern RPU installer paths. Verify in a disposable game copy.
- **Release and merge are blocked** pending full upstream script/prototype compatibility and game QA. The pinned 2.4.34 release must remain untouched.
