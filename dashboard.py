from shiny import App, ui, render, reactive
import pandas as pd
import folium
from shiny.types import SilentException
from folium.plugins import HeatMap
import branca.colormap as cm
import plotly.express as px
import plotly.graph_objects as go

# Data loading function
def load_data(status_filter=None, output_filter=None, topic_filter=None, subfund_filter=None, contrib_range=None):
    try:
        # Cache data to avoid reloading
        if not hasattr(load_data, 'org_df'):
            load_data.org_df = pd.read_csv(r"C:\Users\wency\Desktop\organization.csv", sep=';', on_bad_lines='skip', encoding='utf-8')
        if not hasattr(load_data, 'proj_df'):
            load_data.proj_df = pd.read_csv(r"C:\Users\wency\Desktop\project(1).csv", sep=',', on_bad_lines='skip', encoding='utf-8')
        
        org_df = load_data.org_df
        proj_df = load_data.proj_df
    except Exception as e:
        raise SilentException(f"Failed to read data files: {str(e)}")

    if 'status' not in proj_df.columns:
        raise SilentException("Column 'status' not found in project table")

    # Data cleaning
    proj_df['status'] = proj_df['status'].astype(str).str.strip().str.upper()

    if 'output' not in proj_df.columns:
        proj_df['output'] = 0
    else:
        proj_df['output'] = pd.to_numeric(proj_df['output'], errors='coerce').fillna(0)

    # Apply filters
    if status_filter and status_filter != "ALL":
        proj_df = proj_df[proj_df['status'] == status_filter.strip().upper()].copy()

    if output_filter is not None and output_filter != "ALL":
        proj_df = proj_df[proj_df['output'] == int(output_filter)].copy()

    if topic_filter and topic_filter != "ALL":
        proj_df = proj_df[proj_df["topic"] == topic_filter].copy()

    if subfund_filter and subfund_filter != "ALL":
        proj_df = proj_df[proj_df["sub-fund"] == subfund_filter].copy()

    if contrib_range:
        proj_df = proj_df.copy()
        proj_df.loc[:, "ecMaxContribution"] = pd.to_numeric(proj_df["ecMaxContribution"], errors="coerce")
        proj_df = proj_df[
            (proj_df["ecMaxContribution"] >= contrib_range[0]) &
            (proj_df["ecMaxContribution"] <= contrib_range[1])
        ].copy()

    # Merge organization geographic info
    map_data = []

    for idx, proj in proj_df.iterrows():
        org_matches = org_df[org_df['projectID'] == proj['id']]
        org = org_matches[org_matches['order'] == 1]

        if org.empty:
            continue

        try:
            geolocation = org.iloc[0]['geolocation']
            if pd.isna(geolocation) or not geolocation:
                continue

            coords = str(geolocation).split(',')
            if len(coords) != 2:
                continue

            lat, lon = map(float, coords)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue

            map_data.append({
                'lat': lat,
                'lon': lon,
                'title': str(proj.get('title', 'No Title')),
                'project_id': proj['id'],
                'status': proj['status'],
                'output': int(proj.get('output', 0)),
                'contribution': proj.get('ecMaxContribution', 0),
                'total_cost': proj.get('totalCost', 0),
                'start_date': proj.get('startDate', 'N/A'),
                'end_date': proj.get('endDate', 'N/A'),
                'sub_fund': proj.get('sub-fund', 'N/A'),
                'topic': proj.get('topic', 'N/A')
            })

        except (ValueError, TypeError, IndexError):
            continue

    if not map_data:
        raise SilentException("No valid coordinates after filtering")

    return pd.DataFrame(map_data)

# UI with sidebar layout
app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.style("""
            html, body {
                height: 100vh;
                margin: 0;
                padding: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f8f9fa;
            }
            .container-fluid {
                height: 100vh;
                padding: 15px;
                display: flex;
                flex-direction: column;
            }
            
            /* Header */
            .app-header {
                text-align: center;
                margin-bottom: 20px;
                padding: 20px 0;
                background: linear-gradient(135deg, #6c5ce7 0%, #a29bfe 100%);
                border-radius: 12px;
                color: white;
                box-shadow: 0 8px 25px rgba(108, 92, 231, 0.15);
            }
            .app-title {
                font-size: 2.5em;
                font-weight: 700;
                margin: 0;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            
            /* Statistics Panel */
            .stats-panel {
                background: white;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 15px;
                margin-bottom: 15px;
            }
            .stat-card {
                text-align: center;
                padding: 20px 15px;
                border-radius: 10px;
                color: white;
                font-weight: 600;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                transition: transform 0.2s ease;
            }
            .stat-card:hover {
                transform: translateY(-2px);
            }
            .stat-number {
                font-size: 2.2em;
                display: block;
                margin-bottom: 8px;
                font-weight: 700;
            }
            .stat-label {
                font-size: 0.9em;
                text-transform: uppercase;
                letter-spacing: 1px;
                opacity: 0.9;
            }
            .total-projects { background: linear-gradient(135deg, #6c5ce7, #a29bfe); }
            .with-output { background: linear-gradient(135deg, #00b894, #00cec9); }
            .without-output { background: linear-gradient(135deg, #e17055, #fdcb6e); }
            
            /* Main content area */
            .main-content {
                display: flex;
                gap: 20px;
                flex: 1;
                min-height: 0;
            }
            
            /* Sidebar */
            .sidebar {
                width: 350px;
                flex-shrink: 0;
                display: flex;
                flex-direction: column;
                gap: 15px;
            }
            
            .controls-panel {
                background: white;
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                flex: 1;
            }
            
            .section-title {
                color: #2d3436;
                font-weight: 600;
                margin-bottom: 15px;
                font-size: 1.2em;
                padding-bottom: 8px;
                border-bottom: 2px solid #6c5ce7;
            }
            
            .control-group {
                margin-bottom: 20px;
            }
            
            .legend-panel {
                background: white;
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            }
            
            .legend-item {
                display: flex;
                align-items: center;
                margin-bottom: 10px;
                font-size: 0.95em;
            }
            .legend-color {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                margin-right: 10px;
                display: inline-block;
            }
            
            /* Map and Chart area */
            .content-area {
                flex: 1;
                display: flex;
                flex-direction: column;
                gap: 20px;
                min-width: 0;
            }
            
            .map-container {
                background: white;
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                flex: 1;
                min-height: 500px;
            }
            #map-display {
                height: 100%;
                border-radius: 8px;
                overflow: hidden;
            }
            
            .chart-container {
                background: white;
                border-radius: 12px;
                padding: 25px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                height: 600px;
            }
            .chart-title {
                color: #2d3436;
                font-weight: 600;
                margin-bottom: 20px;
                font-size: 1.5em;
                text-align: center;
            }
            #chart-display {
                height: calc(100% - 60px);
                width: 100%;
            }
        """),
    ),
    
    # Header
    ui.div(
        {"class": "app-header"},
        ui.h1("Project Geographic Distribution Dashboard", class_="app-title")
    ),
    
    # Statistics Panel
    ui.div(
        {"class": "stats-panel"},
        ui.div({"class": "stats-grid"}, ui.output_ui("stats_cards"))
    ),
    
    # Main content with sidebar layout
    ui.div(
        {"class": "main-content"},
        
        # Sidebar
        ui.div(
            {"class": "sidebar"},
            
            # Controls Panel
            ui.div(
                {"class": "controls-panel"},
                ui.h4("Filters & Settings", class_="section-title"),
                
                ui.div(
                    {"class": "control-group"},
                    ui.input_select("status_filter", "Project Status:",
                                  choices=["ALL", "SIGNED", "CLOSED", "TERMINATED"],
                                  selected="ALL"),
                    ui.input_select("output_filter", "Has Output:",
                                  choices=["ALL", "1", "0"],
                                  selected="ALL"),
                    ui.input_select("topic_filter", "Research Topic:",
                                  choices=["ALL"],
                                  selected="ALL"),
                    ui.input_select("subfund_filter", "Sub-fund:",
                                  choices=["ALL"],
                                  selected="ALL")
                ),
                
                ui.div(
                    {"class": "control-group"},
                    ui.input_slider("contrib_filter", "Funding Range (€):",
                                  min=0, max=500_000_000,
                                  value=(0, 500_000_000))
                ),
                
                ui.h5("Map Display", style="color: #2d3436; font-weight: 600; margin-bottom: 10px;"),
                ui.input_checkbox("show_heatmap", "Show Heatmap", value=True),
                ui.input_checkbox("show_markers", "Show Project Markers", value=True),
                ui.input_slider("heat_radius", "Heat Point Radius:",
                              min=5, max=50, value=25),
                ui.input_slider("heat_intensity", "Heat Intensity:",
                              min=0.1, max=2.0, value=1.0, step=0.1)
            ),
            
            # Legend Panel
            ui.div(
                {"class": "legend-panel"},
                ui.h5("Legend", class_="section-title"),
                ui.div(
                    {"class": "legend-item"},
                    ui.div({"class": "legend-color", "style": "background-color: #00b894;"}),
                    ui.span("Projects with output")
                ),
                ui.div(
                    {"class": "legend-item"},
                    ui.div({"class": "legend-color", "style": "background-color: #e17055;"}),
                    ui.span("Projects without output")
                ),
                ui.p("🗺️ Light base map for better heatmap visibility", style="margin: 10px 0 5px 0; font-size: 0.9em;"),
                ui.p("👆 Hover markers for project details", style="margin: 5px 0; font-size: 0.9em;"),
                ui.p("🔥 Heatmap shows project density", style="margin: 5px 0; font-size: 0.9em;")
            )
        ),
        
        # Content Area
        ui.div(
            {"class": "content-area"},
            
            # Map Container
            ui.div(
                {"class": "map-container"},
                ui.div({"id": "map-display"}, ui.output_ui("map"))
            ),
            
            # Chart Container
            ui.div(
                {"class": "chart-container"},
                ui.h3("Top 10 Organizations by Project Participation", class_="chart-title"),
                ui.div({"id": "chart-display"}, ui.output_ui("organization_chart"))
            )
        )
    )
)

# Server logic
def server(input, output, session):
    # Initialize filter options
    @reactive.effect
    def _():
        try:
            proj_df = pd.read_csv(r"C:\Users\wency\Desktop\project(1).csv", sep=',', on_bad_lines='skip', encoding='utf-8')

            if 'topic' in proj_df.columns:
                topics = sorted(proj_df['topic'].dropna().unique().tolist())
                ui.update_select("topic_filter", choices=["ALL"] + topics)

            if 'sub-fund' in proj_df.columns:
                subfunds = sorted(proj_df['sub-fund'].dropna().unique().tolist())
                ui.update_select("subfund_filter", choices=["ALL"] + subfunds)
        except Exception:
            pass

    # Filter data
    @reactive.Calc
    def filtered_data():
        try:
            return load_data(
                status_filter=input.status_filter(),
                output_filter=input.output_filter(),
                topic_filter=input.topic_filter(),
                subfund_filter=input.subfund_filter(),
                contrib_range=input.contrib_filter()
            )
        except SilentException:
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    # Statistics cards
    @output
    @render.ui
    def stats_cards():
        df = filtered_data()
        if df.empty:
            return ui.div(
                {"class": "stat-card total-projects"},
                ui.span("0", class_="stat-number"),
                ui.span("No Data Available", class_="stat-label")
            )
        
        total_projects = len(df)
        with_output = (df['output'] == 1).sum()
        without_output = (df['output'] == 0).sum()
        
        return [
            ui.div(
                {"class": "stat-card total-projects"},
                ui.span(f"{total_projects:,}", class_="stat-number"),
                ui.span("Total Projects", class_="stat-label")
            ),
            ui.div(
                {"class": "stat-card with-output"},
                ui.span(f"{with_output:,}", class_="stat-number"),
                ui.span("With Output", class_="stat-label")
            ),
            ui.div(
                {"class": "stat-card without-output"},
                ui.span(f"{without_output:,}", class_="stat-number"),
                ui.span("Without Output", class_="stat-label")
            )
        ]

    # Get organization data for chart based on current filters
    @reactive.Calc
    def organization_data():
        try:
            # Get filtered project data
            filtered_proj_df = filtered_data()
            if filtered_proj_df.empty:
                return pd.DataFrame()
            
            # Get the list of filtered project IDs
            filtered_project_ids = filtered_proj_df['project_id'].unique()
            
            # Load organization data if not cached
            if not hasattr(load_data, 'org_df'):
                org_df = pd.read_csv(r"C:\Users\wency\Desktop\organization.csv", sep=';', on_bad_lines='skip', encoding='utf-8')
                load_data.org_df = org_df
            else:
                org_df = load_data.org_df
            
            # Filter organizations based on filtered projects
            filtered_org_df = org_df[org_df['projectID'].isin(filtered_project_ids)].copy()
            
            if filtered_org_df.empty:
                return pd.DataFrame()
            
            # Count project participation by organization for filtered projects only
            org_participation = filtered_org_df.groupby('organisationID').agg({
                'projectID': 'nunique',  # Count unique projects per organization
                'name': 'first',         # Get organization name
                'country': 'first'       # Get country
            }).reset_index()
            
            org_participation.columns = ['organisationID', 'project_count', 'name', 'country']
            
            # Sort and get top 10 organizations
            top_orgs = org_participation.nlargest(10, 'project_count')
            
            return top_orgs
        except Exception as e:
            print(f"Error in organization_data: {e}")
            return pd.DataFrame()

    # Enhanced dynamic organization chart
    @output
    @render.ui
    def organization_chart():
        try:
            df = organization_data()
            
            if df.empty:
                return ui.HTML("<div style='text-align: center; color: #6c757d; font-size: 1.2em; padding: 50px;'>No organization data available for current filters.</div>")
            
            # Get current filter info for chart title
            filters_applied = []
            if input.status_filter() != "ALL":
                filters_applied.append(f"Status: {input.status_filter()}")
            if input.output_filter() != "ALL":
                output_text = "With Output" if input.output_filter() == "1" else "Without Output"
                filters_applied.append(f"Output: {output_text}")
            if input.topic_filter() != "ALL":
                filters_applied.append(f"Topic: {input.topic_filter()}")
            if input.subfund_filter() != "ALL":
                filters_applied.append(f"Sub-fund: {input.subfund_filter()}")
            
            # Create chart title with applied filters
            chart_title = "Top 10 Organizations by Project Participation"
            if filters_applied:
                filter_text = " | ".join(filters_applied)
                chart_subtitle = f"Filtered by: {filter_text}"
            else:
                chart_subtitle = "All Projects"
            
            # Create full organization names with country
            org_display_names = []
            for _, row in df.iterrows():
                name = str(row['name']) if pd.notna(row['name']) else 'Unknown'
                country = str(row['country']) if pd.notna(row['country']) else 'Unknown'
                display_name = f"{name} ({country})"
                org_display_names.append(display_name)
            
            # Create horizontal bar chart with enhanced styling
            fig = go.Figure(data=[
                go.Bar(
                    x=df['project_count'].tolist(),
                    y=org_display_names,
                    orientation='h',
                    marker=dict(
                        color=df['project_count'].tolist(),
                        colorscale='viridis',
                        showscale=True,
                        colorbar=dict(
                            title="Project Count",
                            titlefont=dict(size=14),
                            tickfont=dict(size=12)
                        ),
                        line=dict(color='rgba(50,50,50,0.8)', width=1)
                    ),
                    text=[f"{count} projects" for count in df['project_count'].tolist()],
                    textposition='outside',
                    textfont=dict(size=12, color='#2d3436'),
                    hovertemplate='<b>%{y}</b><br>' +
                                 'Projects: %{x}<br>' +
                                 '<extra></extra>'
                )
            ])
            
            fig.update_layout(
                title=dict(
                    text=f"{chart_title}<br><span style='font-size:14px;color:#6c757d'>{chart_subtitle}</span>",
                    x=0.5,
                    font=dict(size=18, color='#2d3436')
                ),
                xaxis_title="Number of Projects",
                yaxis_title="Organization",
                height=500,
                margin=dict(l=300, r=100, t=80, b=50),
                plot_bgcolor='rgba(248,249,250,0.8)',
                paper_bgcolor='white',
                font=dict(size=12, family="Segoe UI, sans-serif"),
                showlegend=False,
                xaxis=dict(
                    gridcolor='rgba(200,200,200,0.3)',
                    gridwidth=1,
                    showgrid=True,
                    tickfont=dict(size=12)
                ),
                yaxis=dict(
                    gridcolor='rgba(200,200,200,0.3)',
                    gridwidth=1,
                    showgrid=True,
                    tickfont=dict(size=11),
                    automargin=True
                )
            )
            
            # Generate chart HTML
            chart_html = fig.to_html(
                include_plotlyjs=True,
                config={
                    'displayModeBar': True,
                    'displaylogo': False,
                    'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d']
                },
                div_id="plotly-chart"
            )
            
            return ui.HTML(chart_html)
            
        except Exception as e:
            print(f"Error in organization_chart: {e}")
            return ui.HTML(f"<div style='text-align: center; color: red; font-size: 1.2em; padding: 50px;'>Error creating chart: {str(e)}</div>")

    # Map display
    @output
    @render.ui
    def map():
        df = filtered_data()
        if df.empty:
            return ui.HTML("<p style='text-align: center; color: #6c757d; font-size: 1.2em; padding: 50px;'>No projects to display on the map.</p>")

        m = folium.Map(location=[48.86, 2.35], zoom_start=3, tiles='CartoDB Positron')

        if input.show_heatmap():
            heat_data = df[['lat', 'lon']].values.tolist()
            HeatMap(
                heat_data,
                radius=input.heat_radius(),
                blur=20,
                max_zoom=10
            ).add_to(m)

            # Add colormap legend for heatmap
            colormap = cm.LinearColormap(
                ['blue', 'lime', 'red'],
                vmin=0, vmax=1,
                caption='Project Density Heatmap'
            )
            colormap.add_to(m)

        if input.show_markers():
            for _, row in df.iterrows():
                color = 'green' if row['output'] == 1 else 'orange'
                folium.Marker(
                    location=[row['lat'], row['lon']],
                    popup=folium.Popup(
                        f"<b>Title:</b> {row['title']}<br>"
                        f"<b>ID:</b> {row['project_id']}<br>"
                        f"<b>Status:</b> {row['status']}<br>"
                        f"<b>Output:</b> {row['output']}<br>"
                        f"<b>Contribution:</b> €{float(row['contribution']):,.0f}<br>"
                        f"<b>Start Date:</b> {row['start_date']}<br>"
                        f"<b>End Date:</b> {row['end_date']}<br>"
                        f"<b>Sub-fund:</b> {row['sub_fund']}<br>"
                        f"<b>Topic:</b> {row['topic']}",
                        max_width=300
                    ),
                    icon=folium.Icon(color=color)
                ).add_to(m)

        return ui.HTML(m._repr_html_())

app = App(app_ui, server)

if __name__ == "__main__":
    import shiny
    shiny.run_app(app)