#!/usr/bin/env python3
"""
mine_delm_complete.py — DELM Extraction Miner, deterministic edition.
================================================================================
Reads named Wikipedia articles out of the multistream archive and writes sealed
niichii volumes. No model, no GPU, no generation. Every character written was
copied from the source.

WHAT CHANGED AND WHY
--------------------
The previous edition sent each passage to an 8B language model and asked it to
produce subject-relation-object triples. That model was never contributing
knowledge: the validation gate already required every subject and every equation
to appear verbatim in the passage. What the model contributed was segmentation,
and segmentation is available from the markup for free.

Wikipedia tags what it holds. A formula sits in a <math> tag. The lead is the
text before the first heading. A section heading names what follows it. The
coordinate comes from the operator's filename. Nothing needs to be inferred, so
nothing is generated, so nothing can be invented.

The measured consequence: a 39-hour run becomes minutes, and the corpus stops
losing the numeric constants that {{val}} and {{physconst}} carry.

WHAT IT EXTRACTS
----------------
Three record kinds, all from one article:

  LEAD      one record per sentence of the lead section.
            subject = article title, relation = "states"

  FORMULA   one record per <math> tag and per {{val}}-style value.
            subject = nearest section heading, or the title in the lead.
            relation = "is expressed by"

  VALUE     numeric quantities with units found in prose.
            relation = "has value"

DOWNLOAD (one time, then offline forever):
    https://dumps.wikimedia.org/enwiki/latest/
        enwiki-latest-pages-articles-multistream.xml.bz2        (~22 GB)
        enwiki-latest-pages-articles-multistream-index.txt.bz2  (~250 MB)

RUN:
    python3 mine_delm_complete.py --build-index    (once)
    python3 mine_delm_complete.py --build-cache    (once, ~30 min)
    python3 mine_delm_complete.py                  (minutes, repeatable)

The cache holds the cleaned text of every listed article as plain files. Rule
changes are then re-run against the cache in seconds rather than paying the
decompression cost again.

LAYOUT:
    mine_delm_complete.py
    article_lists/
        1.0_articles.txt      <- one article title per line
    article_cache/            <- built by --build-cache
    sources/                  <- optional; .txt passages still work
    delm_volumes/             <- output
================================================================================
"""

import os
import re
import sys
import bz2
import json
import time
import struct
import hashlib
import argparse
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Any, Optional, Tuple, Set

# ==============================================================================
# [1] CONFIGURATION
# ==============================================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SOURCES_DIR = os.path.join(BASE_DIR, "sources")
LISTS_DIR = os.path.join(BASE_DIR, "article_lists")
CACHE_DIR = os.path.join(BASE_DIR, "article_cache")
OUTPUT_DIR = os.path.join(BASE_DIR, "delm_volumes")

# The Wikipedia dump. Default location is a wiki_dump folder beside this
# script; override with the WIKI_DUMP_DIR environment variable if the archive
# lives elsewhere. The two files are downloaded once from
# https://dumps.wikimedia.org/enwiki/latest/ and never touched again.
DUMP_DIR = os.environ.get("WIKI_DUMP_DIR") or os.path.join(BASE_DIR, "wiki_dump")
DUMP_DIR = os.path.expanduser(DUMP_DIR)
DUMP_PATH = os.path.join(
    DUMP_DIR, "enwiki-latest-pages-articles-multistream.xml.bz2")
DUMP_INDEX_BZ2 = os.path.join(
    DUMP_DIR, "enwiki-latest-pages-articles-multistream-index.txt.bz2")
TITLE_OFFSET_MAP = os.path.join(BASE_DIR, "title_offsets.json")

CHUNK_SIZE_BYTES = 4 * 1024 * 1024
RECORD_TYPE_EMPIRICAL = 1

# Articles shorter than this after cleaning are stubs.
MIN_ARTICLE_CHARS = 600

# A lead sentence shorter than this carries no claim.
MIN_SENTENCE_CHARS = 30
# Longer than this and it is a run-on that cleaning failed to break.
MAX_SENTENCE_CHARS = 400

# Relations. Structural labels, not authored prose: each names what kind of
# record this is, and the content is entirely copied from the source.
REL_LEAD = "states"
REL_FORMULA = "is expressed by"
REL_VALUE = "has value"


# ==============================================================================
# [2] FISSN COORDINATE TABLE
# ==============================================================================
# Used to validate a list's filename prefix and to reject any record whose
# subject is one of these labels. A coordinate name is where a fact is filed,
# not a thing that acts.

FISSN_COORDS: Dict[str, str] = {
    "0.0": "Zero Domain",
    "0.1": "Quantitative Dimensions & Finites",
    "1.0": "Fundamental Forces & Chemical Dynamics",
    "2.0": "Cosmic Horizon",
    "2.1": "Planetary Enclosure",
    "3.0": "Autonomous Living Substrate",
    "3.1": "Bio-Somatic Maintenance",
    "4.0": "Individual Mind & Neural Hardware",
    "4.1": "Reflexive Epistemics & Cultural Records",
    "4.2": "Semiotic & Aesthetic Projections",
    "5.0": "Distributed Collective Systems",
    "6.0": "Civilizational Infrastructure",
    "6.1": "Synthetic Systems & Applied Mechanics",
    "6.2": "High-Order Multi-Scale Convergence",
}

_ONTOLOGY_LABELS: Set[str] = {n.lower() for n in FISSN_COORDS.values()}


# ==============================================================================
# [3] WIKITEXT CLEANING
# ==============================================================================
# Wikitext carries markup that must never reach a record: templates, citations,
# tables, infoboxes. The aim is plain prose with equations preserved and
# headings kept as markers, because the heading is what names a formula.

_RE_COMMENT = re.compile(r"<!--.*?-->", re.S)
_RE_REF_PAIR = re.compile(r"<ref[^>/]*>.*?</ref>", re.S | re.I)
_RE_REF_SELF = re.compile(r"<ref[^>]*/\s*>", re.I)
_RE_MATH = re.compile(r"<math[^>]*>(.*?)</math>", re.S | re.I)
_RE_TAGGED = re.compile(r"<[^>]+>")
_RE_TABLE = re.compile(r"\{\|.*?\|\}", re.S)
_RE_HEADING = re.compile(r"^={2,}\s*(.*?)\s*={2,}\s*$", re.M)
_RE_BOLD_IT = re.compile(r"'{2,5}")
_RE_FILE_LINK = re.compile(r"\[\[(?:File|Image|Category)\s*:[^\]]*\]\]", re.I)
_RE_LINK_PIPED = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
_RE_LINK_PLAIN = re.compile(r"\[\[([^\]]+)\]\]")
_RE_EXT_LINK = re.compile(r"\[https?://[^\s\]]+\s*([^\]]*)\]")
_RE_LIST_MARK = re.compile(r"^[\*\#:;]+\s*", re.M)
_RE_BLANKS = re.compile(r"\n{3,}")

# Sections past the substance of an article. "history" is deliberately absent:
# in physics articles a History section commonly precedes the mathematical
# treatment, so truncating there discarded the equation-bearing body.
_STOP_SECTIONS = {
    "see also", "references", "notes", "further reading", "external links",
    "bibliography", "sources", "citations", "footnotes", "gallery",
    "in popular culture", "publications",
}

# A heading is kept as a marker line so the lead boundary is findable and a
# formula can be named by the section it sits in.
HEADING_MARK = "@@H@@ "

_TEX_WRAPPERS = ("mathrm|text|textrm|mathbf|mathit|boldsymbol|operatorname|"
                 "hat|vec|bar|tilde|dot|ddot|overline|underline|mbox|"
                 "displaystyle|textstyle|mathcal|mathbb|mathsf|rm|bf|it")
_RE_WRAPPER = re.compile(r"\\(?:" + _TEX_WRAPPERS + r")\s*\{([^{}]*)\}")

# \begin{align} leaves the word "align" and its && alignment markers behind
# once the braces are stripped, so an equation renders as
# "align rho ... &= ... align". The environment name is removed with its
# braces, and the alignment and row-break markers with it.
_RE_ENVIRONMENT = re.compile(
    r"\\(?:begin|end)\s*\{[^{}]*\}")
_RE_ALIGN_MARK = re.compile(r"&|\\\\")

_RE_STRUCTURAL = re.compile(
    r"\\(?:left|right|bigg?l?r?|Bigg?l?r?|langle|rangle|lvert|rvert|"
    r"lVert|rVert|quad|qquad|hspace|vspace|nonumber|label|limits|"
    r",|;|!|:|\s)")

_RE_FRAC = re.compile(r"\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_RE_SQRT = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_RE_SUPSUB = re.compile(r"([_^])\s*\{([^{}]*)\}")

_TEX_SYMBOLS = [
    # The ellipsis runs first and \cdot carries a word boundary. Without both,
    # \cdot matched the first four characters of \cdots and every ellipsis in
    # the corpus was written as "*s".
    (r"\\cdots|\\dots|\\ldots", "..."),
    (r"\\times", "*"), (r"\\cdot\b", "*"), (r"\\div", "/"),
    (r"\\approx", " ~= "), (r"\\propto", " ~ "), (r"\\equiv", " = "),
    (r"\\leq\b|\\le\b", " <= "), (r"\\geq\b|\\ge\b", " >= "),
    (r"\\neq\b|\\ne\b", " != "), (r"\\pm", " +/- "),
    (r"\\to\b|\\rightarrow|\\Rightarrow", " -> "),
    (r"\\leftarrow|\\Leftarrow", " <- "),
    (r"\\partial", "d"), (r"\\nabla", "grad"),
    (r"\\infty", "infinity"),
]
_RE_SYMBOLS = [(re.compile(a), b) for a, b in _TEX_SYMBOLS]

# Formulas are wrapped in these markers during cleaning so they can be pulled
# out afterwards as records in their own right. Without a marker a converted
# formula is indistinguishable from surrounding prose.
EQ_OPEN = "@@EQ@@"
EQ_CLOSE = "@@/EQ@@"


def latex_to_plain(s: str) -> str:
    """
    Reduces a LaTeX fragment to copyable ASCII.

    Iterative because LaTeX nests: a single-level frac pattern cannot match
    until a wrapper inside it has resolved. One pass stored "fracdQT", which is
    neither a formula nor recoverable. Unrecognised commands keep their word,
    since dropping them turned "S = k_B ln Omega" into "S = k_B".
    """
    out = _RE_ENVIRONMENT.sub(" ", s)
    out = _RE_ALIGN_MARK.sub(" ", out)
    for _ in range(8):
        before = out
        out = _RE_WRAPPER.sub(r"\1", out)
        out = _RE_FRAC.sub(r"(\1)/(\2)", out)
        out = _RE_SQRT.sub(r"sqrt(\1)", out)
        out = _RE_SUPSUB.sub(r"\1(\2)", out)
        if out == before:
            break
    out = _RE_STRUCTURAL.sub(" ", out)
    for pat, rep in _RE_SYMBOLS:
        out = pat.sub(rep, out)
    out = re.sub(r"\\([a-zA-Z]+)", r" \1 ", out)
    out = out.replace("{", " ").replace("}", " ")
    out = re.sub(r"\s+([\^_\)\],])", r"\1", out)
    out = re.sub(r"([\(\[])\s+", r"\1", out)
    return re.sub(r"\s+", " ", out).strip()


def strip_templates(text: str) -> str:
    """
    Removes {{...}} including nested braces.

    A regex cannot match balanced delimiters, and infoboxes nest several deep.
    Scanning once with a depth counter is exact and no slower.
    """
    out = []
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("{{", i):
            depth += 1
            i += 2
        elif text.startswith("}}", i):
            if depth:
                depth -= 1
            i += 2
        else:
            if depth == 0:
                out.append(text[i])
            i += 1
    return "".join(out)

def strip_file_links(text: str) -> str:
    """
    Removes [[File:...]], [[Image:...]] and [[Category:...]] including nested
    links inside captions. A regex stops at the first ]] which commonly belongs
    to a link inside the caption, leaving the caption tail as prose: a lead
    sentence then began mid-caption ("s of Thrush nightingale ...").
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("[[", i) and re.match(r"\[\[\s*(?:File|Image|Category)\s*:", text[i:i + 20], re.I):
            depth = 0
            j = i
            while j < n:
                if text.startswith("[[", j):
                    depth += 1
                    j += 2
                elif text.startswith("]]", j):
                    depth -= 1
                    j += 2
                    if depth == 0:
                        break
                else:
                    j += 1
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)

def _expand_val(m) -> str:
    """
    Expands {{val|NUMBER|e=EXP|u=UNIT}}.

    Wikipedia writes every measured value through this template, and
    strip_templates removes braces wholesale. Leaving it unhandled deleted the
    number from the sentence that defined it: the lead of "Speed of light" read
    "exactly equal to  It is exact because", and no physical constant survived
    anywhere in the previous corpus.
    """
    parts = [p.strip() for p in m.group(1).split("|") if p.strip()]
    num = exp = unit = ""
    for p in parts:
        low = p.lower()
        if low.startswith("e="):
            exp = p[2:].strip()
        elif low.startswith("u=") or low.startswith("ul="):
            unit = p.split("=", 1)[1].strip()
        elif not num:
            num = p
    if not num:
        return " "
    out = num
    if exp:
        out += f" * 10^({exp})"
    if unit:
        out += f" {unit}"
    return f" {out} "


def clean_wikitext(text: str) -> str:
    """
    Reduces wikitext to plain prose, with formulas marked and headings kept.

    Order matters throughout. The dump stores article text XML-escaped, so a
    math tag arrives as &lt;math&gt;; every pattern below matches literal angle
    brackets, and unescaping last meant the converters ran against text that
    contained no tags.
    """
    t = text.replace("&lt;", "<").replace("&gt;", ">")
    t = t.replace("&quot;", '"').replace("&nbsp;", " ").replace("&amp;", "&")
    t = _RE_COMMENT.sub(" ", t)
    t = _RE_REF_PAIR.sub(" ", t)
    t = _RE_REF_SELF.sub(" ", t)

    # Math is converted rather than dropped: the equations are the point. The
    # markers survive the rest of cleaning so the formula can be lifted out as
    # its own record afterwards.
    t = _RE_MATH.sub(
        lambda m: f" {EQ_OPEN}{latex_to_plain(m.group(1))}{EQ_CLOSE} ", t)

    # Inline templates carrying content rather than formatting. These must be
    # unwrapped before strip_templates, which removes braces wholesale.
    t = re.sub(r"\{\{\s*(?:math|mvar|nowrap)\s*\|\s*(?:1=)?([^{}|]*)\}\}",
               r" \1 ", t, flags=re.I)
    t = re.sub(r"\{\{\s*val\s*\|([^{}]*)\}\}", _expand_val, t, flags=re.I)
    # convert/cvt hold a quantity and its unit: {{convert|300000|km/s|mph}}.
    # Only the first two parameters are the value and its unit.
    t = re.sub(
        r"\{\{\s*(?:convert|cvt)\s*\|\s*([^|{}]+)\|\s*([^|{}]+)(?:\|[^{}]*)?\}\}",
        r" \1 \2 ", t, flags=re.I)
    t = re.sub(r"\{\{\s*s?frac\s*\|\s*([^|{}]+)\|\s*([^|{}]+)\}\}",
               r" (\1)/(\2) ", t, flags=re.I)
    # Spacing templates. Removed wholesale they fuse adjacent words.
    t = re.sub(r"\{\{\s*(?:nbsp|snd|spaces?)\s*(?:\|[^{}]*)?\}\}", " ",
               t, flags=re.I)

    t = strip_templates(t)
    t = _RE_TABLE.sub(" ", t)
    t = strip_file_links(t)
    t = _RE_LINK_PIPED.sub(r"\2", t)
    t = _RE_LINK_PLAIN.sub(r"\1", t)
    t = _RE_EXT_LINK.sub(r"\1", t)
    t = _RE_TAGGED.sub(" ", t)
    t = _RE_BOLD_IT.sub("", t)
    t = _RE_LIST_MARK.sub("", t)

    # Headings become marker lines rather than blanks. The heading is what
    # names a formula, and the first heading is where the lead ends. Blanking
    # them discarded both facts.
    lines = t.split("\n")
    kept: List[str] = []
    for line in lines:
        h = _RE_HEADING.match(line.strip())
        if h:
            name = h.group(1).strip()
            if name.lower() in _STOP_SECTIONS:
                break
            kept.append("")
            kept.append(HEADING_MARK + name)
            kept.append("")
        else:
            kept.append(line)
    t = "\n".join(kept)

    t = _RE_BLANKS.sub("\n\n", t)
    return t.strip()


# ==============================================================================
# [4] MULTISTREAM ARCHIVE READER
# ==============================================================================

class WikiDumpReader:
    """
    Random access to named articles in a multistream dump.

    The archive is a concatenation of independent bz2 blocks, each holding
    about a hundred pages. The companion index gives, for every page,
    "offset:pageid:title". Reading one article is a seek to its block, a
    decompress of that block alone, and an XML scan of its hundred pages.
    Nothing else in the twenty gigabytes is touched.
    """

    def __init__(self, dump_path: str, offsets_path: str):
        self.dump_path = dump_path
        self.offsets_path = offsets_path
        self.offsets: Dict[str, int] = {}
        self._block_cache_offset: Optional[int] = None
        self._block_cache_xml: str = ""

    @staticmethod
    def build_offset_map(index_bz2: str, out_json: str) -> int:
        """Reads the published index once and writes title -> offset."""
        if not os.path.exists(index_bz2):
            print(f"Index not found: {index_bz2}")
            return 0

        print(f"[INDEX] reading {os.path.basename(index_bz2)} ...")
        offsets: Dict[str, int] = {}
        n = 0
        with bz2.open(index_bz2, "rt", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.rstrip("\n").split(":", 2)
                if len(parts) != 3:
                    continue
                try:
                    off = int(parts[0])
                except ValueError:
                    continue
                # Two keys per page. The exact title is authoritative; the
                # lowercased form is a fallback so an operator's list need not
                # reproduce Wikipedia's capitalisation. Keying only on the
                # lowercase form collapsed "Ideal Gas Law" and "Ideal gas law"
                # into one entry, and the redirect stub won.
                exact = parts[2].strip()
                offsets[exact] = off
                lower = exact.lower()
                if lower not in offsets:
                    offsets[lower] = off
                n += 1
                if n % 1_000_000 == 0:
                    print(f"[INDEX]   {n:,} titles ...")

        print(f"[INDEX] writing {out_json} ({len(offsets):,} titles)")
        tmp = out_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(offsets, f)
        os.replace(tmp, out_json)
        return len(offsets)

    def load_offsets(self) -> bool:
        if not os.path.exists(self.offsets_path):
            return False
        try:
            with open(self.offsets_path, "r", encoding="utf-8") as f:
                self.offsets = json.load(f)
            return True
        except Exception as e:
            print(f"[INDEX] load failed: {e}")
            return False

    def _decompress_block(self, offset: int) -> str:
        """
        Decompresses the single block beginning at offset.

        The decompressor stops of its own accord at the end of one stream, so
        the block boundary needs no lookup: read a generous slice, feed it in,
        and take what comes out before end-of-stream.
        """
        if self._block_cache_offset == offset:
            return self._block_cache_xml

        with open(self.dump_path, "rb") as f:
            f.seek(offset)
            raw = f.read(12 * 1024 * 1024)

        dec = bz2.BZ2Decompressor()
        try:
            data = dec.decompress(raw)
        except Exception:
            return ""
        xml = data.decode("utf-8", errors="ignore")

        self._block_cache_offset = offset
        self._block_cache_xml = xml
        return xml

    def get_article(self, title: str, _depth: int = 0) -> Optional[str]:
        """Returns cleaned prose for a title, or None when absent."""
        want = title.strip()
        key = want.lower()
        off = self.offsets.get(want)
        if off is None:
            off = self.offsets.get(key)
        if off is None:
            return None

        xml = self._decompress_block(off)
        if not xml:
            return None

        # Titles are matched case-sensitively first. A block commonly holds
        # both an article and a redirect stub differing only in capitalisation,
        # and matching case-insensitively took whichever came first, which was
        # the stub.
        candidates = []
        for m in re.finditer(r"<page>(.*?)</page>", xml, re.S):
            page = m.group(1)
            tm = re.search(r"<title>(.*?)</title>", page, re.S)
            if not tm:
                continue
            found = tm.group(1).strip()
            if found == want:
                candidates.insert(0, page)
            elif found.lower() == key:
                candidates.append(page)

        for page in candidates:
            # The published index maps many common titles to a redirect stub
            # rather than to the article itself, so refusing to follow one
            # loses the article entirely. One hop only, so a redirect loop
            # cannot trap the reader.
            rd = re.search(r'<redirect\s+title="([^"]*)"', page)
            if rd and _depth == 0:
                return self.get_article(rd.group(1), _depth=1)
            if rd:
                return None
            xm = re.search(r"<text[^>]*>(.*?)</text>", page, re.S)
            if not xm:
                return None
            return clean_wikitext(xm.group(1))
        return None


# ==============================================================================
# [5] ARTICLE CACHE
# ==============================================================================
# Cleaned articles written once as plain files. Decompressing a block costs a
# second or two of single-threaded bz2; doing that for every rule change made
# iteration expensive for no reason. The cache turns the second run and every
# run after it into a file read.

def cache_path_for(coord: str, title: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", title)[:120]
    return os.path.join(CACHE_DIR, f"{coord}__{safe}.txt")


def build_cache() -> None:
    """Pulls every listed article out of the archive and writes it to disk."""
    lists = discover_article_lists(LISTS_DIR)
    if not lists:
        print(f"No article lists in {LISTS_DIR}")
        return

    reader = WikiDumpReader(DUMP_PATH, TITLE_OFFSET_MAP)
    if not reader.load_offsets():
        print(f"No offset map at {TITLE_OFFSET_MAP}. Run --build-index first.")
        return
    if not os.path.exists(DUMP_PATH):
        print(f"Dump not found: {DUMP_PATH}")
        return

    os.makedirs(CACHE_DIR, exist_ok=True)

    # Sorted by block offset so articles sharing a block decompress once. The
    # reader caches a single block, and an alphabetical list defeats that.
    work: List[Tuple[int, str, str]] = []
    for coord, titles in lists:
        for t in titles:
            off = reader.offsets.get(t) or reader.offsets.get(t.lower()) or 0
            work.append((off, coord, t))
    work.sort()

    total = len(work)
    written = skipped = 0
    start = time.time()

    for i, (_off, coord, title) in enumerate(work, start=1):
        path = cache_path_for(coord, title)
        if os.path.exists(path):
            written += 1
            continue
        text = reader.get_article(title) or ""
        if len(text) < MIN_ARTICLE_CHARS:
            skipped += 1
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            written += 1
        if i % 25 == 0 or i == total:
            el = time.time() - start
            rate = i / max(el, 0.01)
            eta = (total - i) / max(rate, 0.01)
            sys.stdout.write(
                f"\r[CACHE] {i}/{total}  written {written}  skipped {skipped}"
                f"  {rate:.1f}/s  eta {eta/60:.1f} min   ")
            sys.stdout.flush()

    print(f"\n[CACHE] done. {written} cached, {skipped} absent or stub.")
    print(f"[CACHE] {CACHE_DIR}")


def read_cached(coord: str, title: str) -> Optional[str]:
    path = cache_path_for(coord, title)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


# ==============================================================================
# [6] VOLUME PACKER
# ==============================================================================

class DELMVolumePacker:
    """
    Sealed binary volume writer.

    Record layout, unchanged from the format the EnQuerant runtime reads:
        [RecordType uint16][CoordLen uint8][coord bytes][PayloadLen uint32][JSON]

    Volumes fill to 4.00 MB and seal. The final volume seals at its actual
    length: padding writes null bytes carrying no information.
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.current_vol_idx = 0
        self.current_file = None
        self.records_written = 0
        self._recover_state()

    def _recover_state(self) -> None:
        sealed = [f for f in os.listdir(self.output_dir)
                  if f.startswith("niichii_v") and f.endswith(".bin")]
        indices = []
        for f in sealed:
            stem = f.split("_v")[1].split(".bin")[0]
            if stem.isdigit():
                indices.append(int(stem))
        self.current_vol_idx = max(indices) + 1 if indices else 0
        tmp_path = self._tmp_path()
        self.current_file = open(
            tmp_path, "a+b" if os.path.exists(tmp_path) else "wb")

    def _tmp_path(self) -> str:
        return os.path.join(self.output_dir,
                            f"niichii_v{self.current_vol_idx:02d}.tmp")

    @property
    def current_vol_filename(self) -> str:
        return f"niichii_v{self.current_vol_idx:02d}.bin"

    @property
    def current_bytes_count(self) -> int:
        if not self.current_file:
            return 0
        self.current_file.flush()
        return os.path.getsize(self.current_file.name)

    def write_record(self, coord_id: str, data: dict) -> bool:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        coord_bytes = coord_id.encode("utf-8")
        record = struct.pack(
            f"<HB{len(coord_bytes)}sI",
            RECORD_TYPE_EMPIRICAL, len(coord_bytes), coord_bytes, len(payload)
        ) + payload
        self.current_file.write(record)
        self.records_written += 1
        if self.current_bytes_count >= CHUNK_SIZE_BYTES:
            self.seal_volume(pad=True)
            return True
        return False

    def seal_volume(self, pad: bool = True) -> Optional[str]:
        if not self.current_file:
            return None
        tmp_path = self.current_file.name
        self.current_file.close()
        self.current_file = None
        if not os.path.exists(tmp_path):
            return None

        with open(tmp_path, "rb") as f:
            data = bytearray(f.read())
        if len(data) == 0:
            os.remove(tmp_path)
            self.current_file = open(self._tmp_path(), "wb")
            return None

        if pad:
            if len(data) < CHUNK_SIZE_BYTES:
                data.extend(b"\x00" * (CHUNK_SIZE_BYTES - len(data)))
            else:
                data = data[:CHUNK_SIZE_BYTES]

        sha = hashlib.sha256(data).hexdigest()
        final_bin = os.path.join(self.output_dir, self.current_vol_filename)
        with open(final_bin, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.remove(tmp_path)

        with open(os.path.join(
                self.output_dir,
                f"niichii_v{self.current_vol_idx:02d}.manifest"), "w") as mf:
            json.dump({"volume": self.current_vol_filename,
                       "size": len(data), "padded": bool(pad),
                       "sha256": sha}, mf, indent=2)

        sealed = self.current_vol_filename
        self.current_vol_idx += 1
        self.current_file = open(self._tmp_path(), "wb")
        return sealed

    def finalize(self) -> Optional[str]:
        return self.seal_volume(pad=False)


# ==============================================================================
# [7] VALIDATION GATE
# ==============================================================================
# Lighter than the generative edition's gate, because the defects that gate
# existed to catch cannot occur here. Nothing is invented, so no rule needs to
# check that a subject appears in the passage: the subject IS the title or the
# heading. What remains are structural checks on what got copied.

_EQ_OPERATORS = ("=", "≈", "∝", "≤", "≥", "→", "<", ">", "≡")


class Validator:
    def __init__(self) -> None:
        self.counts: Dict[str, int] = {}

    def _reject(self, reason: str) -> Tuple[bool, str]:
        self.counts[reason] = self.counts.get(reason, 0) + 1
        return False, reason

    def check(self, rec: Dict[str, str]) -> Tuple[bool, str]:
        subj = (rec.get("subject") or "").strip()
        rel = (rec.get("relation") or "").strip()
        obj = (rec.get("object") or "").strip()
        eq = (rec.get("equation") or "").strip()

        # A missing positional field is a partial record, not a fact.
        if not subj or not rel or not obj:
            return self._reject("empty_field")

        # An ontology label is where a fact is filed, not a thing that acts.
        if subj.lower() in _ONTOLOGY_LABELS:
            return self._reject("subject_is_ontology_label")

        # An object carrying no word names nothing to move to. A record whose
        # object is "0" renders as a destination the Seeker can select and
        # arrive nowhere. Formula and value records are exempt: for those the
        # quantity IS the content.
        if rel == REL_LEAD and not re.search(r"[a-zA-Z]", obj):
            return self._reject("object_has_no_word")

        # An equation without a relational operator is a symbol, not a
        # statement of relation.
        if eq and not any(op in eq for op in _EQ_OPERATORS):
            return self._reject("equation_no_operator")

        # Cleaning leaves residue on some formulas. A fragment shorter than
        # this carries no relation even when it holds an operator.
        if rel == REL_FORMULA and len(obj) < 3:
            return self._reject("formula_too_short")

        # A run-on sentence is a cleaning failure, not a claim.
        if rel == REL_LEAD and len(obj) > MAX_SENTENCE_CHARS:
            return self._reject("sentence_too_long")
        if rel == REL_LEAD and len(obj) < MIN_SENTENCE_CHARS:
            return self._reject("sentence_too_short")

        return True, "ok"

    def report(self) -> str:
        if not self.counts:
            return "no rejections"
        return ", ".join(f"{k}={v}" for k, v in sorted(self.counts.items()))


# ==============================================================================
# [8] DEDUPLICATION
# ==============================================================================

class Deduplicator:
    """One claim, one record. Keyed on subject-relation-object."""

    def __init__(self) -> None:
        self.seen: Set[str] = set()
        self.suppressed = 0

    @staticmethod
    def key(rec: Dict[str, str]) -> str:
        return (f"{(rec.get('subject') or '').strip().lower()}|"
                f"{(rec.get('relation') or '').strip().lower()}|"
                f"{(rec.get('object') or '').strip().lower()}")

    def is_new(self, rec: Dict[str, str]) -> bool:
        k = self.key(rec)
        if k in self.seen:
            self.suppressed += 1
            return False
        self.seen.add(k)
        return True


# ==============================================================================
# [9] EXTRACTION
# ==============================================================================
# The whole of the extraction logic. Wikipedia tags what it holds, so the
# markup answers every question the generative edition asked a model.

_RE_EQ_BLOCK = re.compile(re.escape(EQ_OPEN) + r"(.*?)" + re.escape(EQ_CLOSE),
                          re.S)

# A sentence boundary: a full stop, question mark or exclamation followed by
# whitespace and a capital. Abbreviations with a following capital are rare in
# encyclopedic prose and cost one malformed record when they occur.
_RE_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# A quantity with a unit: a number, optionally with exponent, followed by a
# unit token. Loose on purpose — the validation gate catches the residue.
_RE_QUANTITY = re.compile(
    r"\b(\d[\d,]*(?:\.\d+)?(?:\s*\*\s*10\^\(?-?\d+\)?)?)\s*"
    r"([a-zA-Zµ°Ω]+(?:[·⋅/^-][a-zA-Z0-9−-]+)*)")


def _extract_one(job: Tuple[str, str, str]) -> Tuple[str, List[Dict[str, str]]]:
    """
    One article, start to finish, in a worker process. Extraction is a pure
    function of the text, so articles are independent and the work parallelises
    exactly. Everything after this — validation, dedup, volume writing — stays
    sequential and in order, because dedup must see every record in the order
    the operator's lists state them.
    """
    kind, coord, ident = job
    if kind == "txt":
        title = os.path.splitext(os.path.basename(ident))[0]
        title = re.sub(r"^\d\.\d[_\-]", "", title).replace("_", " ")
        try:
            with open(ident, "r", encoding="utf-8") as f:
                text = clean_wikitext(f.read())
        except Exception:
            return coord, []
    else:
        title = ident
        text = read_cached(coord, ident) or ""
        if len(text) < MIN_ARTICLE_CHARS:
            return coord, []
    return coord, extract_records(title, text)


def split_sections(text: str) -> List[Tuple[str, str]]:
    """
    Splits cleaned text into (heading, body) pairs.

    The lead has no heading by convention: everything before the first heading
    marker is it. That is the section that names the article's subject, so it
    is returned with an empty heading and the caller substitutes the title.
    """
    parts = text.split("\n" + HEADING_MARK)
    out: List[Tuple[str, str]] = [("", parts[0].strip())]
    for p in parts[1:]:
        nl = p.find("\n")
        if nl == -1:
            out.append((p.strip(), ""))
        else:
            out.append((p[:nl].strip(), p[nl + 1:].strip()))
    return out


def strip_eq_markers(s: str) -> str:
    """Removes formula markers, leaving the formula text in place."""
    return s.replace(EQ_OPEN, " ").replace(EQ_CLOSE, " ")


def extract_records(title: str, text: str) -> List[Dict[str, str]]:
    """
    Produces every record an article yields. Deterministic and total: the same
    article always produces the same records in the same order.
    """
    records: List[Dict[str, str]] = []
    sections = split_sections(text)
    if not sections:
        return records

    # -- lead sentences ------------------------------------------------------
    # The lead states what the article is about, in the terms a Seeker is
    # likely to type. Storing it is what makes token retrieval find the
    # article at all; the formulas alone carry almost no searchable prose.
    lead_body = sections[0][1]
    lead_prose = re.sub(r"\s+", " ", strip_eq_markers(lead_body)).strip()
    for sent in _RE_SENTENCE.split(lead_prose):
        sent = sent.strip()
        if not sent:
            continue
        records.append({
            "subject": title,
            "relation": REL_LEAD,
            "object": sent,
            "equation": "",
        })

    # -- formulas ------------------------------------------------------------
    # Named by the section they sit in, because that is what the section is
    # for. A formula under "Relativistic form" is about that, not about the
    # article in general. In the lead, the title is the name.
    for heading, body in sections:
        # Named by article and section together. A heading alone is often a
        # bare phrase — "Dimension and value", "Conformal infinity" — which
        # names where the formula sits but not what it is about. The article
        # title supplies the subject; the heading narrows it.
        name = title if not heading else f"{title} ({heading})"
        for m in _RE_EQ_BLOCK.finditer(body):
            formula = re.sub(r"\s+", " ", m.group(1)).strip()
            if not formula:
                continue
            records.append({
                "subject": name,
                "relation": REL_FORMULA,
                "object": formula,
                "equation": formula,
            })

    # -- values --------------------------------------------------------------
    # A quantity with a unit is a parameterization. These are what {{val}}
    # carries, and they are the records whose absence made every physical
    # subject look like an unparameterized gap.
    for heading, body in sections:
        name = heading if heading else title
        prose = strip_eq_markers(body)
        for m in _RE_QUANTITY.finditer(prose):
            num, unit = m.group(1), m.group(2)
            # A bare year or a reference number is not a measurement. A unit
            # of one or two letters that is also an ordinary word is the
            # common false positive.
            if unit.lower() in ("in", "a", "an", "the", "of", "to", "and",
                               "is", "as", "at", "by", "or", "on", "it"):
                continue
            if len(num.replace(",", "").replace(".", "")) < 2:
                continue
            # Named by article and section together. A heading alone is often
            # a bare word — "Light", "Energy" — which then becomes a tagged
            # subject that any query mentioning that word matches. One such
            # record made "what is the speed of light" resolve as a
            # placeholder for a 100-metre measurement in a biology article.
            subj = title if not heading else f"{title} ({heading})"
            records.append({
                "subject": subj,
                "relation": REL_VALUE,
                "object": f"{num} {unit}",
                "equation": "",
            })

    return records


# ==============================================================================
# [10] WORK PLANNING
# ==============================================================================

_COORD_PREFIX = re.compile(r"^(\d\.\d)[_\-]")


def discover_txt_sources(sources_dir: str) -> List[Tuple[str, str, str]]:
    """Operator-authored passages. The coordinate is the filename prefix."""
    if not os.path.isdir(sources_dir):
        return []
    found = []
    for name in sorted(os.listdir(sources_dir)):
        if not name.lower().endswith(".txt"):
            continue
        m = _COORD_PREFIX.match(name)
        if not m or m.group(1) not in FISSN_COORDS:
            print(f"[SKIP] {name}: no valid coordinate prefix")
            continue
        found.append((name, m.group(1), os.path.join(sources_dir, name)))
    return found


def discover_article_lists(lists_dir: str) -> List[Tuple[str, List[str]]]:
    """
    Reads the operator's title lists.

    The coordinate is the filename prefix and the placement is an operator
    decision made once per list. No classifier guesses which tier an article
    belongs to.
    """
    if not os.path.isdir(lists_dir):
        return []
    out = []
    for name in sorted(os.listdir(lists_dir)):
        if not name.lower().endswith(".txt"):
            continue
        m = _COORD_PREFIX.match(name)
        if not m or m.group(1) not in FISSN_COORDS:
            print(f"[SKIP] {name}: no valid coordinate prefix")
            continue
        titles = []
        with open(os.path.join(lists_dir, name), "r", encoding="utf-8") as f:
            for line in f:
                t = line.strip()
                if t and not t.startswith("#"):
                    titles.append(t)
        if titles:
            out.append((m.group(1), titles))
    return out


# ==============================================================================
# [11] MAIN
# ==============================================================================

def print_setup_help() -> None:
    print(f"""
No work found.

1. ARTICLE LISTS -- {LISTS_DIR}

   One file per coordinate, each holding article titles, one per line:

       1.0_articles.txt
           Thermodynamics
           Speed of light
           Maxwell's equations

   Requires the Wikipedia multistream dump and its index, downloaded once
   from https://dumps.wikimedia.org/enwiki/latest/ :
       enwiki-latest-pages-articles-multistream.xml.bz2        (~22 GB)
       enwiki-latest-pages-articles-multistream-index.txt.bz2  (~250 MB)

   Both go in:
       {DUMP_DIR}
   Set WIKI_DUMP_DIR to point elsewhere if the archive lives on another disk.

   Then:
       python3 mine_delm_complete.py --build-index
       python3 mine_delm_complete.py --build-cache
       python3 mine_delm_complete.py

2. PLAIN PASSAGES -- {SOURCES_DIR}

   Prose files whose names carry the coordinate: 1.0_thermodynamics.txt

Registered coordinates:""")
    for c, n in FISSN_COORDS.items():
        print(f"    {c}  {n}")


def main() -> None:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--build-index", action="store_true",
                    help="read the published dump index and write title_offsets.json")
    ap.add_argument("--build-cache", action="store_true",
                    help="pull every listed article out of the archive to disk")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after this many articles (0 = no limit)")
    ap.add_argument("--dry-run", action="store_true",
                    help="extract and report, write no volumes")
    args = ap.parse_args()

    os.makedirs(SOURCES_DIR, exist_ok=True)
    os.makedirs(LISTS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.build_index:
        n = WikiDumpReader.build_offset_map(DUMP_INDEX_BZ2, TITLE_OFFSET_MAP)
        print(f"[INDEX] done, {n:,} titles mapped.")
        return

    if args.build_cache:
        build_cache()
        return

    # -- assemble the work list ----------------------------------------------
    units: List[Tuple[str, str, str]] = []      # (kind, coord, identifier)
    for name, coord, path in discover_txt_sources(SOURCES_DIR):
        units.append(("txt", coord, path))
    for coord, titles in discover_article_lists(LISTS_DIR):
        for t in titles:
            units.append(("article", coord, t))

    if not units:
        print_setup_help()
        return
    if args.limit:
        units = units[:args.limit]

    # A reader is opened only if the cache is incomplete. A full cache means
    # the archive is never touched, which is what makes a re-run take seconds.
    reader: Optional[WikiDumpReader] = None

    packer = None if args.dry_run else DELMVolumePacker(OUTPUT_DIR)
    validator = Validator()
    dedup = Deduplicator()

    accepted = rejected = duped = skipped = vols_sealed = 0
    by_relation: Dict[str, int] = {}
    start = time.time()

    print(f"[PLAN] {len(units)} source unit(s).")

    # Extraction runs across every core when the cache covers the work. It is a
    # pure function of the text, so articles are independent. Results come back
    # in submission order, which matters: record order is source order, and the
    # order-of-operations sequence depends on it.
    # The work is split rather than tested all-or-nothing: 84 of the operator's
    # titles do not exist in Wikipedia and were skipped at cache time, so
    # requiring every unit to be cached meant the parallel path never ran.
    parallel = [u for u in units if u[0] == "txt" or read_cached(u[1], u[2])]
    units = [u for u in units if u not in parallel]
    if len(parallel) > 8:
        workers = min(os.cpu_count() or 1, 12)
        print(f"[MINE] cache complete; extracting across {workers} workers.")
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, (coord, recs) in enumerate(pool.map(_extract_one, parallel, chunksize=8), start=1):
                if not recs:
                    skipped += 1
                for rec in recs:
                    ok, _why = validator.check(rec)
                    if not ok:
                        rejected += 1
                        continue
                    if not dedup.is_new(rec):
                        duped += 1
                        continue
                    by_relation[rec["relation"]] = by_relation.get(rec["relation"], 0) + 1
                    accepted += 1
                    if packer and packer.write_record(coord, rec):
                        vols_sealed += 1
                if i % 40 == 0 or i == len(parallel):
                    el = time.time() - start
                    sys.stdout.write(
                        f"\r[MINE] {i}/{len(parallel)}  accepted {accepted:,}"
                        f"  rejected {rejected:,}  duped {duped:,}"
                        f"  {el:.0f}s   ")
                    sys.stdout.flush()
        print()

    for i, (kind, coord, ident) in enumerate(units, start=1):
        # -- obtain the text --------------------------------------------------
        if kind == "txt":
            title = os.path.splitext(os.path.basename(ident))[0]
            title = re.sub(r"^\d\.\d[_\-]", "", title).replace("_", " ")
            try:
                with open(ident, "r", encoding="utf-8") as f:
                    text = clean_wikitext(f.read())
            except Exception:
                skipped += 1
                continue
        else:
            title = ident
            text = read_cached(coord, ident) or ""
            if not text:
                if reader is None:
                    reader = WikiDumpReader(DUMP_PATH, TITLE_OFFSET_MAP)
                    if not reader.load_offsets():
                        print(f"\nNo offset map. Run --build-index first.")
                        return
                text = reader.get_article(ident) or ""
            if len(text) < MIN_ARTICLE_CHARS:
                skipped += 1
                continue

        # -- extract ----------------------------------------------------------
        for rec in extract_records(title, text):
            ok, _why = validator.check(rec)
            if not ok:
                rejected += 1
                continue
            if not dedup.is_new(rec):
                duped += 1
                continue
            by_relation[rec["relation"]] = by_relation.get(rec["relation"], 0) + 1
            accepted += 1
            if packer and packer.write_record(coord, rec):
                vols_sealed += 1

        if i % 20 == 0 or i == len(units):
            el = time.time() - start
            sys.stdout.write(
                f"\r[MINE] {i}/{len(units)}  accepted {accepted:,}"
                f"  rejected {rejected:,}  duped {duped:,}"
                f"  {el:.0f}s   ")
            sys.stdout.flush()

    final = packer.finalize() if packer else None

    print("\n" + "=" * 78)
    print("MINING SESSION ENDED" + ("  (dry run, nothing written)"
                                    if args.dry_run else ""))
    print("=" * 78)
    print(f"  accepted          : {accepted:,}")
    for rel, n in sorted(by_relation.items(), key=lambda kv: -kv[1]):
        print(f"      {rel:20} {n:,}")
    print(f"  rejected          : {rejected:,}")
    print(f"  duplicate claims  : {duped:,}")
    print(f"  skipped sources   : {skipped:,}")
    print(f"  distinct claims   : {len(dedup.seen):,}")
    if packer:
        print(f"  volumes sealed    : {vols_sealed + (1 if final else 0)}")
        if final:
            p = os.path.join(OUTPUT_DIR, final)
            size = os.path.getsize(p) if os.path.exists(p) else 0
            print(f"  final volume      : {final} ({size:,} bytes, unpadded)")
    print(f"  rejection reasons : {validator.report()}")
    print(f"  elapsed           : {time.time() - start:.1f}s")
    if not args.dry_run:
        print(f"  output            : {OUTPUT_DIR}")
    print("=" * 78)


if __name__ == "__main__":
    main()
