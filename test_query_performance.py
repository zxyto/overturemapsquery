"""
Quick test to see what query is being generated and benchmark it
"""
from src.query_builder import OvertureQueryBuilder

# Test bbox query (Tennessee-sized area)
builder = OvertureQueryBuilder()
builder.add_bbox_filter(-90.3, -81.6, 34.9, 36.7)
builder.add_categories(['hospital', 'clinic'])
builder.set_limit(1000)

query = builder.build()

print("Generated Query:")
print("=" * 80)
print(query)
print("=" * 80)
print()

# Check if ST_Within is being used
if "ST_Within" in query:
    print("✓ Using optimized ST_Within spatial predicate")
else:
    print("✗ NOT using ST_Within - using slow metadata filtering!")

if "bbox.xmin" in query:
    print("✗ Still using old bbox metadata filtering!")
else:
    print("✓ Not using old bbox metadata filtering")

print()
print("Expected pattern: ST_Within(geometry, ST_MakeEnvelope(-90.3, 34.9, -81.6, 36.7))")
