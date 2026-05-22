import functools
import os
import time
from rapidfuzz.distance import Levenshtein
from itertools import combinations


def find_fuzzy_match(text: str,
                    search: str,
                    threshold: float = 0.90,
                    min_split_length: int = 3,
                    max_splits:int = 100):
    """
    Find a fuzzy match of `search` in `text` using a split-and-compare strategy.
    Returns a tuple (start, end, candidate, score) for the first match meeting the threshold,
    or None if no fuzzy match is found.

    Parameters:
    - text: The text to search within.
    - search: The string to find approximately.
    - threshold: Minimum similarity score (0.0 to 1.0) to accept a match.
    - min_split_length: Minimum length of each part when splitting search.
    - max_splits: Max number of splits to do.

    Method:
    1) Skip exact match; this finder is for non-exact matches.
    2) For each n in max_splits:
    a) Split search into n parts of (nearly) equal length.
    b) Skip if any part shorter than min_split_length.
    c) Find all exact positions for each part.
    d) For any two parts i < j with occurrences:
        - For each occurrence pair in order, span from start_i to end_j.
        - Compute Levenshtein distance vs search; convert to similarity.
        - If score >= threshold, return (span_start, span_end, candidate, score).
    3) Return None if no match found.
    """
    print(text, search, threshold)

    def split_parts(string: str, n: int):
        l = len(string)
        """Split s into n nearly-equal parts."""
        return [string[int(i * l / n): int((i + 1) * l / n)] for i in range(n)]
    start_t = (time.time())

    def find_positions(part: str):
        """Return list of all start indices of `part` in text."""
        starts = []
        pos = text.find(part)
        while pos != -1:
            starts.append(pos)
            pos = text.find(part, pos + 1)
            if int(time.time()) - start_t > 20:
                print("spending too much time here, timeout")
                break
        return starts
    
    search_lower = search.lower()
    search_eq_lower = search_lower == search
    search_length = len(search)
    best_candidate = [0,0,0,0]
    best_candidates = set()
    no_better_candidate_cnt = 0
    for n in range(1, max_splits):
        if int(time.time()) - start_t > 20:
            print("spending too much time here, timeout")
            break

        parts = split_parts(search, n)
        if any(len(p) < min_split_length for p in parts):
            break
        positions = [find_positions(p) for p in parts]
        empty_head_end_index = -1
        for p in positions:
            if p != []:
                break
            empty_head_end_index += 1
        empty_tail_start_index = len(positions) 
        for p in reversed(positions):
            if p != []:
                break
            empty_tail_start_index -= 1

        nonempty = [i for i, lst in enumerate(positions) if lst]
        if len(nonempty) < 2:
            continue

        for i in range(empty_head_end_index, -1, -1):
            for p in positions[i+1]:
                positions[i].append(p-len(parts[i])-1)

        for i in range(empty_tail_start_index, len(positions)):
            for p in positions[i-1]:
                positions[i].append(p+len(parts[i])-1)

        nonempty = [i for i, lst in enumerate(positions) if lst]
    
        last_best_candidate = best_candidate
        
        for i, j in combinations(nonempty, 2):
            for start_i in positions[i]:
                if int(time.time()) - start_t > 20:
                    print("spending too much time here, timeout")
                    break

                end_i = start_i + len(parts[i])
                for start_j in positions[j]:
                    if start_j >= end_i:
                        end_j = start_j + len(parts[j])
                        span_start = start_i
                        span_end = end_j
                        candidate = text[span_start:span_end]
                        l = max(search_length, len(candidate))
                        ld_score       = 1 - Levenshtein.distance(candidate        , search      ) / l
                        candidate_lower = candidate.lower()
                        if search_eq_lower and candidate_lower == candidate:
                            ld_score_lower = ld_score
                        else:
                            ld_score_lower = 1 - Levenshtein.distance(candidate_lower, search_lower) / l
                                      
                        score = (ld_score + ld_score_lower) / 2
                        if score > best_candidate[3]:
                            best_candidate = (span_start, span_end, candidate, score)
                            best_candidates = set([best_candidate])
                        elif score == best_candidate[3]:
                            best_candidates.add((span_start, span_end, candidate, score))
                            
        if last_best_candidate == best_candidate: # nothing better found, return
            no_better_candidate_cnt += 1
            if no_better_candidate_cnt > 2:
                break
        else:
            no_better_candidate_cnt = 0
        last_best_candidate = best_candidate

    if len(best_candidates) != 1:
        return None
    
    if best_candidate[3] < threshold:
        return None
    
    return best_candidate[2]
