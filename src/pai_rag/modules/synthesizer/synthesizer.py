"""synthesizer factory, used to generate synthesizer instance based on customer config"""

import logging
from typing import Callable, Dict, List, Optional, Any

from llama_index.core.bridge.pydantic import BaseModel
from llama_index.core.callbacks.base import CallbackManager
from llama_index.core.indices.prompt_helper import PromptHelper
from llama_index.core.prompts import (
    BasePromptTemplate,
    PromptTemplate,
)
from llama_index.core.prompts.default_prompt_selectors import (
    DEFAULT_REFINE_PROMPT_SEL,
    DEFAULT_TEXT_QA_PROMPT_SEL,
    DEFAULT_TREE_SUMMARIZE_PROMPT_SEL,
)
from llama_index.core.prompts.default_prompts import DEFAULT_SIMPLE_INPUT_PROMPT
from llama_index.core.response_synthesizers import (
    BaseSynthesizer,
)

# from llama_index.core.response_synthesizers.type import ResponseMode
from llama_index.core.service_context import ServiceContext
from llama_index.core.service_context_elements.llm_predictor import LLMPredictorType
from llama_index.core.settings import (
    Settings,
    callback_manager_from_settings_or_context,
    llm_from_settings_or_context,
)
from llama_index.core.types import BasePydanticProgram
from pai_rag.integrations.synthesizer.pai_synthesizer import PaiSynthesizer
from pai_rag.modules.base.configurable_module import ConfigurableModule
from pai_rag.modules.base.module_constants import MODULE_PARAM_CONFIG
from pai_rag.utils.prompt_template import (
    DEFAULT_TEXT_QA_PROMPT_TMPL,
)


logger = logging.getLogger(__name__)


class SynthesizerModule(ConfigurableModule):
    @staticmethod
    def get_dependencies() -> List[str]:
        return ["LlmModule", "MultiModalLlmModule"]

    def _create_new_instance(self, new_params: Dict[str, Any]):
        config = new_params[MODULE_PARAM_CONFIG]
        llm = new_params["LlmModule"]
        multimodal_llm = new_params["MultiModalLlmModule"]

        text_qa_template_str = config.get(
            "text_qa_template", DEFAULT_TEXT_QA_PROMPT_TMPL
        )
        text_qa_template = None
        if text_qa_template_str:
            text_qa_template = PromptTemplate(text_qa_template_str)

        return self._create_response_synthesizer(
            config=config,
            llm=llm,
            multimodal_llm=multimodal_llm,
            text_qa_template=text_qa_template,
        )

    def _create_response_synthesizer(
        self,
        config,
        llm: Optional[LLMPredictorType] = None,
        multimodal_llm: Any = None,
        prompt_helper: Optional[PromptHelper] = None,
        service_context: Optional[ServiceContext] = None,
        text_qa_template: Optional[BasePromptTemplate] = None,
        refine_template: Optional[BasePromptTemplate] = None,
        summary_template: Optional[BasePromptTemplate] = None,
        simple_template: Optional[BasePromptTemplate] = None,
        callback_manager: Optional[CallbackManager] = None,
        use_async: bool = False,
        streaming: bool = False,
        structured_answer_filtering: bool = False,
        output_cls: Optional[BaseModel] = None,
        program_factory: Optional[
            Callable[[PromptTemplate], BasePydanticProgram]
        ] = None,
        verbose: bool = False,
    ) -> BaseSynthesizer:
        """Get a response synthesizer."""
        text_qa_template = text_qa_template or DEFAULT_TEXT_QA_PROMPT_SEL
        refine_template = refine_template or DEFAULT_REFINE_PROMPT_SEL
        simple_template = simple_template or DEFAULT_SIMPLE_INPUT_PROMPT
        summary_template = summary_template or DEFAULT_TREE_SUMMARIZE_PROMPT_SEL

        callback_manager = (
            callback_manager
            or callback_manager_from_settings_or_context(Settings, service_context)
        )
        llm = llm or llm_from_settings_or_context(Settings, service_context)

        if service_context is not None:
            prompt_helper = service_context.prompt_helper
        else:
            prompt_helper = (
                prompt_helper
                or Settings._prompt_helper
                or PromptHelper.from_llm_metadata(
                    llm.metadata,
                )
            )

        return PaiSynthesizer(
            llm=llm,
            callback_manager=callback_manager,
            prompt_helper=prompt_helper,
            text_qa_template=text_qa_template,
            streaming=streaming,
            multimodal_llm=multimodal_llm,
            multimodal_qa_template=None,  # Customize qa template
        )
