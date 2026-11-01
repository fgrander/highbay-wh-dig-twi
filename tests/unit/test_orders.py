from highbay_sim.orders import ExplicitOrders, GeneratedOrders, OrderRequest


def generated(
    seed: int = 7,
    orders_per_hour: float = 3600.0,
    storage_share: float = 0.5,
    article_weights: dict[str, float] | None = None,
) -> GeneratedOrders:
    return GeneratedOrders(
        seed=seed,
        orders_per_hour=orders_per_hour,
        storage_share=storage_share,
        article_weights=article_weights or {"A": 3.0, "B": 1.0},
    )


def test_explicit_orders_sort_by_time_and_keep_file_order_for_ties() -> None:
    source = ExplicitOrders(
        [
            OrderRequest(5.0, "storage", "late"),
            OrderRequest(1.0, "storage", "first"),
            OrderRequest(1.0, "retrieval", "second"),
        ]
    )
    assert [order.article for order in source.orders(10.0)] == ["first", "second", "late"]


def test_generated_arrivals_stay_in_range_and_order() -> None:
    orders = list(generated().orders(600.0))
    times = [order.arrival_s for order in orders]
    assert times == sorted(times)
    assert all(0.0 <= time_s < 600.0 for time_s in times)


def test_same_seed_gives_same_sequence() -> None:
    assert list(generated(seed=7).orders(600.0)) == list(generated(seed=7).orders(600.0))


def test_different_seed_gives_different_sequence() -> None:
    assert list(generated(seed=7).orders(600.0)) != list(generated(seed=8).orders(600.0))


def test_mean_rate_is_near_configured_rate() -> None:
    orders = list(generated(orders_per_hour=3600.0).orders(36_000.0))
    assert abs(len(orders) - 36_000) < 36_000 * 0.03


def test_storage_share_is_respected() -> None:
    orders = list(generated(storage_share=0.25).orders(36_000.0))
    share = sum(order.order_type == "storage" for order in orders) / len(orders)
    assert abs(share - 0.25) < 0.02


def test_storage_share_limits() -> None:
    assert all(o.order_type == "storage" for o in generated(storage_share=1.0).orders(600.0))
    assert all(o.order_type == "retrieval" for o in generated(storage_share=0.0).orders(600.0))


def test_article_weights_are_respected() -> None:
    orders = list(generated(article_weights={"A": 3.0, "B": 1.0}).orders(36_000.0))
    share = sum(order.article == "A" for order in orders) / len(orders)
    assert abs(share - 0.75) < 0.02


def test_zero_weight_article_never_appears() -> None:
    orders = generated(article_weights={"A": 1.0, "B": 0.0}).orders(600.0)
    assert {order.article for order in orders} == {"A"}


def test_article_key_order_does_not_change_sequence() -> None:
    first = generated(article_weights={"A": 3.0, "B": 1.0})
    second = generated(article_weights={"B": 1.0, "A": 3.0})
    assert list(first.orders(600.0)) == list(second.orders(600.0))


def test_zero_rate_yields_nothing() -> None:
    assert list(generated(orders_per_hour=0.0).orders(600.0)) == []
