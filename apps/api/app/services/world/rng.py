"""Deterministic pseudo-random source for the world generator.

`random.Random` is not used on purpose: its `sample`/`shuffle` internals have changed between
CPython releases, which would silently reshuffle the whole football world on an interpreter
upgrade. SplitMix64 is a fixed 64-bit-state algorithm, so a seed produces the same world on
every Python 3.11+ build and every platform — the property `sync_world`'s content hashes rely on.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import MutableSequence

T = TypeVar("T")

_MASK = (1 << 64) - 1
_GOLDEN = 0x9E3779B97F4A7C15


class WorldRng:
    def __init__(self, seed: int) -> None:
        self._state = (int(seed) ^ _GOLDEN) & _MASK

    def fork(self, label: str) -> WorldRng:
        """A sub-stream that depends only on the parent state + `label`, never on call order."""
        digest = hashlib.sha256(f"{self._state:016x}:{label}".encode()).digest()
        return WorldRng(int.from_bytes(digest[:8], "big"))

    def next_u64(self) -> int:
        self._state = (self._state + _GOLDEN) & _MASK
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return (z ^ (z >> 31)) & _MASK

    def random(self) -> float:
        return self.next_u64() / float(1 << 64)

    def uniform(self, lower: float, upper: float) -> float:
        return lower + (upper - lower) * self.random()

    def int_below(self, upper: int) -> int:
        if upper <= 0:
            raise ValueError("upper bound must be positive")
        return int(self.next_u64() % upper)

    def randint(self, lower: int, upper: int) -> int:
        """Inclusive on both ends, like `random.randint`."""
        return lower + self.int_below(upper - lower + 1)

    def choice(self, items: Sequence[T]) -> T:
        if not items:
            raise ValueError("cannot choose from an empty sequence")
        return items[self.int_below(len(items))]

    def shuffle(self, items: MutableSequence[T]) -> None:
        for index in range(len(items) - 1, 0, -1):
            swap = self.int_below(index + 1)
            items[index], items[swap] = items[swap], items[index]

    def sample(self, items: Sequence[T], count: int) -> list[T]:
        pool = list(items)
        self.shuffle(pool)
        return pool[:count]

    def weighted(self, items: Sequence[T], weights: Sequence[float]) -> T:
        total = float(sum(weights))
        if len(items) != len(weights) or total <= 0:
            raise ValueError("weighted() needs one non-negative weight per item")
        pointer = self.random() * total
        running = 0.0
        for item, weight in zip(items, weights, strict=True):
            running += weight
            if pointer < running:
                return item
        return items[-1]

    def poisson(self, lam: float, *, cap: int = 12) -> int:
        """Knuth sampler with an explicit cap so a tail draw cannot invent a 9-0."""
        if lam <= 0:
            return 0
        limit = math.exp(-lam)
        k, product = 0, self.random()
        while product > limit and k < cap:
            k += 1
            product *= self.random()
        return min(k, cap)

    def unique(self, attempts: int, maker: Callable[[WorldRng], str], taken: Iterable[str]) -> str:
        """Draw until fresh; fall back to a numbered variant so a generation run can never hang."""
        blocked = set(taken)
        for _ in range(max(1, attempts)):
            candidate = maker(self)
            if candidate not in blocked:
                return candidate
        base = maker(self)
        suffix = 2
        while f"{base} {suffix}" in blocked:
            suffix += 1
        return f"{base} {suffix}"


__all__ = ["WorldRng"]
