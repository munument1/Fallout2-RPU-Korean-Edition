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
