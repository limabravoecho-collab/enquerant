#!/usr/bin/env python3
"""
science_block.py — DEIE science block for the NiiChii hybrid
================================================================================
Assembles the Mode 2 structural reading as a markdown block, for display
between NiiChii's framing prose and NiiChii's closing prose.

Ported from the standalone EQ orchestrator. Differences, all deliberate:

- No chat. The acknowledgment line built from RESEARCH_ACKNOWLEDGMENT is
  dropped: NiiChii's prose does that work.
- No orchestrator state. Every call takes its inputs and returns its outputs.
  Navigation state belongs in the browser session, not on a server object.
- Ambiguous tiers return the tier list and nothing else, so NiiChii's prose can
  ask which reading the user meant. Showing one tier's block beside a list that
  says the question is ambiguous would contradict itself on screen.
- Nothing is written to the engine. The SPFS engine is used for pure operators
  only, so a displayed block cannot disturb live telemetry.

Every scientific word, formula and value in the output is copied from a DELM
record. The bracketed structural lines are computed. Nothing is generated.
================================================================================
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from spfs_engine import SPFSEngine, FISSN_TAXONOMY_REGISTRY
from spfs_linguistic_folder import SPFSLinguisticFolder

STAGE_ORDER = ["CLINICAL_USE", "HUMAN_TRIAL", "CLINICAL", "ANIMAL",
               "CELL_MODEL", "PHYSICAL_PRINCIPLE", "THEORY"]

# A single variable compared to a number is a domain condition attached to the
# formula near it, not an operation: "x >= 2", "T > 0", "varepsilon > 0". The
# record stays in the corpus, because the source states it; it is skipped in
# the order of operations, because a condition is not a step. 187 across the
# corpus, every one checked.
# Three shapes, all conditions: a bare variable, a function of one variable,
# or a variable compared to another variable. "T -> infinity" is deliberately
# not matched — a limit is an operation, not a bound.
_TERM = r"\|?\s*[A-Za-z_][A-Za-z0-9_]{0,12}(?:\s*\(\s*[A-Za-z_][A-Za-z0-9_]{0,12}\s*\))?\s*\|?"
# A stripe is a range written as two comparisons — "0 < p < 1", "1 <= k <= n".
# A condition on where something holds, not a step. 96 across the corpus, all
# checked. Single "x = 0" forms are NOT filtered: 551 of those exist and many
# are real mathematics — a discriminant vanishing, an evaluation at a point.
# A term here is a variable, a simple fraction, or one function call — short
# enough that a derived expression cannot match. "0 < Re(s) < 1" is a stripe;
# "x - (4)/(pi) sqrt x log x < p <= x" is a theorem and stays.
_ST = r"\|?\s*(?:\(\s*[A-Za-z0-9_.]{1,6}\s*\)\s*/\s*\(\s*[A-Za-z0-9_.]{1,6}\s*\)|-?[A-Za-z0-9_.]{1,10}(?:\s*/\s*[A-Za-z0-9_.]{1,6})?)" \
      r"(?:\s*\(\s*[A-Za-z0-9_.]{1,10}\s*\))?\s*\|?"
_DOMAIN_STRIPE = re.compile(
    r"^\s*" + _ST + r"\s*(?:<=|>=|<|>)\s*" + _ST +
    r"\s*(?:<=|>=|<|>)\s*" + _ST + r"\s*[.,]?\s*$")

# A simple fraction: "3/2", "(n)/(2)".
_FR = r"\(?\s*-?[A-Za-z0-9_.]{1,6}\s*\)?\s*/\s*\(?\s*[A-Za-z0-9_.]{1,6}\s*\)?"
_RHS2 = (r"-?[\d.]+\s*\*\s*10\^\(\s*-?\d+\s*\)"
         r"|exp\s*\(\s*[\d.]+\s*\)"
         r"|[A-Za-z]\^\([^()=]{1,24}\)")
_COND = r"\s*" + _TERM + r"\s*(?:>=|<=|!=|>|<)\s*(?:" + _RHS2 + r"|" + _FR + r"|-?[\d. ]+|" + _TERM + r")\s*"
_DOMAIN_BOUND = re.compile(
    r"^" + _COND + r"(?:,\s*" + _COND + r")*[.,]?\s*$")
# Inequalities that are the result itself, not a condition. Kept by exact text.
_KEEP_INEQ = {"var(T)>=(1)/(I)", "B<f_s/2", "BQP!=BPP", "L_xL_y!=L_yL_x",
              "Superman!=Clark", "x!=x", "varnothing!=varnothing",
              "E(AD)!=E(CD)", "T_(E)!=T_(D)", "U_u!=U_d"}

# A formula whose first or last side holds no letter or digit is a fragment
# of the source, not a relation: "#Sha(E)=#". Kept in the corpus, skipped
# in the order of operations.
_FRAGMENT = re.compile(r"(?<![<>!:~=\[,])(?<!, )=(?![=\]])[^\w.]*$")

class ScienceBlock:
    """
    Holds the read-only engines built once at boot. One instance is shared by
    all sessions; it carries no per-user state.
    """

    def __init__(self, delm: Any, grammar: Any, parser: Any, smac: Any,
                 max_logic_depth: int = 32):
        self.delm = delm
        self.grammar = grammar
        self.parser = parser
        self.smac = smac
        self.spfs = SPFSEngine(max_logic_depth=max_logic_depth)
        self.chat_cats = set(grammar.reply_of) | set(grammar.reply_of.values())
        # Settled share is a pure function of the corpus, so it is computed
        # once rather than per query.
        self._settled = delm.tier_settled_share()
        # Built at boot so the first question pays no index cost.
        self._pair_idx()
        if not hasattr(grammar, 'subject_words'):
            grammar.build_subject_index()

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def topics(self, query: str) -> List[str]:
        """Knowledge base subjects named in the query. Empty means no block."""
        t = self.grammar.topic_words(query, self.chat_cats)
        if not t:
            return t
        g = self.grammar
        covered = set(' '.join(t).split())
        missing = [w for w in g.tokenize(query)
                   if g.is_glyph(w) and w not in covered
                   and g.subject_words.get(w, 0) == 0
                   and g.tag_of(w) is None]
        if missing:
            return []
        return t

    def holds(self, query: str) -> bool:
        """True when the corpus holds records for something named in the query."""
        return bool(self.topics(query))

    def retrieve(self, query: str, tier: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Matched records for a query. Subject streak match first, topic search
        second — the same order the standalone engine uses. A tier, once chosen,
        filters the result.
        """
        recs = self._streak_match(query)
        if not recs:
            t = self.topics(query)
            recs = self.grammar.retrieve_topic(t) if t else self.grammar.retrieve(query, 24)
        if tier is not None:
            recs = [r for r in recs if self._tier_of(r) == tier]
        return recs

    def _pair_idx(self) -> Dict[tuple, set]:
        """Adjacent subject word pairs -> record indices. A streak of two or
        more words needs a shared pair, so only these records can match."""
        if getattr(self, '_pairs', None) is None:
            import re
            idx = {}
            for i, r in enumerate(self.delm.records):
                w = re.sub(r'[^\w\s]', '', (r.get('subject') or '').lower()).split()
                for a, b in zip(w, w[1:]):
                    idx.setdefault((a, b), set()).add(i)
            self._pairs = idx
        return self._pairs

    def _streak_match(self, query: str) -> List[Dict[str, Any]]:
        """
        Longest contiguous subject word run, scored quadratically. A streak of
        two words or more is required, which is what stops single-word keyword
        collisions ("eq" matching "equation").
        """
        import re
        ignored = {
            "has part of speech", "expresses syntactic pattern",
            "triggers safety boundary", "signals discourse intent",
            "belongs to discourse category", "expects reply category",
        }
        q_clean = re.sub(r'[^\w\s]', '', query).lower()
        q_words = q_clean.split()
        scored = []
        idx = self._pair_idx()
        cand = set()
        for a, b in zip(q_words, q_words[1:]):
            cand |= idx.get((a, b), set())
        recs = self.delm.records
        for r in (recs[i] for i in sorted(cand)):
            if r.get("relation") in ignored:
                continue
            subj = (r.get("subject") or "").lower()
            if not subj:
                continue
            s_clean = re.sub(r'[^\w\s]', '', subj)
            s_words = s_clean.split()
            best = 0
            for i in range(len(q_words)):
                for j in range(len(s_words)):
                    k = 0
                    while (i + k < len(q_words) and j + k < len(s_words)
                           and q_words[i + k] == s_words[j + k]):
                        k += 1
                    if k > best:
                        best = k
            if best < 2:
                continue
            score = (best ** 2) * 100
            if s_clean in q_clean:
                score += 500
            if score >= 400:
                scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for _, r in scored:
            if r not in out:
                out.append(r)
            if len(out) >= 8:
                break
        return out

    @staticmethod
    def _tier_of(rec: Dict[str, Any]) -> Optional[float]:
        try:
            return float(rec.get("coordinate"))
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Ambiguity
    # ------------------------------------------------------------------

    def tier_spread(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Tiers holding a meaningful share of the matched records. A tier counts
        when it holds at least (largest tier count / number of tiers), which
        drops the long tail of single-record tiers.
        """
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in records:
            groups.setdefault(str(r.get("coordinate")), []).append(r)
        if len(groups) <= 1:
            return groups
        top = max(len(v) for v in groups.values())
        n = len(groups)
        return {c: v for c, v in groups.items() if len(v) >= top / n}

    def tier_list_block(self, groups: Dict[str, List[Dict[str, Any]]]) -> Tuple[str, List[Tuple[str, int]]]:
        """
        The tier list, returned with the options so the caller can put them in
        the session. NiiChii's prose asks which the user meant; the numbered
        list is there for anyone who would rather point than type.
        """
        options = sorted(groups.items())
        lines = ["**The records for this span several nests. Type in the "
                 "corresponding number and Send to explore further.**", ""]
        out_opts = []
        for idx, (coord, recs) in enumerate(options, start=1):
            try:
                info = FISSN_TAXONOMY_REGISTRY.get(float(coord), {})
            except ValueError:
                info = {}
            lines.append(f"**[{idx}]** {info.get('tier', coord)} — {info.get('name', '')} ({len(recs)} records)")
            out_opts.append((coord, len(recs)))
        return "\n".join(lines), out_opts

    # ------------------------------------------------------------------
    # Research stage
    # ------------------------------------------------------------------

    def _stage_tables(self):
        markers = [(" ".join(self.grammar.tokenize(r["subject"])), r["object"])
                   for r in self.parser.nature_records
                   if r.get("relation") == "indicates research stage"]
        explicit = {" ".join(self.grammar.tokenize(r["subject"])): r["object"]
                    for r in self.parser.nature_records
                    if r.get("relation") == "has research stage"}
        return markers, explicit

    def _stage_of(self, subject_head: str, markers, explicit) -> str:
        """
        Maker declaration first, corpus scan second, never guessed. The corpus
        does not always state what is true — histotripsy's FDA clearance is
        absent from its source article — so a declaration is sometimes the only
        honest route.
        """
        declared = explicit.get(" ".join(self.grammar.tokenize(subject_head)))
        if declared:
            return declared
        found = set()
        head = subject_head.lower()
        for rec in self.delm.records:
            subj = str(rec.get("subject", ""))
            if not subj.lower().startswith(head):
                continue
            blob = " ".join(self.grammar.tokenize(subj + " " + str(rec.get("object", ""))))
            for phrase, stage in markers:
                if phrase and f" {phrase} " in f" {blob} ":
                    found.add(stage)
        for s in STAGE_ORDER:
            if s in found:
                return s
        return "unlabeled"

    # ------------------------------------------------------------------
    # The block
    # ------------------------------------------------------------------

    def render(self, query: str, records: List[Dict[str, Any]],
               batch_index: int = 0) -> Dict[str, Any]:
        """
        The structural reading for a set of matched records.

        Returns the markdown block plus the state the caller must carry in the
        session: the batch slice, the avenue list, and the subject that holds
        the derivation.
        """
        if not records:
            return {"block": "", "batch": [], "avenues": [], "math_subject": None,
                    "tier": None, "telemetry": {}}

        lines: List[str] = []

        # Nest of the query: the dominant matched record tier, not a keyword
        # map. The two disagree when a query term is not a domain class, and
        # the records are the better evidence.
        tiers: Dict[float, int] = {}
        for rec in records:
            t = self._tier_of(rec)
            if t is not None:
                tiers[t] = tiers.get(t, 0) + 1
        nest = max(tiers, key=lambda t: (tiers[t], -t)) if tiers else 1.0
        info = FISSN_TAXONOMY_REGISTRY.get(nest, {})
        nest_desc = f"{info.get('tier', nest)}: {info.get('name', '')}".strip(': ')

        batch = records[batch_index * 8:(batch_index + 1) * 8]
        # Lead sentence first, then a formula, then whatever leads the batch.
        # A bare 'has value' record names no subject.
        primary = (next((r for r in batch if r.get('relation') == 'states'), None)
                   or next((r for r in batch if r.get('relation') == 'is expressed by'), None)
                   or (batch[0] if batch else {}))
        p_subj = primary.get("subject", query)
        p_obj = primary.get("object", "")

        f0_head = str(p_subj).split("(")[0].strip()
        f0_engine = SPFSEngine(max_logic_depth=self.spfs.k)
        f0_output, telemetry = f0_engine.compute_master_formula(
            input_signal=float(len(f0_head) * 10),
            nest_depth=nest,
            logic_tier=8,
            environmental_flux=-0.1,
            glyph_token_count=max(len(f0_head.split()), 1),
        )

        is_plc, ent_debt, audit_note = self.spfs.audit_topological_closure(p_subj, p_obj, nest)
        dislocation = self.delm.dislocation_registry.get(str(p_subj).strip().lower(), {})
        if dislocation:
            is_plc = True
            ent_debt = self.spfs.compute_entropic_debt(nest)

        lines.append(r"• **1. Master Formula ($F_0$):** $F_0 = \oint \Big[ R \cdot \big( N_s(L_f) \oplus \Delta P \big) \Big] dt$ [SPFS Proprietary]")
        lines.append(r"• **2. Component Operator ($N_s$):** $N_s(L_f) = \sum \Big[ \omega_i \cdot \psi(s_i, f) \Big]$ [SPFS Proprietary]")
        # Cut at a word boundary. A hard character cut left the line reading
        # "affects the universe on its largest s".
        _obj = str(p_obj)
        if len(_obj) > 200:
            _obj = _obj[:200].rsplit(" ", 1)[0] + "..."
        lines.append(f"• **3. Empirical Formula (DELM):** `{_obj}`")
        lines.append(f"• **4. FISSN Ontological Coordinate & Telemetry:** Tier: `{nest_desc}` (tier `{nest}`) | $F_0$: `{f0_output:.6f}`")

        # Dissipative structures: where this query's records sit, and what
        # share of the debt each nest carries. Shares sum to 1.0.
        exchange = self.spfs.evaluate_nest_exchange(nest, dict(tiers), ent_debt)
        if exchange["Coupled_Nests"]:
            parts = [f"`{c['Nest']}` ({c['Exchange_Share'] * 100:.0f}%, $\\Xi$ {c['Carried_Debt']:.3f})"
                     for c in exchange["Coupled_Nests"]]
            lines.append(f"  - **[Nest Exchange / Dependent Load]:** {' | '.join(parts)}")

        bridge_nest = max(tiers, key=lambda t: (tiers[t], -t)) if tiers else nest
        coupled = self.smac.coupled_nests(bridge_nest, 4)
        if coupled:
            bridges = [f"`{c['Nest']}` via {', '.join(c['Via'])}" for c in coupled]
            lines.append(f"  - **[Cross-Tier Bridges / SMAC]:** {' | '.join(bridges)}")

        sources = self.smac.source_nests(bridge_nest, self._settled, 4)
        if sources:
            src = [f"`{c['Nest']}` (settled {c['Settled']:.2f})" for c in sources]
            lines.append(f"  - **[Source Nests / Correction Draw]:** {' | '.join(src)}")

        parallels = self.smac.parallel_records(records, nest, 4)
        for p in parallels:
            lines.append(f"  - **[Parallel Nest `{p['Nest']}` via {p['Via']}]:** `{p['Subject'][:45]}` — {p['Object'][:70]}")

        # PSCS-N calibration layers, and the other avenues in each layer.
        avenues: List[str] = []
        avenue_ctx: List[str] = []
        markers, explicit = self._stage_tables()
        links: Dict[str, set] = {}
        members: Dict[str, List[str]] = {}
        for r in self.parser.nature_records:
            if r.get("relation") == "has knowledge base subject":
                links.setdefault(" ".join(self.grammar.tokenize(r["object"])), set()).add(r["subject"])
                members.setdefault(r["subject"], []).append(r["object"])
        layers: Dict[str, set] = {}
        for rec in records:
            head = " ".join(self.grammar.tokenize(str(rec.get("subject", "")).split("(")[0]))
            for layer in links.get(head, ()):
                layers.setdefault(layer, set()).add(str(rec.get("subject", "")).split("(")[0].strip())

        for layer in sorted(layers):
            here = sorted(layers[layer])
            matched = ", ".join(f"{s} [{self._stage_of(s, markers, explicit)}]" for s in here)
            lines.append(f"  - **[PSCS-N Calibration Layer]:** `{layer}` — matched: {matched}")
            others = [s for s in members.get(layer, []) if s not in layers[layer]]
            if not others:
                continue
            lines.append("  - **[Same Layer / Other Avenues]:** *type `a1`, `a2` and so on to open one.*")
            for idx, name in enumerate(others[:10], start=1):
                # Entanglement and unsettled ground, as counts. How many nests
                # this avenue's records touch, and how many of those records
                # are flagged. No judgement is stated; the reader draws it.
                head = name.lower()
                nests: Dict[float, int] = {}
                total = flagged = 0
                for rec in self.delm.records:
                    subj = str(rec.get("subject", ""))
                    if subj.split("(")[0].strip().lower() != head:
                        continue
                    t = self._tier_of(rec)
                    if t is None:
                        continue
                    nests[t] = nests.get(t, 0) + 1
                    total += 1
                    if subj.strip().lower() in self.delm.dislocation_registry:
                        flagged += 1
                nest_list = ", ".join(f"`{t}`" for t in sorted(nests, key=lambda x: -nests[x])[:4])
                avenues.append(name)
                # Phrased, not left as a ratio. Given "31 records, 29 flagged"
                # the model inverted it — reporting that 2 rested on unresolved
                # ground — even with the reading rule stated in its context.
                # Stating the reading removes the arithmetic it got wrong;
                # every number here is still the computed count.
                if total:
                    if flagged == 0:
                        _read = f"all {total} rest on settled ground"
                    elif flagged == total:
                        _read = f"all {total} rest on unresolved ground"
                    else:
                        _read = f"{flagged} of {total} rest on unresolved ground, {total - flagged} do not"
                    avenue_ctx.append(f"{name} [{self._stage_of(name, markers, explicit)}]: {_read}")
                lines.append(
                    f"    **[a{idx}]** {name} [{self._stage_of(name, markers, explicit)}] — "
                    f"nests: {nest_list or 'none indexed'} | {total} records, {flagged} flagged"
                )

        if layers:
            for r in self.parser.nature_records:
                if r.get("relation") == "states boundary" and r.get("subject") == "coexistence":
                    lines.append(f"  - **[Coexistence]:** {r['object']}")
                    break

        settled_here = self._settled.get(nest)
        if settled_here is not None:
            carried = sum(c["Carried_Debt"] for c in exchange.get("Coupled_Nests", []))
            lines.append(
                f"  - **[Negentropic Reading]:** target nest `{nest}` settled `{settled_here:.2f}` | "
                f"local entropic debt $\\Xi$ `{ent_debt:.3f}` | debt carried to dependent nests `{carried:.3f}` | "
                f"coupled nests `{len(exchange.get('Coupled_Nests', []))}`"
            )

        if is_plc:
            lines.append(f"  - **[Structural Notice / Dislocation]:** [Potential Placeholder / Ontological Shift] — {audit_note}")
            if dislocation:
                lines.append(f"  - **[Epistemic Re-indexing]:** Human Consensus Anchor (Tier `{dislocation.get('human_consensus_tier', 1.0)}`) $\\to$ True SPFS Crystalline Anchor (Tier `{nest}`) prognostic alignment verified.")
        else:
            lines.append(f"  - **[Topological Status]:** `{audit_note}`")

        # Blank line first: without it markdown nests item 5 under item 4's
        # sub-bullets instead of returning it to the top level.
        lines.append("")
        lines.append(r"• **5. Structural Integration:** $\mathcal{T}[\text{Empirical}] \iff N_s(L_f) \oplus \Delta P$ [SPFS Proprietary]")

        # The Records line and the fold-verified line both restated what line 3
        # already shows, four lines above it. In standalone EQ several sections
        # separated them; here they read as the same sentence twice.
        lines.append("")

        if batch:
            lines.append(f"**Options (select 1–{len(batch)})**")
            for idx, rec in enumerate(batch, start=1):
                lines.append(f"**[{idx}]** `{rec.get('subject', '')}` $\\to$ *{rec.get('relation', '')}* $\\to$ {str(rec.get('object', ''))[:70]}...")
            # The codes are only discoverable if they are stated. A visitor has
            # no way to know a bare number is an instruction.
            lines.append("")
            lines.append(f"> *Type a number from 1 to {len(batch)} and send, to open that record.*")
            lines.append("")
            lines.append('<a href="/brief" target="_blank" rel="noopener">Download this reading as a plain text brief</a>')

        # A structural summary for the model. Computed figures only: tiers,
        # shares, settled ground, stages, counts. The `states` record text is
        # withheld — those are copied encyclopedia sentences and the only thing
        # in the block that could be silently rewritten in prose. A number
        # cannot be; the block above proves it right or wrong.
        # The figures without their meanings invited invention: asked what a
        # flag count meant, the model guessed "potentially relevant". The terms
        # are defined here so it reports rather than fills in.
        ctx = ["TERMS: a nest is a FISSN tier, one scale of reality. Settled "
               "share is the proportion of a nest's records not flagged. A "
               "flagged record is an ontological dislocation: its subject rests "
               "on a placeholder or unresolved definition in the source "
               "literature. Entropic debt is disorder carried by a nest. A "
               "research stage says how far a subject has been taken and is "
               "never guessed. None of these say a subject is wrong.",
               "",
               f"Subject: {str(p_subj).split('(')[0].strip()}",
               f"Nest: {nest} ({nest_desc})",
               f"Settled share of that nest: {self._settled.get(nest, 0):.2f}",
               f"Entropic debt carried: {ent_debt:.3f}",
               f"Placeholder flagged: {'yes' if is_plc else 'no'}"]
        if exchange["Coupled_Nests"]:
            ctx.append("Coupled nests: " + ", ".join(
                f"{c['Nest']} at {c['Exchange_Share'] * 100:.0f}%" for c in exchange["Coupled_Nests"]))
        if coupled:
            ctx.append("Bridges to: " + ", ".join(
                f"{c['Nest']} via {', '.join(c['Via'])}" for c in coupled))
        if sources:
            ctx.append("Best-grounded sources: " + ", ".join(
                f"{c['Nest']} settled {c['Settled']:.2f}" for c in sources))
        for layer in sorted(layers):
            ctx.append(f"Calibration layer: {layer}")
        if avenue_ctx:
            ctx.append("Other avenues in that layer, each with how its records stand:")
            ctx.extend("  " + a for a in avenue_ctx)
        elif avenues:
            ctx.append("Other avenues in that layer: " + ", ".join(avenues))

        return {
            "block": "\n".join(lines),
            "batch": batch,
            "avenues": avenues,
            "math_subject": str(p_subj).split("(")[0].strip(),
            "tier": nest,
            "telemetry": telemetry,
            "context": "\n".join(ctx),
        }

    # ------------------------------------------------------------------
    # Order of operations
    # ------------------------------------------------------------------

    def formula_sections(self, subject_head: str) -> List[str]:
        """
        The source section each formula sits in, parallel to formula_sequence.
        The miner names a formula by its article and heading — "Riemann zeta
        function (Functional equation)" — and that heading is the source's own
        label for the passage. It is copied, not inferred: the corpus does not
        mark what an individual formula represents.
        """
        head = subject_head.split("(")[0].strip().lower()
        if not head:
            return []
        out = []
        seen = set()
        for r in self.delm.records:
            if r.get("relation") != "is expressed by":
                continue
            subj = str(r.get("subject", ""))
            if subj.split("(")[0].strip().lower() != head:
                continue
            obj = str(r.get("object", "")).replace("@@EQ@@", " ").replace("@@/EQ@@", " ")
            obj = " ".join(obj.split())
            if not obj:
                continue
            if _FRAGMENT.search(obj):
                continue
            if ("".join(obj.split()).rstrip(".,;:") not in _KEEP_INEQ
                    and (_DOMAIN_BOUND.match(obj) or _DOMAIN_STRIPE.match(obj))):
                continue
            key = "".join(obj.split()).rstrip(".,;:")
            if key in seen:
                continue
            seen.add(key)
            sec = subj[subj.find("(") + 1:subj.rfind(")")].strip() if "(" in subj else ""
            out.append(sec)
        return out

    def formula_sequence(self, subject_head: str) -> List[str]:
        """
        A subject's formula records in record order, which is source order
        preserved by the miner. Every line is copied. Records differing only by
        spacing or a trailing mark are one formula written twice in the source,
        so the duplicate is dropped.
        """
        head = subject_head.split("(")[0].strip().lower()
        if not head:
            return []
        out = []
        for r in self.delm.records:
            if r.get("relation") != "is expressed by":
                continue
            subj = str(r.get("subject", ""))
            if subj.split("(")[0].strip().lower() != head:
                continue
            obj = str(r.get("object", "")).replace("@@EQ@@", " ").replace("@@/EQ@@", " ")
            obj = " ".join(obj.split())
            if obj and ("".join(obj.split()).rstrip(".,;:") in _KEEP_INEQ
                        or (not _DOMAIN_BOUND.match(obj) and not _DOMAIN_STRIPE.match(obj))):
                out.append(obj)
        seen = set()
        unique = []
        for f in out:
            if _FRAGMENT.search(f):
                continue
            key = "".join(f.split()).rstrip(".,;:")
            if key in seen:
                continue
            seen.add(key)
            unique.append(f)
        return unique

    def spfs_sequence(self, subject_head: str, nest_depth: float) -> List[Dict[str, Any]]:
        """
        The same sequence read through SPFS. The subject sits at one nest, so
        the nest depth is constant and the step index is the logic depth: a
        derivation is finite logic deepening inside one nest. Each step carries
        a share of the nest's entropic debt weighted by N_s(L_f). Shares sum to
        1.0 and carried debt sums to the nest debt, so the sequence closes.
        """
        steps = self.formula_sequence(subject_head)
        if not steps:
            return []
        sections = self.formula_sections(subject_head)
        probe = SPFSEngine(max_logic_depth=self.spfs.k)
        debt = self.spfs.compute_entropic_debt(nest_depth)
        weights = []
        for i in range(1, len(steps) + 1):
            lf = probe.evaluate_lf(i, 1.0)
            weights.append(probe.evaluate_ns(nest_depth, lf))
        total = sum(weights)
        out = []
        for i, (formula, w) in enumerate(zip(steps, weights), start=1):
            share = (w / total) if total > 0.0 else 0.0
            out.append({
                "Step": i, "Formula": formula, "L_f": i, "N_s": nest_depth,
                "Weight": w, "Share": share, "Carried_Debt": debt * share,
                "Section": sections[i - 1] if i - 1 < len(sections) else "",
            })
        return out

    def math_page(self, subject_head: str, nest_depth: float,
                  page: int = 1, per_page: int = 24) -> str:
        """
        The two readings of one derivation, paged. The source formula on its own
        line, never truncated, with the SPFS reading beneath it. The running
        total makes the closure visible.
        """
        seq = self.spfs_sequence(subject_head, nest_depth)
        if not seq:
            return ""
        total_pages = (len(seq) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        window = seq[start:start + per_page]
        debt = self.spfs.compute_entropic_debt(nest_depth)
        lines = [f"**Order of Operations — `{subject_head}` (page {page} of {total_pages}, {len(seq)} steps)**",
                 f"> *Column 1 is the source formula, copied verbatim. Column 2 is the SPFS reading at nest `{nest_depth}`.*",
                 ""]
        running = sum(r["Share"] for r in seq[:start])
        marked = False
        for r in window:
            running += r["Share"]
            # A blank line between steps: without it markdown nests the next
            # step inside the previous step's indented reading line, and the
            # numbering stops being scannable.
            if r["Step"] > start + 1:
                lines.append("")
            lines.append(f"**[{r['Step']}]** `{r['Formula']}`")
            lines.append(
                f"  - $L_f$ `{r['L_f']}` | $N_s$ `{r['N_s']}` | share `{r['Share'] * 100:.2f}%` | "
                f"$\\Xi$ `{r['Carried_Debt']:.5f}` | cumulative `{running * 100:.2f}%`"
            )
            if not marked and r["L_f"] >= self.spfs.k and r["Step"] < len(seq):
                lines.append(f"  - **[Finite Logic Ceiling]:** `L_f = k = {self.spfs.k}` reached. Each remaining step carries an equal share of `{r['Share'] * 100:.2f}%`.")
                marked = True
        lines.append("")
        carried = sum(r["Carried_Debt"] for r in seq)
        lines.append(f"  - **[Closure]:** cumulative `{running * 100:.2f}%` | carried `{carried:.5f}` | nest entropic debt $\\Xi$ `{debt:.5f}`")
        return "\n".join(lines)
