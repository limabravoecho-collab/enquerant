#!/usr/bin/env python3
"""
brief.py — the structural brief, as a downloadable plain text document
================================================================================
Assembles everything the visitor refined to — their subject, its nest, its
bridges, its source nests, its calibration layer and avenues, and the full
order of operations — into one file.

Arrangement matters as much as content. The reading leads; the methodology
closes. A reader who discards most of what crosses their desk meets the finding
in the first ten lines, not after four hundred words of preamble.

Every sentence is computed or copied. No sentence is generated, and nothing is
asserted: the observations section states measurements and comparisons, never
a proposal about what they mean.
================================================================================
"""

from typing import Any, Dict, List, Optional
from spfs_engine import FISSN_TAXONOMY_REGISTRY

RULE = "=" * 78
THIN = "-" * 78

METHOD = """\
{rule}
5. HOW THIS DOCUMENT WAS BUILT
{rule}

Engine
    EnQuerant (EQ) V2.0 / Deterministic Empirical Interactive Engine.
    Pure CPU. No language model, no GPU, no randomness. The same subject
    always produces the same document.

Provenance
    Every scientific word, formula and value is copied verbatim from a source
    record mined from encyclopedic sources. Every figure is computed from those
    records. No sentence in this document was generated, and none argues
    anything: it reports where a subject sits and what the source states.

    Lines marked [SPFS Proprietary] are the Maker's own design rather than
    established science. The SPFS operators are built on established principles
    — conservation of energy, the second law, negentropy, dissipative
    structures, Le Chatelier, Poincare recurrence, hierarchy in systems
    ecology, Shannon entropy — but the formulas themselves are not established
    law.

Terms
    Nest
        One FISSN tier: one scale of reality, from 0.0 (axiomatic and
        deductive) to 6.2 (high-order convergence). Where a fact is filed, not
        whether it is right.

    Settled share
        The proportion of a nest's records whose subject is not flagged, 0.00
        to 1.00. Logic sits near 0.93, physiology near 0.30.

    Flagged record
        An ontological dislocation: the subject rests on a placeholder or an
        unresolved definition in the source literature. "31 records, 29
        flagged" means 29 rest on unresolved ground and 2 do not. A flag marks
        ground to inspect. It does not mean the science is wrong.

    Entropic debt (Xi)
        What a nest carries that is not settled. Above nest 1.0 the nests are
        dimensional — matter, energy, time — and the figure reads as disorder
        in the system itself. At nests 0.0 and 0.1 nothing dissipates, so the
        same figure reads as incompleteness in the record of it. The arithmetic
        is identical; the reading is not.

    Bridge
        A term genuinely shared between two nests in the knowledge base. A real
        overlap, never an analogy.

    Research stage
        How far a subject has been taken, read from the corpus or declared,
        never guessed: CLINICAL_USE, HUMAN_TRIAL, CLINICAL, ANIMAL,
        CELL_MODEL, PHYSICAL_PRINCIPLE, THEORY. PHYSICAL_PRINCIPLE is settled
        physics, not an unproven theory.

The SPFS operators
    Shown so the second column can be checked by hand. These are the Maker's
    own design. The constants were set by judgement, not derived.

        Entropic debt of a nest
            Xi(s) = (s * 0.42) * (1 + |s - 1.0| * 0.5)
            Scales with depth and with distance from the reference tier 1.0.

        Logic attenuation at step i
            L_f(i) = 1 / min(i, k)        with k = 32
            Finite: past step k every step attenuates identically. That bound
            is why a long sequence flattens.

        Nest attenuation
            N_s(s, f) = f * (1 / (1 + s))
            A deeper nest attenuates more.

        Share of the nest's debt carried by step i
            w_i    = N_s(s, L_f(i))
            share  = w_i / sum of all w
            Xi_i   = Xi(s) * share

    Worked example, first step of a sequence at nest 0.1:
        Xi(0.1)  = (0.1 * 0.42) * (1 + 0.9 * 0.5) = 0.06090
        L_f(1)   = 1/1 = 1
        N_s      = 1 * (1 / 1.1) = 0.9091
        The remaining weights are computed the same way; each share is that
        step's weight over their sum, and the shares total 1.

    The shares sum to 100% and the carried debt sums to Xi(s). That is the
    closure reported at the end of each sequence. If it does not close, the
    sequence is not shown.

Order of operations
    Column 1 is the subject's formulas in the order the source states them,
    copied verbatim, each labelled with the section it was drawn from. Column 2
    reads the same sequence through SPFS: the nest is constant and the step
    index is the logic depth, so each step carries a share of the nest's
    entropic debt. The shares sum to 100% and the carried debt sums to the nest
    debt. The sequence closes.

    The corpus does not mark logical dependency between formulas, so column 1
    is a faithful source sequence, not a derived order. Domain conditions
    ("x >= 2", "T > 0") are held in the corpus but excluded from the sequence:
    a condition is stated, but it is not a step. Source fragments with an
    empty side ("B =") are excluded for the same reason.

    The weighting makes that order consequential. Where a subject's formulas
    are simultaneous constraints rather than derivation steps — a kinematic
    relation and an equation-of-state parameter, say — reordering them in the
    source would redistribute the debt between them with nothing physical
    changing. The ledger records the order the source states, not causal flow.
    Read the shares as source precedence and weigh them accordingly.

Limits
    The document reports what the knowledge base holds. A subject absent from
    the corpus is absent here. It restates records; it does not verify them.
    Nothing it displays is medical, legal or professional advice, and nothing
    in it is a proof.
"""


class Brief:
    """Assembles a structural brief from a science reading."""

    def __init__(self, science: Any):
        self.science = science

    # ------------------------------------------------------------------

    def build(self, subject: str, nest: float, block: str,
              avenues: Optional[List[str]] = None,
              stamp: str = "") -> str:
        """
        The brief for one refined reading. `block` is the reading as it was
        displayed, so the document and the screen cannot disagree.
        """
        info = FISSN_TAXONOMY_REGISTRY.get(nest, {})
        nest_name = f"{info.get('tier', nest)}: {info.get('name', '')}".strip(': ')
        seq = self.science.spfs_sequence(subject, nest)
        avenues = avenues or []

        out = [RULE,
               f"STRUCTURAL BRIEF — {subject.upper()}",
               RULE,
               "",
               f"Nest       : {nest}  ({nest_name})",
               f"Generated  : {stamp or 'unknown'}",
              "Engine     : EnQuerant (EQ) V2.0 / DEIE — deterministic, CPU, no language model",
               "Note       : F_0 here is fixed per subject. The on-screen F_0 also",
               "             varies with the query text and the session tick.",
               "",
               "Every figure below is computed and every formula copied from a source",
               "record. Nothing here is generated and nothing is argued. Section 5 states",
               "the method and the limits.",
               ""]

        # 1. The finding, first.
        out.append(RULE)
        out.append("1. THE READING")
        out.append(RULE)
        out.append("")
        out.append(self._summary(subject, nest, seq))
        out.append("")

        # 2. What is measurably unusual, stated as comparison only.
        obs = self._observations(subject, nest, seq, avenues)
        if obs:
            out.append(RULE)
            out.append("2. OBSERVATIONS")
            out.append(RULE)
            out.append("")
            out.append("Measurements and comparisons only. Each states what is the case; none")
            out.append("proposes what it means.")
            out.append("")
            out.append(obs)
            out.append("")

        # 3. The full structural reading as displayed.
        out.append(RULE)
        out.append("3. STRUCTURAL POSITION")
        out.append(RULE)
        out.append("")
        out.append(self._plain(block))
        out.append("")

        # 4. The order of operations.
        out.append(RULE)
        out.append(f"4. ORDER OF OPERATIONS — {subject}")
        out.append(RULE)
        out.append("")
        if seq:
            out.append(self._sequence(seq, nest))
        else:
            out.append("The knowledge base holds no formula records for this subject.")
        out.append("")

        if avenues:
            out.append(RULE)
            out.append("4b. ORDER OF OPERATIONS — OTHER AVENUES IN THIS LAYER")
            out.append(RULE)
            out.append("")
            for name in avenues:
                a_seq = self.science.spfs_sequence(name, nest)
                out.append(THIN)
                out.append(name)
                out.append(THIN)
                out.append("")
                out.append(self._sequence(a_seq, nest) if a_seq else "No formula records.")
                out.append("")

        # 5. Method last.
        out.append(METHOD.format(rule=RULE))
        out.append(RULE)
        out.append("END OF BRIEF")
        out.append(RULE)
        return "\n".join(out)

    # ------------------------------------------------------------------

    def _summary(self, subject: str, nest: float, seq: List[Dict[str, Any]]) -> str:
        """
        The finding in one paragraph, arranged rather than argued. A reader who
        discards most of what crosses their desk meets this first.
        """
        settled = self.science._settled.get(nest)
        debt = self.science.spfs.compute_entropic_debt(nest)
        coupled = self.science.smac.coupled_nests(nest, 4)
        sources = self.science.smac.source_nests(nest, self.science._settled, 4)

        lines = [f"{subject} is filed at nest {nest}."]
        if settled is not None:
            lines.append(
                f"That nest is settled to {settled:.2f}: {settled * 100:.0f}% of its records "
                f"rest on ground the source literature does not mark as provisional. It "
                f"carries an entropic debt of {debt:.5f}.")
        if coupled:
            via = "; ".join(f"{c['Nest']} via {', '.join(c['Via'])}" for c in coupled)
            lines.append(f"It shares terms with {len(coupled)} other nests — {via}.")
        if sources:
            best = max(sources, key=lambda c: c['Settled'])
            lines.append(
                f"The best-grounded of its neighbours is nest {best['Nest']}, settled to "
                f"{best['Settled']:.2f}.")
        if seq:
            lines.append(
                f"The source states {len(seq)} formula{'' if len(seq) == 1 else 's'} for it"
                + (", given below. " if len(seq) == 1 else ", in the order given below. ")
                + ("" if len(seq) == 1 else "It marks no dependency between them."))
        else:
            lines.append("The source states no formulas for it.")
        return "\n".join(self._wrap(" ".join(lines)))

    def _observations(self, subject: str, nest: float,
                      seq: List[Dict[str, Any]], avenues: List[str]) -> str:
        """
        What is measurably unusual about this reading. Every line is a
        comparison between computed figures. None says what the comparison
        means: that step belongs to the reader.
        """
        out = []
        settled = self.science._settled.get(nest)
        all_shares = [v for v in self.science._settled.values() if v is not None]

        if settled is not None and all_shares:
            avg = sum(all_shares) / len(all_shares)
            rank = sorted(all_shares, reverse=True).index(settled) + 1
            out.append(
                f"- Nest {nest} is settled to {settled:.2f} against a mean of {avg:.2f} "
                f"across {len(all_shares)} nests: rank {rank} of {len(all_shares)}.")

        sources = self.science.smac.source_nests(nest, self.science._settled, 4)
        firmer = [c for c in sources if settled is not None and c['Settled'] > settled]
        if firmer:
            names = ", ".join(f"{c['Nest']} ({c['Settled']:.2f})" for c in firmer)
            noun = "nest rests" if len(firmer) == 1 else "nests rest"
            out.append(f"- {len(firmer)} bridged {noun} on firmer ground than this one: {names}.")
        elif sources and settled is not None:
            out.append("- No bridged nest rests on firmer ground than this one.")

        coupled = self.science.smac.coupled_nests(nest, 4)
        far = [c for c in coupled if abs(float(c['Nest']) - nest) >= 3.0]
        if far:
            names = ", ".join(f"{c['Nest']} via {', '.join(c['Via'][:2])}" for c in far)
            noun = "bridge reaches" if len(far) == 1 else "bridges reach"
            out.append(f"- {len(far)} {noun} three tiers or further: {names}.")

        if seq:
            k = self.science.spfs.k
            past = sum(1 for r in seq if r["L_f"] >= k)
            if past:
                out.append(
                    f"- {len(seq)} steps are stated; {past} fall at or past the finite logic "
                    f"ceiling (k = {k}) and carry an identical share of the nest's debt.")
            else:
                if len(seq) == 1:
                    out.append(f"- 1 step is stated, below the finite logic ceiling (k = {k}).")
                else:
                    out.append(f"- {len(seq)} steps are stated, all below the finite logic ceiling (k = {k}).")
            if len(seq) == 1:
                out.append("- The single step carries 100.00% of the nest's debt.")
            else:
                out.append(
                    f"- The first step carries {seq[0]['Share'] * 100:.2f}% of the nest's debt; "
                    f"the last carries {seq[-1]['Share'] * 100:.2f}%.")

        secs = [r.get("Section") for r in seq if r.get("Section")]
        if secs:
            uniq = []
            for x in secs:
                if x not in uniq:
                    uniq.append(x)
            if len(uniq) == 1:
                noun = "formula is" if len(seq) == 1 else "formulas are"
                out.append(f"- The {noun} drawn from 1 section of the source.")
            else:
                out.append(f"- The formulas are drawn from {len(uniq)} distinct sections of the source.")

        if avenues:
            markers, explicit = self.science._stage_tables()
            stages = {}
            for a in avenues:
                st = self.science._stage_of(a, markers, explicit)
                stages.setdefault(st, []).append(a)
            if len(stages) > 1:
                parts = "; ".join(f"{k2}: {len(v)}" for k2, v in stages.items())
                out.append(
                    f"- The {len(avenues)} other avenues in this layer span {len(stages)} "
                    f"research stages — {parts}.")

        return "\n".join(out)

    # ------------------------------------------------------------------

    def _sequence(self, seq: List[Dict[str, Any]], nest: float) -> str:
        """The two readings of one derivation, in plain text."""
        debt = self.science.spfs.compute_entropic_debt(nest)
        lines = []
        running = 0.0
        marked = False
        for r in seq:
            running += r["Share"]
            sec = r.get("Section") or ""
            if sec:
                lines.append(f"[{r['Step']}] ({sec})")
                lines.append(f"      {r['Formula']}")
            else:
                lines.append(f"[{r['Step']}] {r['Formula']}")
            lines.append(
                f"      L_f {r['L_f']} | N_s {r['N_s']} | share {r['Share'] * 100:.2f}% | "
                f"Xi {r['Carried_Debt']:.5f} | cumulative {running * 100:.2f}%"
            )
            if not marked and r["L_f"] >= self.science.spfs.k and r["Step"] < len(seq):
                lines.append(f"      [finite logic ceiling: L_f = k = {self.science.spfs.k}; "
                             f"each remaining step carries {r['Share'] * 100:.2f}%]")
                marked = True
            lines.append("")
        carried = sum(r["Carried_Debt"] for r in seq)
        lines.append(f"CLOSURE: cumulative {running * 100:.2f}% | "
                     f"carried {carried:.5f} | nest entropic debt Xi {debt:.5f}")
        return "\n".join(lines)

    @staticmethod
    def _wrap(text: str, width: int = 78) -> List[str]:
        out, line = [], ""
        for word in text.split():
            if len(line) + len(word) + 1 > width:
                out.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            out.append(line)
        return out

    @staticmethod
    def _plain(block: str) -> str:
        """
        The displayed reading, with markdown and math delimiters removed. The
        content is unchanged: this is the same text the visitor saw.
        """
        block = block.replace(
            "**[Same Layer / Other Avenues]:** *type `a1`, `a2` and so on to open one.*",
            "**[Same Layer / Other Avenues]:**")
        cut = block.find("**Options (select")
        if cut != -1:
            block = block[:cut].rstrip()
        tex = [
            ("$\\to$", "->"), ("$\\Xi$", "Xi"), ("\\oint", "\u222e"),
            ("\\sum", "\u03a3"), ("\\cdot", "\u00b7"), ("\\oplus", "\u2295"),
            ("\\Delta", "\u0394"), ("\\omega", "\u03c9"), ("\\psi", "\u03c8"),
            ("\\mathcal{T}", "T"), ("\\text{", "{"), ("\\iff", "<=>"),
            ("\\Big[", "["), ("\\Big]", "]"), ("\\big(", "("), ("\\big)", ")"),
            ("\\Xi", "Xi"),
        ]
        out = []
        for line in block.split("\n"):
            t = line.replace("**", "").replace("`", "")
            for a, b in tex:
                t = t.replace(a, b)
            t = t.replace("$", "").replace("\\", "")
            out.append(t.rstrip())
        return "\n".join(out)
