# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/04_predict.ipynb.

# %% auto 0
__all__ = ['EMAIL_LABEL_SEP', 'LABEL_STR', 'PREDICTION_PROMPT_TEMPLATE', 'PREDICTION_PROMPT', 'filter_examples', 'format_example',
           'make_prediction_prompt', 'predict_batch', 'get_predictions', 'write_predictions']

# %% ../nbs/04_predict.ipynb 2
from pathlib import Path
import json
from typing import List, Tuple
import time
from tqdm import tqdm
import pandas as pd

import chromadb
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain.vectorstores import Chroma
from langchain.document_loaders import DataFrameLoader
from langchain.llms import VertexAI

from .schema import predict, quota_handler, WRITE_PREFIX, PROJECT_BUCKET
from .load import get_possible_labels, get_emails_from_frame, get_idx, LABEL_COLUMN, \
    get_raw_emails_tejas_case_numbers, get_batches
from .process import BISON_MAXIMUM_INPUT_TOKENS
from .chroma import get_or_make_chroma, get_embedder, \
    read_json_lines_from_gcs

# %% ../nbs/04_predict.ipynb 27
EMAIL_LABEL_SEP = "|||"

LABEL_STR = """- Order Processing
- Product Inquiry
- Account/Inquiry
- General Inquiry
- Returns
- Billing / Invoice
- Delivery
- Credits
- Order Discrepancy
- Pricing
- Program / Promotions"""

PREDICTION_PROMPT_TEMPLATE = """\
Our customer service team wants to classify emails so they can be sent to the right support team.
Here are the labels they use;

--LABELS--
""" + LABEL_STR + """

Below are a series of emails that have already been labeled, use their example to identify what label the final email should get.
Your answer must be one of the options in the --LABELS-- list.
Return only the label from the above list that you chose.

--EMAILS--
{examples}
EMAIL: {email} """ + f"{EMAIL_LABEL_SEP} LABEL: "

PREDICTION_PROMPT = PromptTemplate.from_template(PREDICTION_PROMPT_TEMPLATE)

# %% ../nbs/04_predict.ipynb 29
def filter_examples(examples: List[Document], idx: int) -> List[Document]:
    return [e for e in examples if int(e.metadata.get('idx')) != int(idx)]

# %% ../nbs/04_predict.ipynb 33
def format_example(example: Document) -> str:
    return f"EMAIL: {example.page_content.strip()} {EMAIL_LABEL_SEP} LABEL: {example.metadata.get('label')}"


def make_prediction_prompt(
        email_summary: Document,
        chroma: Chroma,
        limit: int = None
) -> str:
    idx = email_summary.metadata.get('idx')
    k = 5
    prompt = None
    keep_stuffing = True
    max_k = len(chroma.get()['ids']) if limit is None else limit
    while keep_stuffing:
        examples = chroma.similarity_search(email_summary.page_content, k=k)
        examples = filter_examples(examples, idx)
        if len(examples) == 0:
            k += 5
            continue
        else:
            example_str = ""
            for e in examples:
                e_formatted = format_example(e)
                if len(example_str) == 0:
                    example_str = e_formatted
                else:
                    example_str = example_str + "\n" + e_formatted
                prompt = PREDICTION_PROMPT.format(
                    email=email_summary.page_content,
                    examples=example_str
                )
                if len(prompt) >= BISON_MAXIMUM_INPUT_TOKENS:
                    keep_stuffing = False
                    break
        k += 5
        if k >= max_k:
            keep_stuffing = False
    return prompt

# %% ../nbs/04_predict.ipynb 44
@quota_handler
def predict_batch(llm: VertexAI, prompts: List[str]) -> List[str]:
    return llm.batch(prompts)


def get_predictions(llm: VertexAI, prompts: List[str]) -> List[str]:
    pbar = tqdm(total=len(prompts), ncols=80, leave=False)
    predictions = []
    for batch in get_batches(iter(prompts), 5):
        batch_predictions = predict_batch(llm, batch)
        predictions.extend(batch_predictions)
        pbar.update(len(batch))
    pbar.close()
    return predictions

# %% ../nbs/04_predict.ipynb 52
def write_predictions(
        predictions: List[str],
        labels: List[str],
        idx: List[str],
        prompts: List[str],
        emails: List[str],
        directory: Path,
        file_name: str = "predictions.csv"):
    pd.DataFrame(
        list(zip(
            predictions, 
            labels,
            idx,
            prompts,
            emails)),
        columns=['prediction', 'label', 'idx', 'prompt', 'email']
    ).to_csv(directory / file_name, index=False)
