"""Orders and the sources they come from."""

import hashlib
import random
from collections.abc import Iterable, Iterator
from typing import NamedTuple, Protocol

from highbay_sim.config import GeneratedParameters, Scenario
from highbay_sim.events import OrderType


class OrderRequest(NamedTuple):
    arrival_s: float
    order_type: OrderType
    article: str


class OrderSource(Protocol):
    def orders(self, duration_s: float) -> Iterable[OrderRequest]:
        """Yield requests in non-decreasing arrival time, each with arrival_s < duration_s."""
        ...


def stream_rng(seed: int, stream: str) -> random.Random:
    """Return a random stream that does not depend on the other streams of a run."""
    digest = hashlib.sha256(f"{seed}:{stream}".encode()).digest()
    return random.Random(int.from_bytes(digest))


class ExplicitOrders:
    def __init__(self, requests: Iterable[OrderRequest]) -> None:
        self._requests = sorted(requests, key=lambda request: request.arrival_s)

    def orders(self, duration_s: float) -> Iterator[OrderRequest]:
        return (request for request in self._requests if request.arrival_s < duration_s)


class GeneratedOrders:
    """Poisson arrivals, with independently drawn type and article."""

    def __init__(
        self,
        seed: int,
        orders_per_hour: float,
        storage_share: float,
        article_weights: dict[str, float],
    ) -> None:
        self._seed = seed
        self._orders_per_second = orders_per_hour / 3600.0
        self._storage_share = storage_share
        self._articles = sorted(article_weights)
        self._weights = [article_weights[article] for article in self._articles]

    def orders(self, duration_s: float) -> Iterator[OrderRequest]:
        if self._orders_per_second == 0:
            return
        rng = stream_rng(self._seed, "orders")
        arrival_s = rng.expovariate(self._orders_per_second)
        while arrival_s < duration_s:
            order_type: OrderType = "storage" if rng.random() < self._storage_share else "retrieval"
            article = rng.choices(self._articles, self._weights)[0]
            yield OrderRequest(arrival_s, order_type, article)
            arrival_s += rng.expovariate(self._orders_per_second)


def order_source_for(scenario: Scenario) -> OrderSource:
    if scenario.orders is not None:
        return ExplicitOrders(
            OrderRequest(order.time_s, order.type, order.article) for order in scenario.orders
        )
    parameters: GeneratedParameters | None = scenario.generated
    if parameters is None:
        raise ValueError("a scenario needs exactly one of generated or orders")
    return GeneratedOrders(
        scenario.seed,
        parameters.orders_per_hour,
        parameters.storage_share,
        parameters.article_weights,
    )
