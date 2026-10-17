# Korean NPC dialogue register review

This is a **review assistant**, NOT an auto-rewriter or a full translation QA pass.

### Why scripts matter

Fallout MSG files mix NPC dialogue, player responses, and narration. Treating
all text inside one dialogue MSG as a single speaker creates serious false
positives. The audit therefore considers only:
- Numeric Reply(ID) references from a matching .ssl script (strong NPC role signal).
- Lines with a voice identifier in MSG (may indicate voiced NPC dialogue).
- Numeric NOption/GOption references are excluded as player choices.
- IDs which are both NPC replies and player options are excluded entirely.

### What a mixed-register result means

The report detects multiple sentence-final register classes for the same MSG
file: formal, polite, archaic hao, and plain/casual. It does NOT establish
that the translation is wrong, nor that every line has the same speaker.
Situational speech shifts (threatening, mocking, addressing superiors, changing
relationship) can be correct.

### Run locally

python -m unittest discover -s korean/tests -v
python korean/audit_dialogue_register.py --script-limit 75 --out korean-speech-report

Set script-limit to 0 for all uniquely matching scripts. This may take a while
because script blobs are downloaded on demand from an upstream partial clone.

Artifacts:
- register-review.md: initial shortlist with examples
- register-review.json: complete structured findings, samples, coverage limits
- speaker-lines.csv: voice- or script-attributed Korean MSG lines for human QA

### Run on GitHub

Actions > Korean dialogue register audit (manual) > Run workflow.
Select how many scripts to inspect; download the artifact after completion.

### Human review checklist

1. Confirm the speaker via script and situation, not just the MSG filename.
2. Compare source English and original character traits to decide register.
3. Define a primary register for the speaker; document justified exceptions
   by ID and context in register-decisions.csv.
4. Check proper nouns, honorific subjects and pronouns, speaker gender/identity,
   CP949 bytes, and game layout after an actual correction.
5. Do not automatically publish a Nexus update from these suggestions.

The common Hangul Text Engine is separate; this script does not patch EXEs.
