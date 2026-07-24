"""Application composition boundary for Portfolio Workspace presentation."""


class PortfolioWorkspacePresentationService:
    def __init__(
        self,
        overview_presentation,
        distribution_presentation,
        concentration_presentation,
        opportunity_alignment_presentation,
        builder,
    ):
        self._overview = overview_presentation
        self._distribution = distribution_presentation
        self._concentration = concentration_presentation
        self._opportunity_alignment = opportunity_alignment_presentation
        self._builder = builder

    def workspace(
        self,
        overview_result=None,
        distribution_result=None,
        concentration_result=None,
        opportunity_alignment_result=None,
        **state,
    ):
        return self._builder.build(
            self._overview.overview_for_result(overview_result),
            self._distribution.distribution_for_result(distribution_result),
            self._concentration.concentration_for_result(concentration_result),
            self._opportunity_alignment.alignment_for_result(
                opportunity_alignment_result
            ),
            **state,
        )

    def navigate(self, workspace, destination):
        return self._builder.navigate(workspace, destination)


__all__ = ["PortfolioWorkspacePresentationService"]
