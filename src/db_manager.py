"""
DuckDB Connection Manager
Singleton pattern for managing DuckDB connections with Overture Maps data
"""

import duckdb
import streamlit as st
from .constants import OVERTURE_CONFIG


class DuckDBManager:
    """
    Singleton pattern for managing DuckDB connections
    Ensures single connection per Streamlit session
    """

    _instance = None
    _connection = None
    _view_created = False
    _current_release = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_connection(self):
        """
        Returns active DuckDB connection with extensions loaded
        Reuses existing connection if available
        """
        if self._connection is None:
            self._connection = self._initialize_connection()
        return self._connection

    def _initialize_connection(self):
        """
        Setup DuckDB with httpfs and spatial extensions
        Configure S3 access for Overture Maps data
        """
        try:
            # Create in-memory database for performance
            con = duckdb.connect()

            # Install and load required extensions
            con.execute("INSTALL httpfs")
            con.execute("LOAD httpfs")
            con.execute("INSTALL spatial")
            con.execute("LOAD spatial")

            # Configure S3 access for Overture Maps
            con.execute(f"SET s3_region='{OVERTURE_CONFIG['s3_region']}'")

            return con
        except Exception as e:
            raise ConnectionError(f"Failed to initialize DuckDB connection: {str(e)}")

    def create_places_view(self, release_version=None):
        """
        Create the places view from Overture Maps S3 data
        Recreates if release version changes

        Args:
            release_version (str, optional): Overture release version. Defaults to config value.
        """
        # Determine which release to use
        target_release = release_version or OVERTURE_CONFIG['release']

        # If view exists and release hasn't changed, skip recreation
        if self._view_created and self._current_release == target_release:
            return

        try:
            con = self.get_connection()

            # Build path for the target release
            base_path = f"s3://overturemaps-us-west-2/release/{target_release}/theme=places/type=place/*"

            # Create view from Overture Maps Parquet files
            con.execute(f"""
                CREATE OR REPLACE VIEW places AS
                SELECT * FROM read_parquet('{base_path}',
                                            filename=true,
                                            hive_partitioning=1)
            """)

            self._view_created = True
            self._current_release = target_release
        except Exception as e:
            raise Exception(f"Failed to create places view: {str(e)}")

    def execute_query(self, query, release_version=None):
        """
        Execute a SQL query and return results as DataFrame

        Args:
            query (str): SQL query string
            release_version (str, optional): Overture release version

        Returns:
            pandas.DataFrame: Query results
        """
        try:
            con = self.get_connection()

            # Ensure places view is created
            if not self._view_created:
                self.create_places_view(release_version)

            # Execute query and return DataFrame
            return con.execute(query).fetchdf()
        except Exception as e:
            raise Exception(f"Query execution failed: {str(e)}")

    def execute_count_query(self, query, release_version=None):
        """
        Execute a COUNT query for fast result preview

        Args:
            query (str): SQL query string
            release_version (str, optional): Overture release version

        Returns:
            int: Count of results
        """
        try:
            con = self.get_connection()

            # Ensure places view is created
            if not self._view_created:
                self.create_places_view(release_version)

            # Wrap query in COUNT
            count_query = f"SELECT COUNT(*) as count FROM ({query}) AS subquery"
            result = con.execute(count_query).fetchone()
            return result[0] if result else 0
        except Exception as e:
            raise Exception(f"Count query failed: {str(e)}")

    def close_connection(self):
        """Cleanup connection on app shutdown"""
        if self._connection:
            self._connection.close()
            self._connection = None
            self._view_created = False


# Helper function for Streamlit session state
def get_db_manager():
    """
    Get DuckDB manager from Streamlit session state
    Creates one if it doesn't exist
    """
    if 'db_manager' not in st.session_state:
        st.session_state.db_manager = DuckDBManager()
    return st.session_state.db_manager
