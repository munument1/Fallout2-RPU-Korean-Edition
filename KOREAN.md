# RPU 2.4.34 Korean source overlay

This is a version-pinned integration branch based on BGforgeNet/Fallout2_Restoration_Project. The upstream-tracking
master branch is deliberately unchanged.

- Original translation repository: https://github.com/munument1/Fallout2-RPU-KR
- Shared Korean renderer: https://github.com/munument1/Fallout2-Korean-Text-Engine/releases/tag/v1.2.0-beta.2
- Korean translation files: 1,340 byte-verified mod-relative files.
- Manifest: korean/manifest.json lists SHA-256 of each file and its game ZIP-relative destination.
- Build: python korean/build_overlay.py produces korean-dist/korean-translation-only.zip.
- This branch contains translation data, NOT a Hangul renderer. A vanilla Fallout 2 EXE
  cannot display Korean by overwriting text files alone. Use the independent text engine,
  or a future combined installer that applies the engine patch for the user.
- Do not redistribute prepatched proprietary game executables.
- Re-evaluate English text and scripts before applying this branch to any newer upstream.

## Automated upstream review and translation build

- Korean source branch: ko/v2.4.34. Upstream-tracking master is kept separately.
- Pinned source baseline: upstream release v2.4.34 (2c5aff7c4132).
- GitHub Actions workflow korean-upstream.yml: daily at 04:23 UTC,
  on edits to Korean tooling, or manually from the Actions tab.
- Local build: python korean/build_overlay.py (byte-verified translation ZIP only).
- Local MSG tests: python -m unittest discover -s korean/tests -v.
- Update upstream reference: git fetch --no-tags upstream master
- Local review: python korean/check_upstream.py --head upstream/master --report-dir korean-report
- Workflow uploads translation ZIP and JSON/Markdown review as separate artifacts.
- Scheduled/manual runs maintain ONE open review issue, updated only when upstream SHA changes.
  Upstream code and Korean translations are NEVER automatically merged or installed.
- Comparison is the pinned release baseline versus current upstream development HEAD,
  not a guarantee that this upstream HEAD is compatible with the existing release.
- This ZIP does not include the Korean text renderer. Central Text Engine is separate.

## One-link QA handoffs and release preparation

- Human dialogue/source review (game-specific): [REVIEW_HANDOFF_KO.md](korean/REVIEW_HANDOFF_KO.md)
- Combined installer candidate & Nexus upload prerequisites: [RELEASE_PREPARATION.md](korean/RELEASE_PREPARATION.md)
- Reproducible Korean ZIP: run python korean/build_overlay.py (manifest checks required).
- After verified text edits: run python korean/update_manifest.py --apply <reviewed-source-file>.
- Windows QA setup is an Actions artifact, not yet a publicly supported stable installer.
- No Nexus file is automatically uploaded until the exact candidate has human
  linguistic review, menu/dialogue/combat/save-load/restore tests and SHA approval.
