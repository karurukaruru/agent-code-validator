"""Tiny demonstration project for ACV."""


def divide(total: float, count: int) -> float:
    return total / count


def average(values: list[float]) -> float:
    return divide(sum(values), len(values))

