import os
from pai_rag.evaluation.metrics.retrieval.hitrate import HitRate
from pai_rag.evaluation.metrics.retrieval.mrr import MRR
from pai_rag.evaluation.metrics.response.faithfulness import Faithfulness
from pai_rag.evaluation.metrics.response.correctness import Correctness

from llama_index.core.async_utils import run_jobs
from pai_rag.evaluation.dataset.rag_eval_dataset import (
    EvaluationSample,
    PaiRagEvalDataset,
)
from llama_index.core.llama_dataset import (
    CreatedBy,
    CreatedByType,
)
from pai_rag.evaluation.dataset.rag_qca_dataset import PaiRagQcaDataset
from loguru import logger


class BaseEvaluator:
    def __init__(
        self,
        llm,
        persist_path: str = None,
        evaluation_dataset_path: str = None,
        enable_multi_modal: bool = False,
        use_granular_metrics: bool = False,
    ):
        self._llm = llm
        self.persist_path = persist_path
        self.hitrate = HitRate(use_granular_hit_rate=use_granular_metrics)
        self.mrr = MRR(use_granular_mrr=use_granular_metrics)
        self.retrieval_evaluators = [self.hitrate, self.mrr]
        self.faithfulness_evaluator = Faithfulness(
            llm=self._llm,
        )
        self.correctness_evaluator = Correctness(
            llm=self._llm,
        )
        self.response_evaluators = [
            self.faithfulness_evaluator,
            self.correctness_evaluator,
        ]
        self.evaluation_dataset_path = evaluation_dataset_path or os.path.join(
            self.persist_path, "evaluation_dataset.json"
        )
        self.created_by = CreatedBy(
            type=CreatedByType.AI, model_name=self._llm.metadata.model_name
        )
        self.qca_dataset_path = os.path.join(self.persist_path, "qca_dataset.json")
        self._show_progress = True
        self._workers = 2
        self.enable_multi_modal = enable_multi_modal

    def load_qca_dataset(self) -> None:
        if os.path.exists(self.qca_dataset_path):
            rag_qca_dataset = PaiRagQcaDataset.from_json(self.qca_dataset_path)
            if rag_qca_dataset.labelled and rag_qca_dataset.predicted:
                logger.info(
                    f"Labelled QCA dataset already exists at {self.qca_dataset_path}."
                )
                return rag_qca_dataset
            else:
                raise ValueError(
                    "The QCA dataset exists but is not labelled and predicted. "
                    "Please either label it or provide a new one."
                )
        else:
            logger.info(
                "No existing QCA dataset found. You can proceed to create a new one."
            )
            return None

    def load_evaluation_dataset(self) -> None:
        if os.path.exists(self.evaluation_dataset_path):
            logger.info(
                f"A evaluation dataset already exists at {self.evaluation_dataset_path}."
            )
            evaluation_dataset = PaiRagEvalDataset.from_json(
                self.evaluation_dataset_path
            )
            return evaluation_dataset
        else:
            logger.info(
                "No existing evaluation dataset found. You can proceed to create a new one."
            )
            return None

    async def compute_retrieval_metrics(self, qca_sample):
        retrieval_eval_example = EvaluationSample(**vars(qca_sample))
        reference_node_ids = retrieval_eval_example.reference_node_ids
        predicted_node_ids = retrieval_eval_example.predicted_node_ids
        for metric in self.retrieval_evaluators:
            metric_score = metric.compute(reference_node_ids, predicted_node_ids)
            setattr(retrieval_eval_example, metric.metric_name, metric_score)
            setattr(retrieval_eval_example, "evaluated_by", self.created_by)

        return retrieval_eval_example

    async def compute_response_metrics(self, qca_sample):
        response_eval_example = EvaluationSample(**vars(qca_sample))
        query = response_eval_example.query
        reference_answer = response_eval_example.reference_answer
        response_answer = response_eval_example.predicted_answer
        reference_image_url_list = response_eval_example.reference_image_url_list
        contexts = (
            response_eval_example.predicted_contexts
            or response_eval_example.reference_contexts
        )

        for metric in self.response_evaluators:
            if self.enable_multi_modal:
                metric_result = await metric.aevaluate_multimodal(
                    query,
                    reference_answer,
                    contexts,
                    reference_image_url_list,
                    response_answer,
                    sleep_time_in_seconds=3,
                )
            else:
                metric_result = await metric.aevaluate(
                    query,
                    reference_answer,
                    contexts,
                    response_answer,
                    sleep_time_in_seconds=3,
                )

            setattr(
                response_eval_example, f"{metric.metric_name}_score", metric_result[0]
            )
            setattr(
                response_eval_example, f"{metric.metric_name}_reason", metric_result[1]
            )
            setattr(response_eval_example, "evaluated_by", self.created_by)

        return response_eval_example

    async def aevaluation(self, stage):
        """Run evaluation with qca dataset."""
        _status = {"retrieval": False, "response": False}
        evaluation_dataset = self.load_evaluation_dataset()
        qca_dataset = self.load_qca_dataset()
        if evaluation_dataset:
            logger.info(
                f"A evaluation dataset already exists with status: [[{evaluation_dataset.status}]]"
            )
            _status = evaluation_dataset.status
            if _status[stage]:
                return evaluation_dataset.results[stage]
            else:
                qca_dataset = evaluation_dataset
        if qca_dataset:
            logger.info(
                f"Starting to generate evaluation dataset for stage: [[{stage}]]..."
            )
            eval_tasks = []
            for qca in qca_dataset.examples:
                if stage == "retrieval":
                    eval_tasks.append(self.compute_retrieval_metrics(qca))
                elif stage == "response":
                    eval_tasks.append(self.compute_response_metrics(qca))
                else:
                    raise ValueError(f"Invalid stage: {stage}")
            eval_examples = await run_jobs(
                eval_tasks, self._show_progress, self._workers
            )
            _status[stage] = True
            eval_dataset = PaiRagEvalDataset(examples=eval_examples, status=_status)
            eval_dataset.save_json(self.evaluation_dataset_path)
            return eval_dataset.results[stage]
        else:
            raise ValueError(
                "No QCA dataset found. Please provide a QCA dataset or "
                "generate one first."
            )
