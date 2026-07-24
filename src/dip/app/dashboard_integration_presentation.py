"""Compose existing workspace presentation services for the Dashboard."""


class DashboardIntegrationPresentationService:
    def __init__(self, portfolio, marketplace, history, builder):
        self._portfolio = portfolio
        self._marketplace = marketplace
        self._history = history
        self._builder = builder

    def dashboard(
        self,
        collection,
        *,
        portfolio_results=(None, None, None, None),
        marketplace_queue=(),
        history_observations=(),
        history_changes=(),
        history_trends=(),
    ):
        if type(portfolio_results) is not tuple or len(portfolio_results) != 4:
            raise TypeError("portfolio_results must contain four results.")
        portfolio = self._portfolio.workspace(*portfolio_results)
        marketplace = self._marketplace.workspace(marketplace_queue)
        history = self._history.explorer(
            history_observations, history_changes, history_trends
        )
        return self._builder.build(collection, portfolio, marketplace, history)


__all__ = ["DashboardIntegrationPresentationService"]
