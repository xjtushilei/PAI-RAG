import os
import ray
import json
from loguru import logger
from pai_rag.core.rag_module import resolve
from pai_rag.tools.data_process.utils.formatters import convert_document_to_dict
from pai_rag.utils.oss_client import OssClient
from pai_rag.core.rag_config_manager import RagConfigManager
from pai_rag.utils.download_models import ModelScopeDownloader
from pai_rag.integrations.readers.pai.pai_data_reader import PaiDataReader
from pai_rag.utils.constants import DEFAULT_MODEL_DIR


@ray.remote(num_cpus=4)
class ParseActor:
    def __init__(self, working_dir, config_file):
        RAY_ENV_MODEL_DIR = os.path.join(working_dir, "model_repository")
        os.environ["PAI_RAG_MODEL_DIR"] = RAY_ENV_MODEL_DIR
        logger.info(f"Init ParseActor with working dir: {RAY_ENV_MODEL_DIR}.")
        config = RagConfigManager.from_file(config_file).get_value()
        self.download_model_list = ["PDF-Extract-Kit"]
        self.load_models(self.download_model_list)

        data_reader_config = config.data_reader
        oss_store = None
        if config.oss_store.bucket:
            oss_store = resolve(
                cls=OssClient,
                bucket_name=config.oss_store.bucket,
                endpoint=config.oss_store.endpoint,
            )
        self.data_reader = resolve(
            cls=PaiDataReader,
            reader_config=data_reader_config,
            oss_store=oss_store,
        )

        logger.info("ParseActor init finished.")

    def load_models(self, model_list):
        download_models = ModelScopeDownloader(
            fetch_config=True,
            download_directory_path=os.getenv("PAI_RAG_MODEL_DIR", DEFAULT_MODEL_DIR),
        )
        for model_name in model_list:
            download_models.load_model(model=model_name)
        download_models.load_mineru_config()

    def load_and_parse(self, input_file):
        documents = self.data_reader.load_data(file_path_or_directory=input_file)
        return convert_document_to_dict(documents[0])

    def write_to_file(self, results, filename):
        with open(filename, "a", encoding="utf-8") as f:
            for result in results:
                json_line = json.dumps(result, ensure_ascii=False)
                f.write(json_line + "\n")
