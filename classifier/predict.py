# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/04_predict.ipynb.

# %% auto 0
__all__ = ['LABEL_STR', 'PREDICTION_PROMPT_TEMPLATE', 'PREDICTION_PROMPT', 'predict']

# %% ../nbs/04_predict.ipynb 2
from pathlib import Path
import json

from langchain.schema import Document
from langchain.prompts import PromptTemplate

from .schema import predict
from .load import get_possible_labels
from .chroma import get_or_make_chroma, concat_email_summaries

# %% ../nbs/04_predict.ipynb 11
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
- Program / Promotions
"""

PREDICTION_PROMPT_TEMPLATE = """Classify the following email into one of these categories:""" + \
    LABEL_STR + """\nEMAIL: {email}\nHere are some similar emails and their labels:{examples}
    Classification: """

PREDICTION_PROMPT = PromptTemplate.from_template(PREDICTION_PROMPT_TEMPLATE)

# %% ../nbs/04_predict.ipynb 13
def predict(document: Document) -> str:
    pass
