#!/usr/bin/env python3
"""
Test S3 connectivity and DuckDB query performance
Run this script to diagnose connection issues
"""

import duckdb
import time

def test_s3_connection():
    """Test basic S3 connectivity and query performance"""
    print("=" * 60)
    print("DuckDB S3 Connection Test")
    print("=" * 60)

    try:
        # Initialize DuckDB
        print("\n1. Initializing DuckDB connection...")
        con = duckdb.connect()
        print("   ✓ DuckDB connection created")

        # Install extensions
        print("\n2. Installing extensions...")
        con.execute("INSTALL httpfs")
        con.execute("LOAD httpfs")
        print("   ✓ httpfs extension loaded")

        con.execute("INSTALL spatial")
        con.execute("LOAD spatial")
        print("   ✓ spatial extension loaded")

        # Configure S3
        print("\n3. Configuring S3 access...")
        con.execute("SET s3_region='us-west-2'")
        print("   ✓ S3 region set to us-west-2")

        # Test S3 access
        print("\n4. Testing S3 connectivity...")
        release = "2026-01-21.0"
        base_path = f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"

        print(f"   Testing: {base_path}")
        start = time.time()
        test_query = f"SELECT COUNT(*) as count FROM read_parquet('{base_path}', filename=true, hive_partitioning=1) LIMIT 1"
        result = con.execute(test_query).fetchone()
        elapsed = time.time() - start
        print(f"   ✓ S3 access successful ({elapsed:.2f}s)")

        # Create view
        print("\n5. Creating places view...")
        start = time.time()
        con.execute(f"""
            CREATE OR REPLACE VIEW places AS
            SELECT * FROM read_parquet('{base_path}',
                                        filename=true,
                                        hive_partitioning=1)
        """)
        elapsed = time.time() - start
        print(f"   ✓ View created ({elapsed:.2f}s)")

        # Test simple query
        print("\n6. Testing simple query (Tennessee hospitals)...")
        query = """
        SELECT
            id,
            names.primary as name,
            categories.primary as category,
            addresses[1].region as state,
            ST_X(geometry) as longitude,
            ST_Y(geometry) as latitude
        FROM places
        WHERE categories.primary IN ('hospital')
          AND addresses[1].region = 'TN'
        LIMIT 10
        """

        print("   Executing query...")
        start = time.time()
        results = con.execute(query).fetchdf()
        elapsed = time.time() - start

        print(f"   ✓ Query completed ({elapsed:.2f}s)")
        print(f"   Results: {len(results)} rows returned")

        if not results.empty:
            print("\n   Sample results:")
            print(results[['name', 'category', 'state']].head(3).to_string(index=False))

        # Test spatial query with bounding box
        print("\n7. Testing spatial query (ST_Within)...")
        bbox_query = """
        SELECT COUNT(*) as count
        FROM places
        WHERE categories.primary IN ('hospital')
          AND ST_Within(geometry, ST_MakeEnvelope(-90.3, 34.9, -81.6, 36.7))
        """

        start = time.time()
        count_result = con.execute(bbox_query).fetchone()
        elapsed = time.time() - start

        print(f"   ✓ Spatial query completed ({elapsed:.2f}s)")
        print(f"   Matching places: {count_result[0]:,}")

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nYour DuckDB and S3 connection is working correctly!")
        print("If the Streamlit app is still slow, the issue may be:")
        print("  - Large result sets (try smaller bounding boxes)")
        print("  - Network latency to us-west-2")
        print("  - First query cold start (subsequent queries should be faster)")

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"\nError: {str(e)}")
        print("\nTroubleshooting:")
        print("  1. Check internet connection")
        print("  2. Verify S3 bucket is accessible")
        print("  3. Try a different Overture release version")
        print("  4. Check DuckDB version (should be >= 0.10.0)")
        import sys
        sys.exit(1)
    finally:
        if 'con' in locals():
            con.close()

if __name__ == "__main__":
    test_s3_connection()
