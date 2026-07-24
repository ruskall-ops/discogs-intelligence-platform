"""Presentation-state boundary for Marketplace Workspace."""


class MarketplaceWorkspacePresentationService:
    def __init__(self, builder):
        self._builder = builder

    def workspace(self, queue=(), **state):
        return self._builder.build(queue, **state)

    def select(self, workspace, release_id, **state):
        return self._builder.select(workspace, release_id, **state)

    def set_research_status(self, workspace, release_id, status):
        return self._builder.with_research_status(workspace, release_id, status)


__all__ = ["MarketplaceWorkspacePresentationService"]
