# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/03_chroma.ipynb.

# %% auto 0
__all__ = ['get_or_make_chroma', 'read_json_lines_from_gcs']

# %% ../nbs/03_chroma.ipynb 2
from typing import List, Dict, Any, Iterable
from pathlib import Path
import json
import pandas as pd

import chromadb
from langchain.vectorstores import Chroma
from langchain.embeddings import VertexAIEmbeddings
from langchain.schema import Document
from langchain.document_loaders import DataFrameLoader
from google.cloud import storage
from tqdm import tqdm

from .schema import get_embedder, get_storage_client, WRITE_PREFIX
from .load import get_emails_from_frame, get_idx, Email, \
    PROJECT_BUCKET, get_train_test_idx, LABEL_COLUMN, get_batches, write_idx, \
    get_raw_emails_tejas_case_numbers

# %% ../nbs/03_chroma.ipynb 16
def get_or_make_chroma(
        data_dir: Path, 
        documents: List[Document] = None,
        overwrite: bool = False):
    chroma_dir = data_dir / 'chroma'
    if not chroma_dir.exists():
        chroma_dir.mkdir()
    embedding_function = get_embedder()
    persist_directory = str(chroma_dir.resolve())
    if len(list(chroma_dir.glob("*.sqlite3"))) > 0:
        if not overwrite:
            return Chroma(
                persist_directory=persist_directory,
                embedding_function=embedding_function
            )
        else:
            for f in chroma_dir.glob("*"):
                f.unlink()
    if documents is None:
        raise ValueError("documents cannot be None")
    return Chroma.from_documents(
        documents,
        embedding_function,
        persist_directory=persist_directory
    )

# %% ../nbs/03_chroma.ipynb 21
def read_json_lines_from_gcs(
        blob_name: str,
        bucket_name: str = PROJECT_BUCKET) -> Iterable[Any]:
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    with blob.open('r') as f:
        for line in f.readlines():
            yield json.loads(line)
