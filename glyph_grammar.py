#!/usr/bin/env python3
"""
glyph_grammar.py — Universal Glyph Grammar
Contains zero words of any language. Words, roles, and order come only
from the active language bin records passed in.
"""

import math
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

TAG_RE = re.compile(r'^\[([^\]]+)\]$')
SURFACE_RE = re.compile(r'^(\W*)(.*?)(\W*)$', re.UNICODE)
PAREN_RE = re.compile(r'\([^)]*\)')
SENT_RE = re.compile(r'[.,!?;:]')
PUNCT_RE = re.compile(r'[^\w\s]', re.UNICODE)
START = '<S>'
END = '</S>'
INTERROGATIVE = 'INTERROGATIVE'


class GlyphGrammar:
    def __init__(self, records: List[Dict[str, Any]], grammar_coordinate: str = '0.0_GIS'):
        self.grammar_coordinate = grammar_coordinate
        self.grammar_records = [r for r in records if r.get('coordinate') == grammar_coordinate]
        self.corpus_records = [r for r in records if r.get('coordinate') != grammar_coordinate]
        self.pattern_relation: Optional[str] = None
        self.pos_relation: Optional[str] = None
        self.category_relation: Optional[str] = None
        self.pair_relation: Optional[str] = None
        self.tagset = set()
        self.lexicon = defaultdict(Counter)
        self.inferred = defaultdict(Counter)
        self.bigram = Counter()
        self.tag_count = Counter()
        self.shapes: List[Tuple[Tuple[str, ...], str]] = []
        self._lp: Dict[Tuple[str, str], float] = {}
        self._detect_relations()
        self._harvest()
        self._build_log_table()
        self.build_index()
        self.build_chat_index()

    @staticmethod
    def tokenize(text: Any) -> List[str]:
        return PUNCT_RE.sub('', SENT_RE.sub(' ', str(text))).lower().split()

    @staticmethod
    def is_glyph(tok: str) -> bool:
        return len(tok) > 1 and any(ch.isalpha() for ch in tok)

    @staticmethod
    def is_word(tok: str) -> bool:
        return len(tok) > 1 and tok.isalpha()

    def _detect_relations(self) -> None:
        objs = defaultdict(list)
        for r in self.grammar_records:
            objs[r.get('relation')].append(str(r.get('object', '')))
        best, best_frac = None, 0.0
        for rel, vals in objs.items():
            hits = sum(1 for v in vals if v.split() and all(TAG_RE.match(t) for t in v.split()))
            frac = hits / len(vals)
            if frac > best_frac:
                best, best_frac = rel, frac
        self.pattern_relation = best
        for v in objs.get(best, []):
            for t in v.split():
                m = TAG_RE.match(t)
                if m:
                    self.tagset.add(m.group(1).upper())
        best, best_frac = None, 0.0
        for rel, vals in objs.items():
            if rel == self.pattern_relation:
                continue
            hits = sum(1 for v in vals if v.strip().upper() in self.tagset)
            frac = hits / len(vals)
            if frac > best_frac:
                best, best_frac = rel, frac
        self.pos_relation = best
        subs = defaultdict(set)
        for r in self.grammar_records:
            subs[r.get('relation')].add(str(r.get('subject', '')))
        obj_sets = {rel: set(vals) for rel, vals in objs.items()}
        for rel in sorted(obj_sets, key=str):
            if rel in (self.pattern_relation, self.pos_relation):
                continue
            for other in sorted(obj_sets, key=str):
                if other == rel:
                    continue
                if subs[rel] and subs[rel] <= obj_sets[other] and obj_sets[rel] <= obj_sets[other]:
                    self.pair_relation, self.category_relation = rel, other

    def _harvest(self) -> None:
        for r in self.grammar_records:
            rel = r.get('relation')
            if rel == self.pos_relation:
                w = ' '.join(self.tokenize(r.get('subject', '')))
                t = str(r.get('object', '')).strip().upper()
                if w and t in self.tagset:
                    self.lexicon[w][t] += 1
            elif rel == self.pattern_relation:
                words = self.tokenize(r.get('subject', ''))
                tags = []
                for t in str(r.get('object', '')).split():
                    m = TAG_RE.match(t)
                    if m:
                        tags.append(m.group(1).upper())
                if not tags:
                    continue
                seq = [START] + tags + [END]
                for a, b in zip(seq, seq[1:]):
                    self.bigram[(a, b)] += 1
                    self.tag_count[a] += 1
                if len(words) == len(tags):
                    self.shapes.append((tuple(tags), str(r.get('subject', ''))))
                    for w, t in zip(words, tags):
                        self.lexicon[w][t] += 1

    def _build_log_table(self) -> None:
        tags = sorted(self.tagset)
        v = len(tags) + 1
        for a in [START] + tags:
            for b in tags + [END]:
                self._lp[(a, b)] = math.log((self.bigram[(a, b)] + 1) / (self.tag_count[a] + v))
        members = Counter()
        for w, c in self.lexicon.items():
            members[c.most_common(1)[0][0]] += 1
        present = [t for t in self.tagset if members[t] > 0]
        gmean = math.exp(sum(math.log(members[t]) for t in present) / max(len(present), 1))
        open_tags = {t: members[t] for t in present if members[t] >= gmean}
        tot = sum(open_tags.values())
        self.open_prior = {t: n / tot for t, n in open_tags.items()}

    def _options(self, w: str) -> Dict[str, float]:
        c = self.lexicon.get(w)
        if c:
            tot = sum(c.values())
            return {t: n / tot for t, n in c.items()}
        return dict(self.open_prior)

    def infer_sequence(self, tokens: List[str]) -> List[Tuple[str, str]]:
        toks = [t for t in tokens if self.is_glyph(t)]
        if not toks:
            return []
        layers = []
        prev = {START: 0.0}
        for w in toks:
            cur, back = {}, {}
            for t, e in self._options(w).items():
                s, pt = max((ps + self._lp[(p, t)], p) for p, ps in prev.items())
                cur[t] = s + math.log(e)
                back[t] = pt
            layers.append(back)
            prev = cur
        last = max(sorted(prev), key=lambda t: prev[t] + self._lp[(t, END)])
        out = [last]
        for back in reversed(layers[1:]):
            out.append(back[out[-1]])
        out.reverse()
        return list(zip(toks, out))

    def map_corpus(self, limit: Optional[int] = None) -> int:
        recs = self.corpus_records if limit is None else self.corpus_records[:limit]
        for r in recs:
            for field in ('subject', 'object'):
                for w, t in self.infer_sequence(self.tokenize(r.get(field, ''))):
                    if w not in self.lexicon:
                        self.inferred[w][t] += 1
        return len(self.inferred)

    def build_index(self) -> None:
        self.index = defaultdict(set)
        for i, r in enumerate(self.corpus_records):
            for field in ('subject', 'object'):
                for w in self.tokenize(r.get(field, '')):
                    if self.is_glyph(w):
                        self.index[w].add(i)
        n = max(len(self.corpus_records), 1)
        self.idf = {w: math.log(n / len(ids)) for w, ids in self.index.items()}

    def retrieve(self, query: str, k: int = 6) -> List[Dict[str, Any]]:
        q = [w for w in self.tokenize(query) if self.is_glyph(w)]
        scores = Counter()
        for w in set(q):
            for i in self.index.get(w, ()):
                scores[i] += self.idf[w]
        ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:k]
        return [self.corpus_records[i] for i, _ in ranked]

    @staticmethod
    def _edit_distance(a: str, b: str, limit: int) -> int:
        """Bounded edit distance. Returns limit+1 as soon as the bound is exceeded."""
        if abs(len(a) - len(b)) > limit:
            return limit + 1
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            if min(cur) > limit:
                return limit + 1
            prev = cur
        return prev[-1]

    def near_words(self, word: str, k: int = 5) -> List[str]:
        """
        Bin words within a small edit distance of an unknown word. Ranked by
        distance, then by how many knowledge base records carry the candidate.
        Contains no words: the vocabulary is the bin itself.
        """
        if not self.is_glyph(word):
            return []
        if not hasattr(self, '_fuzzy_vocab'):
            self._fuzzy_vocab = [w for w in (set(self.lexicon) | set(self.index) | set(self.inferred)) if self.is_glyph(w)]
        limit = 1 if len(word) <= 5 else 2
        flat = unicodedata.normalize('NFKD', word)
        flat = ''.join(c for c in flat if not unicodedata.combining(c))
        out = []
        for cand in self._fuzzy_vocab:
            d = self._edit_distance(word, cand, limit)
            if 0 < d <= limit:
                cflat = unicodedata.normalize('NFKD', cand)
                cflat = ''.join(c for c in cflat if not unicodedata.combining(c))
                accent_only = 0 if cflat == flat else 1
                out.append((d, accent_only, -len(self.index.get(cand, ())), cand))
        out.sort()
        return [c for _, _, _, c in out[:k]]

    def retrieve_topic(self, topics: List[str], k: int = 64) -> List[Dict[str, Any]]:
        if not hasattr(self, 'subject_heads'):
            self.build_subject_index()
        ids = set()
        for t in topics:
            words = [w for w in t.split() if self.is_glyph(w)]
            if not words:
                continue
            common = set(self.index.get(words[0], ()))
            for w in words[1:]:
                common &= self.index.get(w, set())
            if not common and len(words) > 1:
                # A joined phrase that matches no record: fall back to the
                # individual terms, ranked by how few records carry them, so
                # the most specific term leads.
                if not hasattr(self, 'subject_words'):
                    self.build_subject_index()
                for w in sorted(words, key=lambda x: -self.subject_words.get(x, 0)):
                    part = set(self.index.get(w, ()))
                    if part:
                        common = part
                        break
            ids |= common
        ranks = [defaultdict(list), defaultdict(list), defaultdict(list)]
        for i in sorted(ids):
            r = self.corpus_records[i]
            subj = str(r.get('subject', ''))
            head = ' '.join(self.tokenize(PAREN_RE.sub(' ', subj)))
            full = f" {' '.join(self.tokenize(subj))} "
            parts = {p for t in topics for p in t.split()}
            if head in topics or head in parts:
                rank = 0
            elif any(f" {t} " in full for t in topics):
                rank = 1
            else:
                rank = 2
            ranks[rank][str(r.get('coordinate'))].append(r)
        out = []
        for groups in ranks:
            tiers = [groups[c] for c in sorted(groups)]
            depth = max((len(x) for x in tiers), default=0)
            for n in range(depth):
                for x in tiers:
                    if n < len(x):
                        out.append(x[n])
            if len(out) >= k:
                break
        return out[:k]

    def build_chat_index(self) -> None:
        self.chat_units = []
        self.chat_pos = []
        self.chat_sentences = set()
        other_subjects = set()
        for r in self.grammar_records:
            if r.get('relation') not in (self.pattern_relation, self.category_relation, self.pair_relation):
                other_subjects.add(' '.join(self.tokenize(r.get('subject', ''))))
        p = 0
        for r in self.grammar_records:
            rel = r.get('relation')
            if rel == self.pattern_relation:
                words = self.tokenize(r.get('subject', ''))
                tags = []
                for t in str(r.get('object', '')).split():
                    m = TAG_RE.match(t)
                    if m:
                        tags.append(m.group(1).upper())
                if words and len(words) == len(tags):
                    self.chat_units.append((str(r.get('subject', '')), list(zip(words, tags)), tuple(tags)))
                    self.chat_pos.append(None if ' '.join(words) in other_subjects else p)
                    self.chat_sentences.add(' '.join(words))
                p += 1
            elif rel == self.pos_relation:
                w = ' '.join(self.tokenize(r.get('subject', '')))
                t = str(r.get('object', '')).strip().upper()
                if w and t in self.tagset:
                    self.chat_units.append((w, [(w, t)], None))
                    self.chat_pos.append(None)
        self.chat_index = defaultdict(set)
        for i, (_, tagged, _) in enumerate(self.chat_units):
            for w, _ in tagged:
                for p in w.split():
                    self.chat_index[p].add(i)
        n = max(len(self.chat_units), 1)
        self.chat_idf = {w: math.log(n / len(ids)) for w, ids in self.chat_index.items()}
        self.word_next = defaultdict(Counter)
        for _, tg, shape in self.chat_units:
            seq = [w for w, _ in tg]
            if shape is None and len(seq[0].split()) > 1:
                continue
            seq = [START] + seq + [END]
            for a, b in zip(seq, seq[1:]):
                self.word_next[a][b] += 1
        self.word_total = {a: sum(c.values()) for a, c in self.word_next.items()}
        self.word_next2 = defaultdict(Counter)
        for _, tg, shape in self.chat_units:
            if shape is None:
                continue
            seq = [START, START] + [w for w, _ in tg] + [END]
            for a, b, c in zip(seq, seq[1:], seq[2:]):
                self.word_next2[(a, b)][c] += 1
        self.word_total2 = {k: sum(v.values()) for k, v in self.word_next2.items()}
        self.pos_tags = {}
        for (_, _, shape), p in zip(self.chat_units, self.chat_pos):
            if p is not None and shape:
                self.pos_tags[p] = set(shape)
        m = max(len(self.pos_tags), 1)
        df = Counter(t for ts in self.pos_tags.values() for t in ts)
        self.tag_idf = {t: math.log(m / n) for t, n in df.items()}
        self.category_of = defaultdict(set)
        self.reply_of = {}
        for r in self.grammar_records:
            rel = r.get('relation')
            if rel == self.category_relation:
                self.category_of[' '.join(self.tokenize(r.get('subject', '')))].add(str(r.get('object', '')))
            elif rel == self.pair_relation:
                self.reply_of[str(r.get('subject', ''))] = str(r.get('object', ''))
        self.chat_cat = [self.category_of.get(' '.join(w for w, _ in tg), set()) for _, tg, _ in self.chat_units]
        self.surface_mid = defaultdict(Counter)
        self.surface_any = defaultdict(Counter)
        # Forms split by tag. A token that flattens two words apart in meaning
        # ("its" possessive, "it's" contraction) carries a different tag for
        # each, so the tag selects the form where frequency alone picks wrong.
        self.surface_tag = defaultdict(Counter)
        self.pair_mark = defaultdict(Counter)
        self.end_mark = defaultdict(Counter)
        self.end_mark2 = defaultdict(Counter)
        self.clause_end = defaultdict(Counter)
        caps = Counter()
        end_cnt = Counter()
        mid_cnt = Counter()
        for text, tg, shape in self.chat_units:
            if shape is None:
                continue
            toks = []
            for raw in str(text).split():
                m = SURFACE_RE.match(raw)
                core = m.group(2)
                word = ''.join(self.tokenize(core))
                if not word:
                    continue
                toks.append((word, core, m.group(3).strip('"\'')))
            if not toks:
                continue
            first = toks[0][1][:1]
            if first.upper() != first.lower():
                caps[first.isupper()] += 1
            tag_by_slot = [t for _, t in tg] if len(tg) == len(toks) else []
            for i, (w, core, mark) in enumerate(toks):
                self.surface_any[w][core] += 1
                if tag_by_slot:
                    self.surface_tag[(w, tag_by_slot[i])][core] += 1
                if i > 0:
                    self.surface_mid[w][core] += 1
                if i + 1 < len(toks):
                    self.pair_mark[(w, toks[i + 1][0])][mark] += 1
                    if mark:
                        mid_cnt[mark[-1]] += 1
                else:
                    self.end_mark[w][mark] += 1
                    if i > 0:
                        self.end_mark2[(toks[i - 1][0], w)][mark] += 1
                    if mark:
                        end_cnt[mark[-1]] += 1
            last_start = toks[0][0]
            for i in range(1, len(toks)):
                if toks[i - 1][2]:
                    last_start = toks[i][0]
            self.clause_end[last_start][toks[-1][2]] += 1
        self.start_capital = caps[True] > caps[False]
        self.end_chars = {ch for ch in end_cnt if end_cnt[ch] > mid_cnt[ch]}

    def retrieve_chat(self, query: str, k: int = 8) -> List[Tuple[str, List[Tuple[str, str]], Optional[Tuple[str, ...]]]]:
        q = set(self.tokenize(query))
        scores = Counter()
        for w in q:
            for i in self.chat_index.get(w, ()):
                scores[i] += self.chat_idf[w]

        def cover(i: int) -> float:
            parts = [p for w, _ in self.chat_units[i][1] for p in w.split()]
            return sum(1 for p in parts if p in q) / max(len(parts), 1)

        ranked = sorted(scores, key=lambda i: (-scores[i], -cover(i), i))[:k]
        return [self.chat_units[i] for i in ranked]

    def input_tags(self, tokens: List[str]) -> Counter:
        tags = Counter()
        i = 0
        while i < len(tokens):
            matched = False
            for j in range(len(tokens), i, -1):
                ph = ' '.join(tokens[i:j])
                if ph in self.lexicon:
                    tags[self.lexicon[ph].most_common(1)[0][0]] += 1
                    i = j
                    matched = True
                    break
            if not matched:
                i += 1
        return tags

    def retrieve_chat_block(self, query: str, width: int = 36) -> List[Tuple[str, List[Tuple[str, str]], Optional[Tuple[str, ...]]]]:
        tokens = self.tokenize(query)
        q = set(tokens)
        in_tags = set(self.input_tags(tokens))
        hits = defaultdict(set)
        for w in q:
            for i in self.chat_index.get(w, ()):
                if self.chat_pos[i] is not None:
                    hits[self.chat_pos[i]].add(w)
        tag_hit = {}
        for p, ts in self.pos_tags.items():
            s = sum(self.tag_idf[t] for t in ts & in_tags)
            if s > 0.0:
                tag_hit[p] = s
        positions = sorted(set(hits) | set(tag_hit))
        if not positions:
            return []
        h = width // 2
        best_c, best_key = None, None
        for c in positions:
            found = set()
            total = 0.0
            dens = 0.0
            for p in positions:
                if p < c - h or p >= c + h:
                    continue
                found |= hits.get(p, set())
                total += sum(self.chat_idf[w] for w in hits.get(p, ()))
                dens += tag_hit.get(p, 0.0)
            key = (sum(self.chat_idf[w] for w in found) + dens, total)
            if best_key is None or key > best_key:
                best_c, best_key = c, key
        return [u for u, p in zip(self.chat_units, self.chat_pos) if p is not None and best_c - h <= p < best_c + h]

    def build_subject_index(self) -> None:
        self.subject_heads = Counter()
        self.subject_words = Counter()
        for r in self.corpus_records:
            subj = str(r.get('subject', ''))
            key = ' '.join(self.tokenize(PAREN_RE.sub(' ', subj)))
            if key:
                self.subject_heads[key] += 1
            for w in set(self.tokenize(subj)):
                self.subject_words[w] += 1

    def topic_words(self, query: str, chat_cats: set) -> List[str]:
        if not hasattr(self, 'subject_words'):
            self.build_subject_index()
        topic_tag = max(sorted(self.open_prior), key=lambda t: self.open_prior[t]) if self.open_prior else None
        toks = self.tokenize(query)
        out = []
        last_end = -1
        i = 0
        while i < len(toks):
            hit = 0
            for j in range(len(toks), i + 1, -1):
                ph = ' '.join(toks[i:j])
                if ph not in self.subject_heads:
                    continue
                if any(self.tag_of(w) is None or self.tag_of(w) in self.open_prior for w in toks[i:j] if self.is_glyph(w)):
                    out.append(ph)
                    hit = j - i
                    break
            if hit:
                i += hit
                last_end = -1
                continue
            w = toks[i]
            t = self.tag_of(w)
            ok = self.is_glyph(w) and self.subject_words.get(w, 0) > 0 and (t is None or t == topic_tag)
            if ok:
                lean = self.chat_lean(w, chat_cats, strict=True)
                ok = lean is not None and lean <= 0.0
            if ok:
                if last_end == i and out:
                    out[-1] = out[-1] + ' ' + w
                else:
                    out.append(w)
                last_end = i + 1
            i += 1
        return out

    def chat_lean(self, query: str, chat_cats: set, strict: bool = False) -> Optional[float]:
        n_chat = sum(1 for cs in self.chat_cat if cs & chat_cats)
        n_other = sum(1 for cs in self.chat_cat if cs and not cs & chat_cats)
        n_non = n_other + len(self.corpus_records)
        if n_chat == 0 or n_non == 0:
            return None
        lowest = None
        for w in set(self.tokenize(query)):
            if not self.is_glyph(w):
                continue
            t = self.tag_of(w)
            if t is not None and t not in self.open_prior:
                continue
            ids = self.chat_index.get(w, ())
            c = sum(1 for u in ids if self.chat_cat[u] & chat_cats)
            x = sum(1 for u in ids if self.chat_cat[u] and not self.chat_cat[u] & chat_cats)
            k = len(self.index.get(w, ()))
            if strict:
                lean = float('-inf') if c == 0 else math.log(c / n_chat) - math.log((x + k + 1) / n_non)
            else:
                lean = math.log((c + 1) / n_chat) - math.log((x + k + 1) / n_non)
            if lowest is None or lean < lowest:
                lowest = lean
        return lowest

    def input_category(self, query: str, prefer_pair: bool = True) -> Optional[str]:
        tokens = self.tokenize(query)
        found = Counter()
        i = 0
        while i < len(tokens):
            step = 1
            for j in range(len(tokens), i, -1):
                ph = ' '.join(tokens[i:j])
                if ph in self.category_of:
                    for c in self.category_of[ph]:
                        found[c] += j - i
                    step = j - i
                    break
            i += step
        if not found:
            words = defaultdict(set)
            for w in set(tokens):
                for u in self.chat_index.get(w, ()):
                    for c in self.chat_cat[u]:
                        words[c].add(w)
            for c, ws in words.items():
                found[c] = sum(self.chat_idf[w] for w in ws)
        if not found:
            return None
        pool = [c for c in found if c in self.reply_of] if prefer_pair else []
        pool = pool or list(found)
        return max(sorted(pool), key=lambda c: found[c])

    def retrieve_reply_units(self, query: str) -> List[Tuple[str, List[Tuple[str, str]], Optional[Tuple[str, ...]]]]:
        cat = self.input_category(query)
        reply = self.reply_of.get(cat) if cat else None
        if reply is None:
            return []
        return [u for u, cs in zip(self.chat_units, self.chat_cat) if reply in cs and u[2] is not None]

    def surface(self, words: List[str], units: Any = None, shape: Any = None) -> str:
        if not words:
            return ''
        unit_ends = Counter()
        for text, _, _ in units or []:
            parts = str(text).split()
            if parts:
                mk = SURFACE_RE.match(parts[-1]).group(3).strip('"\'')
                if mk:
                    unit_ends[mk] += 1
        out = []
        cap_next = self.start_capital
        clause_start = words[0]
        for i, w in enumerate(words):
            slot_tag = shape[i] if shape and i < len(shape) else None
            tag_forms = self.surface_tag.get((w, slot_tag)) if slot_tag else None
            if tag_forms:
                # The mid-sentence form is preferred where the tag has one: a
                # word that is always capital keeps its capital, and a word
                # capitalised only by sentence position does not.
                mid = Counter({k: n for k, n in tag_forms.items() if self.surface_mid.get(w, {}).get(k)})
                form = (mid or tag_forms).most_common(1)[0][0]
            elif self.surface_mid.get(w):
                form = self.surface_mid[w].most_common(1)[0][0]
            elif self.surface_any.get(w):
                f = self.surface_any[w].most_common(1)[0][0]
                form = f[:1].lower() + f[1:]
            else:
                form = w
            if cap_next and form:
                form = form[:1].upper() + form[1:]
            cap_next = False
            if i + 1 < len(words):
                top = self.pair_mark.get((w, words[i + 1]), Counter()).most_common(1)
                mark = top[0][0] if top else ''
                form += mark
                if mark:
                    clause_start = words[i + 1]
                cap_next = self.start_capital and bool(mark) and mark[-1] in self.end_chars
            else:
                prev = words[i - 1] if i > 0 else None
                # A statement shape takes a statement mark. Without this, a
                # final word that happened to end two questions in the bin
                # drags a question mark onto a declarative sentence
                # ("...heading to the leaves?").
                question = bool(shape) and shape[0] == INTERROGATIVE
                def _filter(c):
                    return Counter({k: n for k, n in c.items()
                                    if k and ((k[-1] == '?') == question)})
                ends2 = _filter(self.end_mark2.get((prev, w), Counter()))
                ends = _filter(self.end_mark.get(w, Counter()))
                endc = _filter(self.clause_end.get(clause_start, Counter()))
                unit_ends = _filter(unit_ends)
                top = (ends2 or endc or ends or unit_ends).most_common(1)
                form += top[0][0] if top else ''
            out.append(form)
        return ' '.join(out)

    def tag_of(self, w: str) -> Optional[str]:
        c = self.lexicon.get(w) or self.inferred.get(w)
        return c.most_common(1)[0][0] if c else None

    def shape_score(self, tags: Tuple[str, ...]) -> float:
        seq = [START] + list(tags) + [END]
        return sum(self._lp[(a, b)] for a, b in zip(seq, seq[1:])) / (len(seq) - 1)

    def select_shapes(self, target_len: int, k: int = 5) -> List[Tuple[str, ...]]:
        seen, out = set(), []
        ranked = sorted(enumerate(self.shapes), key=lambda x: (abs(len(x[1][0]) - target_len), -self.shape_score(x[1][0]), x[0]))
        for _, (tags, _) in ranked:
            if tags[0] == INTERROGATIVE or tags in seen:
                continue
            seen.add(tags)
            out.append(tags)
            if len(out) >= k:
                break
        return out

    def fill_shape_chained(self, shape: Tuple[str, ...], tagged: List[Tuple[str, str]], query_tokens: List[str], engine: Any) -> Tuple[Optional[List[str]], Optional[float]]:
        stats = {}
        for i, (w, t) in enumerate(tagged):
            if w not in stats:
                stats[w] = [0, i, Counter()]
            stats[w][0] += 1
            stats[w][2][t] += 1
        q = set(query_tokens)
        layer = {START: (0.0, [])}
        for slot, tag in enumerate(shape):
            new = {}
            for w, (occ, pos, tags) in sorted(stats.items()):
                if tag not in tags:
                    continue
                emit = engine.score_glyph_candidate(occ, pos, slot, w in q)
                best = None
                for p, (ps, path) in sorted(layer.items()):
                    if w in path and tag in self.open_prior:
                        continue
                    tr = engine.score_glyph_transition(self.word_next[p][w], self.word_total.get(p, 0))
                    if tr <= 0.0:
                        continue
                    s = ps + emit + tr
                    if best is None or s > best[0]:
                        best = (s, path + [w])
                if best is not None:
                    new[w] = best
            if not new:
                return None, None
            layer = new
        final = None
        for w, (s, path) in sorted(layer.items()):
            tr = engine.score_glyph_transition(self.word_next[w][END], self.word_total.get(w, 0))
            if tr <= 0.0:
                continue
            if final is None or s + tr > final[0]:
                final = (s + tr, path)
        if final is None:
            return None, None
        return final[1], final[0] / len(shape)

    def fill_shape_chained3(self, shape: Tuple[str, ...], tagged: List[Tuple[str, str]], query_tokens: List[str], engine: Any) -> Tuple[Optional[List[str]], Optional[float]]:
        stats = {}
        for i, (w, t) in enumerate(tagged):
            if w not in stats:
                stats[w] = [0, i, Counter()]
            stats[w][0] += 1
            stats[w][2][t] += 1
        q = set(query_tokens)
        layer = {(START, START): (0.0, [])}
        for slot, tag in enumerate(shape):
            new = {}
            for w, (occ, pos, tags) in sorted(stats.items()):
                if tag not in tags:
                    continue
                emit = engine.score_glyph_candidate(occ, pos, slot, w in q)
                for key, (ps, path) in sorted(layer.items()):
                    if w in path and tag in self.open_prior:
                        continue
                    nxt = self.word_next2.get(key)
                    tr = engine.score_glyph_transition(nxt.get(w, 0) if nxt else 0, self.word_total2.get(key, 0))
                    if tr <= 0.0:
                        continue
                    s = ps + emit + tr
                    nk = (key[1], w)
                    if nk not in new or s > new[nk][0]:
                        new[nk] = (s, path + [w])
            if not new:
                return None, None
            layer = new
        final = None
        for key, (s, path) in sorted(layer.items()):
            nxt = self.word_next2.get(key)
            tr = engine.score_glyph_transition(nxt.get(END, 0) if nxt else 0, self.word_total2.get(key, 0))
            if tr <= 0.0:
                continue
            if final is None or s + tr > final[0]:
                final = (s + tr, path)
        if final is None:
            return None, None
        return final[1], final[0] / len(shape)

    def _splice_step(self, a: str, b: str, c: str, jumps: int, engine: Any) -> Tuple[float, int]:
        nxt = self.word_next2.get((a, b))
        tr = engine.score_glyph_transition(nxt.get(c, 0) if nxt else 0, self.word_total2.get((a, b), 0))
        if tr > 0.0:
            return tr, jumps
        if jumps >= 1:
            return 0.0, jumps
        tr = engine.score_glyph_transition(self.word_next.get(b, {}).get(c, 0), self.word_total.get(b, 0))
        return tr * 0.5, jumps + 1

    def fill_shape_spliced(self, shape: Tuple[str, ...], tagged: List[Tuple[str, str]], query_tokens: List[str], engine: Any) -> Tuple[Optional[List[str]], Optional[float]]:
        stats = {}
        for i, (w, t) in enumerate(tagged):
            if w not in stats:
                stats[w] = [0, i, Counter()]
            stats[w][0] += 1
            stats[w][2][t] += 1
        q = set(query_tokens)
        layer = {(START, START, 0): (0.0, [])}
        n_slots = len(shape)
        for slot, tag in enumerate(shape):
            # A jump in the final slots decides how the sentence ends, and no
            # bin sentence supports that ending. Mid-sentence jumps between
            # function words recover; a jump onto the last content word does
            # not ("...let's proceed with the time").
            late = slot >= n_slots - 2
            new = {}
            for w, (occ, pos, tags) in sorted(stats.items()):
                if tag not in tags:
                    continue
                emit = engine.score_glyph_candidate(occ, pos, slot, w in q)
                for key, (ps, path) in sorted(layer.items()):
                    if w in path and tag in self.open_prior:
                        continue
                    tr, nj = self._splice_step(key[0], key[1], w, key[2], engine)
                    if tr <= 0.0:
                        continue
                    if late and nj > key[2]:
                        continue
                    s = ps + emit + tr
                    nk = (key[1], w, nj)
                    if nk not in new or s > new[nk][0]:
                        new[nk] = (s, path + [w])
            if not new:
                return None, None
            layer = new
        final = None
        for key, (s, path) in sorted(layer.items()):
            tr, _ = self._splice_step(key[0], key[1], END, key[2], engine)
            if tr <= 0.0:
                continue
            if final is None or s + tr > final[0]:
                final = (s + tr, path)
        if final is None:
            return None, None
        return final[1], final[0] / len(shape)


if __name__ == '__main__':
    import time
    from crystal_loader import CrystalLoader
    c = CrystalLoader()
    if not c.records:
        c.ingest_crystal()
    t0 = time.time()
    g = GlyphGrammar(c.records)
    print('=== detected relations')
    print('  pattern:', g.pattern_relation)
    print('  part of speech:', g.pos_relation)
    print('  tagset:', sorted(g.tagset))
    print('  open tags:', {t: round(p, 3) for t, p in sorted(g.open_prior.items())})
    t0 = time.time()
    n = g.map_corpus(limit=2000)
    print('=== corpus map (2000 records)')
    print('  inferred words:', n, '| time', round(time.time() - t0, 2), 's')
    by_tag = defaultdict(list)
    for w, cnt in g.inferred.items():
        by_tag[cnt.most_common(1)[0][0]].append((sum(cnt.values()), w))
    for t in sorted(by_tag):
        print(' ', t, [w for _, w in sorted(by_tag[t], reverse=True)[:8]])
    print('=== statement shapes near length 5')
    for s in g.select_shapes(5, 5):
        print(' ', ' '.join(s))
    print('=== fill test')
    rec = next(r for r in g.corpus_records if len(str(r.get('object', ''))) > 40)
    text = str(rec.get('subject', '')) + ' ' + str(rec.get('object', ''))
    print('  source:', text[:120])
    tagged = g.infer_sequence(g.tokenize(text))
    print('  tagged:', tagged[:12])
