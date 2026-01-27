"""
Unit tests for query builder
"""

import pytest
from src.query_builder import OvertureQueryBuilder, build_query_from_params


class TestQueryBuilder:
    """Test query builder functionality"""

    def test_basic_state_filter(self):
        builder = OvertureQueryBuilder()
        builder.add_state_filter('TN')
        builder.add_categories(['hospital'])
        query = builder.build()

        assert "addresses[1].region = 'TN'" in query
        assert "categories.primary IN ('hospital')" in query
        assert "FROM places" in query

    def test_bbox_filter(self):
        builder = OvertureQueryBuilder()
        builder.add_bbox_filter(-90.3, -81.6, 34.9, 36.7)
        builder.add_categories(['clinic'])
        query = builder.build()

        # Should use efficient spatial predicate
        assert "ST_Within(geometry, ST_MakeEnvelope(-90.3, 34.9, -81.6, 36.7))" in query
        assert "categories.primary IN ('clinic')" in query

    def test_multiple_categories(self):
        builder = OvertureQueryBuilder()
        builder.add_categories(['hospital', 'clinic', 'pharmacy'])
        query = builder.build()

        assert "'hospital'" in query
        assert "'clinic'" in query
        assert "'pharmacy'" in query
        assert "categories.primary IN" in query

    def test_with_limit(self):
        builder = OvertureQueryBuilder()
        builder.add_state_filter('CA')
        builder.add_categories(['restaurant'])
        builder.set_limit(1000)
        query = builder.build()

        assert "LIMIT 1000" in query

    def test_bbox_preferred_over_state(self):
        """When both bbox and state are set, bbox should be used"""
        builder = OvertureQueryBuilder()
        builder.add_state_filter('TN')
        builder.add_bbox_filter(-90.3, -81.6, 34.9, 36.7)
        builder.add_categories(['hospital'])
        query = builder.build()

        # Should use bbox spatial predicate, not state filter in WHERE clause
        assert "ST_Within" in query
        assert "ST_MakeEnvelope" in query
        assert "addresses[1].region = 'TN'" not in query  # More specific - checking WHERE clause

    def test_count_query(self):
        builder = OvertureQueryBuilder()
        builder.add_state_filter('TN')
        builder.add_categories(['hospital'])
        query = builder.build_count_query()

        assert "SELECT COUNT(*)" in query
        assert "FROM places" in query
        assert "addresses[1].region = 'TN'" in query

    def test_reset(self):
        builder = OvertureQueryBuilder()
        builder.add_state_filter('TN')
        builder.add_categories(['hospital'])
        builder.set_limit(100)
        builder.reset()

        # After reset, should have no filters
        assert builder.state_filter is None
        assert builder.bbox_filter is None
        assert builder.categories == []
        assert builder.limit is None

    def test_method_chaining(self):
        """Test that builder methods can be chained"""
        query = (OvertureQueryBuilder()
                 .add_state_filter('NY')
                 .add_categories(['museum'])
                 .set_limit(500)
                 .build())

        assert "addresses[1].region = 'NY'" in query
        assert "'museum'" in query
        assert "LIMIT 500" in query

    def test_no_filters_builds_basic_query(self):
        """Query with no filters should still be valid"""
        builder = OvertureQueryBuilder()
        query = builder.build()

        assert "SELECT" in query
        assert "FROM places" in query
        # Should not have WHERE clause
        assert query.count("WHERE") == 0

    def test_query_includes_coordinates(self):
        """Verify query selects longitude and latitude"""
        builder = OvertureQueryBuilder()
        builder.add_state_filter('TN')
        builder.add_categories(['hospital'])
        query = builder.build()

        assert "ST_X(geometry) as longitude" in query
        assert "ST_Y(geometry) as latitude" in query

    def test_query_includes_required_fields(self):
        """Verify all required fields are selected"""
        builder = OvertureQueryBuilder()
        query = builder.build()

        assert "id" in query
        assert "names.primary as name" in query
        assert "categories.primary as category" in query
        assert "addresses[1].region as state" in query
        assert "addresses[1].locality as city" in query


class TestBuildQueryFromParams:
    """Test helper function for building queries from parameters"""

    def test_build_from_state_params(self):
        query = build_query_from_params(
            state='TN',
            categories=['hospital', 'clinic'],
            limit=100
        )

        assert "addresses[1].region = 'TN'" in query
        assert "'hospital'" in query
        assert "'clinic'" in query
        assert "LIMIT 100" in query

    def test_build_from_bbox_params(self):
        bbox = {'xmin': -90.3, 'xmax': -81.6, 'ymin': 34.9, 'ymax': 36.7}
        query = build_query_from_params(
            bbox=bbox,
            categories=['restaurant'],
            limit=500
        )

        # Should use spatial predicate
        assert "ST_Within" in query
        assert "ST_MakeEnvelope(-90.3, 34.9, -81.6, 36.7)" in query
        assert "'restaurant'" in query
        assert "LIMIT 500" in query

    def test_build_with_no_limit(self):
        query = build_query_from_params(
            state='CA',
            categories=['park']
        )

        assert "addresses[1].region = 'CA'" in query
        assert "LIMIT" not in query

    def test_build_with_no_categories(self):
        query = build_query_from_params(
            state='NY',
            limit=100
        )

        # Should build query without category filter
        assert "addresses[1].region = 'NY'" in query
        assert "categories.primary IN" not in query
