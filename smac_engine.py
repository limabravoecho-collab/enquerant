#!/usr/bin/env python3
"""
smac_engine.py — Structural Manifold Auto-Correction (SMAC)
================================================================================
Builds the cross-tier bridge matrix (crystallization matrix) in memory at boot.
A bridge term is a topic-bearing subject term shared by two or more FISSN tiers,
present in fewer than half of all tiers. Deterministic: the same records always
produce the same matrix. No persistent file, no user data.
================================================================================
"""

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple


class SMACEngine:
    def __init__(self, grammar: Any, chat_cats: Optional[set] = None, pattern_words: Optional[List[str]] = None):
        self.grammar = grammar
        self.chat_cats = chat_cats or (set(grammar.reply_of) | set(grammar.reply_of.values()))
        self.pattern_words = pattern_words or []
        self.bridges: Counter = Counter()
        self.bridge_terms: Dict[Tuple[float, float], Counter] = defaultdict(Counter)
        self.term_tiers: Dict[str, Counter] = {}
        self.tier_count: int = 0
        self.build()

    def build(self) -> None:
        g = self.grammar
        topic_tag = max(sorted(g.open_prior), key=lambda t: g.open_prior[t]) if g.open_prior else None
        seen = defaultdict(Counter)
        for r in g.corpus_records:
            try:
                tier = float(r.get('coordinate'))
            except (TypeError, ValueError):
                continue
            for w in set(g.tokenize(r.get('subject', ''))):
                if g.is_glyph(w):
                    seen[w][tier] += 1
        self.tier_count = len({t for c in seen.values() for t in c})
        ceiling = self.tier_count / 2
        for w, tiers in seen.items():
            if len(tiers) < 2 or len(tiers) > ceiling:
                continue
            tag = g.tag_of(w)
            if tag is not None and tag != topic_tag:
                continue
            lean = g.chat_lean(w, self.chat_cats, strict=True)
            if lean is None or lean > 0.0:
                continue
            self.term_tiers[w] = tiers
            ts = sorted(tiers)
            for i, a in enumerate(ts):
                for b in ts[i + 1:]:
                    n = min(tiers[a], tiers[b])
                    self.bridges[(a, b)] += n
                    self.bridge_terms[(a, b)][w] += n

    def bridge_strength(self, tier_a: float, tier_b: float) -> int:
        key = (min(tier_a, tier_b), max(tier_a, tier_b))
        return self.bridges.get(key, 0)

    def bridge_via(self, tier_a: float, tier_b: float, k: int = 5) -> List[str]:
        key = (min(tier_a, tier_b), max(tier_a, tier_b))
        return [w for w, _ in self.bridge_terms.get(key, Counter()).most_common(k)]

    def coupled_nests(self, target_nest: float, k: int = 8) -> List[Dict[str, Any]]:
        out = []
        for (a, b), n in self.bridges.items():
            if a == target_nest:
                other = b
            elif b == target_nest:
                other = a
            else:
                continue
            out.append({"Nest": other, "Strength": n, "Via": self.bridge_via(a, b, 3)})
        out.sort(key=lambda x: (-x["Strength"], x["Nest"]))
        return out[:k]

    def source_nests(self, target_nest: float, settled: Dict[float, float], k: int = 4) -> List[Dict[str, Any]]:
        """
        Nests a correction can be drawn from: bridged to the target, ranked by
        bridge strength weighted by settled share. A strongly bridged nest built
        on placeholders is a weaker source than a moderately bridged settled one.
        """
        out = []
        for c in self.coupled_nests(target_nest, k=len(self.bridges)):
            share = settled.get(c["Nest"], 0.0)
            out.append({
                "Nest": c["Nest"],
                "Strength": c["Strength"],
                "Settled": round(share, 2),
                "Score": round(c["Strength"] * share, 1),
                "Via": c["Via"]
            })
        out.sort(key=lambda x: (-x["Score"], x["Nest"]))
        return out[:k]

    def structural_terms(self, min_tiers: int = 5) -> Dict[str, int]:
        """
        Words naming a structural behaviour, supplied by the maker in
        structural_patterns_*.tsv. Five computed approaches failed to derive
        these: frequency, tier span, subject appearance and rarity are all
        proxies, and none of them track meaning. The list is short and stable.
        Returns each term mapped to the number of tiers it appears in.
        """
        if hasattr(self, '_structural'):
            return self._structural
        g = self.grammar
        out = {}
        for w in getattr(self, 'pattern_words', ()):
            tiers = set()
            for i in g.index.get(w, ()):
                try:
                    tiers.add(float(g.corpus_records[i].get('coordinate')))
                except (TypeError, ValueError):
                    continue
            if tiers:
                out[w] = len(tiers)
        self._structural = out
        return out

    def parallel_records(self, records: List[Dict[str, Any]], exclude_tier: float, k: int = 6, min_tiers: int = 5) -> List[Dict[str, Any]]:
        """
        Records from other nests that share this query's structural pattern.
        The same principle, located elsewhere in the manifold, for the
        researcher to transfer. EQ asserts nothing about the transfer.
        """
        struct = self.structural_terms(min_tiers)
        g = self.grammar
        seed = Counter()
        for r in records[:8]:
            for w in set(g.tokenize(r.get('object', ''))) | set(g.tokenize(r.get('subject', ''))):
                if w in struct:
                    seed[w] += 1
        if not seed:
            return []
        # Rarest first: a pattern term shared by few records is a stronger
        # signal than a common one shared by many.
        # Rarest structural term first: a term in few records names a specific
        # pattern, while a common one ("used", "law") names nothing.
        terms = set(sorted(seed, key=lambda w: (len(g.index.get(w, ())), w))[:3])
        by_tier = defaultdict(list)
        for w in terms:
            for i in sorted(g.index.get(w, ())):
                r = g.corpus_records[i]
                try:
                    t = float(r.get('coordinate'))
                except (TypeError, ValueError):
                    continue
                if t == exclude_tier:
                    continue
                by_tier[t].append((w, r))
        out = []
        tiers = sorted(by_tier)
        depth = max((len(v) for v in by_tier.values()), default=0)
        for n in range(depth):
            for t in tiers:
                if n < len(by_tier[t]):
                    w, r = by_tier[t][n]
                    out.append({"Nest": t, "Via": w, "Subject": str(r.get('subject', '')), "Object": str(r.get('object', ''))})
            if len(out) >= k:
                break
        return out[:k]

    def summary(self) -> str:
        return f"SMAC matrix: {len(self.term_tiers)} bridge terms | {len(self.bridges)} tier pairs | {self.tier_count} tiers"


if __name__ == '__main__':
    import time
    from app import EnquerantOrchestrator
    o = EnquerantOrchestrator()
    t0 = time.time()
    s = SMACEngine(o.grammar)
    print(s.summary(), '| build', round(time.time() - t0, 2), 's')
    print('=== top 10 tier pairs')
    for (a, b), n in s.bridges.most_common(10):
        print(' ', a, '<->', b, '| strength', n, '|', s.bridge_via(a, b))
    print('=== coupled to tier 1.0')
    for c in s.coupled_nests(1.0):
        print(' ', c)
