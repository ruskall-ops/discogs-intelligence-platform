"""Application presentation boundary for Portfolio Opportunity Alignment."""


class PortfolioOpportunityAlignmentPresentationService:
    def __init__(self, builder):
        self._builder = builder

    def alignment_for_result(self, result):
        return self._builder.build(result)


__all__ = ["PortfolioOpportunityAlignmentPresentationService"]
