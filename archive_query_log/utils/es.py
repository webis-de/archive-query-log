from datetime import datetime, date, time
from enum import Enum, IntEnum, StrEnum
from pathlib import Path
from types import UnionType
from typing import (
    Literal,
    Annotated,
    Any,
    Sequence,
    Optional,
    Union,
    get_args,
    get_origin,
    Self,
    Callable,
)
from uuid import UUID
from warnings import warn

from elasticsearch_dsl import (
    Document,
    Keyword,
    Date,
    InnerDoc,
    Object,
    Index,
    Integer,
    Nested,
    Long,
    Boolean,
    Mapping,
    Field,
    Ip,
    Double,
    Text,
)
from elasticsearch_dsl.document import IndexMeta, DocumentOptions, DocumentMeta
from elasticsearch_dsl.utils import HitMeta, AttrDict, META_FIELDS, DOC_META_FIELDS
from pydantic import BaseModel, AnyUrl, EmailStr, IPvAnyAddress, PrivateAttr
from pydantic._internal._model_construction import ModelMetaclass
from pydantic_core import Url


_primitive_fields: dict[Any, Callable[[], Field]] = {
    # Pydantic types
    Url: Keyword,
    AnyUrl: Keyword,
    EmailStr: Keyword,
    IPvAnyAddress: Ip,
    # Python enum types
    IntEnum: Integer,
    StrEnum: Keyword,
    Enum: Keyword,
    # Python date types
    datetime: Date,
    date: Date,
    time: Date,
    # Other Python types
    UUID: Keyword,
    Path: Keyword,
    # Python primitive types
    bool: Boolean,
    int: Long,
    float: Double,
    str: Text,
}


def _get_type_hint_field(
    annotation: Any,
    metadata: Sequence[Any] = tuple(),
) -> Field | None:
    # Map back `Annotated` types.
    if len(metadata) > 0:
        return _get_type_hint_field(Annotated[annotation, *metadata])

    # Object field type.
    if isinstance(annotation, type) and issubclass(annotation, InnerDoc):
        return Object(annotation)

    origin = get_origin(annotation)
    args: Sequence[Any] = get_args(annotation)

    # Handle `Literals` as keywords.
    if origin is Literal:
        return Keyword()

    # Handle `Optional` type by unwrapping it.
    if origin is Optional:
        if len(args) != 1:
            raise ValueError(
                f"Expected a single argument for Optional, got {len(args)}."
            )
        return _get_type_hint_field(args[0])

    # Handle `Annotated` type by `Field` annotation or else by unwrapping it.
    if origin == Annotated:
        if len(args) < 2:
            raise ValueError(
                f"Expected at least two arguments for Annotated, got {len(args)}."
            )

        first_field = _get_type_hint_field(args[0])
        fields = [arg for arg in args[1:] if isinstance(arg, Field)]
        if first_field is not None:
            fields = [first_field] + fields
        if len(fields) > 0:
            return fields[-1]

    # Handle `Union` type by common `Field` (if unanimous).
    if origin is Union or origin is UnionType:
        # Remove `None`'s from the `Union`.
        args = [arg for arg in args if arg is not type(None)]

        # Get the field metadata for each argument.
        fields = [_get_type_hint_field(arg) for arg in args]

        # Remove empty field metadata.
        fields = [field for field in fields if field is not None]

        if len(fields) <= 0:
            return None
        elif len(fields) == 1:
            return fields[0]
        else:
            first_field = fields[0]
            if any(field != first_field for field in fields[1:]):
                raise ValueError("Union fields must be of the same type.")
            return first_field

    # Iterable types (e.g., list)
    if hasattr(origin, "__iter__"):
        if len(args) <= 0:
            return None
        if len(args) != 1:
            raise ValueError(
                f"Expected a single argument for Iterable, got {len(args)}."
            )
        if isinstance(args[0], type) and InnerDoc in args[0].mro():
            return Nested(args[0])

        return _get_type_hint_field(args[0])

    if len(args) == 0:
        for primitive, factory in _primitive_fields.items():
            if annotation == primitive:
                return factory()
            elif isinstance(primitive, type) and isinstance(annotation, type):
                if issubclass(annotation, primitive):
                    return factory()

    return None


class _ModelDocumentMeta(ModelMetaclass, DocumentMeta):
    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        **kwds: Any,
    ) -> type:
        # Build document options and mapping.
        doc_options = DocumentOptions(name, bases, namespace)
        mapping: Mapping = doc_options.mapping

        # Register mapping fields based on `Field` defaults (i.e., to be backwards-compatible with elasticsearch-dsl).
        for key, value in namespace.items():
            if isinstance(value, Field):
                mapping.field(key, value)

        # Create new document class.
        new_cls: type[BaseInnerDocument] = super().__new__(
            mcs=cls,
            cls_name=name,
            bases=bases,
            namespace=namespace,
            **kwds,
        )

        # Register mappings based on type hints.
        for key, field_info in new_cls.model_fields.items():
            field = _get_type_hint_field(field_info.annotation, field_info.metadata)
            if field is not None:
                mapping.field(key, field)

        # Warn about missing Elasticsearch field types.
        for key, field_info in new_cls.model_fields.items():
            if mapping.resolve_field(key) is None:
                mro = cls.mro(cls)  # type: ignore
                warn(
                    message=f"Field '{key}' of class '{name}' has no Elasticsearch field type configured.",
                    stacklevel=2 + mro.index(_ModelDocumentMeta),
                )

        # Assign document type to the new class.
        new_cls._doc_type = doc_options

        return new_cls


class _ModelIndexMeta(_ModelDocumentMeta, IndexMeta):
    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        **kwds: Any,
    ) -> type:
        # Build index options.
        index_opts = namespace.pop("Index", None)
        index: Index = cls.construct_index(index_opts, bases)

        # Create new document class.
        new_cls: type[BaseDocument] = super().__new__(
            cls, name, bases, namespace, **kwds
        )  # type: ignore

        # Associate index with document class (but not the base class).
        # TODO: if name != BaseDocument.__name__:
        new_cls._index = index
        index.document(new_cls)

        return new_cls


class BaseInnerDocument(
    BaseModel,
    InnerDoc,
    metaclass=_ModelDocumentMeta,
    validate_assignment=True,
):
    _meta: Annotated[AttrDict | None, PrivateAttr()] = None
    _doc_type: Annotated[DocumentOptions | None, PrivateAttr()] = None

    def __init__(
        self,
        /,
        meta: dict[str, Any] | None = None,
        **data: Any,
    ) -> None:
        if meta is None:
            meta = {}

        # Extract meta fields from data.
        for key in data.keys():
            if key.startswith("_") and key[1:] in META_FIELDS:
                meta[key] = data.pop(key)

        # Initialize the document.
        super().__init__(**data)

        # Update meta information.
        self._meta = HitMeta(meta)

    @property
    def meta(self) -> AttrDict:
        if self._meta is None:
            raise RuntimeError("Meta information is not set.")
        return self._meta

    @classmethod
    def from_es(cls, data: dict[str, Any], data_only: bool = False) -> Self:
        if data_only:
            data = {"_source": data}
        meta = data.copy()
        return cls(
            meta=meta,
            **meta.pop("_source", {}),
        )

    def to_dict(self, skip_empty: bool = True) -> dict[str, Any]:
        return self.model_dump(
            mode="json",
            exclude_unset=skip_empty,
        )


class BaseDocument(
    BaseModel,
    Document,
    metaclass=_ModelIndexMeta,
    validate_assignment=True,
):
    _meta: Annotated[HitMeta | None, PrivateAttr()] = None
    _index: Annotated[Index | None, PrivateAttr()] = None

    def __init__(
        self,
        /,
        id: str | None = None,
        meta: dict[str, Any] | None = None,
        **data: Any,
    ) -> None:
        if meta is None:
            meta = {}

        # Extract meta fields from data.
        for key in data.keys():
            if key.startswith("_") and key[1:] in META_FIELDS:
                meta[key] = data.pop(key)

        # Initialize the document.
        super().__init__(**data)

        # Set document ID.
        if id is not None:
            meta["_id"] = id

        # Update meta information.
        self._meta = HitMeta(meta)

    @property
    def meta(self) -> HitMeta:
        if self._meta is None:
            raise RuntimeError("Meta information is not set.")
        return self._meta

    @classmethod
    def from_es(cls, hit: dict[str, Any]) -> Self:
        meta = hit.copy()
        return cls(
            meta=meta,
            id=meta.pop("_id", None),
            **meta.pop("_source", {}),
        )

    def to_dict(
        self,
        include_meta: bool = False,
        skip_empty: bool = True,
    ) -> dict[str, Any]:
        doc = self.model_dump(
            mode="json",
            exclude_unset=skip_empty,
        )
        if not include_meta:
            return doc

        meta = {
            f"_{key}": self.meta[key] for key in DOC_META_FIELDS if key in self.meta
        }

        index = self._get_index(required=False)
        if index is not None:
            meta["_index"] = index

        meta["_source"] = doc

        return meta

    def create_action(self) -> dict:
        return self.to_dict(include_meta=True)

    def update_action(
        self,
        retry_on_conflict: int | None = 3,
        **fields,
    ) -> dict:
        updated = self.model_copy(update=fields)
        doc = updated.model_dump(
            mode="json",
            include={key for key, _ in fields.items()},
            exclude={"meta"},
            exclude_unset=True,
        )

        action = {
            f"_{key}": self.meta[key]
            for key in META_FIELDS.difference({"score"})
            if key in self.meta
        }
        action["_op_type"] = "update"
        if retry_on_conflict is not None:
            action["_retry_on_conflict"] = retry_on_conflict
        action["doc"] = doc
        return action

    def delete_action(self) -> dict:
        action = {
            f"_{key}": self.meta[key]
            for key in META_FIELDS.difference({"score", "source"})
            if key in self.meta
        }
        action["_op_type"] = "delete"
        return action

    @property
    def id(self) -> UUID:
        return UUID(self.meta.id)

    @id.setter
    def id(self, value: UUID) -> None:
        self.meta.id = str(value)
