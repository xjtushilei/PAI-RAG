"""Prompts."""

from llama_index.core import PromptTemplate

DEFAULT_QUESTION_GENERATION_PROMPT = """\
    #01 你是一个问答对数据集处理专家。
    #02 你的任务是根据我给出的内容，生成适合作为问答对数据集的问题。
    #03 问题要关于文件内容，不要太长。
    #04 一句话中只有一个问题。
    #05 生成问题需要具体明确。
    #06 生成问题需要避免指代不明确，以下是需要避免的示例：这款产品、这些文献、这项研究等。
    #07 以下是我给出的内容：
    ---------------------
    {context_str}
    ---------------------
    #08 请仔细阅读给出的内容，生成适合作为问答对数据集的{num_questions_per_chunk}个问题：
    """

DEFAULT_MULTI_MODAL_QUESTION_GENERATION_PROMPT = """\
    #01 你是一个问答对数据集处理专家，擅长理解和分析多模态信息（文字和图片）。
    #02 你的任务是根据我给出的文字内容和相关图像，生成适合作为问答对数据集的问题。
    #03 问题要紧扣文件内容和图像，确保每个问题都清晰且简短。
    #04 一句话中仅包含一个问题。
    #05 生成的问题需要具体明确，能够准确反映文件内容和图像信息。
    #06 生成问题需要避免指代不明确，以下是需要避免的示例：这款产品、这些文献、这项研究等。
    #07 以下是我给出的文字内容和相关图像链接：
    ---------------------
    {context_str}
    ---------------------
    #08 请仔细阅读给出的内容和图像描述，生成适合作为问答对数据集的{num_questions_per_chunk}个问题：
    """

DEFAULT_TEXT_QA_PROMPT_TMPL = """内容信息如下
    ---------------------
    {context_str}
    ---------------------
    根据提供内容而非其他知识回答问题.
    问题: {query_str}
    答案: """


DEFAULT_QA_GENERATE_PROMPT_TMPL_ZH = """\
上下文信息如下。

---------------------
{context_str}
---------------------

给定上下文信息而不是先验知识。
仅生成基于以下查询的问题。

您是一名教师/教授。 \
您的任务是为即将到来的测验/考试设置 \
    {num_questions_per_chunk} 个问题。
整个文件中的问题本质上应该是多样化的。 \
将问题限制在所提供的上下文信息范围内。"
"""

EVALUATION_PYDANTIC_FORMAT_TMPL = """
Here's a JSON schema to follow:
{schema}

Output a valid JSON object but do not repeat the schema.
The response should be concise to keep json complete。
"""


CONDENSE_QUESTION_CHAT_ENGINE_PROMPT = PromptTemplate(
    """\
Please play the role of an intelligent search rewriting and completion robot. According to the user's chat history and the corresponding new question, please first rewrite the subject inheritance of the new question, and then complete the context information. Note: Do not change the meaning of the new question, the answer should be as concise as possible, do not directly answer the question, and do not output more content.
Example:
<Chat history>
User: What did you do this morning?
Assistant: Go play basketball

<New question>
User: Is it fun?

Answer:
Answer: Is playing basketball fun?

Now it's your turn:
<Chat history>
{chat_history}

<New question>
{question}

Please think carefully and give your answer using the same language as the <New question>:
"""
)

CONDENSE_QUESTION_CHAT_ENGINE_PROMPT_ZH = PromptTemplate(
    """\
请你扮演一个智能搜索改写补全机器人，请根据User的聊天历史以及对应的新问题，对新问题先进行主语继承改写，然后进行上下文信息补全，注意：不要改变新问题的意思，答案要尽可能简洁，不要直接回答该问题，不要输出多于的内容。
例子：
<聊天历史>
User：今天上午你干嘛了
Assistant：去打篮球啦

<新问题>
User：好玩吗？

答案：
答案：打篮球好玩吗？

现在轮到你了：
<聊天历史>
{chat_history}

<新问题>
{question}

请仔细思考后，使用和<新问题>相同的语言，给出你的答案：
"""
)


QUERY_GEN_PROMPT = (
    "You are a helpful assistant that generates multiple search queries based on a single input query. "
    "Generate {num_queries} search queries in Chinese, one on each line, related to the following input query:\n"
    "Query: {query}\n"
    "Queries:\n"
)

DEFAULT_FUSION_TRANSFORM_PROMPT = (
    "You are a helpful assistant that generates multiple search queries based on a "
    "single input query. Generate {num_queries} search queries, one on each line, "
    "related to the following input query:\n"
    "Query: {query}\n"
    "Queries:\n"
)


DEFAULT_SUMMARY_PROMPT = (
    "Summarize the provided text in Chinese, including as many key details as needed."
)

DEFAULT_MULTI_MODAL_TEXT_QA_PROMPT_TMPL = (
    "结合上面给出的图片和下面给出的参考材料来回答用户的问题。\n\n"
    "参考材料:"
    "---------------------\n\n"
    "{context_str}\n"
    "---------------------\n\n"
    "请根据给定的材料回答给出的问题，如果材料中没有找到答案，就说没有找到相关的信息，不要编造答案。\n\n"
    "---------------------\n\n"
    "问题: {query_str}\n"
    "答案: "
)

DEFAULT_MULTI_MODAL_IMAGE_QA_PROMPT_TMPL = (
    "结合上面给出的图片和下面给出的参考材料来回答用户的问题。材料中包含一组图片链接，分别对应到前面给出的图片的地址。\n\n"
    "材料:"
    "---------------------\n\n"
    "{context_str}\n"
    "---------------------\n\n"
    "请根据给定的材料回答给出的问题，回答中需要有文字描述和图片。如果材料中没有找到答案，就说没有找到相关的信息，不要编造答案。\n\n"
    "如果上面有图片对你生成答案有帮助，请找到图片链接并用markdown格式给出，如![](image_url)。\n\n"
    "---------------------\n\n"
    "问题: {query_str}\n请返回文字和展示图片，不需要标明图片顺序"
    "答案: "
)
