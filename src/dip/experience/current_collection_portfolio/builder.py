"""Deterministic projection of Slice 1 Portfolio snapshots into public copy."""

from __future__ import annotations

from dataclasses import replace
from dip.app.current_collection_portfolio import (
    CurrentCollectionContext,
    CurrentCollectionPortfolio,
    CurrentCollectionPortfolioExecutionOutcome,
    PortfolioConcentrationResultSnapshot,
    PortfolioDistributionResultSnapshot,
)
from dip.intelligence import IntelligenceStatus
from dip.portfolio_intelligence.portfolio_concentration import (
    MODULE_ID as CONCENTRATION_MODULE_ID,
    MODULE_VERSION as CONCENTRATION_MODULE_VERSION,
    PortfolioConcentrationAnalysisState,
    PortfolioConcentrationBasis,
    validate_portfolio_concentration_output,
    validate_portfolio_concentration_source,
)
from dip.portfolio_intelligence.portfolio_distribution import (
    MODULE_ID as DISTRIBUTION_MODULE_ID,
    MODULE_VERSION as DISTRIBUTION_MODULE_VERSION,
    PortfolioDistributionAnalysisState,
    PortfolioDistributionDimension,
    validate_portfolio_distribution_output,
)

from .models import (
    ConcentrationBasisPresentation,
    ConcentrationContributionPresentation,
    ConcentrationDifferencePresentation,
    ConcentrationDimensionPresentation,
    ConcentrationPresentation,
    CurrentCollectionPortfolioPresentation,
    DistributionCategoryPresentation,
    DistributionDimensionPresentation,
    DistributionPresentation,
    FirstCategoriesPresentation,
    PortfolioDestination,
    PortfolioPresentationAvailability,
    PresentedDecimal,
    PresentedRatio,
    format_percentage,
)


class CurrentCollectionPortfolioPresentationBuilder:
    def build(
        self,
        outcome: CurrentCollectionPortfolioExecutionOutcome,
        *,
        selected_destination: PortfolioDestination = PortfolioDestination.DISTRIBUTION,
    ) -> CurrentCollectionPortfolioPresentation:
        if type(outcome) is not CurrentCollectionPortfolioExecutionOutcome:
            raise TypeError("outcome must be CurrentCollectionPortfolioExecutionOutcome.")
        if type(selected_destination) is not PortfolioDestination:
            raise TypeError("selected_destination must be PortfolioDestination.")
        if outcome.portfolio is None:
            return CurrentCollectionPortfolioPresentation(
                PortfolioPresentationAvailability.UNAVAILABLE,
                selected_destination,
                None,
                None,
            )
        portfolio = self._portfolio(outcome.portfolio)
        return CurrentCollectionPortfolioPresentation(
            PortfolioPresentationAvailability.AVAILABLE,
            selected_destination,
            _distribution(portfolio.distribution),
            _concentration(portfolio.concentration, portfolio.distribution),
        )

    def select(
        self,
        workspace: CurrentCollectionPortfolioPresentation,
        destination: PortfolioDestination,
    ) -> CurrentCollectionPortfolioPresentation:
        if type(workspace) is not CurrentCollectionPortfolioPresentation:
            raise TypeError("workspace must be CurrentCollectionPortfolioPresentation.")
        if type(destination) is not PortfolioDestination:
            raise TypeError("destination must be PortfolioDestination.")
        return replace(workspace, selected_destination=destination)

    @staticmethod
    def _portfolio(value):
        if type(value) is not CurrentCollectionPortfolio:
            raise TypeError("outcome contains an invalid Portfolio.")
        if type(value.context) is not CurrentCollectionContext or value.context.scope_id != "current_collection":
            raise ValueError("Portfolio scope is unsupported.")
        if type(value.distribution) is not PortfolioDistributionResultSnapshot:
            raise TypeError("Portfolio Distribution snapshot is invalid.")
        if type(value.concentration) is not PortfolioConcentrationResultSnapshot:
            raise TypeError("Portfolio Concentration snapshot is invalid.")
        distribution = validate_portfolio_distribution_output(value.distribution.output)
        concentration = validate_portfolio_concentration_output(value.concentration.output)
        expected_distribution_status = (
            IntelligenceStatus.SKIPPED
            if distribution.analysis_state is PortfolioDistributionAnalysisState.INSUFFICIENT_DATA
            else IntelligenceStatus.COMPLETED
        )
        expected_concentration_status = (
            IntelligenceStatus.SKIPPED
            if concentration.analysis_state is PortfolioConcentrationAnalysisState.INSUFFICIENT_DATA
            else IntelligenceStatus.COMPLETED
        )
        if value.distribution.status is not expected_distribution_status:
            raise ValueError("Portfolio Distribution status contradicts its output.")
        if value.concentration.status is not expected_concentration_status:
            raise ValueError("Portfolio Concentration status contradicts its output.")
        validate_portfolio_concentration_source(distribution, concentration)
        if value.distribution.module_id != DISTRIBUTION_MODULE_ID or value.distribution.module_version != DISTRIBUTION_MODULE_VERSION:
            raise ValueError("Portfolio Distribution identity is unsupported.")
        if value.concentration.module_id != CONCENTRATION_MODULE_ID or value.concentration.module_version != CONCENTRATION_MODULE_VERSION:
            raise ValueError("Portfolio Concentration identity is unsupported.")
        return value


def _ratio(numerator, denominator, value):
    return PresentedRatio(numerator, denominator, value)


def _decimal(value, *, percentage=False):
    return PresentedDecimal(value, percentage)


def _distribution(snapshot):
    output = validate_portfolio_distribution_output(snapshot.output)
    ownership = output.summary.ownership
    dimensions = tuple(_distribution_dimension(item) for item in output.dimensions)
    return DistributionPresentation(
        output.analysis_state.value,
        ownership.unique_owned_releases,
        ownership.total_owned_copies,
        ownership.duplicate_copy_count,
        dimensions,
        snapshot.module_id,
        snapshot.module_version,
        output.rule_set_version,
        output.summary.evidence_coverage.value,
        output.provenance.source_query_id,
        output.provenance.ownership_data_version,
        output.provenance.collection_snapshot_id,
    )


def _distribution_dimension(value):
    categories = tuple(
        DistributionCategoryPresentation(
            item.category_id,
            item.display_name,
            _ratio(item.unique_release_count, item.release_denominator, item.release_ratio),
            _ratio(item.owned_copy_count, item.copy_denominator, item.copy_ratio),
            item.release_ids,
        )
        for item in value.entries
    )
    return DistributionDimensionPresentation(
        value.dimension.value,
        value.represented_category_count,
        value.releases_with_metadata,
        value.copies_with_metadata,
        _ratio(value.releases_with_metadata, value.release_denominator, value.release_metadata_coverage_ratio),
        _ratio(value.copies_with_metadata, value.copy_denominator, value.copy_metadata_coverage_ratio),
        value.releases_missing_metadata,
        value.copies_missing_metadata,
        value.missing_release_ids,
        categories,
    )


def _concentration(snapshot, distribution_snapshot):
    distribution = validate_portfolio_distribution_output(distribution_snapshot.output)
    output = validate_portfolio_concentration_output(snapshot.output)
    validate_portfolio_concentration_source(distribution, output)
    provenance = output.provenance
    source_provenance = provenance.distribution_provenance
    if source_provenance is None or provenance.source_module_version is None or provenance.source_rule_set_version is None or provenance.source_evidence_coverage is None:
        raise ValueError("Concentration source provenance is incomplete.")
    return ConcentrationPresentation(
        output.analysis_state.value,
        output.summary.unique_owned_releases,
        output.summary.total_owned_copies,
        output.summary.duplicate_copy_count,
        tuple(_concentration_dimension(item) for item in output.dimensions),
        tuple(output.summary.unusable_dimensions),
        snapshot.module_id,
        snapshot.module_version,
        output.rule_set_version,
        output.summary.evidence_coverage.value,
        provenance.source_evidence_coverage.value,
        provenance.source_module_id,
        provenance.source_module_version,
        provenance.source_rule_set_version,
        source_provenance.source_query_id,
        source_provenance.ownership_data_version,
        source_provenance.collection_snapshot_id,
    )


def _concentration_dimension(value):
    return ConcentrationDimensionPresentation(
        value.dimension,
        value.represented_category_count,
        _ratio(value.releases_with_metadata, value.releases_with_metadata + value.releases_missing_metadata, value.release_metadata_coverage_ratio),
        _ratio(value.copies_with_metadata, value.copies_with_metadata + value.copies_missing_metadata, value.copy_metadata_coverage_ratio),
        value.missing_release_ids,
        _basis(value.release_concentration, value.source_entries),
        _basis(value.copy_concentration, value.source_entries),
        _difference(value.difference),
    )


def _contribution(value):
    return ConcentrationContributionPresentation(
        value.category_id, value.display_name, value.membership_count, value.release_ids
    )


def _first(value):
    if value is None:
        return None
    return FirstCategoriesPresentation(
        value.requested_count,
        value.included_category_count,
        _ratio(value.membership_numerator, value.membership_denominator, value.share),
        tuple(_contribution(item) for item in value.contributions),
    )


def _basis(value, source_entries):
    release_basis = value.basis is PortfolioConcentrationBasis.RELEASE_MEMBERSHIP
    largest = None
    if value.largest_category_share is not None:
        largest = _ratio(
            value.largest_membership_count,
            value.largest_membership_denominator,
            value.largest_category_share,
        )
    return ConcentrationBasisPresentation(
        value.basis.value,
        value.membership_total,
        value.represented_category_count,
        tuple(
            ConcentrationContributionPresentation(
                item.category_id,
                item.display_name,
                item.unique_release_count if release_basis else item.owned_copy_count,
                item.release_ids,
            )
            for item in source_entries
        ),
        largest,
        tuple(_contribution(item) for item in value.largest_categories),
        _first(value.top_three),
        _first(value.top_five),
        _decimal(value.hhi),
        _decimal(value.normalized_hhi),
        _decimal(value.effective_category_count),
        value.state.value,
    )


def _difference(value):
    return ConcentrationDifferencePresentation(
        _decimal(value.largest_category_share_delta, percentage=True),
        _decimal(value.top_three_share_delta, percentage=True),
        _decimal(value.top_five_share_delta, percentage=True),
        _decimal(value.hhi_delta),
        _decimal(value.normalized_hhi_delta),
        _decimal(value.effective_category_count_delta),
    )


__all__ = ["CurrentCollectionPortfolioPresentationBuilder", "format_percentage"]
