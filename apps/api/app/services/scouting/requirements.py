"""The scout's requirement vocabulary, and the parser that turns a sentence into filters (M7, spec §23).

§23 asks for something a manager can say out loud: *"find me a left-footed under-22 who can play inverted
full-back, budget €20m."* The step before any search runs is a rule about language. Every phrase in that
sentence is either turned into a filter the database can execute, or named back to the reader as something
this build did not understand. A parser that quietly drops the words it cannot handle is the one failure
mode that makes the rest of the pipeline a lie: a shortlist that ignored "left-footed" looks exactly like a
shortlist that honoured it.

So the invariant this file exists to keep is recorded in `Parsed.unaccounted` and enforced at the bottom of
`parse_requirements`: nothing in the request disappears. Each span of the input ends up as a parsed
requirement, a connector (a word the parser was *told* to ignore, listed in `CONNECTORS` rather than guessed
at), or a refusal carrying its reason and — when the catalogue has something nearby — the names worth trying.

Two things are deliberately not done here:

* **No fuzzy matching in the filter path.** A suggestion is arithmetic over catalogue labels
  (`SUGGESTION_FORMULA`), is returned beside a refusal, and never becomes a cut. The parser will not decide
  that "inverted full-back" meant "inverted winger".
* **No invented vocabulary.** Positions come from the squads the generator staffs
  (`app/services/world/builder.py` `SQUAD_PLAN`), bands from the engine (`simulation/profile.py` `BANDS`),
  roles from the Tactical Lab (`tactics/roles.py` `ROLES`) and attributes from the player model
  (`services/attributes.py` `ALL_ATTRIBUTES`). Where those disagree — positions the band table names and no
  squad carries, roles no stored position occupies — the disagreement is published, not smoothed over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Final

from app.services.attributes import ALL_ATTRIBUTES
from app.services.simulation.profile import BANDS, band_of_position
from app.services.tactics.roles import ROLES

SCOUT_DISCLAIMER: Final = (
    "A scout report describes generated players in a generated world. The requirements below are filters "
    "over stored rows, the numbers beside every candidate are arithmetic this project runs on its own "
    "tables, and none of it measures a real footballer, a real fee or a real club."
)

# --- the vocabulary, taken from the tables that already own it ---------------------------------------------------

#: The positions this world actually stores, in the generator's own squad plan.
STAFFED_POSITIONS: Final = ("GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST")

#: Positions the engine's band table names and the generator never produces. A search for one of these is
#: not a typo — it is a question about a player nobody in this world is.
UNSTAFFED_POSITIONS: Final = tuple(sorted({code for band in BANDS.values() for code in band} - set(STAFFED_POSITIONS)))

POSITION_LABELS: Final[dict[str, str]] = {
    "GK": "goalkeeper",
    "CB": "centre-back",
    "LB": "left-back",
    "RB": "right-back",
    "CDM": "holding midfielder",
    "CM": "central midfielder",
    "CAM": "attacking midfielder",
    "LW": "left winger",
    "RW": "right winger",
    "ST": "striker",
}

#: English and Chinese spellings the parser accepts. The sweep is longest-name-first, so a two-word alias is
#: never read as the shorter word inside it.
POSITION_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "GK": ("sweeper keeper", "goalkeeper", "keeper", "gk", "门将", "守门员"),
    "CB": ("centre back", "center back", "centre-back", "center-back", "cb", "中后卫", "中卫"),
    "LB": ("left back", "left-back", "lb", "左后卫"),
    "RB": ("right back", "right-back", "rb", "右后卫"),
    "CDM": ("defensive midfielder", "holding midfielder", "defensive mid", "cdm", "后腰", "防守型中场"),
    "CM": ("central midfielder", "central mid", "cm", "中前卫"),
    "CAM": ("attacking midfielder", "number ten", "number 10", "cam", "前腰", "攻击型中场"),
    "LW": ("left winger", "left wing", "lw", "左边锋", "左翼"),
    "RW": ("right winger", "right wing", "rw", "右边锋", "右翼"),
    "ST": ("striker", "centre forward", "centre-forward", "center forward", "cf", "st", "前锋", "中锋"),
}

#: The engine's four bands, in its own key order. A band requirement is a position requirement widened to
#: everything the side of the pitch covers, and it is resolved through `band_of_position`, the same function
#: the market and the profile use.
BAND_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "keeper": ("goalkeepers", "keepers"),
    "defence": ("defenders", "defender", "defence", "defense", "后防", "防守", "后卫"),
    "midfield": ("midfielders", "midfielder", "midfield", "中场"),
    "attack": ("attackers", "attacker", "forwards", "forward", "进攻", "锋线"),
}

BAND_RULE: Final = (
    "a band requirement keeps a player whose stored `position` or any `secondary_positions` entry is one of "
    "that band's codes, as `band_of_position` reads them — the same four bands the engine's team profile "
    "reports, so a band asked for here is a band the simulation can measure"
)

#: Which stored positions can occupy each Tactical Lab role slot. `ROLES` is board vocabulary (15 slots) and
#: the world's squads use 10 position codes, so the mapping is authored here and published by the rules
#: route rather than inferred at request time.
ROLE_POSITIONS: Final[dict[str, tuple[str, ...]]] = {
    "GK": ("GK",),
    "DCB": ("CB",),
    "RB": ("RB",),
    "LB": ("LB",),
    "RWB": ("RB",),
    "LWB": ("LB",),
    "DM": ("CDM",),
    "CM": ("CM",),
    "AM": ("CAM",),
    "RM": (),
    "LM": (),
    "RW": ("RW", "LW"),
    "LW": ("LW", "RW"),
    "ST": ("ST",),
    "SS": ("ST", "CAM"),
}

FOOT_VALUES: Final = ("left", "right", "both")

FOOT_RULE: Final = (
    "a foot requirement keeps a player whose `preferred_foot` is that foot or `both` — a two-footed player "
    "can take the kick with either — and `both` is only ever matched exactly, because a requirement for a "
    "two-footed player is a different question from a requirement for a left foot"
)

SORTS: Final = ("overall", "potential", "headroom", "value_for_money", "need_fit", "cheapest", "youth")

#: Every kind of cut the parser can produce. `search.py` handles each one, and `vocabulary_problems` checks
#: the two files cannot drift apart without an integrity line going red.
FILTER_KINDS: Final = ("age_max", "age_min", "foot", "position", "band", "role", "attribute_min", "fee_max")

MATCH_RULE: Final = (
    "a position or band cut reads a player's stored `position` *and* their `secondary_positions`, because a versatile player "
    "answers a request for a slot they do not primarily occupy; a role cut is the same rule through the positions that role "
    "names can occupy, and the role's tactical demands are reported beside the candidate as a fit rather than applied as a cut"
)

SORT_FORMULA: Final = (
    "overall = the stored `overall`; potential = the stored `potential`; headroom = potential − overall; "
    "value_for_money = overall × 1,000,000 ÷ asking_fee (rating points per million credits, on the same "
    "`asking_fee` the market's valuation formula prints); need_fit = the market's tactical fit against the "
    "band this club is weakest in, which needs a career; cheapest = the lowest asking fee; youth = youngest "
    "first. Ties always break on the player's slug, so a re-run answers the same question the same way"
)

SUGGESTION_FORMULA: Final = (
    "an unparsed name is scored against every catalogue entry: a word of the phrase that appears in the "
    "entry's label or aliases once spaces, hyphens and underscores are removed scores 2 (so 'fullback' reaches "
    "'full-back'), and a word that shares a prefix of at least 5 characters and at least 80% of the shorter "
    "of the two forms scores 1 (so 'dribble' reaches 'dribbling'); entries scoring at least one point are "
    "listed by score, then by name. A suggestion is printed beside the refusal and never applied as a filter"
)

MONEY_RULE: Final = (
    "a fee is read as career credits, the unit every budget in this project is stored in: a bare number is "
    "itself, `k`/`thousand` multiplies by 1e3, `m`/`million`/`万` by 1e6, `亿` by 1e8, and a currency sign is "
    "ignored rather than converted — this world has no exchange rate, so €20m is read as 20,000,000 career "
    "credits and the assumption is reported with the result"
)

#: Words the parser is told to ignore. Named rather than guessed, so that a leftover can be called one.
#: Foot words are deliberately absent: a foot is a filter, not a connector, and `左脚` or `left-footed` that
#: no claim took must come back as a refusal rather than disappear into this list.
CONNECTORS: Final = (
    "find me a",
    "find me",
    "find",
    "looking for",
    "look for",
    "search for",
    "i want",
    "i need",
    "need",
    "want",
    "show me",
    "give me",
    "players who can",
    "player who can",
    "who can play",
    "can play",
    "capable of",
    "playable at",
    "able to play",
    "that plays",
    "who plays",
    "playing",
    "plays",
    "player",
    "players",
    "someone",
    "somebody",
    "having",
    "whose",
    "who is",
    "who",
    "with",
    "and a",
    "and",
    "or",
    "the",
    "for",
    "our",
    "your",
    "their",
    "team",
    "squad",
    "club",
    "best",
    "top",
    "any",
    "please",
    "aged",
    "years",
    "year",
    "old",
    "younger",
    "older",
    "maximum",
    "minimum",
    "max",
    "min",
    "under",
    "over",
    "below",
    "above",
    "upto",
    "at least",
    "of at least",
    "least",
    "budget",
    "fee",
    "spend",
    "cost",
    "price",
    "asking",
    "worth",
    "strong",
    "weak",
    "sort by",
    "order by",
    "sort",
    "ranked",
    "rank",
    "me",
    "us",
    "my",
    "i",
    "a",
    "an",
    "in",
    "is",
    "be",
    "as",
    "of",
    "to",
    "that",
    "this",
    "must",
    "have",
    "has",
    "also",
    "named",
    "called",
    "找一个",
    "寻找",
    "搜索",
    "找个",
    "我需要",
    "我要",
    "给我",
    "请",
    "能踢",
    "可以踢",
    "能打",
    "可以打",
    "踢",
    "打",
    "会",
    "的",
    "球员",
    "选手",
    "岁",
    "以下",
    "及以下",
    "以内",
    "以上",
    "不超过",
    "不低于",
    "至少",
    "预算",
    "身价",
    "费用",
    "报价",
    "工资",
    "排名",
    "排序",
    "最",
    "和",
    "或",
    "一个",
    "名",
)

_PUNCTUATION_CLASS: Final = r"""\s,.;:!?"'()\[\]{}·、。！？；：，（）《》"""
_PUNCTUATION_RUN: Final = re.compile(f"[{_PUNCTUATION_CLASS}]+")
_WORD: Final = re.compile(f"""[^{_PUNCTUATION_CLASS}]+""")


class RequirementError(ValueError):
    """A stated requirement this vocabulary does not contain, with what it would accept instead."""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), **self.detail}


#: §51's sets for this tier: a stated requirement this vocabulary does not contain is always the
#: caller's own words — a position, role, band, foot or field this world does not store — so every
#: code answers 422, the same answer `/api/v1/scout/parse` already spelled at the door.
UNPROCESSABLE_CODES: Final = frozenset(
    {
        "attribute_out_of_range",
        "no_request",
        "unknown_attribute",
        "unknown_band",
        "unknown_field",
        "unknown_foot",
        "unknown_position",
        "unknown_role",
        "unknown_sort",
        "unparseable_fee",
        "unstaffed_position",
        "unstaffed_role",
    }
)


@dataclass
class Requirement:
    """One filter the database can run, with the words that produced it."""

    kind: str
    field: str
    value: Any
    phrase: str
    rule: str
    source: str = "parsed"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "field": self.field, "value": self.value, "phrase": self.phrase, "rule": self.rule, "source": self.source}


@dataclass
class Refusal:
    """A phrase the parser will not pretend to understand."""

    phrase: str
    code: str
    message: str
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"phrase": self.phrase, "code": self.code, "message": self.message, "suggestions": self.suggestions}


@dataclass
class Parsed:
    #: The sentence this came from, so a search can carry the words with the filters they produced.
    text: str = ""
    requirements: list[Requirement] = field(default_factory=list)
    refused: list[Refusal] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    connectors: list[str] = field(default_factory=list)
    #: Text of the input that was neither parsed, nor a listed connector, nor turned into a refusal. No code
    #: path puts anything in here — the leftover sweep refuses it first, and the 200-step guard is the only
    #: way in. The field exists so a test can prove that claim instead of reading it.
    unaccounted: list[str] = field(default_factory=list)

    @property
    def filters(self) -> list[Requirement]:
        return [item for item in self.requirements if item.kind != "sort"]

    @property
    def sort(self) -> str:
        for item in self.requirements:
            if item.kind == "sort":
                return str(item.value)
        return "overall"

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.text,
            "requirements": [item.to_dict() for item in self.requirements],
            "filters_applied": len(self.filters),
            "sort": self.sort,
            "refused": [item.to_dict() for item in self.refused],
            "assumptions": self.assumptions,
            "connectors_ignored": len(self.connectors),
            "unaccounted": self.unaccounted,
            "rule": "every phrase in the request is either a filter, a refusal with its reason, or a listed connector — nothing is dropped",
        }


def _normalise(word: str) -> str:
    return re.sub(r"[\s\-_]+", "", str(word).lower())


def _names_for_position(code: str) -> tuple[str, ...]:
    return (code, POSITION_LABELS[code], *POSITION_ALIASES.get(code, ()))


def _names_for_role(key: str) -> tuple[str, ...]:
    return (key, ROLES[key].label)


_POSITION_LOOKUP: Final[dict[str, str]] = {_normalise(name): code for code in STAFFED_POSITIONS for name in _names_for_position(code)}
_ROLE_LOOKUP: Final[dict[str, str]] = {_normalise(name): key for key in ROLES for name in _names_for_role(key)}
_BAND_LOOKUP: Final[dict[str, str]] = {_normalise(name): band for band, names in BAND_ALIASES.items() for name in names}
#: Role slots that read exactly as a position code. The position wins, because it is the narrower claim, and
#: the rules route names the collision rather than leaving a reader to wonder why "CM" was not the role.
OVERLAPPING_ROLE_KEYS: Final = tuple(sorted(key for key in ROLES if _normalise(key) in _POSITION_LOOKUP and _POSITION_LOOKUP[_normalise(key)] in ROLE_POSITIONS.get(key, ("",))))

#: Names that read as both a position and a band word (`keeper`/`goalkeeper`, `forward`). The narrower claim —
#: the position — wins in `_claim_vocabulary`, and this list is what the rules route prints so the priority
#: rule is a published fact rather than something a reader has to rediscover from a query.
BAND_NAMES_READ_AS_POSITIONS: Final = tuple(sorted(name for name in _BAND_LOOKUP if name in _POSITION_LOOKUP))

_CATALOGUE: Final[dict[str, tuple[str, ...]]] = (
    {f"position {code}": _names_for_position(code) for code in STAFFED_POSITIONS}
    | {f"role {key}": _names_for_role(key) for key in ROLES}
    | {f"band {band}": names for band, names in BAND_ALIASES.items()}
)
_ATTRIBUTE_CATALOGUE: Final[dict[str, tuple[str, ...]]] = {key: (key.replace("_", " "), key) for key in ALL_ATTRIBUTES}


def _needles(entry: tuple[str, ...]) -> set[str]:
    """Every word of an entry's names, plus each adjacent pair and triple joined — what a loose typing hits."""
    found: set[str] = set()
    for name in entry:
        words = [word for word in re.split(r"[^\w]+", str(name).lower()) if word]
        found.update(_normalise(word) for word in words)
        for left, right in zip(words, words[1:], strict=False):
            found.add(_normalise(f"{left}{right}"))
        for first, second, third in zip(words, words[1:], words[2:], strict=False):
            found.add(_normalise(f"{first}{second}{third}"))
    return found


_MIN_PREFIX_CHARS: Final = 5


def _prefix_hit(word: str, entry: set[str]) -> bool:
    """Whether `word` is the catalogue word with a suffix missing — the shape of a common mistyping."""
    if len(word) < _MIN_PREFIX_CHARS:
        return False
    for name in entry:
        shared = 0
        for left, right in zip(word, name, strict=False):
            if left != right:
                break
            shared += 1
        if shared >= _MIN_PREFIX_CHARS and shared * 100 >= min(len(word), len(name)) * 80:
            return True
    return False


def _scored(phrase: str, needles: dict[str, set[str]]) -> list[str]:
    words = [word for word in (_normalise(part) for part in re.split(r"[^\w]+", str(phrase).lower())) if word]
    scored: list[tuple[int, str]] = []
    for name, entry in needles.items():
        points = 2 * sum(1 for word in words if word in entry) + sum(1 for word in words if word not in entry and _prefix_hit(word, entry))
        if points:
            scored.append((points, name))
    return [name for _, name in sorted(scored, key=lambda pair: (-pair[0], pair[1]))]


_NEEDLES: Final[dict[str, set[str]]] = {name: _needles(entry) for name, entry in _CATALOGUE.items()}
_ATTRIBUTE_NEEDLES: Final[dict[str, set[str]]] = {name: _needles(entry) for name, entry in _ATTRIBUTE_CATALOGUE.items()}


def suggest(phrase: str) -> list[str]:
    """Catalogue positions and roles whose names share a word with `phrase`. Never applied as a filter."""
    return _scored(phrase, _NEEDLES)


def suggest_attributes(phrase: str) -> list[str]:
    """Attribute keys whose spelled-out name shares a word with `phrase`. Never applied as a filter."""
    return _scored(phrase, _ATTRIBUTE_NEEDLES)


def _position_requirement(code: str, phrase: str, source: str = "parsed") -> Requirement:
    return Requirement("position", "position", code, phrase, f"the player's stored `position` or one of their `secondary_positions` is {code}", source)


def _band_requirement(band: str, phrase: str, source: str = "parsed") -> Requirement:
    return Requirement("band", "band", band, phrase, f"{BAND_RULE}; {band} covers {', '.join(BANDS[band])}", source)


def _foot_requirement(foot: str, phrase: str, source: str = "parsed") -> Requirement:
    return Requirement("foot", "preferred_foot", foot, phrase, FOOT_RULE, source)


def _role_requirement(key: str, phrase: str, source: str = "parsed") -> Requirement:
    return Requirement(
        "role",
        "role",
        key,
        phrase,
        f"the {ROLES[key].label} slot is occupied by {', '.join(ROLE_POSITIONS[key])}; a player sits in it when one of their stored "
        "positions is among those, and their fit against the slot's tactical demands is ranked, never cut",
        source,
    )


def _unstaffed_role_error(key: str) -> RequirementError:
    return RequirementError(
        "unstaffed_role",
        f"{ROLES[key].label} ({key}) is a board slot no stored position occupies in this world, so it cannot filter a squad list",
        role=key,
        staffed_roles=[item for item in ROLES if ROLE_POSITIONS.get(item)],
        see="/api/v1/scout/rules",
    )


# --- the structured path: a caller who already speaks in fields ---------------------------------------------------


def _position_code(name: str) -> str:
    wanted = _normalise(name)
    code = _POSITION_LOOKUP.get(wanted)
    if code:
        return code
    if wanted in {_normalise(unstaffed) for unstaffed in UNSTAFFED_POSITIONS}:
        raise RequirementError(
            "unstaffed_position",
            f"{name!r} is a position the engine's band table names and this world's generator never produces, so no player can be found with it",
            position=str(name),
            staffed=list(STAFFED_POSITIONS),
            see="/api/v1/scout/rules",
        )
    raise RequirementError("unknown_position", f"{name!r} is not a position this world stores", position=str(name), suggestions=suggest(str(name)), see="/api/v1/scout/rules")


def _role_key(name: str) -> str:
    key = _ROLE_LOOKUP.get(_normalise(name)) or ""
    if not key:
        raise RequirementError(
            "unknown_role",
            f"{name!r} is not one of the {len(ROLES)} tactical roles the Tactical Lab authors",
            role=str(name),
            suggestions=suggest(str(name)),
            see="/api/v1/scout/rules",
        )
    if not ROLE_POSITIONS.get(key):
        raise _unstaffed_role_error(key)
    return key


def _attribute_key(name: str) -> str:
    wanted = _normalise(name)
    for key in ALL_ATTRIBUTES:
        if wanted == _normalise(key):
            return key
    raise RequirementError(
        "unknown_attribute",
        f"{name!r} is not one of the {len(ALL_ATTRIBUTES)} attributes this project's player model stores",
        attribute=str(name),
        suggestions=suggest_attributes(str(name)),
        see="/api/v1/scout/rules",
    )


_MULTIPLIERS: Final[dict[str, int]] = {"k": 1_000, "thousand": 1_000, "m": 1_000_000, "million": 1_000_000, "万": 10_000, "亿": 100_000_000}


def _money(raw: str, unit: str | None) -> int:
    digits = re.sub(r"[^0-9.]", "", str(raw).replace(",", ""))
    if not digits or digits.count(".") > 1:
        raise RequirementError("unparseable_fee", f"{raw!r} is not a fee this parser can read", fee=raw)
    magnitude = float(digits)
    if unit:
        magnitude *= _MULTIPLIERS.get(str(unit).lower(), 1)
    if magnitude < 0 or magnitude > 10**12:
        raise RequirementError("unparseable_fee", f"{raw}{unit or ''} is outside the range this market prices in", fee=raw)
    return int(round(magnitude))


def _fee_requirement(fee: int, phrase: str, unit: str | None, source: str) -> Requirement:
    rule = "the asking fee this project's valuation formula prints for the player ≤ the stated value"
    if unit:
        rule += f", with {unit!r} read as a multiplier over career credits"
    return Requirement("fee_max", "asking_fee", fee, phrase, rule, source)


def _band_key(name: str) -> str:
    wanted = _normalise(name)
    band = next((item for item in BANDS if wanted == _normalise(item)), "") or _BAND_LOOKUP.get(wanted, "")
    if not band:
        raise RequirementError(
            "unknown_band",
            f"{name!r} is not one of the four bands the engine's team profile reports",
            band=str(name),
            bands=list(BANDS),
            suggestions=suggest(str(name)),
            see="/api/v1/scout/rules",
        )
    return band


def stated_requirements(payload: dict[str, Any]) -> list[Requirement]:
    """Turn a JSON body of stated fields into requirements. Anything unknown raises rather than being skipped."""
    allowed = {"max_age", "min_age", "foot", "positions", "bands", "role", "attributes", "max_fee", "sort"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise RequirementError(
            "unknown_field",
            f"{unknown} is not a field this search understands, and nothing was filtered on it",
            fields=unknown,
            fields_accepted=sorted(allowed),
            see="/api/v1/scout/rules",
        )
    out: list[Requirement] = []
    if payload.get("max_age") is not None:
        out.append(Requirement("age_max", "age", int(payload["max_age"]), f"stated max_age={payload['max_age']}", "stored `age` ≤ the stated value", "stated"))
    if payload.get("min_age") is not None:
        out.append(Requirement("age_min", "age", int(payload["min_age"]), f"stated min_age={payload['min_age']}", "stored `age` ≥ the stated value", "stated"))
    if payload.get("foot"):
        foot = str(payload["foot"]).lower()
        if foot not in FOOT_VALUES:
            raise RequirementError("unknown_foot", f"{foot!r} is not a foot this world stores", foot=foot, values=list(FOOT_VALUES))
        out.append(Requirement("foot", "preferred_foot", foot, f"stated foot={foot}", FOOT_RULE, "stated"))
    for name in payload.get("positions") or []:
        code = _position_code(str(name))
        out.append(_position_requirement(code, f"stated position {code}", "stated"))
    for name in payload.get("bands") or []:
        band = _band_key(str(name))
        out.append(_band_requirement(band, f"stated band {band}", "stated"))
    if payload.get("role"):
        key = _role_key(str(payload["role"]))
        out.append(_role_requirement(key, f"stated role={key}", "stated"))
    for name, floor in (payload.get("attributes") or {}).items():
        key = _attribute_key(str(name))
        value = int(floor)
        if not 1 <= value <= 99:
            raise RequirementError("attribute_out_of_range", f"{key} is stored between 28 and 96 in this world, so a floor of {value} asks for nothing or nobody", attribute=key, floor=value)
        out.append(Requirement("attribute_min", f"attributes.{key}", value, f"stated {key} ≥ {value}", f"the player's stored `attributes['{key}']` ≥ {value}", "stated"))
    if payload.get("max_fee") is not None:
        fee = _money(str(payload["max_fee"]), None)
        out.append(_fee_requirement(fee, f"stated max_fee={fee}", None, "stated"))
    if payload.get("sort"):
        sort = str(payload["sort"]).lower()
        if sort not in SORTS:
            raise RequirementError("unknown_sort", f"{sort!r} is not one of the published sortings", sort=sort, sorts=list(SORTS))
        out.append(Requirement("sort", "sort", sort, f"stated sort={sort}", SORT_FORMULA, "stated"))
    return out


# --- the sentence path -------------------------------------------------------------------------------------------

_AGE_MAX: Final = re.compile(
    r"(\d{1,3})[\s/-]*(?:岁(?:以下|及以下|以内)|-\s*years?\s*old|and\s*under|or\s*(?:under|younger|below))|(?:under|below|max(?:imum)?\s*age(?:\s*of)?|upto|up\s*to|not\s*older\s*than)[\s/-]*(\d{1,3})",
    re.IGNORECASE,
)
_AGE_MIN: Final = re.compile(r"(\d{1,3})\s*岁以上|(?:over|above|min(?:imum)?\s*age(?:\s*of)?|older\s*than)[\s/-]*(\d{1,3})", re.IGNORECASE)
#: A foot is stated as the foot itself (`left-footed`, `左脚`), as a two-footed pair, or as a preference
#: (`prefers left`). The bare words are not connectors, so a claim that does not take one of these comes back
#: as a refusal naming it — the failure mode this file exists to prevent.
_FOOT: Final = re.compile(
    r"(?:both|two)[\s/-]*(?:footed|feet|foot)|(?:left|right)[\s/-]*(?:footed|foot|feet)|(?:左|右)(?:只)?脚|(?:两只|双|两)只?脚|(?:prefers?|preferred|preferably)[\s/-]+(?:the[\s/-]+)?(?:left|right|both)(?:[\s/-]+foot)?",
    re.IGNORECASE,
)
_FEE: Final = re.compile(
    r"(?:€|£|\$|¥)\s*(\d[\d,._]*)\s*(million|万|亿|k|m|thousand)?(?![\w])|(\d[\d,._]*)\s*(million|万|亿|k|m|thousand)(?![\w])|(?:(?:budget|fee|spend|报价|预算|身价)[^\d]{0,10}?)(\d[\d,._]*)\s*(million|万|亿|k|m|thousand)?(?![\d])",
    re.IGNORECASE,
)
_ATTR: Final = re.compile(r"\b([a-z][a-z_]{2,28})\s*(?:at least|of at least|>=|≥)\s*(\d{1,3})", re.IGNORECASE)
_SORT: Final = re.compile(r"\b(most valuable|cheapest|lowest fee|lowest price|youngest|highest potential|best player|best overall|highest rated)\b|(最有潜力|最便宜|最年轻)", re.IGNORECASE)
_AGE_RANGE: Final = (15, 45)

_SORT_VALUES: Final[dict[str, str]] = {
    "most valuable": "value_for_money",
    "cheapest": "cheapest",
    "lowest fee": "cheapest",
    "lowest price": "cheapest",
    "youngest": "youth",
    "highest potential": "potential",
    "best player": "overall",
    "best overall": "overall",
    "highest rated": "overall",
    "最有潜力": "potential",
    "最便宜": "cheapest",
    "最年轻": "youth",
}

_CONNECTOR_RE: Final = re.compile(
    "(?:" + "|".join(sorted((re.escape(word) for word in CONNECTORS), key=lambda raw: (-len(raw), raw))) + ")",
    re.IGNORECASE,
)


@dataclass
class _Claim:
    """One span of the request and what became of it."""

    start: int
    end: int
    requirement: Requirement | None = None
    refusal: Refusal | None = None

    def clashes(self, other: _Claim) -> bool:
        return self.start < other.end and other.start < self.end


def _ascii_start(word: str) -> bool:
    return bool(word) and ord(word[0]) < 128


def _occurrences(text: str, needle: str) -> list[tuple[int, int]]:
    """Every place `needle` reads as a word rather than as the inside of another word.

    An ASCII name has to start and finish on a non-alphanumeric; a Chinese name need not, because that
    script puts no spaces between words and `左后卫` inside a longer run is still `左后卫`.
    """
    found: list[tuple[int, int]] = []
    lowered = text.lower()
    target = needle.lower()
    start = lowered.find(target)
    while start != -1:
        end = start + len(target)
        before = lowered[start - 1] if start else ""
        after = lowered[end] if end < len(lowered) else ""
        if not (_ascii_start(target) and before.isalnum()) and not (after.isalnum() and _ascii_start(target[-1:])):
            found.append((start, end))
        start = lowered.find(target, start + 1)
    return found


def _refuse_age(phrase: str, age: int) -> Refusal:
    return Refusal(phrase, "absurd_age", f"{age} is outside the {_AGE_RANGE[0]}–{_AGE_RANGE[1]} age range this world generates, so nobody was cut on it", [])


def _claim_age(text: str, pattern: re.Pattern[str], taken: list[_Claim], kind: str) -> None:
    for match in pattern.finditer(text):
        claim = _Claim(match.start(), match.end())
        if any(claim.clashes(other) for other in taken):
            continue
        age = int(next((group for group in match.groups() if group), "0"))
        if not _AGE_RANGE[0] <= age <= _AGE_RANGE[1]:
            claim.refusal = _refuse_age(match.group(0), age)
        else:
            claim.requirement = Requirement(kind, "age", age, match.group(0), f"stored `age` {'≤' if kind == 'age_max' else '≥'} the stated value", "parsed")
        taken.append(claim)


def _foot_value(phrase: str) -> str:
    """Which foot the words ask for. Two-footed is checked first because `两只脚` contains a foot word."""
    lowered = phrase.lower()
    if "both" in lowered or "two" in lowered or "两只脚" in lowered or "双脚" in lowered or "两脚" in lowered:
        return "both"
    if "left" in lowered or "左" in lowered:
        return "left"
    if "right" in lowered or "右" in lowered:
        return "right"
    return ""


def _claim_foot(text: str, taken: list[_Claim]) -> None:
    for match in _FOOT.finditer(text):
        claim = _Claim(match.start(), match.end())
        if any(claim.clashes(other) for other in taken):
            continue
        foot = _foot_value(match.group(0))
        if foot:
            claim.requirement = _foot_requirement(foot, match.group(0))
        else:  # pragma: no cover - every alternative in `_FOOT` names one of the three stored values
            claim.refusal = Refusal(match.group(0), "unreadable_foot", f"{match.group(0)!r} names a foot this parser cannot tell left from right", [])
        taken.append(claim)


def _claim_fee(text: str, taken: list[_Claim], parsed: Parsed) -> None:
    for match in _FEE.finditer(text):
        claim = _Claim(match.start(), match.end())
        if any(claim.clashes(other) for other in taken):
            continue
        raw = next((group for group in (match.group(1), match.group(3), match.group(5)) if group), "")
        unit = next((group for group in (match.group(2), match.group(4), match.group(6)) if group), None)
        try:
            fee = _money(raw, unit)
        except RequirementError as error:
            claim.refusal = Refusal(match.group(0), error.code, str(error), [])
        else:
            claim.requirement = _fee_requirement(fee, match.group(0), unit, "parsed")
            parsed.assumptions.append(f"the fee {match.group(0).strip()!r} was read as {fee:,} career credits: {MONEY_RULE}")
        taken.append(claim)


def _claim_attribute(text: str, taken: list[_Claim]) -> None:
    for match in _ATTR.finditer(text):
        claim = _Claim(match.start(), match.end())
        if any(claim.clashes(other) for other in taken):
            continue
        name, floor = match.group(1), int(match.group(2))
        try:
            key = _attribute_key(name)
        except RequirementError as error:
            claim.refusal = Refusal(match.group(0), error.code, str(error), [str(item) for item in error.detail.get("suggestions", [])])
        else:
            if not 1 <= floor <= 99:
                claim.refusal = Refusal(match.group(0), "attribute_out_of_range", f"{key} is stored between 28 and 96 in this world, so a floor of {floor} asks for nothing or nobody", [])
            else:
                claim.requirement = Requirement("attribute_min", f"attributes.{key}", floor, match.group(0), f"the player's stored `attributes['{key}']` ≥ {floor}", "parsed")
        taken.append(claim)


def _claim_vocabulary(text: str, taken: list[_Claim]) -> None:
    """Longest-name-first sweep over all three catalogues, refusing what is near the vocabulary but not in it.

    The order of resolution is a published rule, not an accident of the dict: a name that reads as a position
    is taken as a position even when the band tables carry the same word, because the position is the narrower
    claim. `BAND_NAMES_READ_AS_POSITIONS` lists the names where that priority binds.
    """
    names = sorted({name for entry in _CATALOGUE.values() for name in entry}, key=lambda name: (-len(name), name.lower()))
    for name in names:
        for start, end in _occurrences(text, name):
            if any(_Claim(start, end).clashes(other) for other in taken):
                continue
            phrase = text[start:end]
            wanted = _normalise(name)
            claim = _Claim(start, end)
            if wanted in _POSITION_LOOKUP:
                claim.requirement = _position_requirement(_POSITION_LOOKUP[wanted], phrase)
            elif wanted in _ROLE_LOOKUP:
                key = _ROLE_LOOKUP[wanted]
                if ROLE_POSITIONS.get(key):
                    claim.requirement = _role_requirement(key, phrase)
                else:
                    error = _unstaffed_role_error(key)
                    claim.refusal = Refusal(phrase, error.code, str(error), [str(item) for item in error.detail.get("suggestions", [])])
            elif wanted in _BAND_LOOKUP:
                claim.requirement = _band_requirement(_BAND_LOOKUP[wanted], phrase)
            else:  # pragma: no cover - the sweep only walks catalogue names
                continue
            taken.append(claim)


def _account_for(fragment: str, parsed: Parsed) -> None:
    """Sort a gap between the claimed spans into listed connectors and refusals.

    Consecutive words the vocabulary did not claim are refused as one phrase rather than one word apiece,
    because the question a reader asks back is "what did you not understand?" and `Inverted Fullback` is a
    different answer from `inverted` plus `full-back`. The suggestions are recomputed over the whole phrase,
    so a two-word name can reach an entry no single one of its words would.
    """
    remaining = fragment
    pending: list[str] = []

    def refuse_pending() -> None:
        if not pending:
            return
        phrase = " ".join(pending)
        pending.clear()
        parsed.refused.append(
            Refusal(
                phrase,
                "not_in_vocabulary",
                f"{phrase!r} is not a position, band, role, foot, age, fee or attribute floor this parser knows, so nothing was filtered on it",
                suggest(phrase)[:6],
            )
        )

    for _ in range(200):
        remaining = remaining.strip()
        if not remaining:
            break
        match = _CONNECTOR_RE.match(remaining)
        if match:
            word = match.group(0)
            tail = remaining[len(word) :]
            if not _ascii_start(word[-1:]) or not tail[:1].isalnum():
                refuse_pending()
                parsed.connectors.append(word)
                remaining = tail
                continue
        leftover = _WORD.match(remaining)
        if leftover:
            pending.append(leftover.group(0))
            remaining = remaining[len(leftover.group(0)) :]
            continue
        punctuation = _PUNCTUATION_RUN.match(remaining)
        if punctuation:
            remaining = remaining[punctuation.end() :]
            continue
        remaining = remaining[1:]
    refuse_pending()
    if remaining.strip():
        parsed.unaccounted.append(remaining)


def parse_requirements(text: str) -> Parsed:
    """Read a scout's sentence. Every span of it is accounted for; nothing silently disappears."""
    parsed = Parsed()
    if not text or not text.strip():
        raise RequirementError("no_request", "there is nothing to parse: send `query` text, stated fields, or both", see="/api/v1/scout/rules")
    parsed.text = text
    taken: list[_Claim] = []
    _claim_age(text, _AGE_MAX, taken, "age_max")
    _claim_age(text, _AGE_MIN, taken, "age_min")
    _claim_fee(text, taken, parsed)
    _claim_attribute(text, taken)
    _claim_vocabulary(text, taken)
    # After the vocabulary, so that `left back` is claimed as a position and never read as a foot.
    _claim_foot(text, taken)

    for match in _SORT.finditer(text):
        claim = _Claim(match.start(), match.end())
        if any(claim.clashes(other) for other in taken):
            continue
        value = _SORT_VALUES.get(match.group(0).lower(), "")
        if value:
            claim.requirement = Requirement("sort", "sort", value, match.group(0), SORT_FORMULA, "parsed")
            taken.append(claim)

    taken.sort(key=lambda claim: claim.start)
    parsed.requirements = [claim.requirement for claim in taken if claim.requirement]
    parsed.refused = [claim.refusal for claim in taken if claim.refusal]

    # Everything the spans above did not claim is either a listed connector or a refusal. That is the whole
    # promise of this file, so it is enforced here rather than asserted in prose.
    cursor = 0
    for claim in taken:
        _account_for(text[cursor : claim.start], parsed)
        cursor = max(cursor, claim.end)
    _account_for(text[cursor:], parsed)
    parsed.refused.sort(key=lambda item: item.phrase.lower())
    return parsed


def vocabulary_problems() -> list[str]:
    """Where this file's own published facts disagree. Empty is the only acceptable answer, and a test says so.

    These are the ways a vocabulary rots quietly: an alias that resolves to the wrong code, a band word that
    is also a connector (so a filter disappears into the ignore list), a role slot pointing at a position the
    generator never produces, a position the engine cannot place on a side.
    """
    problems: list[str] = []
    for code in STAFFED_POSITIONS:
        if code not in POSITION_LABELS:
            problems.append(f"position {code} has no published label")
        if band_of_position(code) not in BANDS:
            problems.append(f"position {code} resolves to band {band_of_position(code)!r}, which the engine does not measure")
    for code in UNSTAFFED_POSITIONS:
        if code in _POSITION_LOOKUP:
            problems.append(f"{code} is published as unstaffed and still resolves as a position")
    for code, names in POSITION_ALIASES.items():
        for name in names:
            if _POSITION_LOOKUP.get(_normalise(name)) != code:
                problems.append(f"alias {name!r} of position {code} resolves to {_POSITION_LOOKUP.get(_normalise(name))!r}")
    for key, codes in ROLE_POSITIONS.items():
        if key not in ROLES:
            problems.append(f"role slot {key} is mapped but the Tactical Lab does not author it")
        for code in codes:
            if code not in STAFFED_POSITIONS:
                problems.append(f"role {key} claims it can be occupied by {code}, which this world does not staff")
    for band, names in BAND_ALIASES.items():
        if band not in BANDS:
            problems.append(f"band {band} is not one the engine measures")
        for name in names:
            wanted = _normalise(name)
            if wanted in _POSITION_LOOKUP and wanted not in {_normalise(item) for item in BAND_NAMES_READ_AS_POSITIONS}:
                problems.append(f"band alias {name!r} is shadowed by position {_POSITION_LOOKUP[wanted]!r} and is not published as a collision")
    for word in CONNECTORS:
        wanted = _normalise(word)
        if wanted in _POSITION_LOOKUP or wanted in _ROLE_LOOKUP or wanted in _BAND_LOOKUP:
            problems.append(f"connector {word!r} is also a vocabulary name, so a filter would be dropped into the ignore list")
    return problems


#: One requirement of every kind the parser can emit, from the sentences the spec and this file's own examples
#: use. `search.py` runs each of them against a real candidate and reports the ones it cannot answer, so the
#: two files cannot drift apart quietly: a new kind with no handler in the search shows up as a problem line.
SAMPLE_REQUIREMENTS: Final = [
    Requirement("age_max", "age", 21, "under 21", "sample"),
    Requirement("age_min", "age", 18, "over 18", "sample"),
    Requirement("foot", "preferred_foot", "left", "left-footed", "sample"),
    Requirement("position", "position", "CB", "centre-back", "sample"),
    Requirement("band", "band", "midfield", "midfielder", "sample"),
    Requirement("role", "role", "AM", "number ten", "sample"),
    Requirement("attribute_min", "attributes.stamina", 70, "stamina at least 70", "sample"),
    Requirement("fee_max", "asking_fee", 20_000_000, "budget €20m", "sample"),
    Requirement("sort", "sort", "cheapest", "cheapest", "sample"),
]


def scout_rules() -> dict[str, Any]:
    """The published vocabulary and arithmetic: what a request can say, and what each saying does."""
    return {
        "positions": {code: {"label": POSITION_LABELS[code], "band": band_of_position(code), "aliases": list(POSITION_ALIASES.get(code, ()))} for code in STAFFED_POSITIONS},
        "positions_the_engine_names_and_the_world_does_not_staff": list(UNSTAFFED_POSITIONS),
        "roles": {
            key: {
                "label": role.label,
                "board_band": role.band,
                "occupiable_by": list(ROLE_POSITIONS.get(key, ())),
                "demands": dict(role.demands),
                "risk": role.risk,
            }
            for key, role in ROLES.items()
        },
        #: Two modules in this project keep a band vocabulary and neither name matches the other. Publishing
        #: the disagreement beats a reader finding it by asking for a "defensive" band and getting a refusal.
        "band_vocabularies": {
            "engine": {"keys": list(BANDS), "used_by": "app/services/simulation/profile.py — the four indices the match engine reports", "meaning": "a band requirement here is one of these keys"},
            "board": {
                "keys": sorted({role.band for role in ROLES.values()}),
                "used_by": "app/services/tactics/roles.py — the zone a role card belongs to",
                "meaning": "published beside a role as `board_band`; it is not a filter",
            },
        },
        "roles_no_stored_position_occupies": [key for key in ROLES if not ROLE_POSITIONS.get(key)],
        "role_names_that_read_as_a_position": list(OVERLAPPING_ROLE_KEYS),
        "bands": {band: {"codes": list(codes), "aliases": list(BAND_ALIASES.get(band, ()))} for band, codes in BANDS.items()},
        "band_names_that_read_as_a_position": list(BAND_NAMES_READ_AS_POSITIONS),
        "feet": list(FOOT_VALUES),
        "attributes": list(ALL_ATTRIBUTES),
        "sorts": list(SORTS),
        "fields": ["max_age", "min_age", "foot", "positions", "bands", "role", "attributes", "max_fee", "sort", "query", "career"],
        "rules": {
            "positions": "a position requirement matches a player's stored `position` or any of their `secondary_positions`",
            "bands": BAND_RULE,
            "roles": "a role requirement cuts on the slots it occupies and ranks on the fit; it never cuts on the fit",
            "matching": MATCH_RULE,
            "feet": FOOT_RULE,
            "money": MONEY_RULE,
            "sort": SORT_FORMULA,
            "suggestions": SUGGESTION_FORMULA,
            "vocabulary_priority": "a word the position, role and band catalogues share resolves to the position, because that is the narrower claim; the shared words are listed under `band_names_that_read_as_a_position` and `role_names_that_read_as_a_position`",
            "parsing": "a sentence is read span by span; anything that is neither a listed connector nor a known vocabulary word comes back as a refusal naming the phrase, and consecutive unknown words are refused together as the phrase they were said in",
        },
        "connectors_ignored": list(CONNECTORS),
        "example": {
            "request": "找一个 22 岁以下、左脚、能踢 Inverted Fullback、预算 €20m 的球员",
            "what_happens": "the age, the foot and the fee become filters, and Inverted Fullback is refused: this project's role catalogue has no inverted full-back, so the search says so and lists the names it does have rather than guessing one",
        },
        "data_origin": "simulation",
        "is_demo_data": True,
        "disclaimer": SCOUT_DISCLAIMER,
    }
