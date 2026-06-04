"""
Simple liveness check command. Responds with agent/session info.
"""
from __future__ import annotations
from runtime.session.session import Session
from collections import Counter, defaultdict
from itertools import combinations


def ocr(session: Session, image_data: str | None = None, allow_cloud=False, ) -> str:
    get aimodels where cloud ==allow_cloud vision =True
    ocr_results = []
    for aimodel in aimodels:
        model_session = ocragent . session_create ("ocr %s" % aimodel)
        model_session.settings.aimodel = aimodel
        ocr_result = model_session.add_user_message(image_data)
        ocr_results.append((model_session, ocr_result))
    

def scorme(session: Session, ocr_results):
    final_result = merge.delay([x[1] for x in ocr_results])
    for i in range(6):
        result_wordcombos =set( get_ngrams(final_result, i))
        for ocr_result in ocr_results:
            ocr_result_wordcombos =  set(get_ngrams(ocr_result, i))
            # reject rate = is in ocr_result, but not in final result
            rejected =  (ocr_result_wordcombos - result_wordcombos)
            reject_rate = 1 / len(ocr_result_wordcombos) * len(rejected)

            # miss rate = is in final_result, but not in ocr_result
            misses = result_wordcombos - ocr_result_wordcombos
            miss_rate = 1 / len(result_wordcombos) * len(misses)

            # is in ocr_result and in final_result
            hits = result_wordcombos & ocr_result_wordcombos
            hit_rate = 1 / len(result_wordcombos) * len(hits)

    return ""


def weighted_jaccard_similarity(a, b, support):
    if not a and not b:
        return 1.0

    union = a | b
    if not union:
        return 1.0

    weighted_intersection = sum(support.get(ng, 0.0) for ng in (a & b))
    weighted_union = sum(support.get(ng, 0.0) for ng in union)

    if weighted_union == 0:
        return 0.0

    return weighted_intersection / weighted_union


def jaccard_similarity(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def get_ngrams(text, n):
    tokens = text.split()
    return [tuple(tokens[i:i+n]) for i in range(len(tokens)-n+1)]



def calculate_diversity_metrics(missing_ngram_sets, spell_error_sets,  support):
    """
    Returns:
        missing_similarity_matrix
        spell_similarity_matrix
        uniqueness_scores
    """

    n = len(missing_ngram_sets)

    missing_similarity_matrix = [[0.0] * n for _ in range(n)]
    spell_similarity_matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        missing_similarity_matrix[i][i] = 1.0
        spell_similarity_matrix[i][i] = 1.0

    for i, j in combinations(range(n), 2):

        ms = weighted_jaccard_similarity(
            missing_ngram_sets[i],
            missing_ngram_sets[j],
            support
        )

        ss = jaccard_similarity(
            spell_error_sets[i],
            spell_error_sets[j]
        )

        missing_similarity_matrix[i][j] = ms
        missing_similarity_matrix[j][i] = ms

        spell_similarity_matrix[i][j] = ss
        spell_similarity_matrix[j][i] = ss

    uniqueness_scores = []

    for i in range(n):

        avg_missing_similarity = (
            sum(missing_similarity_matrix[i]) - 1
        ) / (n - 1)

        avg_spell_similarity = (
            sum(spell_similarity_matrix[i]) - 1
        ) / (n - 1)

        avg_similarity = (
            avg_missing_similarity +
            avg_spell_similarity
        ) / 2

        uniqueness_scores.append(
            1.0 - avg_similarity
        )


    return (
        missing_similarity_matrix,
        spell_similarity_matrix,
        uniqueness_scores,
    )




def score(session, ocr_results, max_n=5):
    """
    Returns:
        spell_scores: list[float]
        coverage_scores: list[float]
        missing_scores: list[float]
        global_support: dict
    """

    N = len(ocr_results)

    # ---------------------------------------------------
    # 1. Extract n-grams per OCR result
    # ---------------------------------------------------
    ocr_ngrams = []
    for text in ocr_results:
        ng_set = set()
        for n in range(1, max_n + 1):
            ng_set.update(get_ngrams(text, n))
        ocr_ngrams.append(ng_set)

    # ---------------------------------------------------
    # 2. Compute global n-gram support
    # ---------------------------------------------------
    counts = Counter()
    for ng_set in ocr_ngrams:
        counts.update(ng_set)

    support = {
        ng: counts[ng] / N
        for ng in counts
    }

    # ---------------------------------------------------
    # 3. Per-OCR scoring
    # ---------------------------------------------------
    coverage_scores = []
    missing_scores = []

    for ng_set in ocr_ngrams:

        if not ng_set:
            coverage_scores.append(0.0)
            missing_scores.append(1.0)
            continue

        # ---- coverage: how supported is what I contain?
        coverage = sum(support[ng] for ng in ng_set) / len(ng_set)

        # ---- missing: how much supported signal did I miss?
        missing_ngrams = [ng for ng in support if ng not in ng_set]
        missing = 0.0
        if missing_ngrams:
            missing = sum(support[ng] for ng in missing_ngrams) / len(missing_ngrams)
    
        coverage_scores.append(coverage)
        missing_scores.append(missing)

    # ---------------------------------------------------
    # 4. Spellcheck signal (external)
    # ---------------------------------------------------
    spell_errors = spellcheck(ocr_results)  # assumed: lower = better
    spell_scores = [1 - e for e in spell_errors]

    # build missing ngram sets
    missing_ngram_sets = []
    for ng_set in ocr_ngrams:
        missing = {ng for ng in support if ng not in ng_set}
        missing_ngram_sets.append(missing)


    missing_similarity_matrix, spell_similarity_matrix, uniqueness_scores = calculate_diversity_metrics(missing_ngram_sets, spell_errors,  support)

    # ---------------------------------------------------
    # 5. Global debug stats
    # ---------------------------------------------------
    global_support = {
        "avg_coverage": sum(coverage_scores) / N,
        "avg_missing": sum(missing_scores) / N,
        "avg_spell": sum(spell_scores) / N,
    }

    return spell_scores, coverage_scores, missing_scores, global_support