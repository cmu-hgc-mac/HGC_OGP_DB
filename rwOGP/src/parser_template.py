# This file contains the template for the parser
header_template_bp_hxb = """
{{ ProjectName }}
LastModified: {{ LastModifiedDate }} {{ LastModifiedTime }}
Runtime: {{ RunDate }} {{ RunTime }}
Component ID: {{ ComponentID }}
Operator: {{ Operator }}
Geometry: {{ Geometry }}
Density: {{ Density }}
Sensor size: {{ SensorSize }}
Flatness: {{ Flatness }}
Thickness1: {{ Thickness1 }}
Thickness2: {{ Thickness2 }}
Thickness3: {{ Thickness3 }}
Thickness4: {{ Thickness4 }}
Thickness5: {{ Thickness5 }}
Thickness6: {{ Thickness6 }}
Thickness_Offset: {{Thickness_Offset}}
Position ID: {{ PositionID }}
TrayNo: {{ TrayNo }}
Comment: {{ Comment }}
"""

header_template_pm_module = """
{{ ProjectName }}
LastModified: {{ LastModifiedDate }} {{ LastModifiedTime }}
Runtime: {{ RunDate }} {{ RunTime }}
Component ID: {{ ComponentID }}
Operator: {{ Operator }}
Geometry: {{ Geometry }}
Density: {{ Density }}
Sensor size: {{ SensorSize }}
Flatness: {{ Flatness }}
Thickness: {{ Thickness }}
Thickness_Offset: {{Thickness_Offset}}
Position ID: {{ PositionID }}
TrayNo: {{ TrayNo }}
"""

data_template = """
{{FeatureType}} {{FeatureName}}
Point     {{X_coordinate}}    {{Y_coordinate}}    {{Z_coordinate}}
direction cosine:    {{I_coordinate}}    {{J_coordinate}}    {{K_coordinate}}
Radius            {{Radius}}
"""

data_template_simple = """
{{FeatureType}} {{FeatureName}}
Point\s+{{X_coordinate | float}}\s+{{Y_coordinate | float}}\s+{{Z_coordinate | float | default(None)}}
"""

# DataParser looks for these keys in the metadata
required_keys = ['TrayNo', 'ComponentID', 'Operator', 'Geometry', 'Density', 'Flatness', 'PositionID']
# If the following keys are missing from the header, a warning will be raised
warning_keys = ['Thickness', 'SensorSize', 'Comment', 'Thickness_Offset']
