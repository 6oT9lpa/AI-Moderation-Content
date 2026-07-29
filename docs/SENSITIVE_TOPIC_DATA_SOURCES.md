# Sensitive-topic training data

`scripts/training/curate_sensitive_topics.py` builds a reproducible extension of
`data/exports/moderation_dataset_v2` for racial, gender, and family-directed
moderation cases.

## Sources

| Source | Pinned revision | License | Usage |
| --- | --- | --- | --- |
| `ucberkeley-dlab/measuring-hate-speech` | `5468f6e118396646b02a2f691e771f6b6d9502ea` | CC BY 4.0 | Race/gender target flags, hate score, and high-confidence violence fields |
| `google/civil_comments` | `f2970eb3a55777454c94069077cc8d9b5866312d` | CC0 1.0 | Toxicity, identity attack, threat, obscenity, and sexual-explicit scores for target-topic text |
| Local `profanity_train.jsonl` | Local file supplied by the dataset owner | Project-local | Russian slang, profanity, evasion, toxicity, and contrast examples |

The Measuring Hate Speech adapter retains only comments where at least half of
the annotations mark race or gender as the target. Its dataset card defines a
`hate_speech_score > 0.5` as approximately hate speech and `< -1` as counter or
supportive speech. Ambiguous examples are excluded.

Civil Comments examples are retained only when the text contains a configured
race, gender, or family target. Harmful labels require high upstream scores:
`toxicity/insult >= 0.7`, `severe_toxicity >= 0.5`, `identity_attack >= 0.5`,
`threat >= 0.5`, `sexual_explicit >= 0.5`, or `obscene >= 0.7`. Target-topic
rows with every score at or below `0.1` are retained as SAFE contrast examples.

## Relabeling safeguards

Existing rows are automatically changed only when a target expression occurs
near an explicit degradation, hate-action, threat, sexual, or profanity
pattern. Counter-speech patterns suppress automatic relabeling. Ambiguous rows
that already carry a relevant harmful label are written to the review JSONL
files instead of being guessed.

The final merge:

- reads label order from `configs/training/rubert_tiny2.yaml`;
- unions labels for duplicate normalized text;
- keeps SAFE exclusive;
- gives validation precedence over train to prevent text leakage;
- validates every JSONL row before replacing the active files;
- creates checksummed backups of the previous train and validation files;
- removes its temporary staging directory and SQLite database.

Install the curation dependencies and run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-curation.txt
.\.venv\Scripts\python.exe scripts\training\curate_sensitive_topics.py
```

## Gap completion sources

The follow-up `complete_dataset_gaps.py` pipeline adds:

- `wangyuancheng/discord-phishing-scam-clean` at revision
  `acd7149c2cd227c296f1f4f82411160dfcd9adb7` (MIT). Only rows containing
  the source's `<DISCORD_INVITE>` privacy placeholder are accepted.
- `klamas/russian-toxic` at revision
  `eea2e077780960596524fc5bffcdd473775edaed` (MIT). Only positive rows
  where the local matcher independently confirms family-targeted `TOXIC`
  evidence are accepted.
- `IvanFed/russian-toxic-comments-multilabel` at revision
  `ac1ea37cb7b85cfec6f09ba22f71d4fe487b43d7` (Apache-2.0). Only source
  `threat=1` rows where the local matcher independently confirms an explicit
  family-targeted threat are accepted.

`INVITE` is a technical class: production sanitization replaces actual Discord
invite URLs with `<DISCORD_INVITE>`. The pipeline therefore uses controlled
bilingual templates containing the canonical placeholder to fill the remaining
coverage gap without storing live invite codes.

Family-only insults and threats are deliberately not labelled `HATE`. The
project contract reserves `HATE` for protected-group attacks; family insults
map to `TOXIC`, and family threats map to `THREAT + TOXIC`.
