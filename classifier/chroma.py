# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/03_chroma.ipynb.

# %% auto 0
__all__ = ['concat_email_summaries', 'get_or_make_chroma']

# %% ../nbs/03_chroma.ipynb 2
from typing import List, Dict
from pathlib import Path
import json

from langchain.vectorstores import Chroma
from langchain.embeddings import VertexAIEmbeddings
from langchain.schema import Document

from .schema import get_embedder

# %% ../nbs/03_chroma.ipynb 6
def concat_email_summaries(
    summaries: Dict[str, Dict[str, List[str]]]
    ) -> List[Document]:
    documents = []
    for idx, idx_dict in summaries.items():
        label = idx_dict.get('label')
        idx_content = ""
        for _, summary in idx_dict['summaries'].items():
            idx_content = idx_content + summary.strip() + "\n"
        documents.append(
            Document(
                page_content=idx_content,
                metadata={
                    'idx': int(idx),
                    'label': label
                }
            )
        )
    return documents

# %% ../nbs/03_chroma.ipynb 11
def get_or_make_chroma(
        data_dir: Path, 
        documents: List[Document] = None,
        overwrite: bool = False):
    chroma_dir = data_dir / 'chroma'
    if not chroma_dir.exists():
        chroma_dir.mkdir()
    embedding_function = get_embedder()
    persist_directory = str(chroma_dir.resolve())
    if len(list(chroma_dir.glob("*.sqlite3"))) > 0 and not overwrite:
        return Chroma(
            persist_directory=persist_directory,
            embedding_function=embedding_function
        )
    if documents is None:
        raise ValueError("documents cannot be None")
    return Chroma.from_documents(
        documents,
        embedding_function,
        persist_directory=persist_directory
    )