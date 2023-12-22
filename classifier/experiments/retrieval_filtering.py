# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/experiments/08_10k_retrieval_filtering.ipynb.

# %% auto 0
__all__ = ['EXPERIMENT_PREFIX', 'EXPERIMENT_WRITE_PREFIX', 'TOP_3_PROMPT_TEMPLATE', 'TOP_3_PROMPT', 'PREDICTION_TEMPLATE',
           'PREDICTION_PROMPT', 'FINAL_REGEX', 'make_categories_str', 'get_llm', 'format_category_answer', 'fix_string',
           'get_top_3_chain', 'get_label_filtered_documents', 'get_prediction_chain', 'format_filtered_examples',
           'format_final_category_string', 'invoke_chain', 'get_summary_prediction']

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 2
from typing import Dict, List, Any, Tuple
from pathlib import Path
import os
import re

import numpy as np
import pandas as pd
from tqdm import tqdm
from sklearn import metrics, model_selection

from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnableSequence
from langchain.llms import VertexAI
from langchain.vectorstores import Chroma
from langchain.document_loaders import DataFrameLoader
from langchain.output_parsers import CommaSeparatedListOutputParser, RegexParser

from ..schema import WRITE_PREFIX, PROJECT_BUCKET, quota_handler
from ..load import Email, get_batches, get_emails_from_frame, \
    get_raw_emails, email_small_enough
from ..chroma import get_or_make_chroma
from ..predict import write_predictions
from classifier.experiments.split_processing import \
    format_email_for_train_summary, \
    format_email_for_test_summary, \
    make_description_from_row, batch_predict, \
    TRAIN_PROMPT, TEST_PROMPT

# GRPC requires this
os.environ["GRPC_DNS_RESOLVER"] = "native"
EXPERIMENT_PREFIX = "retrieval_filtering"
EXPERIMENT_WRITE_PREFIX = WRITE_PREFIX + "/" + EXPERIMENT_PREFIX

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 40
def make_categories_str(
        category_descriptions: Dict[str, str], 
        ignore: List[str] = [], 
        include: List[str] = []) -> str:
    if len(include) == 0:
        include = list(category_descriptions.keys())
    return "\n".join(
        [f"- {c}" for c, d in category_descriptions.items() \
            if (c not in ignore) and (c in include)]
    )

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 42
TOP_3_PROMPT_TEMPLATE = """Below is a summary of an email sent to our customer service department. 

-- EMAIL --
{email}
-- END EMAIL --

Here is a list of categories we assign to emails;

-- CATEGORIES --
{categories}
-- END CATEGORIES --

Of the options in the above list, choose the 3 likeliest that describe the following email. 
Only return the categories you choose.
Your response should be a list of comma separated values.

-- TOP 3 LIKELIEST LABELS --
"""

TOP_3_PROMPT = PromptTemplate.from_template(TOP_3_PROMPT_TEMPLATE)

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 43
_LLM = None


def get_llm() -> VertexAI:
    global _LLM
    if _LLM is None:
        _LLM = VertexAI()
    return _LLM


def format_category_answer(answer: List[str]):
    return [s.replace("||","") for s in answer]


def fix_string(string: str) -> str:
    return string.replace("[", "").replace("]","")


def get_top_3_chain() -> RunnableSequence:
    return TOP_3_PROMPT | get_llm() | fix_string | CommaSeparatedListOutputParser() | format_category_answer

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 49
def get_label_filtered_documents(
        query: str,
        labels: List[str],
        chroma: Chroma,
        k: int = 3
        ) -> Dict[str, List[Document]]:
    documents = {}
    for l in labels:
        label_documents = chroma.similarity_search(
            query,
            filter={'label': l},
            k=k
        )
        documents[l] = label_documents
    return documents

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 52
# categories is a list like;
# 0. CATEGORY
# 1. CATEGORY 2
# 2. CATEGORY 3
PREDICTION_TEMPLATE = """Below is a summary of an email sent to our customer service department.
It is your job to decide which category the email belongs to.

-- EMAIL --
{email}
-- END EMAIL --

Choose which of the following categories the email above belongs to;

-- CATEGORIES --
{categories}
-- END CATEGORIES --

Here are some similar emails and how they were labeled to help you decide.

-- EXAMPLES --
{examples}
-- END EXAMPLES --

Return only the number of the category you have picked.

Category Number: """

PREDICTION_PROMPT = PromptTemplate.from_template(PREDICTION_TEMPLATE)

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 53
FINAL_REGEX = "(\d+)(?!.*\d)"

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 54
def get_prediction_chain() -> RunnableSequence:
    return PREDICTION_PROMPT | get_llm() | RegexParser(
        regex=FINAL_REGEX, 
        output_keys=['result'], 
        default_output_key='result')

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 56
def format_filtered_examples(examples: Dict[str, List[Document]]) -> str:
    result = ""
    for cat, docs in examples.items():
        cat_header = f"||{cat}|| examples;"
        document_content = "\n".join(
            [
                f"Summary: {d.page_content}\nLabel: {d.metadata.get('label')}\n" for d in docs
            ])
        result = result + cat_header + document_content
    return result

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 57
def format_final_category_string(categories: List[str]) -> str:
    return "\n".join([f'{i}. {cat}' for i, cat in enumerate(categories)])

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 59
@quota_handler
def invoke_chain(chain: RunnableSequence, *args, **kwargs) -> Any:
    return chain.invoke(*args, **kwargs)

# %% ../../nbs/experiments/08_10k_retrieval_filtering.ipynb 60
def get_summary_prediction(
        summary: str, 
        chroma: Chroma, 
        step_1_chain: RunnableSequence,
        step_2_chain: RunnableSequence,
        descriptions: Dict[str, str]) -> Tuple[List[str], List[Document], int, str]:
    step_1_answer = None
    similar_documents = None
    step_1_answer_position = None
    final_answer = None
    if summary is None:
        return step_1_answer, similar_documents, step_1_answer_position, final_answer
    categories_str = make_categories_str(descriptions)
    # Make a prediction for an input summary
    step_1_answer = invoke_chain(
        step_1_chain, 
        {
            'categories': categories_str,
            'email': summary
        })
    # I've run out of time to tinker with this. If it ain't right, ignore it.
    # TODO: Fix step one prompt / chain to handle outlier inference cases that aren't formatted right.
    if len(step_1_answer) != 3:
        return step_1_answer, similar_documents, step_1_answer_position, final_answer
    # Get similar documents for each likely category
    similar_documents = get_label_filtered_documents(
        query=summary,
        labels=step_1_answer,
        chroma=chroma
    )
    step_2_answer = invoke_chain(
        step_2_chain,
        {
            'categories': format_final_category_string(step_1_answer),
            'examples': format_filtered_examples(similar_documents),
            'email': summary
        })
    step_1_answer_position = int(step_2_answer.get('result'))
    if step_1_answer_position > len(step_1_answer):
        return step_1_answer, similar_documents, step_1_answer_position, final_answer
    try:
        final_answer = step_1_answer[step_1_answer_position].strip()
    except IndexError as e:
        print("Position was ", step_1_answer_position)
        print("List was ", step_1_answer)
        raise e
    return step_1_answer, similar_documents, step_1_answer_position, final_answer
