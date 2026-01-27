"""
Unit tests for data exporters
"""

import pytest
import pandas as pd
import io
import json
from src.exporters import (
    CSVExporter,
    GeoJSONExporter,
    KMLExporter,
    ParquetExporter,
    ExporterFactory,
    export_dataframe
)


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing"""
    return pd.DataFrame({
        'id': ['id1', 'id2', 'id3'],
        'name': ['Place 1', 'Place 2', 'Place 3'],
        'category': ['hospital', 'clinic', 'pharmacy'],
        'state': ['TN', 'TN', 'CA'],
        'city': ['Memphis', 'Nashville', 'Los Angeles'],
        'longitude': [-90.05, -86.78, -118.24],
        'latitude': [35.15, 36.16, 34.05]
    })


@pytest.fixture
def empty_dataframe():
    """Create an empty DataFrame"""
    return pd.DataFrame()


class TestCSVExporter:
    """Test CSV export functionality"""

    def test_csv_export(self, sample_dataframe):
        exporter = CSVExporter()
        buffer = io.BytesIO()

        exporter.export(sample_dataframe, buffer)
        buffer.seek(0)

        # Read back and verify
        result = pd.read_csv(buffer)
        assert len(result) == 3
        assert 'name' in result.columns
        assert 'longitude' in result.columns

    def test_csv_mime_type(self):
        exporter = CSVExporter()
        assert exporter.get_mime_type() == 'text/csv'

    def test_csv_extension(self):
        exporter = CSVExporter()
        assert exporter.get_file_extension() == 'csv'

    def test_csv_export_empty(self, empty_dataframe):
        exporter = CSVExporter()
        buffer = io.BytesIO()

        # Should not raise error during export
        exporter.export(empty_dataframe, buffer)

        # Verify something was written
        buffer.seek(0)
        content = buffer.read().decode('utf-8')
        # Empty dataframe produces empty CSV (just newline or empty)
        assert content == "" or content == "\n"


class TestGeoJSONExporter:
    """Test GeoJSON export functionality"""

    def test_geojson_export(self, sample_dataframe):
        exporter = GeoJSONExporter()
        buffer = io.BytesIO()

        exporter.export(sample_dataframe, buffer)
        buffer.seek(0)

        # Read and parse JSON
        text = buffer.read().decode('utf-8')
        geojson = json.loads(text)

        assert geojson['type'] == 'FeatureCollection'
        assert len(geojson['features']) == 3

        # Check first feature
        feature = geojson['features'][0]
        assert feature['type'] == 'Feature'
        assert feature['geometry']['type'] == 'Point'
        assert len(feature['geometry']['coordinates']) == 2
        assert feature['properties']['name'] == 'Place 1'

    def test_geojson_coordinates_format(self, sample_dataframe):
        """Verify coordinates are [lon, lat] not [lat, lon]"""
        exporter = GeoJSONExporter()
        buffer = io.BytesIO()

        exporter.export(sample_dataframe, buffer)
        buffer.seek(0)

        geojson = json.loads(buffer.read().decode('utf-8'))
        coords = geojson['features'][0]['geometry']['coordinates']

        # Longitude should be first (around -90)
        assert coords[0] == pytest.approx(-90.05)
        # Latitude should be second (around 35)
        assert coords[1] == pytest.approx(35.15)

    def test_geojson_empty(self, empty_dataframe):
        exporter = GeoJSONExporter()
        buffer = io.BytesIO()

        exporter.export(empty_dataframe, buffer)
        buffer.seek(0)

        geojson = json.loads(buffer.read().decode('utf-8'))
        assert geojson['type'] == 'FeatureCollection'
        assert geojson['features'] == []

    def test_geojson_mime_type(self):
        exporter = GeoJSONExporter()
        assert exporter.get_mime_type() == 'application/geo+json'

    def test_geojson_extension(self):
        exporter = GeoJSONExporter()
        assert exporter.get_file_extension() == 'geojson'

    def test_geojson_skips_missing_coordinates(self):
        """Test that rows with NaN coordinates are skipped"""
        df = pd.DataFrame({
            'id': ['id1', 'id2'],
            'name': ['Place 1', 'Place 2'],
            'category': ['hospital', 'clinic'],
            'longitude': [-90.05, None],
            'latitude': [35.15, 36.16]
        })

        exporter = GeoJSONExporter()
        buffer = io.BytesIO()

        exporter.export(df, buffer)
        buffer.seek(0)

        geojson = json.loads(buffer.read().decode('utf-8'))
        # Should only have 1 feature (second one skipped due to missing lon)
        assert len(geojson['features']) == 1


class TestKMLExporter:
    """Test KML export functionality"""

    def test_kml_export(self, sample_dataframe):
        exporter = KMLExporter()
        buffer = io.BytesIO()

        exporter.export(sample_dataframe, buffer)
        buffer.seek(0)

        # Read and verify KML structure
        content = buffer.read().decode('utf-8')

        assert '<?xml version="1.0" encoding="UTF-8"?>' in content
        assert '<kml xmlns="http://www.opengis.net/kml/2.2">' in content
        assert '<Document>' in content
        assert '</Document>' in content
        assert '<Placemark>' in content
        assert 'Place 1' in content

    def test_kml_coordinates(self, sample_dataframe):
        """Verify coordinates are in KML format (lon,lat,alt)"""
        exporter = KMLExporter()
        buffer = io.BytesIO()

        exporter.export(sample_dataframe, buffer)
        buffer.seek(0)

        content = buffer.read().decode('utf-8')

        # Check for first location coordinates (lon,lat,0)
        assert '-90.05,35.15,0' in content

    def test_kml_empty(self, empty_dataframe):
        exporter = KMLExporter()
        buffer = io.BytesIO()

        exporter.export(empty_dataframe, buffer)
        buffer.seek(0)

        content = buffer.read().decode('utf-8')
        assert '<kml' in content
        assert '<Document>' in content
        # Should not have any placemarks
        assert '<Placemark>' not in content

    def test_kml_mime_type(self):
        exporter = KMLExporter()
        assert exporter.get_mime_type() == 'application/vnd.google-earth.kml+xml'

    def test_kml_extension(self):
        exporter = KMLExporter()
        assert exporter.get_file_extension() == 'kml'

    def test_kml_escapes_xml_characters(self):
        """Test that special XML characters are escaped"""
        df = pd.DataFrame({
            'id': ['id1'],
            'name': ['Place <1> & More'],
            'category': ['hospital'],
            'state': ['TN'],
            'city': ['City <Test>'],
            'longitude': [-90.05],
            'latitude': [35.15]
        })

        exporter = KMLExporter()
        buffer = io.BytesIO()

        exporter.export(df, buffer)
        buffer.seek(0)

        content = buffer.read().decode('utf-8')

        # Check that < and & are escaped
        assert '&lt;' in content
        assert '&amp;' in content
        assert 'Place <1>' not in content  # Should be escaped

    def test_kml_skips_missing_coordinates(self):
        """Test that rows with NaN coordinates are skipped"""
        df = pd.DataFrame({
            'id': ['id1', 'id2'],
            'name': ['Place 1', 'Place 2'],
            'category': ['hospital', 'clinic'],
            'longitude': [-90.05, None],
            'latitude': [35.15, 36.16]
        })

        exporter = KMLExporter()
        buffer = io.BytesIO()

        exporter.export(df, buffer)
        buffer.seek(0)

        content = buffer.read().decode('utf-8')

        # Should only have 1 placemark
        assert content.count('<Placemark>') == 1


class TestParquetExporter:
    """Test Parquet export functionality"""

    def test_parquet_export(self, sample_dataframe):
        exporter = ParquetExporter()
        buffer = io.BytesIO()

        exporter.export(sample_dataframe, buffer)
        buffer.seek(0)

        # Read back and verify
        result = pd.read_parquet(buffer)
        assert len(result) == 3
        assert 'name' in result.columns

    def test_parquet_mime_type(self):
        exporter = ParquetExporter()
        assert exporter.get_mime_type() == 'application/octet-stream'

    def test_parquet_extension(self):
        exporter = ParquetExporter()
        assert exporter.get_file_extension() == 'parquet'

    def test_parquet_preserves_datatypes(self, sample_dataframe):
        """Verify Parquet preserves data types"""
        exporter = ParquetExporter()
        buffer = io.BytesIO()

        exporter.export(sample_dataframe, buffer)
        buffer.seek(0)

        result = pd.read_parquet(buffer)
        # Longitude should still be float
        assert result['longitude'].dtype == 'float64'


class TestExporterFactory:
    """Test exporter factory"""

    def test_get_csv_exporter(self):
        exporter = ExporterFactory.get_exporter('csv')
        assert isinstance(exporter, CSVExporter)

    def test_get_geojson_exporter(self):
        exporter = ExporterFactory.get_exporter('geojson')
        assert isinstance(exporter, GeoJSONExporter)

    def test_get_kml_exporter(self):
        exporter = ExporterFactory.get_exporter('kml')
        assert isinstance(exporter, KMLExporter)

    def test_get_parquet_exporter(self):
        exporter = ExporterFactory.get_exporter('parquet')
        assert isinstance(exporter, ParquetExporter)

    def test_case_insensitive(self):
        exporter1 = ExporterFactory.get_exporter('CSV')
        exporter2 = ExporterFactory.get_exporter('csv')
        assert type(exporter1) == type(exporter2)

    def test_unsupported_format(self):
        with pytest.raises(ValueError, match="Unsupported export format"):
            ExporterFactory.get_exporter('pdf')

    def test_get_supported_formats(self):
        formats = ExporterFactory.get_supported_formats()
        assert 'csv' in formats
        assert 'geojson' in formats
        assert 'kml' in formats
        assert 'parquet' in formats


class TestExportDataFrame:
    """Test the main export_dataframe function"""

    def test_export_csv(self, sample_dataframe):
        buffer, mime_type, extension = export_dataframe(sample_dataframe, 'csv')

        assert mime_type == 'text/csv'
        assert extension == 'csv'
        assert buffer is not None
        assert buffer.tell() == 0  # Should be at start

    def test_export_geojson(self, sample_dataframe):
        buffer, mime_type, extension = export_dataframe(sample_dataframe, 'geojson')

        assert mime_type == 'application/geo+json'
        assert extension == 'geojson'

        # Verify it's valid JSON
        geojson = json.loads(buffer.read().decode('utf-8'))
        assert geojson['type'] == 'FeatureCollection'

    def test_export_kml(self, sample_dataframe):
        buffer, mime_type, extension = export_dataframe(sample_dataframe, 'kml')

        assert mime_type == 'application/vnd.google-earth.kml+xml'
        assert extension == 'kml'

        # Verify it's valid KML
        content = buffer.read().decode('utf-8')
        assert '<kml' in content
        assert '<Placemark>' in content

    def test_export_parquet(self, sample_dataframe):
        buffer, mime_type, extension = export_dataframe(sample_dataframe, 'parquet')

        assert mime_type == 'application/octet-stream'
        assert extension == 'parquet'

        # Verify it can be read back
        result = pd.read_parquet(buffer)
        assert len(result) == 3
