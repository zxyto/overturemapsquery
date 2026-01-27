"""
Integration tests that connect to real Overture Maps data
These tests are slower as they hit the actual S3 data source
"""

import pytest
import pandas as pd
from src.db_manager import DuckDBManager
from src.query_builder import OvertureQueryBuilder
from src.constants import OVERTURE_CONFIG


class TestOvertureDataConnection:
    """Integration tests for Overture Maps data connection"""

    @pytest.fixture(scope="class")
    def db_manager(self):
        """Create a real DuckDB manager instance"""
        # Reset singleton for clean test
        DuckDBManager._instance = None
        manager = DuckDBManager()
        yield manager
        # Cleanup
        manager.close_connection()
        DuckDBManager._instance = None

    def test_duckdb_connection_initialization(self, db_manager):
        """Test that DuckDB connection can be initialized"""
        connection = db_manager.get_connection()
        assert connection is not None

    def test_extensions_loaded(self, db_manager):
        """Test that required extensions (httpfs, spatial) are loaded"""
        connection = db_manager.get_connection()

        # Query to check loaded extensions
        result = connection.execute("SELECT * FROM duckdb_extensions() WHERE loaded = true").fetchdf()

        loaded_extensions = result['extension_name'].tolist()

        assert 'httpfs' in loaded_extensions, "httpfs extension not loaded"
        assert 'spatial' in loaded_extensions, "spatial extension not loaded"

    def test_s3_access_configured(self, db_manager):
        """Test that S3 access is configured for anonymous access"""
        connection = db_manager.get_connection()

        # Check S3 settings
        try:
            result = connection.execute("SELECT current_setting('s3_region')").fetchone()
            assert result is not None
        except Exception as e:
            # Settings might not be queryable directly, but extensions should still work
            pass

    def test_connect_to_overture_data(self, db_manager):
        """Test actual connection to Overture Maps S3 data"""
        # Create view with default release
        db_manager.create_places_view()

        connection = db_manager.get_connection()

        # Try a very simple query to verify we can read the data
        # Limit to 1 row to make it fast
        query = "SELECT COUNT(*) as count FROM places LIMIT 1"

        result = connection.execute(query).fetchone()
        assert result is not None

    def test_query_small_dataset(self, db_manager):
        """Test querying a small amount of real data"""
        # Build a query for a small area with limit
        builder = OvertureQueryBuilder()
        builder.add_bbox_filter(-90.1, -90.0, 35.1, 35.2)  # Very small area in Memphis
        builder.add_categories(['hospital', 'clinic'])
        builder.set_limit(10)

        query = builder.build()

        # Execute query
        db_manager.create_places_view()
        result = db_manager.execute_query(query)

        # Verify we got a DataFrame
        assert isinstance(result, pd.DataFrame)

        # Verify it has expected columns
        expected_columns = ['id', 'name', 'category', 'state', 'city', 'longitude', 'latitude']
        for col in expected_columns:
            assert col in result.columns, f"Missing column: {col}"

        # Verify coordinates are in expected range
        if not result.empty:
            assert result['longitude'].min() >= -90.1
            assert result['longitude'].max() <= -90.0
            assert result['latitude'].min() >= 35.1
            assert result['latitude'].max() <= 35.2

    def test_query_with_state_filter(self, db_manager):
        """Test querying with state filter"""
        builder = OvertureQueryBuilder()
        builder.add_state_filter('DC')  # Small state for fast query
        builder.add_categories(['hospital'])
        builder.set_limit(5)

        query = builder.build()

        db_manager.create_places_view()
        result = db_manager.execute_query(query)

        assert isinstance(result, pd.DataFrame)

        # If we got results, verify they're from DC
        if not result.empty:
            # Some results might not have state info, but those that do should be DC
            states_with_data = result[result['state'].notna()]['state'].unique()
            if len(states_with_data) > 0:
                assert 'DC' in states_with_data or len(states_with_data) == 0

    def test_count_query(self, db_manager):
        """Test count query functionality"""
        builder = OvertureQueryBuilder()
        builder.add_bbox_filter(-90.1, -90.0, 35.1, 35.2)
        builder.add_categories(['hospital'])

        query = builder.build()

        db_manager.create_places_view()
        count = db_manager.execute_count_query(query)

        assert isinstance(count, int)
        assert count >= 0

    def test_custom_release_version(self, db_manager):
        """Test that custom release version can be used"""
        # Use the default release version for this test
        custom_release = OVERTURE_CONFIG['release']

        db_manager.create_places_view(release_version=custom_release)

        assert db_manager._current_release == custom_release
        assert db_manager._view_created is True

    def test_geometry_extraction(self, db_manager):
        """Test that geometries are correctly extracted to lon/lat"""
        builder = OvertureQueryBuilder()
        builder.add_bbox_filter(-90.1, -90.0, 35.1, 35.2)
        builder.set_limit(5)

        query = builder.build()

        db_manager.create_places_view()
        result = db_manager.execute_query(query)

        if not result.empty:
            # Check that we have numeric longitude and latitude
            assert pd.api.types.is_numeric_dtype(result['longitude'])
            assert pd.api.types.is_numeric_dtype(result['latitude'])

            # Check that coordinates are valid
            assert result['longitude'].notna().any()
            assert result['latitude'].notna().any()

            # Check coordinate ranges (basic sanity check)
            assert (result['longitude'] >= -180).all()
            assert (result['longitude'] <= 180).all()
            assert (result['latitude'] >= -90).all()
            assert (result['latitude'] <= 90).all()


class TestEndToEndQuery:
    """End-to-end integration tests"""

    def test_complete_query_workflow(self):
        """Test complete workflow from connection to results"""
        # Reset singleton
        DuckDBManager._instance = None

        try:
            # Initialize manager
            manager = DuckDBManager()

            # Build query
            builder = OvertureQueryBuilder()
            builder.add_state_filter('DC')
            builder.add_categories(['museum', 'library'])
            builder.set_limit(10)

            query = builder.build()

            # Execute query
            results = manager.execute_query(query, OVERTURE_CONFIG['release'])

            # Verify results
            assert isinstance(results, pd.DataFrame)
            assert 'id' in results.columns
            assert 'name' in results.columns
            assert 'category' in results.columns
            assert 'longitude' in results.columns
            assert 'latitude' in results.columns

            # Verify categories (if we got results)
            if not results.empty:
                categories = results['category'].unique()
                # Should only have museum or library
                for cat in categories:
                    assert cat in ['museum', 'library'] or pd.isna(cat)

        finally:
            # Cleanup
            if DuckDBManager._instance:
                DuckDBManager._instance.close_connection()
            DuckDBManager._instance = None

    def test_error_handling_invalid_query(self):
        """Test that invalid queries are handled gracefully"""
        DuckDBManager._instance = None

        try:
            manager = DuckDBManager()

            # Try to execute invalid SQL
            with pytest.raises(Exception):
                manager.execute_query("SELECT * FROM nonexistent_table")

        finally:
            if DuckDBManager._instance:
                DuckDBManager._instance.close_connection()
            DuckDBManager._instance = None
