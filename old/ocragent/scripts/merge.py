from pathlib import Path
from typing import Dict, List
import numpy as np
import random
import re

EMBEDDING_MODEL = "qwen3-embedding:4b"
MIN_SIMILARITY = 0.995
SEP_CELL = re.compile(r"^:?-{2,}:?$")

#@task()  
def merge(self, texts:list[str]=[], output_file: str|None=None):
    embeddings = self.compute_embeddings_task.delay(texts=texts)
    return self.merge_iteration_task.delay(embeddings=embeddings, pool=texts, merge_index=0, output_file=output_file)

#@chain()
def _merge_results(self, texts=[], **kwargs):
    if not self.agent_instance_version.select_profile().task_prompt:
        raise Exception("Agent must define  a task prompt")
    result_chain = [
        self._create_query.i(),     # **kwargs -> query
        self._execute_query.i(),    # query -> response
        self._handle_response.i(),  # response -> response, tool_runs
        self._decide_next_step.i(), # response, tool_runs -> str
    ]
    if hasattr(self, "_parse_response"):
        result_chain.append(self._parse_response.i())
    return result_chain

#@task()
def merge_iteration_task(self, embeddings:List[str], pool:List[str], merge_index=0, output_file: str|None= None):
    if len(pool) <= 1:
        return pool[0]
    avg_sims = [self.average_similarity(i, embeddings) for i in range(len(pool))]
    if min(avg_sims) > self.MIN_SIMILARITY:
        return random.choice(pool)
    outlier_idx = int(np.argmin(avg_sims))
    remaining = [i for i in range(len(pool)) if i != outlier_idx]
    if not remaining:
        return pool[0]

    sims = [self.cosine_similarity(embeddings[outlier_idx], embeddings[i]) for i in remaining]
    similar_idx = remaining[int(np.argmax(sims))]
    docs_to_merge = [pool[similar_idx], pool[outlier_idx]]
    choose_from = [pool[i] for i in remaining if i != similar_idx]
    if choose_from:
        docs_to_merge.append(random.choice(choose_from))
    if merge_index >= len(self.agent_version.profile.variant_defs)*2: # try max 2 times for each merge llm variant
        new_pool = [x for x in pool]
        new_embeddings = [x for x in embeddings]
        new_pool.pop(outlier_idx)
        new_embeddings.pop(outlier_idx)
        if len(new_pool) == 1:
            return new_pool[0]
        return self.merge_iteration_task.delay(embeddings=new_embeddings, pool=new_pool, merge_index=0, output_file=output_file)
    candidate = self._merge_results.delay(texts=docs_to_merge)
    candidate_embeddings = self.compute_embeddings_task.delay(texts=[candidate])
    return self.evaluate_candidate_with_embedding.delay(candidate_embeddings=candidate_embeddings, candidate=candidate, pool=pool, embeddings=embeddings, outlier_idx=outlier_idx, merge_index=merge_index, output_file=output_file)

#@task()
def evaluate_candidate_with_embedding( self, candidate_embeddings:List[str], candidate:str, pool:List[str], embeddings:List[str], outlier_idx, merge_index, output_file: str|None= None):
    candidate_embedding = candidate_embeddings[0]
    avg_sims = [self.average_similarity(i, embeddings) for i in range(len(pool))]
    if candidate in pool:
        print("candidate in pool")
        return self.merge_iteration_task.delay(embeddings=embeddings, pool=pool, merge_index=merge_index + 1, output_file=output_file)
    cand_avg_sim = np.mean([self.cosine_similarity(candidate_embedding, embeddings[i]) for i in range(len(pool)) if i != outlier_idx])
    print("cand_avg_sim", cand_avg_sim)
    if cand_avg_sim > avg_sims[outlier_idx]:
        print("NEW IS BETTER", cand_avg_sim)
        new_pool = [x for x in pool]
        new_embeddings = [x for x in embeddings]
        new_pool.append(candidate)
        new_embeddings.append(candidate_embedding)
        new_pool.pop(outlier_idx)
        new_embeddings.pop(outlier_idx)
        return self.merge_iteration_task.delay(embeddings=new_embeddings, pool=new_pool, merge_index=0, output_file=output_file)
    if cand_avg_sim > self.MIN_SIMILARITY:
        print("NEW IS GOOD", cand_avg_sim)
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(candidate)
        return candidate
    return self.merge_iteration_task.delay(embeddings=embeddings, pool=pool, merge_index=merge_index + 1, output_file=output_file)

#@task()
def compute_embeddings_task(self, texts:list[list[float]]):
    import ollama
    batch = ollama.embed(model=self.EMBEDDING_MODEL, input=texts)
    return batch["embeddings"]

def cosine_similarity(self, vec1, vec2) -> float:
    vec1 = np.asarray(vec1)
    vec2 = np.asarray(vec2)
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

def average_similarity(self, index: int, embeddings: List[str]) -> float:
    sims = [self.cosine_similarity(embeddings[index], embeddings[i])for i in range(len(embeddings)) if i != index]  # foo
    return float(np.mean(sims)) if sims else 1.0

#helper funtions that many users need

def normalize_markdown_tables(self, md):
    lines = md.splitlines()
    out = []
    i = 0
    while i < len(lines):
        # detect header + separator
        if "|" in lines[i] and i + 1 < len(lines) and self.is_separator_row(lines[i+1]):
            header_line = lines[i]
            header_cells = self.split_md_row(header_line)
            ncols = len(header_cells)
            block = [lines[i], lines[i+1]]
            i += 2
            # collect table rows
            while i < len(lines) and "|" in lines[i]:
                block.append(lines[i])
                i += 1
            if len(block) >= 3:
                normalized = []
                normalized.append(self.normalize_row(block[0], ncols))
                normalized.append(self.normalize_separator(ncols))
                for row in block[2:]:
                    normalized.append(self.normalize_row(row, ncols))
                out.extend(normalized)
            else:
                out.extend(block)
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)

def split_md_row(self, line):
    """Split on non-escaped pipes."""
    parts = re.split(r'(?<!\\)\|', line.strip())
    return [p.strip() for p in parts if p.strip() != ""]

def is_separator_row(self, line):
    cells = self.split_md_row(line)
    if not cells:
        return False
    return all(self.SEP_CELL.match(c) for c in cells)

def normalize_row(self, line, ncols):
    cells = self.split_md_row(line)
    # fix column mismatch
    if len(cells) < ncols:
        cells += [""] * (ncols - len(cells))
    elif len(cells) > ncols:
        cells = cells[:ncols]

    return "| " + " | ".join(cells) + " |"

def normalize_separator(self, ncols):
    return "| " + " | ".join(["---"] * ncols) + " |"

