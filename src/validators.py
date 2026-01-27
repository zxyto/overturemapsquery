"""
Input Validation for Overture Maps Query Application
Validates user inputs for safety and correctness
"""

import re
from typing import List, Tuple
from .constants import US_STATES, MAX_RESULTS


class ValidationError(Exception):
    """Custom exception for validation failures"""
    pass


class InputValidator:
    """Centralized input validation logic"""

    @staticmethod
    def validate_state_code(state_code: str) -> Tuple[bool, str]:
        """
        Verify state code is valid US state

        Args:
            state_code (str): Two-letter state code

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if not state_code:
            return False, "State code cannot be empty"

        state_code = state_code.upper().strip()

        if state_code not in US_STATES:
            return False, f"Invalid state code: {state_code}. Must be a valid US state abbreviation."

        return True, ""

    @staticmethod
    def validate_bbox(xmin: float, xmax: float, ymin: float, ymax: float) -> Tuple[bool, str]:
        """
        Validate bounding box coordinates

        Args:
            xmin (float): Minimum longitude
            xmax (float): Maximum longitude
            ymin (float): Minimum latitude
            ymax (float): Maximum latitude

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        # Check longitude range: -180 to 180
        if not (-180 <= xmin <= 180):
            return False, f"Minimum longitude must be between -180 and 180. Got: {xmin}"

        if not (-180 <= xmax <= 180):
            return False, f"Maximum longitude must be between -180 and 180. Got: {xmax}"

        # Check latitude range: -90 to 90
        if not (-90 <= ymin <= 90):
            return False, f"Minimum latitude must be between -90 and 90. Got: {ymin}"

        if not (-90 <= ymax <= 90):
            return False, f"Maximum latitude must be between -90 and 90. Got: {ymax}"

        # Verify xmin < xmax, ymin < ymax
        if xmin >= xmax:
            return False, f"Minimum longitude ({xmin}) must be less than maximum longitude ({xmax})"

        if ymin >= ymax:
            return False, f"Minimum latitude ({ymin}) must be less than maximum latitude ({ymax})"

        # Check bbox isn't too large (performance consideration)
        lon_range = xmax - xmin
        lat_range = ymax - ymin

        if lon_range > 50 or lat_range > 50:
            return False, f"Bounding box is too large (lon: {lon_range}°, lat: {lat_range}°). Maximum 50° in each dimension for performance."

        return True, ""

    @staticmethod
    def validate_category(category_name: str) -> Tuple[bool, str]:
        """
        Check if category name is reasonable

        Args:
            category_name (str): Category name to validate

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if not category_name:
            return False, "Category name cannot be empty"

        # Check for SQL injection patterns
        dangerous_patterns = [
            r"'.*--",  # SQL comment
            r";.*",    # Multiple statements
            r"DROP\s+TABLE",  # DROP TABLE
            r"DELETE\s+FROM",  # DELETE
            r"INSERT\s+INTO",  # INSERT
            r"UPDATE\s+",      # UPDATE
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, category_name, re.IGNORECASE):
                return False, "Category name contains invalid characters"

        # Check reasonable length
        if len(category_name) > 100:
            return False, "Category name is too long (max 100 characters)"

        # Check for valid characters (letters, numbers, underscores, hyphens)
        if not re.match(r'^[a-zA-Z0-9_\- ]+$', category_name):
            return False, "Category name can only contain letters, numbers, spaces, underscores, and hyphens"

        return True, ""

    @staticmethod
    def validate_categories(category_list: List[str]) -> Tuple[bool, str]:
        """
        Validate a list of categories

        Args:
            category_list (List[str]): List of category names

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if not category_list:
            return False, "At least one category must be selected"

        if len(category_list) > 50:
            return False, "Too many categories selected (max 50)"

        for category in category_list:
            is_valid, error_msg = InputValidator.validate_category(category)
            if not is_valid:
                return False, f"Invalid category '{category}': {error_msg}"

        return True, ""

    @staticmethod
    def validate_limit(limit_value: int, export_format: str = 'csv') -> Tuple[bool, str]:
        """
        Ensure result limit is reasonable

        Args:
            limit_value (int): Result limit
            export_format (str): Export format to check against limits

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if limit_value is None:
            return True, ""  # No limit is okay

        # Check positive integer
        if not isinstance(limit_value, int) or limit_value <= 0:
            return False, "Limit must be a positive integer"

        # Check against format-specific limits
        max_for_format = MAX_RESULTS.get(export_format.lower(), 1_000_000)

        if limit_value > max_for_format:
            return False, f"Limit {limit_value:,} exceeds maximum for {export_format} format ({max_for_format:,})"

        return True, ""

    @staticmethod
    def sanitize_category_name(category_name: str) -> str:
        """
        Sanitize category name for safe SQL use

        Args:
            category_name (str): Raw category name

        Returns:
            str: Sanitized category name
        """
        # Remove leading/trailing whitespace
        sanitized = category_name.strip()

        # Replace multiple spaces with single space
        sanitized = re.sub(r'\s+', ' ', sanitized)

        # Convert to lowercase for consistency
        sanitized = sanitized.lower()

        # Replace spaces with underscores
        sanitized = sanitized.replace(' ', '_')

        return sanitized
