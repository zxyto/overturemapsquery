"""
Data Export Handlers for Multiple Formats
Supports CSV, GeoJSON, KML, Parquet, and Shapefile exports
"""

import json
import io
import zipfile
from abc import ABC, abstractmethod
from typing import BinaryIO
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


class BaseExporter(ABC):
    """Abstract base class for export formats"""

    @abstractmethod
    def export(self, df: pd.DataFrame, buffer: BinaryIO) -> None:
        """
        Export DataFrame to buffer

        Args:
            df (pd.DataFrame): Data to export
            buffer (BinaryIO): Output buffer
        """
        pass

    @abstractmethod
    def get_mime_type(self) -> str:
        """
        Get MIME type for this format

        Returns:
            str: MIME type string
        """
        pass

    @abstractmethod
    def get_file_extension(self) -> str:
        """
        Get file extension for this format

        Returns:
            str: File extension (e.g., 'csv', 'json')
        """
        pass


class CSVExporter(BaseExporter):
    """Standard CSV with coordinates"""

    def export(self, df: pd.DataFrame, buffer: BinaryIO) -> None:
        """Export to CSV format"""
        # Convert buffer to text mode for pandas
        text_buffer = io.TextIOWrapper(buffer, encoding='utf-8', newline='', write_through=True)
        df.to_csv(text_buffer, index=False)
        text_buffer.detach()  # Detach to prevent closing the underlying buffer
        buffer.seek(0)

    def get_mime_type(self) -> str:
        return 'text/csv'

    def get_file_extension(self) -> str:
        return 'csv'


class GeoJSONExporter(BaseExporter):
    """GeoJSON FeatureCollection with proper geometry"""

    def export(self, df: pd.DataFrame, buffer: BinaryIO) -> None:
        """Export to GeoJSON format"""
        if df.empty:
            # Empty FeatureCollection
            geojson = {
                "type": "FeatureCollection",
                "features": []
            }
        else:
            # Create features list
            features = []

            for _, row in df.iterrows():
                # Skip rows without coordinates
                if pd.isna(row.get('longitude')) or pd.isna(row.get('latitude')):
                    continue

                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(row['longitude']), float(row['latitude'])]
                    },
                    "properties": {
                        "id": str(row.get('id', '')),
                        "name": str(row.get('name', '')),
                        "category": str(row.get('category', '')),
                        "state": str(row.get('state', '')),
                        "city": str(row.get('city', ''))
                    }
                }
                features.append(feature)

            geojson = {
                "type": "FeatureCollection",
                "features": features
            }

        # Write to buffer
        text_buffer = io.TextIOWrapper(buffer, encoding='utf-8', write_through=True)
        json.dump(geojson, text_buffer, indent=2)
        text_buffer.detach()  # Detach to prevent closing the underlying buffer
        buffer.seek(0)

    def get_mime_type(self) -> str:
        return 'application/geo+json'

    def get_file_extension(self) -> str:
        return 'geojson'


class ParquetExporter(BaseExporter):
    """Efficient Parquet format for large datasets"""

    def export(self, df: pd.DataFrame, buffer: BinaryIO) -> None:
        """Export to Parquet format"""
        df.to_parquet(buffer, compression='snappy', index=False)
        buffer.seek(0)

    def get_mime_type(self) -> str:
        return 'application/octet-stream'

    def get_file_extension(self) -> str:
        return 'parquet'


class KMLExporter(BaseExporter):
    """KML format for Google Earth and mapping applications"""

    def export(self, df: pd.DataFrame, buffer: BinaryIO) -> None:
        """Export to KML format"""
        # Build KML XML structure
        kml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            '<Document>',
            '<name>Overture Maps Places Export</name>',
            '<description>Exported places data from Overture Maps</description>'
        ]

        # Add styles for different categories
        kml_parts.extend([
            '<Style id="defaultStyle">',
            '<IconStyle>',
            '<Icon><href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href></Icon>',
            '</IconStyle>',
            '</Style>'
        ])

        # Add placemarks for each location
        if not df.empty:
            for _, row in df.iterrows():
                # Skip rows without coordinates
                if pd.isna(row.get('longitude')) or pd.isna(row.get('latitude')):
                    continue

                name = str(row.get('name', 'Unknown')).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                category = str(row.get('category', 'N/A')).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                city = str(row.get('city', 'N/A')).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                state = str(row.get('state', 'N/A')).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                placemark = f'''
<Placemark>
    <name>{name}</name>
    <description>
        <![CDATA[
        <b>Category:</b> {category}<br/>
        <b>City:</b> {city}<br/>
        <b>State:</b> {state}
        ]]>
    </description>
    <styleUrl>#defaultStyle</styleUrl>
    <Point>
        <coordinates>{row['longitude']},{row['latitude']},0</coordinates>
    </Point>
</Placemark>'''
                kml_parts.append(placemark)

        # Close document
        kml_parts.extend(['</Document>', '</kml>'])

        # Write to buffer
        kml_content = '\n'.join(kml_parts)
        text_buffer = io.TextIOWrapper(buffer, encoding='utf-8', write_through=True)
        text_buffer.write(kml_content)
        text_buffer.detach()
        buffer.seek(0)

    def get_mime_type(self) -> str:
        return 'application/vnd.google-earth.kml+xml'

    def get_file_extension(self) -> str:
        return 'kml'


class ShapefileExporter(BaseExporter):
    """Zipped shapefile bundle (requires geopandas)"""

    def export(self, df: pd.DataFrame, buffer: BinaryIO) -> None:
        """Export to zipped shapefile format"""
        if df.empty:
            raise ValueError("Cannot export empty dataset to shapefile")

        # Remove rows with missing coordinates
        df_clean = df.dropna(subset=['longitude', 'latitude'])

        if df_clean.empty:
            raise ValueError("No valid coordinates found in dataset")

        # Create GeoDataFrame with Point geometries
        geometry = [Point(xy) for xy in zip(df_clean['longitude'], df_clean['latitude'])]
        gdf = gpd.GeoDataFrame(df_clean, geometry=geometry, crs='EPSG:4326')

        # Shapefiles have field name limitations (10 chars)
        # Rename columns to fit
        gdf = gdf.rename(columns={
            'category': 'cat',
            'longitude': 'lon',
            'latitude': 'lat'
        })

        # Drop geometry columns that are now in the geometry field
        if 'lon' in gdf.columns:
            gdf = gdf.drop(columns=['lon', 'lat'])

        # Create temporary directory for shapefile components
        with io.BytesIO() as temp_buffer:
            # Save to temporary shapefile
            temp_shp_path = '/tmp/export_temp.shp'
            gdf.to_file(temp_shp_path, driver='ESRI Shapefile')

            # Create zip file with all shapefile components
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add all shapefile components
                extensions = ['.shp', '.shx', '.dbf', '.prj', '.cpg']
                for ext in extensions:
                    file_path = temp_shp_path.replace('.shp', ext)
                    try:
                        zipf.write(file_path, f'export{ext}')
                    except FileNotFoundError:
                        # Some extensions might not exist
                        pass

            buffer.seek(0)

    def get_mime_type(self) -> str:
        return 'application/zip'

    def get_file_extension(self) -> str:
        return 'zip'


class ExporterFactory:
    """Factory for creating appropriate exporter"""

    _exporters = {
        'csv': CSVExporter,
        'geojson': GeoJSONExporter,
        'kml': KMLExporter,
        'parquet': ParquetExporter,
        'shapefile': ShapefileExporter
    }

    @classmethod
    def get_exporter(cls, format_name: str) -> BaseExporter:
        """
        Get exporter instance for format

        Args:
            format_name (str): Format name (csv, geojson, parquet, shapefile)

        Returns:
            BaseExporter: Exporter instance

        Raises:
            ValueError: If format not supported
        """
        format_lower = format_name.lower()

        if format_lower not in cls._exporters:
            raise ValueError(f"Unsupported export format: {format_name}")

        return cls._exporters[format_lower]()

    @classmethod
    def get_supported_formats(cls) -> list:
        """
        Get list of supported format names

        Returns:
            list: List of format names
        """
        return list(cls._exporters.keys())


def export_dataframe(df: pd.DataFrame, format_name: str) -> tuple:
    """
    Export DataFrame to specified format

    Args:
        df (pd.DataFrame): Data to export
        format_name (str): Export format

    Returns:
        tuple: (buffer, mime_type, file_extension)
    """
    exporter = ExporterFactory.get_exporter(format_name)

    # Create buffer
    buffer = io.BytesIO()

    # Export to buffer
    exporter.export(df, buffer)

    return buffer, exporter.get_mime_type(), exporter.get_file_extension()
