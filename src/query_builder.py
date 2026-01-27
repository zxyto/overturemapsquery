"""
SQL Query Builder for Overture Maps
Constructs parameterized DuckDB SQL queries with validation
"""

from typing import List, Optional, Dict


class OvertureQueryBuilder:
    """
    Constructs parameterized DuckDB SQL queries
    Supports multiple filter types with validation
    """

    def __init__(self):
        self.filters = []
        self.categories = []
        self.limit = None
        self.state_filter = None
        self.bbox_filter = None

    def add_state_filter(self, state_code: str):
        """
        Add US state region filter

        Args:
            state_code (str): Two-letter state code (e.g., 'TN', 'CA')
        """
        self.state_filter = state_code
        return self

    def add_bbox_filter(self, xmin: float, xmax: float, ymin: float, ymax: float):
        """
        Add bounding box spatial filter

        Args:
            xmin (float): Minimum longitude
            xmax (float): Maximum longitude
            ymin (float): Minimum latitude
            ymax (float): Maximum latitude
        """
        self.bbox_filter = {
            'xmin': xmin,
            'xmax': xmax,
            'ymin': ymin,
            'ymax': ymax
        }
        return self

    def add_categories(self, category_list: List[str]):
        """
        Add category.primary filters

        Args:
            category_list (List[str]): List of category names
        """
        self.categories = category_list
        return self

    def set_limit(self, max_results: int):
        """
        Limit result count

        Args:
            max_results (int): Maximum number of results to return
        """
        self.limit = max_results
        return self

    def build(self) -> str:
        """
        Construct final SQL query with all filters

        Returns:
            str: Complete SQL query string
        """
        # Base SELECT statement with coordinates
        query = """
        SELECT
            id,
            names.primary as name,
            categories.primary as category,
            addresses[1].region as state,
            addresses[1].locality as city,
            ST_X(geometry) as longitude,
            ST_Y(geometry) as latitude
        FROM places
        """

        # Build WHERE clause
        where_conditions = []

        # Add category filter
        if self.categories:
            # Escape and format category names
            formatted_categories = [f"'{cat}'" for cat in self.categories]
            categories_str = ', '.join(formatted_categories)
            where_conditions.append(f"categories.primary IN ({categories_str})")

        # Add spatial filter (prefer bbox over state for performance)
        if self.bbox_filter:
            bbox = self.bbox_filter
            # Use spatial predicate for efficient filtering
            # Filter on actual point location, not bbox metadata
            where_conditions.append(
                f"ST_Within(geometry, ST_MakeEnvelope({bbox['xmin']}, {bbox['ymin']}, {bbox['xmax']}, {bbox['ymax']}))"
            )
        elif self.state_filter:
            where_conditions.append(f"addresses[1].region = '{self.state_filter}'")

        # Combine WHERE conditions
        if where_conditions:
            query += "\nWHERE " + "\nAND ".join(where_conditions)

        # Add LIMIT
        if self.limit:
            query += f"\nLIMIT {self.limit}"

        return query

    def build_count_query(self) -> str:
        """
        Fast count query for result preview

        Returns:
            str: COUNT query string
        """
        # Build a query similar to build() but only selecting COUNT
        query = "SELECT COUNT(*) as count FROM places"

        # Build WHERE clause
        where_conditions = []

        # Add category filter
        if self.categories:
            formatted_categories = [f"'{cat}'" for cat in self.categories]
            categories_str = ', '.join(formatted_categories)
            where_conditions.append(f"categories.primary IN ({categories_str})")

        # Add spatial filter
        if self.bbox_filter:
            bbox = self.bbox_filter
            # Use spatial predicate for efficient filtering
            where_conditions.append(
                f"ST_Within(geometry, ST_MakeEnvelope({bbox['xmin']}, {bbox['ymin']}, {bbox['xmax']}, {bbox['ymax']}))"
            )
        elif self.state_filter:
            where_conditions.append(f"addresses[1].region = '{self.state_filter}'")

        # Combine WHERE conditions
        if where_conditions:
            query += "\nWHERE " + "\nAND ".join(where_conditions)

        return query

    def reset(self):
        """Reset all filters and settings"""
        self.filters = []
        self.categories = []
        self.limit = None
        self.state_filter = None
        self.bbox_filter = None
        return self


def build_query_from_params(
    state: Optional[str] = None,
    bbox: Optional[Dict[str, float]] = None,
    categories: Optional[List[str]] = None,
    limit: Optional[int] = None
) -> str:
    """
    Helper function to build query from parameters

    Args:
        state (str, optional): State code
        bbox (Dict, optional): Bounding box with xmin, xmax, ymin, ymax
        categories (List[str], optional): List of category names
        limit (int, optional): Maximum results

    Returns:
        str: SQL query string
    """
    builder = OvertureQueryBuilder()

    if categories:
        builder.add_categories(categories)

    if bbox:
        builder.add_bbox_filter(
            bbox['xmin'], bbox['xmax'],
            bbox['ymin'], bbox['ymax']
        )
    elif state:
        builder.add_state_filter(state)

    if limit:
        builder.set_limit(limit)

    return builder.build()
