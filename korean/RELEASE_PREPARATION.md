# Korean edition release preparation (Et Tu / RPU)

Status: **QA candidate, no approved release.**
The setup embeds the game-specific translation ZIP, downloads a SHA-256 pinned
shared Text Engine setup from its central repo, and invokes the engine GUI.
Choose the SAME copied game folder in both installer windows. Never distribute
third-party game EXEs, patched runtime binaries, or modified sfall DLL.

## Candidate build
1. python -m unittest discover -s korean/tests -v
2. python korean/build_overlay.py
3. python korean/build_combined.py
4. python korean/combined_installer.py --verify-bundle --config-file korean-dist/installer-config.json --zip-file korean-dist/korean-translation-only.zip
5. On Windows: python -m pip install pyinstaller==6.20.0
6. On Windows: python korean/package_installer.py
Or run GitHub Actions: Korean combined installer - QA candidate.
The result is a private/CI QA artifact, not a Nexus release.

## Manual release QA
- Finish line-by-line speaker consistency checks with English source context.
- Test on a disposable game copy. Confirm menu, dialogue, cutscenes, combat,
  save/load, options, and all sfall/HRP behaviors.
- Restore game translations and engine; compare hashes to original files.
- Fill korean/release-approval.json only after playtesting the EXACT artifact:
  approved=true, version, candidate_run_id, package_sha256, reviewer,
  linguistic_review=true, and all gameplay flags=true.

## Nexus Mods (intentionally blocked until review)
- Nexus v3 official action uploads NEW VERSIONS of an existing Nexus file:
  https://github.com/Nexus-Mods/upload-action
- Create the Nexus page and first file manually. Save its existing file ID as
  repository Actions variable NEXUS_FILE_ID.
- Configure secret NEXUSMODS_API_KEY (never commit API keys).
- Add reviewer protection to the GitHub Actions environment nexus-publish.
- Run Publish approved Korean installer to Nexus Mods manually with approved
  candidate run ID and exact approved version.
- The action downloads the old, tested artifact and verifies its ZIP SHA
  against the committed approval. Without approval it MUST refuse.
- There is no auto-release on upstream pushes.
Nexus API docs: https://api-docs.nexusmods.com/
