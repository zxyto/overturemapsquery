"""
Unit tests for DuckDB manager
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.db_manager import DuckDBManager


class TestDuckDBManager:
    """Test DuckDB manager functionality"""

    def test_singleton_pattern(self):
        """Verify only one instance is created"""
        manager1 = DuckDBManager()
        manager2 = DuckDBManager()
        assert manager1 is manager2

    @patch('src.db_manager.duckdb.connect')
    def test_initialize_connection(self, mock_connect):
        """Test connection initialization"""
        mock_con = Mock()
        mock_connect.return_value = mock_con

        manager = DuckDBManager()
        manager._connection = None  # Reset
        con = manager.get_connection()

        # Should install extensions
        assert mock_con.execute.called
        execute_calls = [str(call) for call in mock_con.execute.call_args_list]

        # Check that httpfs and spatial were installed/loaded
        assert any('httpfs' in str(call) for call in execute_calls)
        assert any('spatial' in str(call) for call in execute_calls)

    @patch('src.db_manager.duckdb.connect')
    def test_create_places_view_default_release(self, mock_connect):
        """Test view creation with default release"""
        mock_con = Mock()
        mock_connect.return_value = mock_con

        manager = DuckDBManager()
        manager._connection = mock_con
        manager._view_created = False
        manager._current_release = None

        manager.create_places_view()

        # Should create view with default path
        assert mock_con.execute.called
        execute_calls = [str(call) for call in mock_con.execute.call_args_list]

        # Check that CREATE VIEW was called
        assert any('CREATE' in str(call) and 'places' in str(call) for call in execute_calls)
        assert manager._view_created is True

    @patch('src.db_manager.duckdb.connect')
    def test_create_places_view_custom_release(self, mock_connect):
        """Test view creation with custom release"""
        mock_con = Mock()
        mock_connect.return_value = mock_con

        manager = DuckDBManager()
        manager._connection = mock_con
        manager._view_created = False
        manager._current_release = None

        custom_release = "2026-02-15.0"
        manager.create_places_view(release_version=custom_release)

        # Should create view with custom release path
        execute_calls = [call[0][0] for call in mock_con.execute.call_args_list]

        # Check that custom release is in the path
        assert any(custom_release in str(call) for call in execute_calls)
        assert manager._current_release == custom_release

    @patch('src.db_manager.duckdb.connect')
    def test_view_recreation_on_release_change(self, mock_connect):
        """Test that view is recreated when release changes"""
        mock_con = Mock()
        mock_connect.return_value = mock_con

        manager = DuckDBManager()
        manager._connection = mock_con
        manager._view_created = True
        manager._current_release = "2026-01-21.0"

        # Change to different release
        new_release = "2026-02-15.0"
        manager.create_places_view(release_version=new_release)

        # Should recreate view
        assert mock_con.execute.called
        assert manager._current_release == new_release

    @patch('src.db_manager.duckdb.connect')
    def test_view_not_recreated_same_release(self, mock_connect):
        """Test that view is not recreated if release hasn't changed"""
        mock_con = Mock()
        mock_connect.return_value = mock_con

        manager = DuckDBManager()
        manager._connection = mock_con
        manager._view_created = True
        manager._current_release = "2026-01-21.0"

        # Clear call history
        mock_con.execute.reset_mock()

        # Call with same release
        manager.create_places_view(release_version="2026-01-21.0")

        # Should NOT execute any queries
        assert not mock_con.execute.called

    @patch('src.db_manager.duckdb.connect')
    def test_execute_query_with_release(self, mock_connect):
        """Test query execution with custom release"""
        mock_con = Mock()
        mock_result = Mock()
        mock_result.fetchdf.return_value = "mock_dataframe"
        mock_con.execute.return_value = mock_result
        mock_connect.return_value = mock_con

        manager = DuckDBManager()
        manager._connection = mock_con
        manager._view_created = False

        custom_release = "2026-02-15.0"
        query = "SELECT * FROM places LIMIT 10"

        result = manager.execute_query(query, release_version=custom_release)

        # Should create view with custom release
        assert manager._current_release == custom_release
        assert result == "mock_dataframe"

    @patch('src.db_manager.duckdb.connect')
    def test_execute_count_query_with_release(self, mock_connect):
        """Test count query execution with custom release"""
        mock_con = Mock()
        mock_con.execute.return_value.fetchone.return_value = (42,)
        mock_connect.return_value = mock_con

        manager = DuckDBManager()
        manager._connection = mock_con
        manager._view_created = False

        custom_release = "2026-02-15.0"
        query = "SELECT * FROM places"

        count = manager.execute_count_query(query, release_version=custom_release)

        assert count == 42
        assert manager._current_release == custom_release

    @patch('src.db_manager.duckdb.connect')
    def test_connection_error_handling(self, mock_connect):
        """Test error handling on connection failure"""
        mock_connect.side_effect = Exception("Connection failed")

        manager = DuckDBManager()
        manager._connection = None

        with pytest.raises(ConnectionError, match="Failed to initialize DuckDB connection"):
            manager.get_connection()

    @patch('src.db_manager.duckdb.connect')
    def test_view_creation_error_handling(self, mock_connect):
        """Test error handling on view creation failure"""
        mock_con = Mock()
        mock_con.execute.side_effect = Exception("S3 access denied")
        mock_connect.return_value = mock_con

        manager = DuckDBManager()
        manager._connection = mock_con
        manager._view_created = False

        with pytest.raises(Exception, match="Failed to create places view"):
            manager.create_places_view()

    @patch('src.db_manager.duckdb.connect')
    def test_query_execution_error_handling(self, mock_connect):
        """Test error handling on query execution failure"""
        mock_con = Mock()
        mock_con.execute.side_effect = Exception("Query syntax error")
        mock_connect.return_value = mock_con

        manager = DuckDBManager()
        manager._connection = mock_con
        manager._view_created = True

        with pytest.raises(Exception, match="Query execution failed"):
            manager.execute_query("INVALID SQL")

    @patch('src.db_manager.duckdb.connect')
    def test_close_connection(self, mock_connect):
        """Test connection cleanup"""
        mock_con = Mock()
        mock_connect.return_value = mock_con

        manager = DuckDBManager()
        manager._connection = mock_con
        manager._view_created = True
        manager._current_release = "2026-01-21.0"

        manager.close_connection()

        assert mock_con.close.called
        assert manager._connection is None
        assert manager._view_created is False


class TestGetDBManager:
    """Test the get_db_manager helper function"""

    @patch('src.db_manager.st')
    def test_creates_manager_if_not_exists(self, mock_st):
        """Test that manager is created if not in session state"""
        # Create a mock that acts like a dict but supports attribute access
        session_state_mock = Mock()
        session_state_mock.__contains__ = Mock(return_value=False)
        mock_st.session_state = session_state_mock

        from src.db_manager import get_db_manager
        manager = get_db_manager()

        # Verify db_manager was set
        assert hasattr(session_state_mock, 'db_manager')
        assert isinstance(manager, DuckDBManager)

    @patch('src.db_manager.st')
    def test_returns_existing_manager(self, mock_st):
        """Test that existing manager is returned"""
        existing_manager = DuckDBManager()

        # Create a mock that acts like a dict but supports attribute access
        session_state_mock = Mock()
        session_state_mock.__contains__ = Mock(return_value=True)
        session_state_mock.db_manager = existing_manager
        mock_st.session_state = session_state_mock

        from src.db_manager import get_db_manager
        manager = get_db_manager()

        assert manager is existing_manager
