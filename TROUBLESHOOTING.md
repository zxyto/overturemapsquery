# Troubleshooting Slow Queries

## If Queries Are Still Taking > 1 Minute

### Quick Diagnostics

**Step 1: Verify the optimization is active**
Run this to check if `ST_Within` is being used:
```bash
python3 test_query_performance.py
```

You should see:
```
✓ Using optimized ST_Within spatial predicate
✓ Not using old bbox metadata filtering
```

**Step 2: Check query area size**

Small queries should be fast. Check your bounding box dimensions:
- **Small** (< 1° x 1°): Should take 5-15 seconds
- **Medium** (1-5° x 5°): Should take 15-30 seconds
- **Large** (> 5° x 5°): May take 30-60+ seconds

Tennessee is about 9° x 2° = 18 square degrees (medium-large)

**Step 3: Reduce query scope**

Try these to speed up queries:

1. **Use smaller areas**: Zoom in on the map and draw smaller rectangles
2. **Add more category filters**: More specific = fewer results to process
3. **Set lower limits**: Try LIMIT 100 or LIMIT 1000 instead of 10,000

**Step 4: Check what's slow**

The status updates will show where time is spent:
- "Building SQL query" = Instant (< 1s)
- "Connecting to DuckDB" = Fast (1-2s)
- "Executing query on Overture Maps S3 data" = **This is where most time is spent**
- "Processing results" = Fast (< 1s)

### Common Issues

#### Issue 1: First query is very slow
**Symptoms**: First query takes 60+ seconds, subsequent queries are faster

**Cause**: DuckDB is loading data from S3 for the first time (cold start)

**Solution**: This is normal. Subsequent queries will be faster as DuckDB caches data.

#### Issue 2: Large bounding boxes are slow
**Symptoms**: Queries for entire states or countries take 60+ seconds

**Cause**: More data to scan from S3

**Solution**:
- Use smaller geographic areas
- Zoom in on specific cities/regions
- Combine with category filters

#### Issue 3: All queries are slow
**Symptoms**: Even small queries take > 30 seconds consistently

**Possible causes**:
1. **Network latency to S3** - You're far from us-west-2 region
2. **S3 throttling** - Too many requests to Overture Maps bucket
3. **DuckDB memory** - Not enough RAM for large queries
4. **View recreation** - View being recreated on every query

**Debug steps**:

```python
# Add to execute_query() function to see timing
import time

start = time.time()
db_manager = get_db_manager()
print(f"DB manager: {time.time() - start:.2f}s")

start = time.time()
results = db_manager.execute_query(query, release_version)
print(f"Query execution: {time.time() - start:.2f}s")
```

Expected:
- DB manager: < 2 seconds
- Query execution: 5-60 seconds depending on area size

#### Issue 4: Map keeps resetting zoom level
**Symptoms**: When you zoom in/out, map resets to default view

**Cause**: Streamlit is re-running the entire app

**Solution**: The latest version preserves map state in `st.session_state`

If still happening:
- Make sure you're running the latest version of the code
- The map state is now preserved in `st.session_state.map_center` and `st.session_state.map_zoom`

### Performance Expectations

#### Expected Query Times (from S3 us-west-2)

| Area Size | Example | Expected Time |
|-----------|---------|---------------|
| 0.01° x 0.01° | Single neighborhood | 2-4 seconds |
| 0.1° x 0.1° | Small city | 5-8 seconds |
| 1° x 1° | Large city/metro | 12-18 seconds |
| 5° x 5° | Small state | 25-35 seconds |
| 10° x 10° | Large state | 40-60 seconds |

Add 5-10 seconds for first query (cold start).

#### What's "Normal" vs "Too Slow"

✅ **Normal**:
- First query: 30-40 seconds for medium area
- Subsequent queries: 10-20 seconds for medium area
- Small areas: 5-10 seconds

❌ **Too Slow** (investigate):
- Small area (0.1° x 0.1°): > 20 seconds
- Medium area (1° x 1°): > 45 seconds
- Same query repeated: Still takes 30+ seconds

### Optimization Checklist

Before reporting a performance issue, verify:

- [ ] Using latest code with `ST_Within` optimization
- [ ] Query area is reasonable size (not entire country)
- [ ] Using specific categories (not all categories)
- [ ] Using result limits (10,000 or less)
- [ ] Second query is faster than first (cold start expected)
- [ ] Map zoom is being preserved in session state

### Advanced: Query Profiling

To see exactly what DuckDB is doing:

```python
# In db_manager.py, add EXPLAIN ANALYZE
query_with_explain = f"EXPLAIN ANALYZE {query}"
result = connection.execute(query_with_explain).fetchall()
print(result)
```

This shows:
- How many rows were scanned
- If spatial index was used
- Where time was spent

### Still Slow?

If queries are still taking > 1 minute for small areas:

1. Check network latency to AWS us-west-2
2. Verify DuckDB version >= 0.10.0
3. Check available RAM (DuckDB needs memory for large queries)
4. Try different times of day (S3 might be throttling)
5. Consider using a different Overture Maps release (some may have different data sizes)

### Quick Wins

**Fastest possible queries:**
```python
# Example 1: Downtown area with specific category
Bbox: [−90.05, 35.14] to [−90.04, 35.15]  # 0.01° x 0.01°
Categories: hospital
Limit: 100
Expected: 3-5 seconds

# Example 2: Neighborhood with multiple categories
Bbox: [−90.1, 35.1] to [−90.0, 35.2]  # 0.1° x 0.1°
Categories: restaurant, cafe
Limit: 1000
Expected: 6-10 seconds
```

**Slowest queries to avoid:**
```python
# Example 1: Entire state with no category filter
Bbox: [−90.3, 34.9] to [−81.6, 36.7]  # 9° x 2° = 18 sq deg
Categories: (none)
Limit: (none)
Expected: 90+ seconds (or timeout)

# Example 2: Multiple large states
Queries with > 20 square degrees
Expected: 60-120 seconds
```

## Getting Help

If you've tried everything and queries are still slow:

1. Note your query parameters (bbox coordinates, categories, limit)
2. Note actual execution time
3. Check the generated SQL query (test_query_performance.py)
4. Check DuckDB logs for errors
5. Report issue with all the above information
