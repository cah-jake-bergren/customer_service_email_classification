# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_schema.ipynb.

# %% auto 0
__all__ = ['PROJECT_ID', 'PROJECT_BUCKET', 'REGION', 'WRITE_PREFIX', 'DEFAULT_PREDICT_PARAMS', 'ONE_MINUTE', 'get_embedder',
           'get_storage_client', 'init_vertexai', 'get_model', 'predict', 'batch_predict']

# %% ../nbs/00_schema.ipynb 3
import os
from typing import Dict
from ratelimit import limits, sleep_and_retry

import vertexai
from vertexai.language_models import TextGenerationModel
from vertexai.language_models._language_models import MultiCandidateTextGenerationResponse
from google.cloud.aiplatform import BatchPredictionJob
from google.cloud import storage

from langchain.embeddings import VertexAIEmbeddings

# GRPC requires this
os.environ["GRPC_DNS_RESOLVER"] = "native"

PROJECT_ID = "cdejam-gbsrc-ext-cah"
PROJECT_BUCKET = "pharma_email_classification"
REGION = "us-central1"

# %% ../nbs/00_schema.ipynb 5
def get_embedder() -> VertexAIEmbeddings:
    return VertexAIEmbeddings(
        project=PROJECT_ID,
        location=REGION,
        model_name='textembedding-gecko'
    )

# %% ../nbs/00_schema.ipynb 7
WRITE_PREFIX = "JDB_experiments"

DEFAULT_PREDICT_PARAMS = {
    "temperature": 0.2,
    "top_p": 0.95,
    "top_k": 40,
}

_VERTEX_INITIATED = False
ONE_MINUTE = 60


def get_storage_client() -> storage.Client:
    return storage.Client(project=PROJECT_ID)


def init_vertexai(
    project_id: str = PROJECT_ID,
    region: str = REGION):
    global _VERTEX_INITIATED
    if not _VERTEX_INITIATED:
        vertexai.init(project=project_id, location=region)
        _VERTEX_INITIATED = True


def get_model() -> TextGenerationModel:
    init_vertexai()
    return TextGenerationModel.from_pretrained("text-bison")


@sleep_and_retry
@limits(calls=50, period=ONE_MINUTE)
def predict(
        prompt: str,
        parameters: Dict[str, str] = DEFAULT_PREDICT_PARAMS
        ) -> MultiCandidateTextGenerationResponse:
    model = get_model()
    return model.predict(
        prompt,
        **parameters)


def batch_predict(
        source_uri: str,
        destination_uri_prefix: str,
        model_parameters: Dict[str, str] = DEFAULT_PREDICT_PARAMS
) -> BatchPredictionJob:
    """
    Make a batch prediction request to text-bison.

    :param source_uri: Source file in GCS with prompted requests, 
        I.E. 'gs://BUCKET_NAME/test_table.jsonl'
    :param destination_uri_prefix: Where the results will be written, 
        ex: 'gs://BUCKET_NAME/tmp/2023-05-25-vertex-LLM-Batch-Prediction/result3'
    """
    model = get_model()
    batch_prediction_job = model.batch_predict(
        source_uri=[source_uri],
        destination_uri_prefix=destination_uri_prefix,
        # Optional:
        model_parameters=model_parameters
    )
    # print(batch_prediction_job.display_name)
    # print(batch_prediction_job.resource_name)
    # print(batch_prediction_job.state)
    return batch_prediction_job
