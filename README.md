# EnQuerant (EQ) V2.0

A deterministic science exploration engine. No LLM, no GPU, no randomness. It
reads a sealed knowledge base compiled from encyclopedic sources and shows you
what it holds, where each subject sits, and what it connects to.

The same input always gives the same output.

Maker Note: EQ DELM's are intentionally built to 4 MB so it can be used for
legacy/obsolete systems. You can tinker with the py files as you see fit. EQ
requires no internet connection to function.

---

## What it is

EQ is a Static Logic Crystal (SLC) running on the Deterministic Empirical
Interactive Engine (DEIE) framework. It computes on CPU through pure
mathematical topology and substrate logic formulas.

Every scientific word, formula and value on screen is copied from a source
record. EQ restates; it does not rewrite, derive or assert. Where a line is EQ's
own design rather than established science, it is marked `[SPFS Proprietary]`.

EQ is a science bot, not a chat bot. It will greet you and close a session, but
that is incidental. It is not a companion and gives no support content.

---

## What is here, and what is not

**Included**

- The runtime: 9 Python files.
- Maker-written data: FISSN taxonomy, PSCS-N calibration, SLC nature,
  structural patterns, query fillers, state directions.
- `gis_english.bin` — the language data. Ships with the system; see below.
- `delm_miner/` — the DELM miner and the article lists.
- `gis_miner/` — the language miner, for transparency; see below.
- Documentation: architecture, help, about, spfs.

**Not included**

- `niichii_v*.bin` — the knowledge base. You mine your own. See below.

---

### Example output

Two structural briefs generated from this engine, deliberately different:

- `examples/riemann-hypothesis-brief.txt` — a settled subject in a
  dimensionless nest, where entropic debt reads as incompleteness in the
  record. No bridged nest rests on firmer ground.
- `examples/navier-stokes-brief.txt` — an unsettled subject in a dimensional
  nest, where the same figure reads as disorder in the system. Two bridged
  nests rest on firmer ground than its own.

Same arithmetic, different reading. Every figure in both is computed and every
formula copied from a source record.

The brief generator is part of a proprietary bridge between EQ and my own
AI/LLM system, and is not included here. The engine, the ontology and the
miners are — building your own bridge is straightforward, and any capable AI
tool will help you do it.

---

## Building the knowledge base

EQ needs its DELM volumes before it can do anything. They are not shipped: the
content comes from Wikipedia, and it is better that each installation pulls it
from the source rather than receiving a binary.

1. Download the Wikipedia multistream dump and its index, once, from
   https://dumps.wikimedia.org/enwiki/latest/

   - `enwiki-latest-pages-articles-multistream.xml.bz2` (~22 GB)
   - `enwiki-latest-pages-articles-multistream-index.txt.bz2` (~250 MB)

   Put both in `delm_miner/wiki_dump/`, or set `WIKI_DUMP_DIR` to point
   wherever they live.

2. Build the index and the article cache. Both are one-time.

   ```
   cd delm_miner
   python3 mine_delm_complete.py --build-index
   python3 mine_delm_complete.py --build-cache
   ```

3. Mine.

   ```
   python3 mine_delm_complete.py
   ```

If you change the miner's cleaning rules, delete `article_cache/` before
re-mining. The cache holds already-cleaned text, so a rule change has no
effect until the cache is rebuilt.

4. Copy the sealed volumes up to the runtime directory.

   ```
   cp delm_volumes/niichii_v*.bin ..
   ```

   The copy is deliberate rather than automatic: a failed mine writing directly
   into the runtime would overwrite a working knowledge base.

Nothing is generated at any point. The miner reads Wikipedia's own markup — a
formula sits in a `<math>` tag, the lead is the text before the first heading,
a section heading names what follows it — so every character written was copied
from the source.

---

## The article lists

`delm_miner/article_lists/` holds 1,183 article titles across 12 FISSN
coordinates, one file per coordinate. Which tier an article belongs to is a
classification decision, made once per list, by hand. No classifier guesses.

Tiers 4.1 (Reflexive Epistemics & Cultural Records) and 4.2 (Semiotic &
Aesthetic Projections) appear in the FISSN registry but have no article list.
That is deliberate, not an omission.

Add your own titles to any list and re-mine. Adding a subject is article titles
plus a re-mine, never a hand-written record.

---

## The language data

`gis_english.bin` ships with EQ and is the reference build. It carries word
roles, sentence patterns, discourse categories and reply pairs, and it is what
the documentation describes.

`gis_miner/gis_mine.py` is included for transparency. It requires a local LLM,
which supplies raw sentence text only — all tagging, categories and reply pairs
are assigned deterministically by the script, and no LLM is used by EQ at
runtime.

A re-mined bin will produce a different system: different chat, different
cross-tier bridges, different structural lines. Configure it for your own model
if you want to explore. The shipped bin is the one described here.

---

## Running it

```
python3 enquerant_gui.py
```

Boot is about 2.5 seconds. The knowledge base, the glyph grammar and the
cross-tier bridge matrix are built in memory at every start; nothing is cached
to disk, because the same records always produce the same matrix.

EQ will not start until the knowledge base is built. Complete the mining steps
above first; the volumes must sit beside the runtime files.

Type `!help` for the codes, `!about` for what the screen labels mean, and
`!spfs` for the formula system.

---

## The boundary

SPFS is EQ's own logic layer. It is built on established principles —
conservation of energy, the second law, negentropy (Schrödinger), dissipative
structures (Prigogine), Le Chatelier, Poincaré recurrence, hierarchy in systems
ecology, Shannon entropy — but the formulas themselves are EQ design, not
established law.

Every line carrying them is marked `[SPFS Proprietary]` so the two can be told
apart at a glance.

Every structural reading is a conservation reading: a quantity is divided and
the parts sum back to the whole. Shares total 100%, carried debt totals the
nest's debt, the energy ledger balances at zero every turn. If a reading cannot
close, it is not shown.

---

## Licence

Free for non-commercial use — personal, study, teaching, academic research,
non-profit organisations — with credit to this repository. You may integrate it
into your own systems, including AI and LLM systems.

Commercial use requires a separate agreement.
[Open an issue](https://github.com/limabravoecho-collab/enquerant/issues) to arrange one.

See LICENSE.md for the full terms.

---

## Attribution

DELM content is derived from Wikipedia, licensed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Mined
knowledge base volumes are derivative works and carry the same licence. None
are distributed here.

The runtime, the SPFS and FISSN systems, the maker-written data files and the
article list classifications are proprietary to EQ/SPFS.
