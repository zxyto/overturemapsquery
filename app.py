"""
Overture Maps Query Tool
Interactive web application for querying Overture Maps places data
"""

import streamlit as st
import pandas as pd
import time
import threading
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium

from src.db_manager import get_db_manager
from src.query_builder import OvertureQueryBuilder
from src.validators import InputValidator
from src.exporters import export_dataframe, ExporterFactory
from src.constants import (
    US_STATES,
    COMMON_CATEGORIES,
    STATE_BBOXES,
    OVERTURE_CONFIG,
    DEFAULT_SETTINGS
)

# Page configuration
st.set_page_config(
    page_title="Overture Maps Query Tool",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'query_results' not in st.session_state:
    st.session_state.query_results = None
if 'query_executed' not in st.session_state:
    st.session_state.query_executed = False
if 'execution_time' not in st.session_state:
    st.session_state.execution_time = 0

# Background task tracking
if 'bg_task' not in st.session_state:
    st.session_state.bg_task = {
        'thread': None,
        'status': 'idle',
        'results': None,
        'error': None,
        'start_time': None,
        'cancelled': False
    }
if 'query_running' not in st.session_state:
    st.session_state.query_running = False

# Filter change tracking
if 'last_filter_type' not in st.session_state:
    st.session_state.last_filter_type = "State/Region"
if 'pending_filter_change' not in st.session_state:
    st.session_state.pending_filter_change = None
if 'confirm_clear_results' not in st.session_state:
    st.session_state.confirm_clear_results = False

# Export dialog tracking
if 'show_export_dialog' not in st.session_state:
    st.session_state.show_export_dialog = False


def render_header():
    """Render application header"""
    st.title("🗺️ Overture Maps Places Query Tool")

    # Get current release version from session state or default
    current_release = st.session_state.get('overture_release', OVERTURE_CONFIG['release'])

    st.markdown(f"""
    Query and export Overture Maps places data with custom filters.

    **Data Release:** `{current_release}`
    **Source:** S3 ({OVERTURE_CONFIG['s3_region']})
    """)
    st.divider()


def render_sidebar():
    """Render sidebar with filter controls"""
    st.sidebar.header("🔍 Query Filters")

    # Show query status indicator
    if st.session_state.query_running:
        st.sidebar.info("⏳ Query in progress...")
    elif st.session_state.query_executed and st.session_state.query_results is not None:
        result_count = len(st.session_state.query_results)
        st.sidebar.success(f"✅ {result_count:,} results loaded")

    st.sidebar.divider()

    # Filter type selection
    filter_type = st.sidebar.radio(
        "Filter Type",
        ["State/Region", "Map Search"],
        help="Choose how to filter places geographically",
        disabled=st.session_state.query_running,
        key="filter_type_radio"
    )

    # Detect filter type change
    if filter_type != st.session_state.last_filter_type:
        # Check if we have results and need confirmation
        if st.session_state.query_executed and st.session_state.query_results is not None:
            st.session_state.pending_filter_change = filter_type
            filter_type = st.session_state.last_filter_type  # Keep old selection temporarily
        else:
            st.session_state.last_filter_type = filter_type

    state_filter = None
    bbox_filter = None

    # State filter
    if filter_type == "State/Region":
        state_options = {f"{code} - {name}": code for code, name in sorted(US_STATES.items())}
        default_state = f"{DEFAULT_SETTINGS['state']} - {US_STATES[DEFAULT_SETTINGS['state']]}"

        selected_state = st.sidebar.selectbox(
            "Select State",
            options=list(state_options.keys()),
            index=list(state_options.keys()).index(default_state) if default_state in state_options else 0,
            help="Choose a US state or territory"
        )
        state_filter = state_options[selected_state]

    # Map-based search
    else:  # filter_type == "Map Search"
        st.sidebar.markdown("**Map Search Options**")
        st.sidebar.caption("Enter coordinates in the main area to define your search boundary")

        # Initialize session state for map bounds
        if 'map_bounds' not in st.session_state:
            st.session_state.map_bounds = STATE_BBOXES['TN']

        # Store that we need to render map in main area
        bbox_filter = st.session_state.map_bounds

    st.sidebar.divider()

    # Category selection
    st.sidebar.subheader("📍 Place Categories")

    # Multiselect for common categories
    default_categories = DEFAULT_SETTINGS['categories']
    selected_categories = st.sidebar.multiselect(
        "Select Categories",
        options=COMMON_CATEGORIES,
        default=default_categories,
        help="Choose one or more place categories to search for",
        disabled=st.session_state.query_running
    )

    # Custom category input
    with st.sidebar.expander("➕ Add Custom Category"):
        st.caption("Enter custom category names (e.g., 'coffee_shop', 'bike_rental')")
        custom_category = st.text_input(
            "Category Name",
            help="Enter a custom category name from Overture Maps schema",
            disabled=st.session_state.query_running
        )
        if st.button("Add Category", disabled=st.session_state.query_running) and custom_category:
            sanitized = InputValidator.sanitize_category_name(custom_category)
            if sanitized not in selected_categories:
                selected_categories.append(sanitized)
                st.success(f"✓ Added: {sanitized}")
            else:
                st.info(f"Already selected: {sanitized}")

    # Display selected categories count
    if selected_categories:
        st.sidebar.caption(f"✓ {len(selected_categories)} {'category' if len(selected_categories) == 1 else 'categories'} selected")
    else:
        st.sidebar.warning("⚠️ No categories selected")

    st.sidebar.divider()

    # Advanced options
    with st.sidebar.expander("⚙️ Advanced Options"):
        enable_limit = st.checkbox(
            "Limit Results",
            value=True,
            disabled=st.session_state.query_running
        )
        limit = None
        if enable_limit:
            limit = st.number_input(
                "Maximum Results",
                min_value=1,
                max_value=1000000,
                value=DEFAULT_SETTINGS['limit'],
                step=100,
                help="Limit the number of results returned",
                disabled=st.session_state.query_running
            )

        st.markdown("---")
        st.markdown("**Data Source Configuration**")

        # Initialize session state for custom release
        if 'overture_release' not in st.session_state:
            st.session_state.overture_release = OVERTURE_CONFIG['release']

        custom_release = st.text_input(
            "Overture Release Version",
            value=st.session_state.overture_release,
            help="e.g., 2026-01-21.0 (check Overture docs for latest releases)"
        )

        if custom_release != st.session_state.overture_release:
            st.session_state.overture_release = custom_release
            st.info("Release version updated. Execute query to use new version.")

        st.caption("📚 [Check latest releases](https://docs.overturemaps.org/getting-data/)")

        if st.button("Reset to Default", key="reset_release"):
            st.session_state.overture_release = OVERTURE_CONFIG['release']
            st.success("Reset to default release")

    return {
        'filter_type': filter_type,
        'state': state_filter,
        'bbox': bbox_filter,
        'categories': selected_categories,
        'limit': limit
    }


def validate_inputs(params):
    """
    Validate user inputs

    Args:
        params (dict): Query parameters

    Returns:
        tuple: (is_valid, error_messages)
    """
    errors = []

    # Validate categories
    if not params['categories']:
        errors.append("Please select at least one category")
    else:
        is_valid, msg = InputValidator.validate_categories(params['categories'])
        if not is_valid:
            errors.append(msg)

    # Validate state or bbox
    if params['filter_type'] == "State/Region":
        if params['state']:
            is_valid, msg = InputValidator.validate_state_code(params['state'])
            if not is_valid:
                errors.append(msg)
    else:
        if params['bbox']:
            bbox = params['bbox']
            is_valid, msg = InputValidator.validate_bbox(
                bbox['xmin'], bbox['xmax'],
                bbox['ymin'], bbox['ymax']
            )
            if not is_valid:
                errors.append(msg)

    # Validate limit
    if params['limit']:
        is_valid, msg = InputValidator.validate_limit(params['limit'])
        if not is_valid:
            errors.append(msg)

    return len(errors) == 0, errors


def execute_query(params, status_container=None):
    """
    Execute query with given parameters

    Args:
        params (dict): Query parameters
        status_container: Streamlit status container for progress updates

    Returns:
        pd.DataFrame: Query results
    """
    def update_status(message):
        """Helper to update status if container provided"""
        if status_container:
            status_container.update(label=message)

    try:
        # Build query
        update_status("Building SQL query...")
        builder = OvertureQueryBuilder()

        if params['categories']:
            builder.add_categories(params['categories'])

        if params['filter_type'] == "State/Region" and params['state']:
            builder.add_state_filter(params['state'])
        elif params['filter_type'] == "Map Search" and params['bbox']:
            bbox = params['bbox']
            builder.add_bbox_filter(bbox['xmin'], bbox['xmax'], bbox['ymin'], bbox['ymax'])

        if params['limit']:
            builder.set_limit(params['limit'])

        query = builder.build()
        update_status("✓ SQL query built")

        # Show query in expander for debugging
        if status_container:
            with st.expander("View SQL Query"):
                st.code(query, language="sql")

        # Initialize database connection
        update_status("Initializing DuckDB...")
        db_manager = get_db_manager()
        update_status("✓ Getting database connection...")

        # Get connection
        con = db_manager.get_connection()
        update_status("✓ Database connection ready")

        # Create view if needed
        release_version = st.session_state.get('overture_release', OVERTURE_CONFIG['release'])

        if not db_manager._view_created or db_manager._current_release != release_version:
            update_status(f"Creating data view for release {release_version}...")
            update_status("Testing S3 connectivity...")

            # Test S3 access first with a simple query
            try:
                base_path = f"s3://overturemaps-us-west-2/release/{release_version}/theme=places/type=place/*"
                test_query = f"SELECT COUNT(*) FROM read_parquet('{base_path}', filename=true, hive_partitioning=1) LIMIT 1"
                con.execute(test_query).fetchone()
                update_status("✓ S3 connectivity confirmed")
            except Exception as test_error:
                raise Exception(f"S3 connection test failed: {str(test_error)}")

            db_manager.create_places_view(release_version)
            update_status("✓ Data view created")

        # Execute query directly (skip count to avoid double scan)
        update_status("Fetching results from S3...")
        results = con.execute(query).fetchdf()

        if results.empty:
            update_status("⚠️ No results found with current filters")
            return results

        update_status(f"✓ Query complete - {len(results):,} results")

        return results

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        if status_container:
            status_container.update(label=f"❌ {error_msg}", state="error")
        raise


def execute_query_in_background(params, status_dict):
    """
    Execute DuckDB query in background thread (doesn't block main thread)

    Args:
        params (dict): Query parameters
        status_dict (dict): Shared dictionary for status tracking
    """
    try:
        # Check for cancellation before starting
        if status_dict.get('cancelled', False):
            status_dict['status'] = 'Cancelled'
            status_dict['error'] = 'Query cancelled by user'
            status_dict['results'] = None
            return

        # Update status
        status_dict['status'] = 'Building SQL query...'

        # Build query
        builder = OvertureQueryBuilder()

        if params['categories']:
            builder.add_categories(params['categories'])

        if params['filter_type'] == "State/Region" and params['state']:
            builder.add_state_filter(params['state'])
        elif params['filter_type'] == "Map Search" and params['bbox']:
            bbox = params['bbox']
            builder.add_bbox_filter(bbox['xmin'], bbox['xmax'], bbox['ymin'], bbox['ymax'])

        if params['limit']:
            builder.set_limit(params['limit'])

        query = builder.build()
        status_dict['query'] = query
        status_dict['status'] = '✓ SQL query built'

        # Check for cancellation after building query
        if status_dict.get('cancelled', False):
            status_dict['status'] = 'Cancelled'
            status_dict['error'] = 'Query cancelled by user'
            status_dict['results'] = None
            return

        # Initialize database connection
        status_dict['status'] = 'Initializing DuckDB...'
        db_manager = get_db_manager()

        # Get connection
        con = db_manager.get_connection()
        status_dict['connection'] = con  # Store connection for cancellation
        status_dict['status'] = '✓ Database connection ready'

        # Check for cancellation before creating view
        if status_dict.get('cancelled', False):
            status_dict['status'] = 'Cancelled'
            status_dict['error'] = 'Query cancelled by user'
            status_dict['results'] = None
            return

        # Create view if needed
        release_version = OVERTURE_CONFIG['release']

        if not db_manager._view_created or db_manager._current_release != release_version:
            status_dict['status'] = f'Creating data view for release {release_version}...'

            # Test S3 access first
            try:
                base_path = f"s3://overturemaps-us-west-2/release/{release_version}/theme=places/type=place/*"
                test_query = f"SELECT COUNT(*) FROM read_parquet('{base_path}', filename=true, hive_partitioning=1) LIMIT 1"
                con.execute(test_query).fetchone()
                status_dict['status'] = '✓ S3 connectivity confirmed'
            except Exception as test_error:
                raise Exception(f"S3 connection test failed: {str(test_error)}")

            db_manager.create_places_view(release_version)
            status_dict['status'] = '✓ Data view created'

        # Final check for cancellation before executing main query
        if status_dict.get('cancelled', False):
            status_dict['status'] = 'Cancelled'
            status_dict['error'] = 'Query cancelled by user'
            status_dict['results'] = None
            return

        # Execute query (THIS is the blocking call, but only blocks THIS thread)
        # Can now be interrupted via connection.interrupt() from main thread
        status_dict['status'] = 'Fetching results from S3...'
        try:
            results = con.execute(query).fetchdf()
        except Exception as query_error:
            # Check if this was an intentional interruption
            if status_dict.get('cancelled', False):
                status_dict['status'] = 'Cancelled'
                status_dict['error'] = 'Query interrupted by user'
                status_dict['results'] = None
                return
            else:
                # Re-raise actual errors to be caught by outer exception handler
                raise

        # Check if cancelled while query was running
        if status_dict.get('cancelled', False):
            status_dict['status'] = 'Cancelled'
            status_dict['error'] = 'Query cancelled by user'
            status_dict['results'] = None
            return

        # Check if we got any results
        if results.empty or len(results) == 0:
            status_dict['status'] = 'No results found'
            status_dict['error'] = 'no_results'  # Special error code
            status_dict['results'] = None
            return

        # Store results
        status_dict['results'] = results
        status_dict['status'] = f'✓ Query complete - {len(results):,} results'
        status_dict['error'] = None

    except Exception as e:
        # Check if error was due to cancellation
        if status_dict.get('cancelled', False):
            status_dict['status'] = 'Cancelled'
            status_dict['error'] = 'Query cancelled by user'
        else:
            status_dict['status'] = 'Error'
            status_dict['error'] = str(e)
        status_dict['results'] = None


def render_results(df):
    """
    Render query results

    Args:
        df (pd.DataFrame): Query results
    """
    if df is None or df.empty:
        st.warning("No results found. Try adjusting your filters.")
        return

    # Results summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Results", f"{len(df):,}")
    with col2:
        st.metric("Execution Time", f"{st.session_state.execution_time:.2f}s")
    with col3:
        unique_categories = df['category'].nunique()
        st.metric("Unique Categories", unique_categories)

    # Category breakdown
    with st.expander("Category Breakdown"):
        category_counts = df['category'].value_counts()
        st.bar_chart(category_counts)

    st.divider()

    # Data table with export button
    col_table1, col_table2 = st.columns([3, 1])
    with col_table1:
        st.subheader("Results Table")
    with col_table2:
        st.write("")  # Spacer for alignment
        if st.button("📥 Export Data", type="primary", width="stretch", key="export_btn_top"):
            st.session_state.show_export_dialog = True

    st.dataframe(
        df,
        use_container_width=True,
        height=400
    )

    # Map view
    st.divider()
    render_map(df)


def render_map_search_interface():
    """
    Render full-width map search interface in main content area with interactive drawing

    Returns:
        dict: Updated bbox_filter from map interaction
    """
    st.subheader("🗺️ Map Search - Draw Your Search Area")

    current_bbox = st.session_state.map_bounds

    # Quick presets for common areas
    col_preset1, col_preset2, col_preset3 = st.columns(3)
    with col_preset1:
        if st.button("📍 Nashville, TN", use_container_width=True, help="Small area for quick testing"):
            st.session_state.map_bounds = STATE_BBOXES['TN']
            st.rerun()
    with col_preset2:
        if st.button("🌆 New York City", use_container_width=True):
            st.session_state.map_bounds = {
                'xmin': -74.3, 'xmax': -73.7,
                'ymin': 40.5, 'ymax': 40.9
            }
            st.rerun()
    with col_preset3:
        if st.button("🌁 San Francisco", use_container_width=True):
            st.session_state.map_bounds = {
                'xmin': -122.5, 'xmax': -122.3,
                'ymin': 37.7, 'ymax': 37.85
            }
            st.rerun()

    st.divider()

    # Calculate map center
    center_lat = (current_bbox['ymin'] + current_bbox['ymax']) / 2
    center_lon = (current_bbox['xmin'] + current_bbox['xmax']) / 2

    # Create Folium map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=7,
        tiles='OpenStreetMap'
    )

    # Add current bounding box as a rectangle
    folium.Rectangle(
        bounds=[
            [current_bbox['ymin'], current_bbox['xmin']],
            [current_bbox['ymax'], current_bbox['xmax']]
        ],
        color='#0078FF',
        fill=True,
        fillColor='#0078FF',
        fillOpacity=0.3,
        weight=3,
        popup='Current Search Area'
    ).add_to(m)

    # Add drawing tools
    draw = Draw(
        export=False,
        draw_options={
            'polyline': False,
            'polygon': False,
            'circle': False,
            'marker': False,
            'circlemarker': False,
            'rectangle': {
                'shapeOptions': {
                    'color': '#FF6B00',
                    'fillColor': '#FF6B00',
                    'fillOpacity': 0.3,
                    'weight': 3
                }
            }
        },
        edit_options={
            'edit': True,
            'remove': True
        }
    )
    draw.add_to(m)

    # Display map and capture drawn shapes
    st.markdown("**🖍️ Draw a rectangle on the map to define your search area**")
    st.caption("Use the rectangle tool (□) in the top-left corner of the map. Click 'Execute Query' in the sidebar after drawing.")

    map_data = st_folium(
        m,
        width=None,
        height=500,
        returned_objects=["all_drawings", "last_active_drawing"]
    )

    st.divider()

    # Process drawn shapes
    if map_data and map_data.get('all_drawings'):
        drawings = map_data['all_drawings']
        if len(drawings) > 0:
            # Get the last drawn rectangle
            last_drawing = drawings[-1]
            if last_drawing['geometry']['type'] == 'Polygon':
                coords = last_drawing['geometry']['coordinates'][0]
                # Extract bounding box from polygon coordinates
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]

                new_bbox = {
                    'xmin': min(lons),
                    'xmax': max(lons),
                    'ymin': min(lats),
                    'ymax': max(lats)
                }

                # Update if different from current
                if new_bbox != st.session_state.map_bounds:
                    st.session_state.map_bounds = new_bbox
                    st.success("✅ Search area updated from drawing!")
                    st.rerun()

    # Manual bounding box entry (fallback)
    with st.expander("📐 Or Enter Coordinates Manually"):
        col1, col2 = st.columns(2)
        with col1:
            st.caption("**Southwest Corner (Bottom-Left)**")
            xmin = st.number_input(
                "Min Longitude (West)",
                value=current_bbox['xmin'],
                min_value=-180.0,
                max_value=180.0,
                format="%.4f",
                key="manual_xmin",
                help="Western edge of search area"
            )
            ymin = st.number_input(
                "Min Latitude (South)",
                value=current_bbox['ymin'],
                min_value=-90.0,
                max_value=90.0,
                format="%.4f",
                key="manual_ymin",
                help="Southern edge of search area"
            )
        with col2:
            st.caption("**Northeast Corner (Top-Right)**")
            xmax = st.number_input(
                "Max Longitude (East)",
                value=current_bbox['xmax'],
                min_value=-180.0,
                max_value=180.0,
                format="%.4f",
                key="manual_xmax",
                help="Eastern edge of search area"
            )
            ymax = st.number_input(
                "Max Latitude (North)",
                value=current_bbox['ymax'],
                min_value=-90.0,
                max_value=90.0,
                format="%.4f",
                key="manual_ymax",
                help="Northern edge of search area"
            )

        # Update button
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        with col_btn2:
            if st.button("🔄 Update from Coordinates", use_container_width=True, type="primary"):
                # Validate bbox
                if xmin >= xmax or ymin >= ymax:
                    st.error("❌ Invalid bounding box: Min values must be less than Max values")
                else:
                    st.session_state.map_bounds = {
                        'xmin': xmin,
                        'xmax': xmax,
                        'ymin': ymin,
                        'ymax': ymax
                    }
                    st.success("✅ Map updated!")
                    st.rerun()

    # Show current selected area info
    area_size = (current_bbox['xmax'] - current_bbox['xmin']) * (current_bbox['ymax'] - current_bbox['ymin'])

    st.info(f"""
    **📊 Current Search Area:**
    - **Longitude:** {current_bbox['xmin']:.4f}° to {current_bbox['xmax']:.4f}° ({abs(current_bbox['xmax'] - current_bbox['xmin']):.2f}° wide)
    - **Latitude:** {current_bbox['ymin']:.4f}° to {current_bbox['ymax']:.4f}° ({abs(current_bbox['ymax'] - current_bbox['ymin']):.2f}° tall)
    - **Area:** {area_size:.2f} square degrees

    **💡 Tip:** Smaller areas query faster. For testing, use Nashville preset (~0.2 sq deg).

    Click **Execute Query** in the sidebar to search this area
    """)

    return st.session_state.map_bounds


def render_map(df):
    """
    Render interactive map with results using Folium

    Args:
        df (pd.DataFrame): Query results with lat/lon
    """
    st.subheader("Map View")

    if df.empty or 'latitude' not in df.columns or 'longitude' not in df.columns:
        st.info("No location data available for mapping")
        return

    # Remove rows with missing coordinates
    df_map = df.dropna(subset=['latitude', 'longitude'])

    if df_map.empty:
        st.info("No valid coordinates found in results")
        return

    # Limit to first 1000 for performance (Folium can be slower with many markers)
    max_points = 1000
    df_display = df_map.head(max_points)

    if len(df_map) > max_points:
        st.info(f"Showing first {max_points:,} of {len(df_map):,} points on map")

    # Calculate map center
    center_lat = df_display['latitude'].mean()
    center_lon = df_display['longitude'].mean()

    # Create Folium map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles='OpenStreetMap'
    )

    # Define color mapping for categories
    unique_categories = df_display['category'].unique()
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred',
              'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
              'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen',
              'gray', 'black', 'lightgray']
    category_colors = {cat: colors[i % len(colors)] for i, cat in enumerate(unique_categories)}

    # Add markers for each location
    for idx, row in df_display.iterrows():
        # Create popup content
        popup_html = f"""
        <div style="font-family: Arial; width: 200px;">
            <h4 style="margin-bottom: 5px;">{row.get('name', 'Unknown')}</h4>
            <hr style="margin: 5px 0;">
            <b>Category:</b> {row.get('category', 'N/A')}<br>
            <b>City:</b> {row.get('city', 'N/A')}<br>
            <b>State:</b> {row.get('state', 'N/A')}<br>
            <b>Coordinates:</b> {row['latitude']:.4f}, {row['longitude']:.4f}
        </div>
        """

        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=6,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=row.get('name', 'Unknown'),
            color=category_colors.get(row.get('category'), 'gray'),
            fillColor=category_colors.get(row.get('category'), 'gray'),
            fillOpacity=0.7,
            weight=2
        ).add_to(m)

    # Add a legend
    if len(unique_categories) <= 10:  # Only show legend if not too many categories
        legend_html = """
        <div style="position: fixed;
                    bottom: 50px; right: 50px; width: 200px; height: auto;
                    background-color: white; z-index:9999; font-size:14px;
                    border:2px solid grey; border-radius: 5px; padding: 10px">
        <h4 style="margin-top: 0;">Categories</h4>
        """
        for cat in unique_categories[:10]:  # Limit to 10 categories
            color = category_colors[cat]
            legend_html += f'<p style="margin: 5px 0;"><i class="fa fa-circle" style="color:{color}"></i> {cat}</p>'
        legend_html += "</div>"
        m.get_root().html.add_child(folium.Element(legend_html))

    # Display map
    st_folium(m, width=None, height=600, returned_objects=[])


@st.dialog("Export Data")
def show_export_dialog(df):
    """
    Modal dialog for exporting data

    Args:
        df (pd.DataFrame): Data to export
    """
    st.write(f"**Export {len(df):,} results to file**")
    st.divider()

    # Format selection
    export_format = st.selectbox(
        "Format",
        options=ExporterFactory.get_supported_formats(),
        format_func=lambda x: x.upper(),
        help="Choose export format",
        key="export_format_select"
    )

    # Filename input
    filename_base = st.text_input(
        "Filename (without extension)",
        value="overture_places_export",
        help="Extension will be added automatically",
        key="export_filename_input"
    )

    st.divider()

    # Export button
    col_exp1, col_exp2 = st.columns([1, 1])
    with col_exp1:
        if st.button("Cancel", width="stretch", key="export_cancel"):
            st.session_state.show_export_dialog = False
            st.rerun()

    with col_exp2:
        if st.button("Export", type="primary", width="stretch", key="export_confirm"):
            try:
                with st.spinner(f"Preparing {export_format.upper()} export..."):
                    buffer, mime_type, extension = export_dataframe(df, export_format)
                    filename = f"{filename_base}.{extension}"
                    file_size_kb = len(buffer.getvalue()) / 1024

                st.success(f"✅ Export ready! ({len(df):,} rows, {file_size_kb:.1f} KB)")

                st.download_button(
                    label=f"📥 Download {filename}",
                    data=buffer.getvalue(),
                    file_name=filename,
                    mime=mime_type,
                    width="stretch",
                    type="primary"
                )
            except Exception as e:
                st.error(f"Export failed: {str(e)}")


def main():
    """Main application function"""

    # Render header
    render_header()

    # Render sidebar and get parameters
    params = render_sidebar()

    # Execute query button
    st.sidebar.divider()

    # Show helpful message based on state
    if not params.get('categories'):
        st.sidebar.error("⚠️ Select at least one category")
        execute_button = False
    else:
        if st.session_state.query_running:
            st.sidebar.info("⏳ Query in progress... Please wait")
            execute_button = False
        else:
            execute_button = st.sidebar.button(
                "🔍 Execute Query",
                type="primary",
                use_container_width=True,
                help="Run query with current filters"
            )

            # Show clear results button if results exist
            if st.session_state.query_executed and st.session_state.query_results is not None:
                if st.sidebar.button("🗑️ Clear Results", use_container_width=True):
                    st.session_state.query_results = None
                    st.session_state.query_executed = False
                    st.rerun()

    # Main content area
    if execute_button:
        # Validate inputs
        is_valid, errors = validate_inputs(params)

        if not is_valid:
            st.error("Validation errors:")
            for error in errors:
                st.error(f"• {error}")
            return

        # Reset background task state
        st.session_state.bg_task = {
            'thread': None,
            'status': 'Starting query...',
            'results': None,
            'error': None,
            'start_time': time.time(),
            'query': None,
            'cancelled': False
        }
        st.session_state.query_running = True

        # Start background thread
        thread = threading.Thread(
            target=execute_query_in_background,
            args=(params, st.session_state.bg_task),
            daemon=True
        )
        thread.start()
        st.session_state.bg_task['thread'] = thread

    # Handle background query execution
    if st.session_state.query_running and st.session_state.bg_task['thread'] is not None:
        # Check if cancellation was requested
        if st.session_state.bg_task.get('cancelled', False):
            # Check how long we've been waiting for cancellation
            if 'cancel_start_time' not in st.session_state.bg_task:
                st.session_state.bg_task['cancel_start_time'] = time.time()

            cancel_elapsed = time.time() - st.session_state.bg_task['cancel_start_time']

            # If thread still alive after 3 seconds, force cleanup
            if cancel_elapsed > 3.0 and st.session_state.bg_task['thread'].is_alive():
                st.warning(f"""
                ⚠️ **Query Interrupted** ({cancel_elapsed:.1f}s)

                The query was interrupted but DuckDB is still cleaning up. Forcing stop now.
                """)
                # Force cleanup
                st.session_state.query_running = False
                st.session_state.bg_task = {
                    'thread': None,
                    'status': 'idle',
                    'results': None,
                    'error': None,
                    'start_time': None,
                    'cancelled': False
                }
                st.rerun()

            # Show cancelling message
            st.markdown("### ⏸️ Cancelling Query...")
            st.info(f"""
            **Query cancellation in progress...** ({cancel_elapsed:.1f}s)

            The running query has been interrupted. Waiting for cleanup...
            """)

            # Wait a bit for thread to finish cleaning up
            time.sleep(0.3)
            st.rerun()

        # Check if thread is still alive
        elif st.session_state.bg_task['thread'].is_alive():
            # Thread still running - show live progress
            elapsed = time.time() - st.session_state.bg_task['start_time']
            current_status = st.session_state.bg_task['status']

            # Use st.spinner for smoother updates (less jarring than status widget)
            with st.spinner(f"🔄 Query Running... {elapsed:.0f}s elapsed"):
                # Small sleep to show spinner
                time.sleep(0.1)

            # Show minimalist progress info
            col_prog1, col_prog2 = st.columns([3, 1])
            with col_prog1:
                st.info(f"**{current_status}**")
            with col_prog2:
                st.metric("Elapsed", f"{elapsed:.0f}s")

            # Progress bar
            progress_value = min(elapsed / 60.0, 0.95)
            st.progress(progress_value)

            # Show query if available (collapsed by default to reduce redraw)
            if st.session_state.bg_task.get('query'):
                with st.expander("📋 View SQL Query"):
                    st.code(st.session_state.bg_task['query'], language="sql")

            # Cancel button
            col_cancel1, col_cancel2, col_cancel3 = st.columns([1, 1, 1])
            with col_cancel2:
                if st.button("❌ Cancel Query", width="stretch", type="secondary", key=f"cancel_btn_{int(elapsed)}"):
                    st.session_state.bg_task['cancelled'] = True
                    st.session_state.bg_task['cancel_start_time'] = time.time()
                    # Interrupt the running query if connection exists
                    if 'connection' in st.session_state.bg_task:
                        try:
                            st.session_state.bg_task['connection'].interrupt()
                            st.session_state.bg_task['interrupt_called'] = True
                        except Exception as e:
                            st.session_state.bg_task['interrupt_error'] = str(e)
                    st.rerun()

            st.caption("💡 Updates every 4 seconds")

            # Poll again after 4 seconds (reduced frequency to minimize flickering)
            time.sleep(4.0)
            st.rerun()

        else:
            # Thread finished - process results
            st.session_state.query_running = False

            # Check if cancelled
            if st.session_state.bg_task.get('cancelled', False):
                elapsed = time.time() - st.session_state.bg_task['start_time']
                st.warning(f"⚠️ Query cancelled by user after {elapsed:.1f}s")
                # Reset task state
                st.session_state.bg_task = {
                    'thread': None,
                    'status': 'idle',
                    'results': None,
                    'error': None,
                    'start_time': None,
                    'cancelled': False
                }
                st.stop()

            # Check for errors
            if st.session_state.bg_task['error']:
                # Handle no results specially
                if st.session_state.bg_task['error'] == 'no_results':
                    elapsed = time.time() - st.session_state.bg_task['start_time']
                    st.warning(f"""
                    **ℹ️ No Results Found** ({elapsed:.1f}s)

                    Your query didn't return any results. Try adjusting your filters:
                    - Select a different state or expand your bounding box
                    - Choose different categories
                    - Increase the result limit
                    - Check that your filters aren't too restrictive

                    The query completed successfully, but no places matched your criteria.
                    """)
                else:
                    # Regular error
                    st.error(f"❌ Query failed: {st.session_state.bg_task['error']}")

                # Reset task state but don't st.stop() so user can adjust filters
                st.session_state.bg_task = {
                    'thread': None,
                    'status': 'idle',
                    'results': None,
                    'error': None,
                    'start_time': None,
                    'cancelled': False
                }
                st.stop()

            # Success - store results
            results = st.session_state.bg_task['results']
            end_time = time.time()
            execution_time = end_time - st.session_state.bg_task['start_time']

            st.session_state.query_results = results
            st.session_state.query_executed = True
            st.session_state.execution_time = execution_time

            # Show success message
            st.success(f"✅ Query completed! Found {len(results):,} results in {execution_time:.2f}s")

            # Force rerun to display results
            st.rerun()

    # Handle pending filter type change (confirmation dialog)
    if st.session_state.pending_filter_change:
        st.warning(f"""
        **⚠️ Filter Type Change Detected**

        You currently have **{len(st.session_state.query_results):,} results** loaded.
        Switching from **{st.session_state.last_filter_type}** to **{st.session_state.pending_filter_change}** will clear these results.
        """)

        col_conf1, col_conf2, col_conf3 = st.columns([1, 1, 1])
        with col_conf1:
            if st.button("✅ Yes, Switch Filter", type="primary", use_container_width=True):
                # Clear results and switch filter
                st.session_state.query_results = None
                st.session_state.query_executed = False
                st.session_state.last_filter_type = st.session_state.pending_filter_change
                st.session_state.pending_filter_change = None
                st.rerun()
        with col_conf2:
            if st.button("❌ Cancel", use_container_width=True):
                # Keep current filter
                st.session_state.pending_filter_change = None
                st.rerun()

        st.stop()  # Don't render anything else while confirmation is pending

    # Display results
    if st.session_state.query_executed and st.session_state.query_results is not None:
        render_results(st.session_state.query_results)

        # Show export dialog if triggered
        if st.session_state.show_export_dialog:
            show_export_dialog(st.session_state.query_results)
    else:
        # Show map search interface or welcome message
        if params['filter_type'] == "Map Search":
            render_map_search_interface()
        else:
            # Welcome message
            st.info("""
            👈 **Get Started** - Configure your query filters in the sidebar and click **Execute Query**.

            **🚀 Quick Start:**
            1. Select a **State/Region** or switch to **Map Search**
            2. Choose one or more **Place Categories** (e.g., hospital, restaurant)
            3. Click **🔍 Execute Query** to fetch data from Overture Maps

            **✨ Features:**
            - 🗺️ Filter by US state or custom bounding box
            - 📍 60+ common place categories + custom categories
            - 📊 Interactive data table and map visualization
            - 📥 Export to CSV, GeoJSON, KML, Parquet, or Shapefile
            """)


if __name__ == "__main__":
    main()
