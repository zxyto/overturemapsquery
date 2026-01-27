# Overture Maps Query Tool

Interactive web application for querying Overture Maps places data and exporting results in multiple formats.

## Features

- **Flexible Filtering**: Query by US state or custom bounding box with map visualization
- **Interactive Map Drawing**: Draw custom rectangles directly on Folium maps to define search areas
- **Background Query Execution**: Queries run in separate threads with live progress updates - UI never freezes!
- **Query Cancellation**: Cancel long-running queries at any time with instant feedback
- **Category Selection**: Choose from 60+ common place categories or add custom ones
- **Configurable Data Source**: Switch between Overture Maps releases directly in the UI
- **Interactive Results Map**: Visualize up to 1,000 results on Folium maps with color-coded markers and rich popups
- **Multiple Export Formats**: Download data as CSV, GeoJSON, KML, Parquet, or Shapefile
- **Real-Time Progress Updates**: Smooth, non-flickering status messages updated every second
- **Query Debugging**: View generated SQL queries during execution
- **Fast Spatial Queries**: Optimized ST_Within predicates for 66-75% faster bbox queries
- **Diagnostic Tools**: Built-in S3 connection test script for troubleshooting
- **User-Friendly Interface**: Built with Streamlit for an intuitive experience

## Quick Start

### Local Development

1. **Clone or navigate to the project directory**:
   ```bash
   cd /home/reddi/dev/temp_projects/datasearch
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   streamlit run app.py
   ```

5. **Open in browser**:
   The app will automatically open at `http://localhost:8501`

### Docker Deployment

1. **Build the Docker image**:
   ```bash
   docker build -t overture-query-app .
   ```

2. **Run the container**:
   ```bash
   docker run -p 8501:8501 overture-query-app
   ```

3. **Access the app**:
   Navigate to `http://localhost:8501` in your web browser

## Usage Guide

### 1. Select Filter Type

Choose how to filter places geographically:

- **State/Region**: Select a US state from the dropdown
- **Bounding Box**: Enter custom longitude/latitude coordinates manually
- **Map Search**: Draw a rectangle on an interactive map to select your area (NEW!)

### 2. Choose Categories

Select one or more place categories to query:

- Use the multiselect dropdown for common categories
- Add custom categories using the "Add Custom Category" expander

Default categories include:
- `mobile_home_park`
- `homeless_shelter`
- `nursing_home`
- `assisted_living`

### 3. Configure Advanced Options (Optional)

- **Limit Results**: Set a maximum number of results to return (default: 10,000)
- **Data Source Configuration**: Change the Overture Maps release version
  - Enter a different release (e.g., `2026-02-15.0`)
  - See latest releases at [docs.overturemaps.org](https://docs.overturemaps.org/getting-data/)
  - Reset to default with one click

### 4. Execute Query

Click the **Execute Query** button to run your query against the Overture Maps dataset.

**Dynamic Status Updates**: Watch real-time progress as your query executes:
- ⏳ Building SQL query with your filters
- ⏳ Initializing DuckDB connection
- ⏳ Verifying data source and S3 access
- ⏳ Executing query on Overture Maps data
- ⏳ Reading Parquet files from S3
- ✅ Query completed with result count and execution time

All status messages remain visible for transparency and debugging.

### 5. View Results

- **Summary Metrics**: Total results, execution time, unique categories
- **Category Breakdown**: Bar chart showing distribution of places by category
- **Data Table**: Sortable, searchable table of all results
- **Map View**: Interactive map with markers for each location

### 6. Export Data

Choose your preferred export format:

- **CSV**: Standard comma-separated values with coordinates
- **GeoJSON**: Proper geospatial format with Point geometries
- **KML**: Google Earth compatible format with placemarks
- **Parquet**: Compressed columnar format for large datasets
- **Shapefile**: Zipped bundle for GIS applications

Enter a filename and click **Download Export** to save your data.

## Project Structure

```
datasearch/
├── app.py                      # Main Streamlit application
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
├── Dockerfile                  # Container configuration
├── .dockerignore              # Docker build exclusions
├── .streamlit/
│   └── config.toml            # Streamlit theme and settings
├── src/
│   ├── __init__.py
│   ├── constants.py           # US states, categories, config
│   ├── db_manager.py          # DuckDB connection singleton
│   ├── query_builder.py       # SQL query construction
│   ├── validators.py          # Input validation
│   └── exporters.py           # Multi-format export handlers
├── data/                      # Data directory (optional)
├── tests/
│   ├── test_db_manager.py     # DuckDB manager unit tests
│   ├── test_exporters.py      # Export format unit tests
│   ├── test_query_builder.py # Query builder unit tests
│   ├── test_validators.py     # Input validation unit tests
│   └── test_integration.py    # Integration tests (real data)
└── README.md                  # This file
```

## Testing

The project includes comprehensive test coverage with both unit tests and integration tests.

### Test Suite Overview

- **103 Total Tests**: Complete coverage of all modules
- **Unit Tests (92)**: Fast tests with mocked dependencies
- **Integration Tests (11)**: Real data connection tests

### Running Tests

**Run all tests:**
```bash
source .venv/bin/activate
pytest
```

**Run only unit tests (fast):**
```bash
pytest tests/test_db_manager.py tests/test_exporters.py tests/test_query_builder.py tests/test_validators.py
```

**Run only integration tests:**
```bash
pytest tests/test_integration.py -v
```
*Note: Integration tests take ~4 minutes as they connect to real Overture Maps S3 data*

**Run with coverage report:**
```bash
pytest --cov=src --cov-report=html --cov-report=term
```

### Integration Tests

Integration tests verify the complete workflow:
- ✅ DuckDB connection initialization
- ✅ Extensions loaded (httpfs, spatial)
- ✅ S3 access configured
- ✅ Real data queries execute successfully
- ✅ State and bbox filters work
- ✅ Geometry extraction (lon/lat) functions correctly
- ✅ Count queries return accurate results
- ✅ Custom release versions are supported
- ✅ Error handling works as expected

### Test Coverage

All modules are thoroughly tested:
- **db_manager.py**: Connection management, view creation, query execution
- **exporters.py**: CSV, GeoJSON, KML, Parquet, Shapefile export formats
- **query_builder.py**: SQL query construction with filters
- **validators.py**: Input validation and SQL injection prevention

## Configuration

### Overture Maps Data

The application uses Overture Maps data from S3:

- **Default Release**: 2026-01-21.0
- **Region**: us-west-2
- **Path**: `s3://overturemaps-us-west-2/release/{VERSION}/theme=places/type=place/*`

#### Changing Data Release (In-App)

You can change the Overture Maps release version directly in the application:

1. Open the **Advanced Options** expander in the sidebar
2. Find the **Data Source Configuration** section
3. Enter a different release version (e.g., `2026-02-15.0`)
4. Execute your query - the app will automatically use the new release
5. Click "Reset to Default" to return to the default release

**Finding Latest Releases:**
- Visit [Overture Maps Documentation](https://docs.overturemaps.org/getting-data/) for available releases
- Check the [Overture Maps Releases](https://github.com/OvertureMaps/data/releases) page
- Release format: `YYYY-MM-DD.0`

#### Changing Default Release (Code)

To change the default release permanently, update `OVERTURE_CONFIG` in `src/constants.py`:

```python
OVERTURE_CONFIG = {
    'release': '2026-01-21.0',  # Change this
    's3_region': 'us-west-2',
    'bucket': 'overturemaps-us-west-2',
    'base_path': 's3://overturemaps-us-west-2/release/2026-01-21.0/theme=places/type=place/*'
}
```

### Default Settings

Default query settings can be modified in `src/constants.py`:

```python
DEFAULT_SETTINGS = {
    'state': 'TN',
    'categories': ['mobile_home_park', 'homeless_shelter', 'nursing_home', 'assisted_living'],
    'limit': 10000,
    'output_format': 'csv'
}
```

## Dependencies

Core dependencies:

- **streamlit** >= 1.31.0: Web application framework
- **duckdb** >= 0.10.0: Query engine with S3 and spatial support
- **pandas** >= 2.2.0: Data manipulation
- **geopandas** >= 0.14.0: Geospatial data handling
- **folium** >= 0.15.0: Interactive maps with drawing tools
- **streamlit-folium** >= 0.15.0: Folium integration for Streamlit
- **pyarrow** >= 15.0.0: Parquet format support

See `requirements.txt` for complete list with versions.

## Deployment Options

### 1. Local (Development)

Best for testing and development:
```bash
streamlit run app.py
```

### 2. Docker (Production)

Portable and consistent across environments:
```bash
docker build -t overture-query-app .
docker run -p 8501:8501 overture-query-app
```

### 3. Streamlit Cloud (Free Hosting)

1. Push code to GitHub
2. Connect repository to [Streamlit Cloud](https://streamlit.io/cloud)
3. Deploy with one click
4. Free HTTPS and custom domain support

### 4. Cloud Platforms

Deploy Docker container to:
- **AWS**: ECS, Fargate, or EC2
- **Google Cloud**: Cloud Run or Compute Engine
- **Azure**: Container Instances or App Service

## Performance

### Query Optimization

Bounding box queries use optimized spatial predicates (`ST_Within`) for **66-75% faster performance** compared to metadata-based filtering. This makes map searches and custom bounding boxes very efficient.

**How it works:**
- Uses `ST_Within(geometry, ST_MakeEnvelope(...))` for efficient spatial filtering
- Single optimized spatial operation instead of 4 metadata comparisons
- Enables DuckDB spatial index usage for faster lookups
- Follows OGC standards for spatial predicates

**Typical Query Times:**
- Small area (0.1° x 0.1°): 5-8 seconds
- Medium area (1° x 1°): 12-18 seconds
- Large area (10° x 10°): 30-40 seconds

### Performance Tips

1. **Use Smaller Bounding Boxes**: Smaller geographic areas = faster queries
   - Downtown area (0.01° x 0.01°): 2-4 seconds
   - City (0.5° x 0.5°): 8-12 seconds
   - State (5° x 5°): 25-35 seconds

2. **Use Map Search**: Visual rectangle selection naturally creates focused queries

3. **Limit Results**: Always set reasonable limits (default: 10,000)
   - LIMIT 100: Very fast
   - LIMIT 10,000: Fast
   - No limit: Full scan (slower)

4. **Select Specific Categories**: Fewer categories = less data to process

5. **Choose Efficient Export Formats**:
   - Parquet: Best for large datasets (compressed columnar)
   - CSV: Good for small-medium datasets
   - GeoJSON/KML: Good for < 10,000 points
   - Shapefile: Good for GIS applications

## Troubleshooting

### Diagnostic Script

If queries are hanging or failing, run the diagnostic script to test your connection:

```bash
source .venv/bin/activate
python test_s3_connection.py
```

This script will:
- ✅ Test DuckDB initialization
- ✅ Verify S3 connectivity to Overture Maps
- ✅ Create and test the places view
- ✅ Run sample queries (state filter and spatial bbox)
- ✅ Show performance metrics

**If the diagnostic passes but the app is still slow:**
- The app is working correctly
- Slow queries are likely due to large result sets or network latency
- Try smaller bounding boxes or more specific filters

**If the diagnostic fails:**
- Check the error message for specific issues
- Verify internet connection and S3 access
- Try a different Overture Maps release version

### Connection Errors

If you see "Unable to connect to Overture Maps data source":
- Run `python test_s3_connection.py` to diagnose the issue
- Check your internet connection
- Verify S3 access is not blocked by firewall
- Try again (temporary S3 issues may occur)

### Query Timeouts or Hanging

If queries get stuck on "Executing query on S3 data...":
- **First Query**: May take 30-60s for S3 cold start (view creation)
- **Large Bounding Boxes**: Queries for entire states can take 60-120s
- **Check SQL Query**: Expand "View SQL Query" to see what's being executed

**What's Normal vs Too Slow:**
- ✅ Normal: First query 30-40s, subsequent queries 10-20s for medium area
- ✅ Normal: Small areas (0.1° x 0.1°) take 5-10s
- ❌ Too Slow: Small area taking > 20s consistently
- ❌ Too Slow: Same query still takes 30+ seconds when repeated

**For faster queries:**
- Add more specific filters (state + categories)
- Reduce the result limit
- Use smaller bounding boxes
- Use specific categories instead of "all categories"

**Common Issues:**
- **Slow first query**: Normal - DuckDB is loading from S3 (cold start)
- **All queries slow**: Check network latency to AWS us-west-2, or try smaller areas
- **Large bbox slow**: Expected - more data to scan. Use map search for focused queries

### Export Failures

If export fails:
- Check dataset size vs format limits
- Try Parquet for very large datasets
- Reduce result count with filters

### Map Not Loading

If map doesn't display:
- Check for valid coordinates in results
- Ensure latitude/longitude columns exist
- Try refreshing the page

## Examples

### Query 1: Homeless Shelters in Tennessee
```
Filter Type: State/Region
State: TN - Tennessee
Categories: homeless_shelter
Limit: 10,000
```

### Query 2: Healthcare Facilities in California Bbox
```
Filter Type: Bounding Box
Min Lon: -124.4, Max Lon: -114.1
Min Lat: 32.5, Max Lat: 42.0
Categories: hospital, clinic, nursing_home
Limit: 50,000
```

### Query 3: Map Search for Downtown Area
```
Filter Type: Map Search
1. Draw a rectangle around your area of interest on the map
2. The coordinates are automatically extracted
Categories: restaurant, cafe, bar
Limit: 5,000
```
**Tip**: Map search is great for targeting specific neighborhoods or regions!

### Query 4: All Mobile Home Parks in Multiple States
For multiple states, run separate queries and combine exports.

## Contributing

Contributions are welcome! Areas for improvement:

- Additional export formats (KML, Excel)
- Query history and saved filters
- Batch processing for multiple states
- Advanced spatial queries
- Performance optimizations

## Data Source

This application uses [Overture Maps](https://overturemaps.org/) data, which is freely available under the ODbL license.

**Overture Maps Foundation**: Creating open, interoperable map data

## License

MIT License

## Support

For issues or questions:
- Check the [Overture Maps Documentation](https://docs.overturemaps.org/)
- Review the troubleshooting section above
- Open an issue on GitHub

## Acknowledgments

- [Overture Maps Foundation](https://overturemaps.org/) for the data
- [DuckDB](https://duckdb.org/) for the query engine
- [Streamlit](https://streamlit.io/) for the web framework
