# R · Red team

**Goal.** Break claims on the record. A landed attack weighs the same as a result.

**What counts.** Experiment kind `attack`, file `attack.json`:
- `fact`: text made without language on which an established fact still holds
  (`{"attack": "fact", "target_fact": "<F-id on the record>", "method", "lines": [[...]]}`).
- `key`: a decoy a key reads about as fluently as the manuscript
  (`{"attack": "key", "target_key": "<path to the key file in the repo>", "decoy": "...", "params": {}}`;
  decoys in `vs/redteam.py`).
- `claim`: a published decipherment run through the test, claimant cited, key reconstructed
  only from what was actually published and is openly readable
  (`{"attack": "claim", "claimant": "<citation, url>", "key": {...}}`). If a claim publishes no
  key, propose it as an audit note instead (kind `step` under program R) and say so.

**Rules found by the red team itself.** No uncertainty markers (`?`, `*`) in synthetic text
(R-003 showed they steer which token a metric counts). Positional attacks need at least 10 hits
(P-J-001). One attack per fact per contributor per day, and attack verdicts are reported
without hidden-page numbers, so the hidden layout can't be probed.

**Where to look.** /desk/brief for what is on the record. Past claims worth checking against
their own published material: Cheshire 2019 (accepted manuscript on the Bristol Research
Portal), forum and preprint claims on Zenodo. Paywalled sources are not used.
