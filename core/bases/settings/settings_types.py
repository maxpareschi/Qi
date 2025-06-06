# core/bases/settings_types.py

from __future__ import annotations

from typing import Annotated, TypeAlias, TypeVar, overload

T = TypeVar("T")

Vector2: TypeAlias = tuple[float, float]
Vector3: TypeAlias = tuple[float, float, float]
Vector4: TypeAlias = tuple[float, float, float, float]

Color: TypeAlias = tuple[int, int, int]
ColorAlpha: TypeAlias = tuple[int, int, int, int]
ColorFloat: TypeAlias = tuple[float, float, float]
ColorFloatAlpha: TypeAlias = tuple[float, float, float, float]

Choices: TypeAlias = list[T]


# 1) Exactly a Python list (mutable) of some T -> allow multi_select, choices, title, description
@overload
def Meta(
    __base: list[T],
    *,
    multi_select: bool,
    choices: list[T],
    title: str = ...,
    description: str = ...,
) -> Annotated[
    list[T],
    {"multi_select": bool, "choices": list[T], "title": str, "description": str},
]: ...


@overload
def Meta(
    __base: list[T],
    *,
    title: str = ...,
    description: str = ...,
) -> Annotated[
    list[T],
    {"title": str, "description": str},
]: ...


# 2) Exactly a fixed-length tuple of floats (tuple[float, ...]) -> allow vector_length, title, description
@overload
def Meta(
    __base: tuple[float, ...],
    *,
    vector_length: int,
    title: str = ...,
    description: str = ...,
) -> Annotated[
    tuple[float, ...],
    {"vector_length": int, "title": str, "description": str},
]: ...


@overload
def Meta(
    __base: tuple[float, ...],
    *,
    title: str = ...,
    description: str = ...,
) -> Annotated[
    tuple[float, ...],
    {"title": str, "description": str},
]: ...


# 3) A plain string with a finite set of choices -> single-choice enum
@overload
def Meta(
    __base: str,
    *,
    choices: list[str],
    title: str = ...,
    description: str = ...,
) -> Annotated[
    str,
    {"choices": list[str], "title": str, "description": str},
]: ...


@overload
def Meta(
    __base: str,
    *,
    title: str = ...,
    description: str = ...,
) -> Annotated[
    str,
    {"title": str, "description": str},
]: ...


# 4) A plain int with a finite set of choices -> integer-enum
@overload
def Meta(
    __base: int,
    *,
    choices: list[int],
    title: str = ...,
    description: str = ...,
) -> Annotated[
    int,
    {"choices": list[int], "title": str, "description": str},
]: ...


@overload
def Meta(
    __base: int,
    *,
    title: str = ...,
    description: str = ...,
) -> Annotated[
    int,
    {"title": str, "description": str},
]: ...


# 5) A plain float with a finite set of choices -> float-enum
@overload
def Meta(
    __base: float,
    *,
    choices: list[float],
    title: str = ...,
    description: str = ...,
) -> Annotated[
    float,
    {"choices": list[float], "title": str, "description": str},
]: ...


@overload
def Meta(
    __base: float,
    *,
    title: str = ...,
    description: str = ...,
) -> Annotated[
    float,
    {"title": str, "description": str},
]: ...


# 6) A boolean leaf -> only title/description
@overload
def Meta(
    __base: bool,
    *,
    title: str = ...,
    description: str = ...,
) -> Annotated[
    bool,
    {"title": str, "description": str},
]: ...


# 7) Fallback: any other base -> only title/description
@overload
def Meta(
    __base: T,
    *,
    title: str = ...,
    description: str = ...,
) -> Annotated[
    T,
    {"title": str, "description": str},
]: ...


def Meta(__base, **kwargs):
    """
    Runtime: simply wrap base in Annotated[..., metadata].
    Type-checkers pick the correct overload above.
    """
    return Annotated[__base, kwargs]
