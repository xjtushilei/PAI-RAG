from loguru import logger
import re
from typing import Any, List, NamedTuple, Optional, Type, Union
from urllib.parse import quote_plus

import asyncpg  # noqa
import pgvector  # noqa
import psycopg2  # noqa
import sqlalchemy
import sqlalchemy.ext.asyncio
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.schema import BaseNode, MetadataMode, TextNode
from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    FilterOperator,
    MetadataFilters,
    MetadataFilter,
    VectorStoreQuery,
    VectorStoreQueryMode,
    VectorStoreQueryResult,
)
from llama_index.core.vector_stores.utils import (
    metadata_dict_to_node,
    node_to_metadata_dict,
)


class DBEmbeddingRow(NamedTuple):
    node_id: str  # FIXME: verify this type hint
    text: str
    metadata: dict
    similarity: float


def get_data_model(
    base: Type,
    index_name: str,
    schema_name: str,
    hybrid_search: bool,
    text_search_config: str,
    cache_okay: bool,
    embed_dim: int = 1536,
    use_jsonb: bool = False,
) -> Any:
    """
    This part create a dynamic sqlalchemy model with a new table.
    """
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import Column, Computed
    from sqlalchemy.dialects.postgresql import BIGINT, JSON, JSONB, TSVECTOR, VARCHAR
    from sqlalchemy.schema import Index
    from sqlalchemy.types import TypeDecorator

    class TSVector(TypeDecorator):
        impl = TSVECTOR
        cache_ok = cache_okay

    tablename = "data_%s" % index_name  # dynamic table name
    class_name = "Data%s" % index_name  # dynamic class name
    indexname = "%s_idx" % index_name  # dynamic class name

    metadata_dtype = JSONB if use_jsonb else JSON

    if hybrid_search:

        class HybridAbstractData(base):  # type: ignore
            __abstract__ = True  # this line is necessary
            id = Column(BIGINT, primary_key=True, autoincrement=True)
            text = Column(VARCHAR, nullable=False)
            metadata_ = Column(metadata_dtype)
            node_id = Column(VARCHAR, unique=True)
            embedding = Column(Vector(embed_dim))  # type: ignore
            text_search_tsv = Column(  # type: ignore
                TSVector(),
                Computed(
                    "to_tsvector('%s', text)" % text_search_config, persisted=True
                ),
            )

        model = type(
            class_name,
            (HybridAbstractData,),
            {"__tablename__": tablename, "__table_args__": {"schema": schema_name}},
        )

        Index(
            indexname,
            model.text_search_tsv,  # type: ignore
            postgresql_using="gin",
        )
    else:

        class AbstractData(base):  # type: ignore
            __abstract__ = True  # this line is necessary
            id = Column(BIGINT, primary_key=True, autoincrement=True)
            text = Column(VARCHAR, nullable=False)
            metadata_ = Column(metadata_dtype)
            node_id = Column(VARCHAR, unique=True)
            embedding = Column(Vector(embed_dim))  # type: ignore

        model = type(
            class_name,
            (AbstractData,),
            {"__tablename__": tablename, "__table_args__": {"schema": schema_name}},
        )

    """
    Using hnsw index, it has better query performance than IVFFlat.
    postgresql_with m - the max number of connections per layer (16 by default)
    postgresql_with ef_construction - the size of the dynamic candidate list for constructing the graph (64 by default)
    reference: https://github.com/pgvector/pgvector
    """
    Index(
        tablename + "_embedding",
        model.embedding,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": "16", "ef_construction": "64"},
    )
    return model


class PGVectorStore(BasePydanticVectorStore):
    """Postgres Vector Store.

    Examples:
        `pip install llama-index-vector-stores-postgres`

        ```python
        from llama_index.vector_stores.postgres import PGVectorStore

        # Create PGVectorStore instance
        vector_store = PGVectorStore.from_params(
            database="vector_db",
            host="localhost",
            password="password",
            port=5432,
            user="postgres",
            table_name="paul_graham_essay",
            embed_dim=1536,  # openai embedding dimension,
            hybrid_search=True,  # if using VectorStoreQueryMode.HYBRID
            text_search_config='jiebacfg' # postgresql extension pg_jieba
        )
        ```
    """

    from sqlalchemy.sql.selectable import Select

    stores_text = True
    flat_metadata = False

    connection_string: str
    async_connection_string: Union[str, sqlalchemy.engine.URL]
    table_name: str
    schema_name: str
    embed_dim: int
    hybrid_search: bool
    text_search_config: str
    cache_ok: bool
    perform_setup: bool
    debug: bool
    use_jsonb: bool

    _base: Any = PrivateAttr()
    _table_class: Any = PrivateAttr()
    _engine: Any = PrivateAttr()
    _session: Any = PrivateAttr()
    _async_engine: Any = PrivateAttr()
    _async_session: Any = PrivateAttr()
    _is_initialized: bool = PrivateAttr(default=False)
    _is_extension_load: bool = PrivateAttr(default=False)
    _is_async_extension_load: bool = PrivateAttr(default=False)

    def __init__(
        self,
        connection_string: Union[str, sqlalchemy.engine.URL],
        async_connection_string: Union[str, sqlalchemy.engine.URL],
        table_name: str,
        schema_name: str,
        hybrid_search: bool = False,
        text_search_config: str = "english",
        embed_dim: int = 1536,
        cache_ok: bool = False,
        perform_setup: bool = True,
        debug: bool = False,
        use_jsonb: bool = False,
    ) -> None:
        table_name = table_name.lower()
        schema_name = schema_name.lower()

        if hybrid_search and text_search_config is None:
            raise ValueError(
                "Sparse vector index creation requires "
                "a text search configuration specification."
            )

        from sqlalchemy.orm import declarative_base

        # sqlalchemy model
        self._base = declarative_base()
        self._table_class = get_data_model(
            self._base,
            table_name,
            schema_name,
            hybrid_search,
            text_search_config,
            cache_ok,
            embed_dim=embed_dim,
            use_jsonb=use_jsonb,
        )

        super().__init__(
            connection_string=connection_string,
            async_connection_string=async_connection_string,
            table_name=table_name,
            schema_name=schema_name,
            hybrid_search=hybrid_search,
            text_search_config=text_search_config,
            embed_dim=embed_dim,
            cache_ok=cache_ok,
            perform_setup=perform_setup,
            debug=debug,
            use_jsonb=use_jsonb,
        )

    async def close(self) -> None:
        if not self._is_initialized:
            return

        self._session.close_all()
        self._engine.dispose()

        await self._async_engine.dispose()

    @classmethod
    def class_name(cls) -> str:
        return "PGVectorStore"

    @classmethod
    def from_params(
        cls,
        host: Optional[str] = None,
        port: Optional[str] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        table_name: str = "llamaindex",
        schema_name: str = "public",
        connection_string: Optional[Union[str, sqlalchemy.engine.URL]] = None,
        async_connection_string: Optional[Union[str, sqlalchemy.engine.URL]] = None,
        hybrid_search: bool = False,
        text_search_config: str = "english",
        embed_dim: int = 1536,
        cache_ok: bool = False,
        perform_setup: bool = True,
        debug: bool = False,
        use_jsonb: bool = False,
    ) -> "PGVectorStore":
        """Return connection string from database parameters."""
        conn_str = (
            connection_string
            or f"postgresql+psycopg2://{user}:{quote_plus(password)}@{host}:{port}/{database}"
        )
        async_conn_str = async_connection_string or (
            f"postgresql+asyncpg://{user}:{quote_plus(password)}@{host}:{port}/{database}"
        )
        return cls(
            connection_string=conn_str,
            async_connection_string=async_conn_str,
            table_name=table_name,
            schema_name=schema_name,
            hybrid_search=hybrid_search,
            text_search_config=text_search_config,
            embed_dim=embed_dim,
            cache_ok=cache_ok,
            perform_setup=perform_setup,
            debug=debug,
            use_jsonb=use_jsonb,
        )

    @property
    def client(self) -> Any:
        if not self._is_initialized:
            return None
        return self._engine

    def _connect(self) -> Any:
        from sqlalchemy import create_engine
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        self._engine = create_engine(self.connection_string, echo=self.debug)
        self._session = sessionmaker(self._engine)

        self._async_engine = create_async_engine(self.async_connection_string)
        self._async_session = sessionmaker(self._async_engine, class_=AsyncSession)  # type: ignore

    def _create_schema_if_not_exists(self) -> None:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", self.schema_name):
            raise ValueError(f"Invalid schema_name: {self.schema_name}")
        with self._session() as session, session.begin():
            # Check if the specified schema exists with "CREATE" statement
            check_schema_statement = sqlalchemy.text(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema_name"
            ).bindparams(schema_name=self.schema_name)
            result = session.execute(check_schema_statement).fetchone()

            # If the schema does not exist, then create it
            if not result:
                create_schema_statement = sqlalchemy.text(
                    # DDL won't tolerate quoted string literal here for schema_name,
                    # so use a format string to embed the schema_name directly, instead of a param.
                    f"CREATE SCHEMA IF NOT EXISTS {self.schema_name}"
                )
                session.execute(create_schema_statement)

            session.commit()

    def _create_tables_if_not_exists(self) -> None:
        with self._session() as session, session.begin():
            self._base.metadata.create_all(session.connection())

    def _create_extension(self) -> None:
        import sqlalchemy

        with self._session() as session, session.begin():
            statement = sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS vector")
            session.execute(statement)
            try:
                statement = sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS pg_jieba")
                session.execute(statement)
            except Exception:
                logger.warning("create extension pg_jieba failed")
            session.commit()

    def _initialize(self) -> None:
        if not self._is_initialized:
            self._connect()
            if self.perform_setup:
                self._create_extension()
                self._create_schema_if_not_exists()
                self._create_tables_if_not_exists()
            self._is_initialized = True

    def _extension_load(self) -> None:
        if not self._is_extension_load:
            try:
                with self._session() as session, session.begin():
                    res = session.execute(
                        sqlalchemy.text("show shared_preload_libraries")
                    )
                    result = res.all()
                    if "pg_jieba" in result[0][0]:
                        session.execute(
                            sqlalchemy.text("SELECT jieba_load_user_dict(0,0)")
                        )
                        logger.info("session load jieba_load_user_dict success!")
                    session.commit()
            except Exception as e:
                logger.warning(e)
            self._is_extension_load = True
            logger.info("load extension done!")

    async def _async_extension_load(self) -> None:
        if not self._is_async_extension_load:
            try:
                async with self._async_session() as async_session, async_session.begin():
                    res = await async_session.execute(
                        sqlalchemy.text("show shared_preload_libraries")
                    )
                    result = res.all()
                    if "pg_jieba" in result[0][0]:
                        await async_session.execute(
                            sqlalchemy.text("SELECT jieba_load_user_dict(0,0)")
                        )
                        logger.info("async_session load jieba_load_user_dict success!")
            except Exception as e:
                logger.warning(e)
            self._is_async_extension_load = True
            logger.info("async load extension done!")

    def _node_to_table_row(self, node: BaseNode) -> Any:
        return self._table_class(
            node_id=node.node_id,
            embedding=node.get_embedding(),
            text=node.get_content(metadata_mode=MetadataMode.NONE),
            metadata_=node_to_metadata_dict(
                node,
                remove_text=True,
                flat_metadata=self.flat_metadata,
            ),
        )

    def add(self, nodes: List[BaseNode], **add_kwargs: Any) -> List[str]:
        self._initialize()
        ids = []
        with self._session() as session, session.begin():
            from sqlalchemy import delete

            for node in nodes:
                stmt = delete(self._table_class).where(
                    self._table_class.node_id == node.node_id
                )
                session.execute(stmt)
                ids.append(node.node_id)
                item = self._node_to_table_row(node)
                session.add(item)
            session.commit()
        return ids

    async def async_add(self, nodes: List[BaseNode], **kwargs: Any) -> List[str]:
        self._initialize()
        ids = []
        async with self._async_session() as session, session.begin():
            for node in nodes:
                ids.append(node.node_id)
                item = self._node_to_table_row(node)
                session.add(item)
            await session.commit()
        return ids

    def _to_postgres_operator(self, operator: FilterOperator) -> str:
        if operator == FilterOperator.EQ:
            return "="
        elif operator == FilterOperator.GT:
            return ">"
        elif operator == FilterOperator.LT:
            return "<"
        elif operator == FilterOperator.NE:
            return "!="
        elif operator == FilterOperator.GTE:
            return ">="
        elif operator == FilterOperator.LTE:
            return "<="
        elif operator == FilterOperator.IN:
            return "IN"
        elif operator == FilterOperator.NIN:
            return "NOT IN"
        elif operator == FilterOperator.CONTAINS:
            return "@>"
        else:
            logger.warning(f"Unknown operator: {operator}, fallback to '='")
            return "="

    def _build_filter_clause(self, filter_: MetadataFilter) -> Any:
        from sqlalchemy import text

        if filter_.operator in [FilterOperator.IN, FilterOperator.NIN]:
            # Expects a single value in the metadata, and a list to compare

            # In Python, to create a tuple with a single element, you need to include a comma after the element
            # This code will correctly format the IN clause whether there is one element or multiple elements in the list:
            filter_value = ", ".join(f"'{e}'" for e in filter_.value)

            return text(
                f"metadata_->>'{filter_.key}' "
                f"{self._to_postgres_operator(filter_.operator)} "
                f"({filter_value})"
            )
        elif filter_.operator == FilterOperator.CONTAINS:
            # Expects a list stored in the metadata, and a single value to compare
            return text(
                f"metadata_::jsonb->'{filter_.key}' "
                f"{self._to_postgres_operator(filter_.operator)} "
                f"'[\"{filter_.value}\"]'"
            )
        else:
            # Check if value is a number. If so, cast the metadata value to a float
            # This is necessary because the metadata is stored as a string
            try:
                return text(
                    f"(metadata_->>'{filter_.key}')::float "
                    f"{self._to_postgres_operator(filter_.operator)} "
                    f"{float(filter_.value)}"
                )
            except ValueError:
                # If not a number, then treat it as a string
                return text(
                    f"metadata_->>'{filter_.key}' "
                    f"{self._to_postgres_operator(filter_.operator)} "
                    f"'{filter_.value}'"
                )

    def _recursively_apply_filters(self, filters: List[MetadataFilters]) -> Any:
        """
        Returns a sqlalchemy where clause.
        """
        import sqlalchemy

        sqlalchemy_conditions = {
            "or": sqlalchemy.sql.or_,
            "and": sqlalchemy.sql.and_,
        }

        if filters.condition not in sqlalchemy_conditions:
            raise ValueError(
                f"Invalid condition: {filters.condition}. "
                f"Must be one of {list(sqlalchemy_conditions.keys())}"
            )

        return sqlalchemy_conditions[filters.condition](
            *(
                (
                    self._build_filter_clause(filter_)
                    if not isinstance(filter_, MetadataFilters)
                    else self._recursively_apply_filters(filter_)
                )
                for filter_ in filters.filters
            )
        )

    def _apply_filters_and_limit(
        self,
        stmt: Select,
        limit: int,
        metadata_filters: Optional[MetadataFilters] = None,
    ) -> Any:
        if metadata_filters:
            stmt = stmt.where(  # type: ignore
                self._recursively_apply_filters(metadata_filters)
            )
        return stmt.limit(limit)  # type: ignore

    def _build_query(
        self,
        embedding: Optional[List[float]],
        limit: int = 10,
        metadata_filters: Optional[MetadataFilters] = None,
    ) -> Any:
        from sqlalchemy import select, text

        stmt = select(  # type: ignore
            self._table_class.id,
            self._table_class.node_id,
            self._table_class.text,
            self._table_class.metadata_,
            self._table_class.embedding.cosine_distance(embedding).label("distance"),
        ).order_by(text("distance asc"))

        return self._apply_filters_and_limit(stmt, limit, metadata_filters)

    def _query_with_score(
        self,
        embedding: Optional[List[float]],
        limit: int = 10,
        metadata_filters: Optional[MetadataFilters] = None,
        **kwargs: Any,
    ) -> List[DBEmbeddingRow]:
        stmt = self._build_query(embedding, limit, metadata_filters)
        with self._session() as session, session.begin():
            from sqlalchemy import text

            if kwargs.get("ivfflat_probes"):
                ivfflat_probes = kwargs.get("ivfflat_probes")
                session.execute(
                    text("SET ivfflat.probes = :ivfflat_probes"),
                    {"ivfflat_probes": ivfflat_probes},
                )
            if kwargs.get("hnsw_ef_search"):
                hnsw_ef_search = kwargs.get("hnsw_ef_search")
                session.execute(
                    text("SET hnsw.ef_search = :hnsw_ef_search"),
                    {"hnsw_ef_search": hnsw_ef_search},
                )

            res = session.execute(
                stmt,
            )
            return [
                DBEmbeddingRow(
                    node_id=item.node_id,
                    text=item.text,
                    metadata=item.metadata_,
                    similarity=(1 - item.distance) if item.distance is not None else 0,
                )
                for item in res.all()
            ]

    async def _aquery_with_score(
        self,
        embedding: Optional[List[float]],
        limit: int = 10,
        metadata_filters: Optional[MetadataFilters] = None,
        **kwargs: Any,
    ) -> List[DBEmbeddingRow]:
        stmt = self._build_query(embedding, limit, metadata_filters)
        async with self._async_session() as async_session, async_session.begin():
            from sqlalchemy import text

            if kwargs.get("hnsw_ef_search"):
                hnsw_ef_search = kwargs.get("hnsw_ef_search")
                await async_session.execute(
                    text("SET hnsw.ef_search = :hnsw_ef_search"),
                    {"hnsw_ef_search": hnsw_ef_search},
                )
            if kwargs.get("ivfflat_probes"):
                ivfflat_probes = kwargs.get("ivfflat_probes")
                await async_session.execute(
                    text("SET ivfflat.probes = :ivfflat_probes"),
                    {"ivfflat_probes": ivfflat_probes},
                )

            res = await async_session.execute(stmt)
            return [
                DBEmbeddingRow(
                    node_id=item.node_id,
                    text=item.text,
                    metadata=item.metadata_,
                    similarity=(1 - item.distance) if item.distance is not None else 0,
                )
                for item in res.all()
            ]

    def _build_sparse_query(
        self,
        query_str: Optional[str],
        limit: int,
        metadata_filters: Optional[MetadataFilters] = None,
    ) -> Any:
        from sqlalchemy import select, type_coerce
        from sqlalchemy.sql import func, text
        from sqlalchemy.types import UserDefinedType

        class REGCONFIG(UserDefinedType):
            # The TypeDecorator.cache_ok class-level flag indicates if this custom TypeDecorator is safe to be used as part of a cache key.
            # If the TypeDecorator is not guaranteed to produce the same bind/result behavior and SQL generation every time,
            # this flag should be set to False; otherwise if the class produces the same behavior each time, it may be set to True.
            cache_ok = True

            def get_col_spec(self, **kw: Any) -> str:
                return "regconfig"

        if query_str is None:
            raise ValueError("query_str must be specified for a sparse vector query.")

        # Replace '&' with '|' to perform an OR search for higher recall
        ts_query = func.to_tsquery(
            func.replace(
                func.text(
                    func.plainto_tsquery(
                        type_coerce(self.text_search_config, REGCONFIG), query_str
                    )
                ),
                "&",
                "|",
            )
        )
        stmt = (
            select(  # type: ignore
                self._table_class.id,
                self._table_class.node_id,
                self._table_class.text,
                self._table_class.metadata_,
                func.ts_rank(self._table_class.text_search_tsv, ts_query).label("rank"),
            )
            .where(self._table_class.text_search_tsv.op("@@")(ts_query))
            .order_by(text("rank desc"))
        )

        # type: ignore
        return self._apply_filters_and_limit(stmt, limit, metadata_filters)

    async def _async_sparse_query_with_rank(
        self,
        query_str: Optional[str] = None,
        limit: int = 10,
        metadata_filters: Optional[MetadataFilters] = None,
    ) -> List[DBEmbeddingRow]:
        stmt = self._build_sparse_query(query_str, limit, metadata_filters)
        async with self._async_session() as async_session, async_session.begin():
            res = await async_session.execute(stmt)
            return [
                DBEmbeddingRow(
                    node_id=item.node_id,
                    text=item.text,
                    metadata=item.metadata_,
                    similarity=item.rank,
                )
                for item in res.all()
            ]

    def _sparse_query_with_rank(
        self,
        query_str: Optional[str] = None,
        limit: int = 10,
        metadata_filters: Optional[MetadataFilters] = None,
    ) -> List[DBEmbeddingRow]:
        stmt = self._build_sparse_query(query_str, limit, metadata_filters)
        with self._session() as session, session.begin():
            res = session.execute(stmt)
            return [
                DBEmbeddingRow(
                    node_id=item.node_id,
                    text=item.text,
                    metadata=item.metadata_,
                    similarity=item.rank,
                )
                for item in res.all()
            ]

    async def _async_hybrid_query(
        self, query: VectorStoreQuery, **kwargs: Any
    ) -> List[DBEmbeddingRow]:
        import asyncio

        if query.alpha is not None:
            logger.warning("postgres hybrid search does not support alpha parameter.")

        sparse_top_k = query.sparse_top_k or query.similarity_top_k

        results = await asyncio.gather(
            self._aquery_with_score(
                query.query_embedding,
                query.similarity_top_k,
                query.filters,
                **kwargs,
            ),
            self._async_sparse_query_with_rank(
                query.query_str, sparse_top_k, query.filters
            ),
        )

        dense_results, sparse_results = results
        all_results = dense_results + sparse_results
        return _dedup_results(all_results)

    def _hybrid_query(
        self, query: VectorStoreQuery, **kwargs: Any
    ) -> List[DBEmbeddingRow]:
        if query.alpha is not None:
            logger.warning("postgres hybrid search does not support alpha parameter.")

        sparse_top_k = query.sparse_top_k or query.similarity_top_k

        dense_results = self._query_with_score(
            query.query_embedding,
            query.similarity_top_k,
            query.filters,
            **kwargs,
        )

        sparse_results = self._sparse_query_with_rank(
            query.query_str, sparse_top_k, query.filters
        )

        all_results = dense_results + sparse_results
        return _dedup_results(all_results)

    def _db_rows_to_query_result(
        self, rows: List[DBEmbeddingRow]
    ) -> VectorStoreQueryResult:
        nodes = []
        similarities = []
        ids = []
        for db_embedding_row in rows:
            try:
                node = metadata_dict_to_node(db_embedding_row.metadata)
                node.set_content(str(db_embedding_row.text))
            except Exception:
                # NOTE: deprecated legacy logic for backward compatibility
                node = TextNode(
                    id_=db_embedding_row.node_id,
                    text=db_embedding_row.text,
                    metadata=db_embedding_row.metadata,
                )
            similarities.append(db_embedding_row.similarity)
            ids.append(db_embedding_row.node_id)
            nodes.append(node)

        return VectorStoreQueryResult(
            nodes=nodes,
            similarities=similarities,
            ids=ids,
        )

    async def aquery(
        self, query: VectorStoreQuery, **kwargs: Any
    ) -> VectorStoreQueryResult:
        self._initialize()
        await self._async_extension_load()
        if query.mode == VectorStoreQueryMode.HYBRID:
            results = await self._async_hybrid_query(query, **kwargs)
        elif query.mode in [
            VectorStoreQueryMode.SPARSE,
            VectorStoreQueryMode.TEXT_SEARCH,
        ]:
            sparse_top_k = query.sparse_top_k or query.similarity_top_k
            results = await self._async_sparse_query_with_rank(
                query.query_str, sparse_top_k, query.filters
            )
        elif query.mode == VectorStoreQueryMode.DEFAULT:
            results = await self._aquery_with_score(
                query.query_embedding,
                query.similarity_top_k,
                query.filters,
                **kwargs,
            )
        else:
            raise ValueError(f"Invalid query mode: {query.mode}")

        return self._db_rows_to_query_result(results)

    def query(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        self._initialize()
        self._extension_load()
        if query.mode == VectorStoreQueryMode.HYBRID:
            results = self._hybrid_query(query, **kwargs)
        elif query.mode in [
            VectorStoreQueryMode.SPARSE,
            VectorStoreQueryMode.TEXT_SEARCH,
        ]:
            sparse_top_k = query.sparse_top_k or query.similarity_top_k
            results = self._sparse_query_with_rank(
                query.query_str, sparse_top_k, query.filters
            )
        elif query.mode == VectorStoreQueryMode.DEFAULT:
            results = self._query_with_score(
                query.query_embedding,
                query.similarity_top_k,
                query.filters,
                **kwargs,
            )
        else:
            raise ValueError(f"Invalid query mode: {query.mode}")

        return self._db_rows_to_query_result(results)

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        from sqlalchemy import delete

        self._initialize()
        with self._session() as session, session.begin():
            stmt = delete(self._table_class).where(
                self._table_class.metadata_["doc_id"].astext == ref_doc_id
            )

            session.execute(stmt)
            session.commit()


def _dedup_results(results: List[DBEmbeddingRow]) -> List[DBEmbeddingRow]:
    seen_ids = set()
    deduped_results = []
    for result in results:
        if result.node_id not in seen_ids:
            deduped_results.append(result)
            seen_ids.add(result.node_id)
    return deduped_results
