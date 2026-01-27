# Overture Maps Query Tool - Features

## Dynamic Status Updates

The application now provides real-time, granular status updates during query execution, making it easy to track progress and understand what's happening.

### Query Execution Progress

When you click "Execute Query", you'll see a dynamic status panel that shows:

```
⏳ Building SQL query...
✓ Query built: 4 categories, State: TN

⏳ Initializing DuckDB connection...
✓ DuckDB connection ready

⏳ Verifying data source (release: 2026-01-21.0)...
✓ Data source configured: S3 bucket (us-west-2)

⏳ Executing query on Overture Maps data...
⏳ Reading Parquet files from S3...
✓ Query returned 175 results

⏳ Finalizing 175 results...

✅ Query completed! Found 175 results in 8.42s
```

### Export Progress

When exporting data, you'll see:

```
⏳ Converting 175 rows to CSV format...
✓ Export complete: 12.3 KB

✅ Export ready! (175 rows, 12.3 KB)
```

### Benefits

- **Transparency**: See exactly what the app is doing at each step
- **Progress Tracking**: Know if the query is stuck or just processing large data
- **Diagnostics**: Easier to identify where issues occur
- **Confidence**: Visual feedback that the app is working

### Status Indicators

- ⏳ = In progress
- ✓ = Step completed
- ✅ = All done
- ❌ = Error occurred

## Key Features

### 1. Multi-Step Status Updates

Instead of a single "Connecting..." spinner, the app now shows:
1. **Building SQL query** - Constructing the query with your filters
2. **Initializing DuckDB** - Setting up the database connection
3. **Verifying data source** - Configuring S3 access and extensions
4. **Executing query** - Running the query against Overture Maps data
5. **Reading Parquet files** - Fetching data from S3
6. **Processing results** - Converting to DataFrame format

### 2. Contextual Information

Status messages include relevant details:
- Number of categories selected
- Filter type and values (state code, bbox coordinates)
- Data release version being used
- S3 bucket region
- Result count
- Execution time
- Export file size

### 3. Expandable Status Panel

The status panel is expanded by default so you can see all progress steps, but can be collapsed to save space.

### 4. Persistent History

All status messages remain visible even after completion, so you can review what happened if there were any issues.

## Usage Examples

### Example 1: State Query

```
User Action: Select Tennessee, homeless_shelter category, click Execute Query

Status Updates:
⏳ Building SQL query...
✓ Query built: 1 categories, State: TN
⏳ Initializing DuckDB connection...
✓ DuckDB connection ready
⏳ Verifying data source (release: 2026-01-21.0)...
✓ Data source configured: S3 bucket (us-west-2)
⏳ Executing query on Overture Maps data...
⏳ Reading Parquet files from S3...
✓ Query returned 52 results
⏳ Finalizing 52 results...
✅ Query completed! Found 52 results in 7.21s
```

### Example 2: Bounding Box Query

```
User Action: Enter custom bbox, multiple categories, click Execute Query

Status Updates:
⏳ Building SQL query...
✓ Query built: 3 categories, Bbox: [-90.31, 34.98] to [-81.65, 36.68]
⏳ Initializing DuckDB connection...
✓ DuckDB connection ready
⏳ Verifying data source (release: 2026-01-21.0)...
✓ Data source configured: S3 bucket (us-west-2)
⏳ Executing query on Overture Maps data...
⏳ Reading Parquet files from S3...
✓ Query returned 423 results
⏳ Finalizing 423 results...
✅ Query completed! Found 423 results in 12.54s
```

### Example 3: Map Search Query

```
User Action: Draw rectangle on map, select categories, click Execute Query

Status Updates:
⏳ Building SQL query...
✓ Query built: 2 categories, Map Search area
⏳ Initializing DuckDB connection...
✓ DuckDB connection ready
⏳ Verifying data source (release: 2026-01-21.0)...
✓ Data source configured: S3 bucket (us-west-2)
⏳ Executing query on Overture Maps data...
⏳ Reading Parquet files from S3...
✓ Query returned 89 results
⏳ Finalizing 89 results...
✅ Query completed! Found 89 results in 9.33s
```

### Example 4: Large Result Export

```
User Action: Export 10,000 results to GeoJSON

Status Updates:
⏳ Converting 10,000 rows to GEOJSON format...
✓ Export complete: 2847.3 KB
✅ Export ready! (10,000 rows, 2847.3 KB)
```

## Technical Implementation

The dynamic status updates are implemented using:
- **Streamlit's `st.status()` component** - Provides expandable status container
- **Progressive updates** - Each step updates the label and adds detail messages
- **Real-time feedback** - Updates appear as they happen, not at the end
- **Context preservation** - All steps remain visible for debugging

## Performance Impact

The status updates add minimal overhead:
- Status message updates: <1ms each
- No impact on query execution time
- Slightly more UI rendering, but negligible for user experience

The benefits of transparency far outweigh any minimal performance cost.
