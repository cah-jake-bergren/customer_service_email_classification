# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_load.ipynb.

# %% auto 0
__all__ = ['LABEL_COLUMN', 'EMAIL_SIZE_LIMIT', 'INCLUSION_COUNT', 'TRAIN_IDX_NAME', 'TEST_IDX_NAME', 'get_possible_labels',
           'TrainingInstance', 'training_instance_from_row', 'email_small_enough', 'get_train_test_idx', 'write_idx',
           'get_idx', 'get_training_instances', 'get_document_batches']

# %% ../nbs/01_load.ipynb 2
import math
from typing import Dict, Any, Iterable, List, Tuple
import pandas as pd
import json

from pydantic import BaseModel
from langchain.schema import Document
from langchain.document_loaders.base import BaseLoader
from sklearn.model_selection import train_test_split
from google.cloud import storage

from .schema import PROJECT_ID, PROJECT_BUCKET, WRITE_PREFIX

# %% ../nbs/01_load.ipynb 6
LABEL_COLUMN = "sfdc_category"

# %% ../nbs/01_load.ipynb 10
def get_possible_labels() -> List[str]:
    return pd.read_excel(
        f"gs://{PROJECT_BUCKET}/Last50KCases_withSubjectAndBody.xlsx"
        ).sfdc_category.unique().tolist()

# %% ../nbs/01_load.ipynb 11
class TrainingInstance(BaseModel):
    idx: int
    label: str
    email_subject: str
    email_body: str
    metadata: Dict[str, Any]

    def to_series(self) -> pd.Series:
        data = self.metadata.copy()
        data['idx'] = self.idx
        data['label'] = self.label
        data['email_subject'] = self.email_subject
        data['email_body'] = self.email_body
        return pd.Series(data)


def training_instance_from_row(idx: int, row: pd.Series):
    metadata = row.drop(
        [
            'sfdc_category', 
            'email_subject',
            'email_body'
        ]).to_dict()
    return TrainingInstance(
        idx=idx,
        label=row.sfdc_category,
        email_subject=str(row.email_subject),
        email_body=str(row.email_body),
        metadata=metadata
    )

# %% ../nbs/01_load.ipynb 15
# Our prompt to summarize takes up some amount of prompt space. This is a rough limit
EMAIL_SIZE_LIMIT = 7800


def email_small_enough(subject: str, body: str, limit: int = EMAIL_SIZE_LIMIT) -> bool:
    if not isinstance(subject, str):
        subject = str(subject)
    if not isinstance(body, str):
        body = str(body)
    return (len(subject) + len(body)) < limit

# %% ../nbs/01_load.ipynb 19
INCLUSION_COUNT = 1000


def get_train_test_idx(
        data: pd.DataFrame,
        inclusion_count: int = INCLUSION_COUNT, 
        train_proportion: int = 0.9,
        label_column: str = LABEL_COLUMN,
        random_state: int = 42):
    train_count = int(round(inclusion_count * train_proportion))
    test_count = inclusion_count - train_count
    train, test = train_test_split(
        data,
        test_size=test_count, 
        train_size=train_count,
        random_state=random_state,
        stratify=data[label_column])
    input_data = pd.concat([train, test], axis=0)
    return train_test_split(
        input_data,
        test_size=1-train_proportion,
        train_size=train_proportion,
        random_state=random_state,
        stratify=input_data[label_column]
    )

# %% ../nbs/01_load.ipynb 23
TRAIN_IDX_NAME = "train_idx.csv"
TEST_IDX_NAME = "test_idx.csv"


def write_idx(
        train_idx: pd.Index, 
        test_idx: pd.Index, 
        bucket_name: str = PROJECT_BUCKET,
        prefix: str = WRITE_PREFIX):
    
    train_idx.to_series().to_csv(f"gs://{bucket_name}/{prefix}/{TRAIN_IDX_NAME}", index=False)
    test_idx.to_series().to_csv(f"gs://{bucket_name}/{prefix}/{TEST_IDX_NAME}", index=False)

# %% ../nbs/01_load.ipynb 25
def get_idx(
        bucket_name: str = PROJECT_BUCKET,
        prefix: str = WRITE_PREFIX) -> Tuple[pd.Series, pd.Series]:
    return pd.read_csv(f'gs://{bucket_name}/{prefix}/{TRAIN_IDX_NAME}').iloc[:, 0], \
        pd.read_csv(f'gs://{bucket_name}/{prefix}/{TEST_IDX_NAME}').iloc[:, 0]

# %% ../nbs/01_load.ipynb 28
def get_training_instances(
        bucket_name: str = PROJECT_BUCKET
) -> Iterable[TrainingInstance]:
    data = pd.read_excel(
        f"gs://{bucket_name}/Last50KCases_withSubjectAndBody.xlsx")
    # Load train and test idx
    train_idx, test_idx = get_idx(bucket_name=bucket_name)
    full_idx = pd.concat([train_idx, test_idx], axis=0, ignore_index=True)
    data = data.loc[full_idx, :]
    for idx, row in data.iterrows():
        yield training_instance_from_row(idx, row)

# %% ../nbs/01_load.ipynb 30
def get_document_batches(loader: Iterable[TrainingInstance], batch_size: int = 32) -> Iterable[List[TrainingInstance]]:
    "Get a batch of documents of size `batch_size` from a BaseLoader with `.lazy_load` implemented."
    batch = []
    for instance in loader:
        batch.append(instance)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    yield batch
