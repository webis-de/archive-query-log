from typing import runtime_checkable, TypeVar, Protocol, Sized, Iterable

T = TypeVar("T", covariant=True)


@runtime_checkable
class SizedIterable(Sized, Iterable[T], Protocol):
    pass
