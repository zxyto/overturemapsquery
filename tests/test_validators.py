"""
Unit tests for input validators
"""

import pytest
from src.validators import InputValidator, ValidationError


class TestStateCodeValidation:
    """Test state code validation"""

    def test_valid_state_code(self):
        is_valid, msg = InputValidator.validate_state_code('TN')
        assert is_valid is True
        assert msg == ""

    def test_valid_state_code_lowercase(self):
        is_valid, msg = InputValidator.validate_state_code('tn')
        assert is_valid is True
        assert msg == ""

    def test_invalid_state_code(self):
        is_valid, msg = InputValidator.validate_state_code('XX')
        assert is_valid is False
        assert "Invalid state code" in msg

    def test_empty_state_code(self):
        is_valid, msg = InputValidator.validate_state_code('')
        assert is_valid is False
        assert "cannot be empty" in msg


class TestBboxValidation:
    """Test bounding box validation"""

    def test_valid_bbox(self):
        is_valid, msg = InputValidator.validate_bbox(-90.3, -81.6, 34.9, 36.7)
        assert is_valid is True
        assert msg == ""

    def test_invalid_longitude_range_min(self):
        is_valid, msg = InputValidator.validate_bbox(-200, -81.6, 34.9, 36.7)
        assert is_valid is False
        assert "longitude" in msg.lower()

    def test_invalid_longitude_range_max(self):
        is_valid, msg = InputValidator.validate_bbox(-90.3, 200, 34.9, 36.7)
        assert is_valid is False
        assert "longitude" in msg.lower()

    def test_invalid_latitude_range_min(self):
        is_valid, msg = InputValidator.validate_bbox(-90.3, -81.6, -100, 36.7)
        assert is_valid is False
        assert "latitude" in msg.lower()

    def test_invalid_latitude_range_max(self):
        is_valid, msg = InputValidator.validate_bbox(-90.3, -81.6, 34.9, 100)
        assert is_valid is False
        assert "latitude" in msg.lower()

    def test_xmin_greater_than_xmax(self):
        is_valid, msg = InputValidator.validate_bbox(-81.6, -90.3, 34.9, 36.7)
        assert is_valid is False
        assert "must be less than" in msg.lower()

    def test_ymin_greater_than_ymax(self):
        is_valid, msg = InputValidator.validate_bbox(-90.3, -81.6, 36.7, 34.9)
        assert is_valid is False
        assert "must be less than" in msg.lower()

    def test_bbox_too_large(self):
        is_valid, msg = InputValidator.validate_bbox(-100, 100, -50, 50)
        assert is_valid is False
        assert "too large" in msg.lower()


class TestCategoryValidation:
    """Test category name validation"""

    def test_valid_category(self):
        is_valid, msg = InputValidator.validate_category('mobile_home_park')
        assert is_valid is True
        assert msg == ""

    def test_valid_category_with_spaces(self):
        is_valid, msg = InputValidator.validate_category('mobile home park')
        assert is_valid is True
        assert msg == ""

    def test_empty_category(self):
        is_valid, msg = InputValidator.validate_category('')
        assert is_valid is False
        assert "cannot be empty" in msg

    def test_sql_injection_attempt(self):
        is_valid, msg = InputValidator.validate_category("'; DROP TABLE places;--")
        assert is_valid is False
        assert "invalid characters" in msg.lower()

    def test_category_too_long(self):
        long_name = 'a' * 101
        is_valid, msg = InputValidator.validate_category(long_name)
        assert is_valid is False
        assert "too long" in msg.lower()

    def test_category_with_invalid_chars(self):
        is_valid, msg = InputValidator.validate_category('category@#$%')
        assert is_valid is False
        assert "can only contain" in msg.lower()


class TestCategoriesListValidation:
    """Test category list validation"""

    def test_valid_categories_list(self):
        categories = ['hospital', 'clinic', 'pharmacy']
        is_valid, msg = InputValidator.validate_categories(categories)
        assert is_valid is True
        assert msg == ""

    def test_empty_categories_list(self):
        is_valid, msg = InputValidator.validate_categories([])
        assert is_valid is False
        assert "at least one category" in msg.lower()

    def test_too_many_categories(self):
        categories = [f'category_{i}' for i in range(51)]
        is_valid, msg = InputValidator.validate_categories(categories)
        assert is_valid is False
        assert "too many" in msg.lower()

    def test_invalid_category_in_list(self):
        categories = ['hospital', 'DROP TABLE', 'clinic']
        is_valid, msg = InputValidator.validate_categories(categories)
        assert is_valid is False


class TestLimitValidation:
    """Test result limit validation"""

    def test_valid_limit(self):
        is_valid, msg = InputValidator.validate_limit(1000, 'csv')
        assert is_valid is True
        assert msg == ""

    def test_none_limit(self):
        is_valid, msg = InputValidator.validate_limit(None, 'csv')
        assert is_valid is True

    def test_negative_limit(self):
        is_valid, msg = InputValidator.validate_limit(-100, 'csv')
        assert is_valid is False
        assert "positive integer" in msg.lower()

    def test_zero_limit(self):
        is_valid, msg = InputValidator.validate_limit(0, 'csv')
        assert is_valid is False
        assert "positive integer" in msg.lower()

    def test_limit_exceeds_format_max(self):
        is_valid, msg = InputValidator.validate_limit(200000, 'geojson')
        assert is_valid is False
        assert "exceeds maximum" in msg.lower()


class TestSanitization:
    """Test category name sanitization"""

    def test_sanitize_removes_whitespace(self):
        result = InputValidator.sanitize_category_name('  mobile_home  ')
        assert result == 'mobile_home'

    def test_sanitize_converts_to_lowercase(self):
        result = InputValidator.sanitize_category_name('Mobile_Home_Park')
        assert result == 'mobile_home_park'

    def test_sanitize_replaces_spaces(self):
        result = InputValidator.sanitize_category_name('mobile home park')
        assert result == 'mobile_home_park'

    def test_sanitize_multiple_spaces(self):
        result = InputValidator.sanitize_category_name('mobile   home   park')
        assert result == 'mobile_home_park'
