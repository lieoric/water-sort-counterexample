#!/usr/bin/env python3
"""Small audit for the unique four-source E=2,Q=5 later-rotor bypass."""

from __future__ import annotations

import math
from collections import Counter
from itertools import product


HEIGHT = 7
Q, F, G, H = range(4)
Debt = tuple[int, int, int, int]
Word = tuple[int, ...]


def add(*vectors: Debt) -> Debt:
    return tuple(sum(vector[color] for vector in vectors) for color in range(4))  # type: ignore[return-value]


def basis(color: int, amount: int) -> Debt:
    values = [0, 0, 0, 0]
    values[color] = amount
    return tuple(values)  # type: ignore[return-value]


def counts(word: Word) -> Debt:
    result = Counter(word)
    return tuple(result[color] for color in range(4))  # type: ignore[return-value]


def positive_count(values: Debt) -> int:
    return sum(value > 0 for value in values)


def run_ends(word: Word) -> tuple[int, ...]:
    result = []
    cursor = 0
    while cursor < len(word):
        end = cursor + 1
        while end < len(word) and word[end] == word[cursor]:
            end += 1
        result.append(end)
        cursor = end
    return tuple(result)


def source_tests(background: Debt, word: Word) -> tuple[Debt, ...]:
    return tuple(add(background, counts(word[:end])) for end in run_ends(word))


def walk_legal(background: Debt, word: Word, threshold: int) -> bool:
    return all(positive_count(test) <= threshold for test in source_tests(background, word))


def past_templates() -> tuple[tuple[Word, Word, Word, Word], ...]:
    result = []
    wanted = Counter({Q: 3, G: 1, H: 4})
    for letters in product((Q, G, H), repeat=8):
        if Counter(letters) != wanted:
            continue
        words = tuple(
            tuple(letters[2 * column:2 * column + 2]) + (Q,)
            for column in range(4)
        )
        assert add(*(counts(word) for word in words)) == (7, 0, 1, 4)
        result.append(words)
    assert len(result) == 280
    return tuple(result)


def lambda_q(word: Word) -> int:
    return counts(word)[Q]


def is_binary(word: Word) -> bool:
    return G not in word


def check_template(words: tuple[Word, Word, Word, Word]) -> str:
    bad = words[0]
    siblings = list(words[1:])
    zero: Debt = (0, 0, 0, 0)

    if G not in bad:
        binary = [word for word in siblings if is_binary(word)]
        assert len(binary) >= 2
        u, v = binary[:2]
        assert walk_legal(zero, u, 2)
        after_u = add(counts(u), basis(H, -3))
        lam_u = lambda_q(u)
        assert after_u == add(basis(Q, lam_u), basis(H, -lam_u))
        assert walk_legal(after_u, bad, 2)
        after_bad = add(after_u, counts(bad), basis(F, 4))
        tests_v = source_tests(after_bad, v)
        assert all(test[G] == 0 for test in tests_v)
        assert all(positive_count(test) <= 3 for test in tests_v)
        return "g_outside_bad"

    assert counts(bad)[G] == 1
    assert all(is_binary(word) for word in siblings)
    ordered = sorted(siblings, key=lambda word: (-lambda_q(word), word))
    u, v = ordered[:2]
    lam_u, lam_v = lambda_q(u), lambda_q(v)
    mu = counts(bad)[Q]
    b_count = counts(bad)[H]
    assert (mu, b_count) in ((2, 0), (1, 1))
    assert bad in ((G, Q, Q), (Q, G, Q), (G, H, Q), (H, G, Q))
    assert sum(lambda_q(word) for word in siblings) == 7 - mu
    assert lam_u + lam_v >= 4

    assert walk_legal(zero, u, 2)
    after_u = add(counts(u), basis(H, -3))
    for test in source_tests(after_u, bad):
        assert test[H] <= -lam_u + b_count <= 0
        assert positive_count(test) <= 2
    after_bad = add(after_u, counts(bad), basis(F, 4))
    bound = -lam_u + b_count + 3 - lam_v
    assert bound <= (-1 if (mu, b_count) == (2, 0) else 0)
    for test in source_tests(after_bad, v):
        assert test[H] <= bound <= 0
        assert positive_count(test) <= 3
    return "g_in_bad"


def check_pair_cap_lemma() -> int:
    checked = 0
    for hidden in range(HEIGHT + 1):
        for cap_1 in range(1, HEIGHT + 1):
            for cap_2 in range(1, HEIGHT + 1):
                if cap_1 + cap_2 < HEIGHT:
                    continue
                for cap_3 in range(1, HEIGHT + 1):
                    debt = HEIGHT - hidden - cap_1 - cap_2 - cap_3
                    assert debt + cap_3 <= 0
                    checked += 1
    return checked


def main() -> None:
    # One bad f^4 tail and three h^1 cards leave f^3 g^6 in nine cells.
    edge_summed_weight = math.factorial(9) // (
        math.factorial(3) * math.factorial(6)
    )
    assert edge_summed_weight == 84
    classes = Counter(check_template(words) for words in past_templates())
    assert sum(classes.values()) == 280
    assert set(classes) == {"g_in_bad", "g_outside_bad"}
    pair_cases = check_pair_cap_lemma()
    print(
        "c4_h7_d2_four_source_q5_bypass_ok",
        "decorations=1",
        f"edge_summed_weight={edge_summed_weight}",
        "past_templates=280",
        "classes=" + ",".join(
            f"{name}:{count}" for name, count in sorted(classes.items())
        ),
        f"pair_cap_cases={pair_cases}",
        "residual_tails_enumerated=0",
        "checkpoint_dp_runs=0",
        "scope=q_form_e2_q5_later_rotor_only",
    )


if __name__ == "__main__":
    main()
