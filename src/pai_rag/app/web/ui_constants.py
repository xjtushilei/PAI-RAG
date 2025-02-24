from pai_rag.integrations.synthesizer.pai_synthesizer import (
    DEFAULT_MULTI_MODAL_IMAGE_QA_PROMPT_TMPL,
)

DEFAULT_MULTI_MODAL_IMAGE_QA_PROMPT_TMPL = DEFAULT_MULTI_MODAL_IMAGE_QA_PROMPT_TMPL

NL2SQL_GENERAL_PROMPTS = "给定一个输入问题，创建一个语法正确的{dialect}查询语句来执行。要求：\n----------\n1.只根据问题查询几个相关的列。\n2.请注意只使用提供的数据库结构信息db_schema以及可能历史查询db_history中看到的列名，不要查询不存在的列。\n3.请注意哪个列位于哪个表中，必要时请使用表名限定列名。\n4.如果问题中包含了SQL语句，请提取并基于提供的db_schema和db_history校验优化。\n----------\n用户问题: {query_str} \n数据表结构信息和数据样例: {db_schema} \n历史查询: {db_history} \n\n你必须使用以下格式，每项占一行：\nQuestion: Question here \nSQLQuery: SQL Query (end with ;) to run"
DA_SQL_PROMPTS = "给定一个输入问题，其中包含了需要执行的SQL语句，请提取问题中的SQL语句，并使用{schema}进行校验优化，生成符合相应语法{dialect}和schema的SQL语句。\n-----------\n 你必须使用以下格式，每项占一行：\n\n Question: Question here\n SQLQuery: SQL Query to run \n\n Only use tables listed below.\n {schema}\n\n Question: {query_str} \n SQLQuery: "
SYN_GENERAL_PROMPTS = "给定一个输入问题，根据查询代码指令以及查询结果生成最终回复。要求：\n----------\n1.生成的回复语言需要与输入问题的语言保持一致。\n2.生成的回复需要关注数据表信息描述中可能存在的字段单位或其他补充信息。\n----------\n输入问题: {query_str} \n数据表信息描述: {db_schema} \nSQL 或 Python 查询代码指令（可选）: {query_code_instruction}\n查询结果: {query_output}\n\n最终回复: "


# WELCOME_MESSAGE = """
#             # \N{fire} Chatbot with RAG on PAI !
#             ### \N{rocket} Build your own personalized knowledge base question-answering chatbot.

#             #### \N{fire} Platform: [PAI](https://help.aliyun.com/zh/pai)  /  [PAI-EAS](https://www.aliyun.com/product/bigdata/learn/eas)  / [PAI-DSW](https://pai.console.aliyun.com/notebook) &emsp;  \N{rocket} Supported VectorStores:  [Milvus](https://www.aliyun.com/product/bigdata/emapreduce/milvus) / [Hologres](https://www.aliyun.com/product/bigdata/hologram)  /  [ElasticSearch](https://www.aliyun.com/product/bigdata/elasticsearch)  /  [AnalyticDB](https://www.aliyun.com/product/apsaradb/gpdb)  /  [FAISS](https://python.langchain.com/docs/integrations/vectorstores/faiss) / [OpenSearch](https://help.aliyun.com/zh/open-search/vector-search-edition/product-overview/)

#             #### \N{fire} <a href='/docs'>API Docs</a> &emsp; \N{rocket} \N{fire}  欢迎加入【PAI】RAG答疑群 27370042974
#             """

WELCOME_MESSAGE = """
            # \N{fire} PAI-RAG Dashboard

            #### \N{rocket} Join the DingTalk Q&A Group: 27370042974
            """

DEFAULT_CSS_STYPE = """
        h1, h3, h4 {
            text-align: center;
            display:block;
        }
        """

DEFAULT_EMBED_SIZE = 1024

DEFAULT_HF_EMBED_MODEL = "bge-m3"


EMBEDDING_MODEL_DEPRECATED = [
    "bge-small-zh-v1.5",
    "SGPT-125M-weightedmean-nli-bitfit",
    "text2vec-large-chinese",
    "paraphrase-multilingual-MiniLM-L12-v2",
]

EMBEDDING_MODEL_LIST = [
    "bge-m3",
    "bge-large-zh-v1.5",
    "Chuxin-Embedding",
    "bge-large-en-v1.5",
    "gte-large-en-v1.5",
    "multilingual-e5-large-instruct",
]

EMBEDDING_DIM_DICT = {
    "bge-large-zh-v1.5": 1024,
    "Chuxin-Embedding": 1024,
    "bge-large-en-v1.5": 1024,
    "gte-large-en-v1.5": 1024,
    "bge-m3": 1024,
    "multilingual-e5-large-instruct": 1024,
    "bge-small-zh-v1.5": 512,
    "SGPT-125M-weightedmean-nli-bitfit": 768,
    "text2vec-large-chinese": 1024,
    "paraphrase-multilingual-MiniLM-L12-v2": 384,
}

EMBEDDING_TYPE_DICT = {
    "bge-large-zh-v1.5": "Chinese",
    "Chuxin-Embedding": "Chinese",
    "bge-large-en-v1.5": "English",
    "gte-large-en-v1.5": "English",
    "bge-m3": "Multilingual",
    "multilingual-e5-large-instruct": "Multilingual",
    "bge-small-zh-v1.5": "Chinese",
    "SGPT-125M-weightedmean-nli-bitfit": "Multilingual",
    "text2vec-large-chinese": "Chinese",
    "paraphrase-multilingual-MiniLM-L12-v2": "Multilingual",
}

EMBEDDING_MODEL_LINK_DICT = {
    "bge-large-zh-v1.5": "https://huggingface.co/BAAI/bge-large-zh-v1.5",
    "Chuxin-Embedding": "https://huggingface.co/chuxin-llm/Chuxin-Embedding",
    "bge-large-en-v1.5": "https://huggingface.co/BAAI/bge-large-en-v1.5",
    "gte-large-en-v1.5": "https://huggingface.co/Alibaba-NLP/gte-large-en-v1.5",
    "bge-m3": "https://huggingface.co/BAAI/bge-m3",
    "multilingual-e5-large-instruct": "https://huggingface.co/intfloat/multilingual-e5-large-instruct",
    "bge-small-zh-v1.5": "https://huggingface.co/BAAI/bge-small-zh-v1.5",
    "SGPT-125M-weightedmean-nli-bitfit": "https://huggingface.co/Muennighoff/SGPT-125M-weightedmean-nli-bitfit",
    "text2vec-large-chinese": "https://huggingface.co/GanymedeNil/text2vec-large-chinese",
    "paraphrase-multilingual-MiniLM-L12-v2": "https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
}

EMBEDDING_API_KEY_DICT = {"huggingface": False, "dashscope": True}

LLM_MODEL_KEY_DICT = {
    "dashscope": [
        "qwen-turbo",
        "qwen-plus",
        "qwen-max",
        "qwen-max-1201",
        "qwen-max-longcontext",
    ],
    "openai": [
        "gpt-3.5-turbo",
        "gpt-4-turbo",
    ],
}

MLLM_MODEL_KEY_DICT = {
    "dashscope": [
        "qwen-vl-max",
        "qwen-vl-plus",
    ]
}

EMPTY_KNOWLEDGEBASE_MESSAGE = "We couldn't find any documents related to your question: {query_str}. \n\n You may try lowering the similarity_threshold or uploading relevant knowledge files."
