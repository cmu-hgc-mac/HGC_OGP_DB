from colorama import Fore
baseplates_params = {"key":"Surface", "vmini": 1.2, "vmaxi": 2.2, "new_angle": 0, "db_table_name": 'bp_inspect', "material": 'cf'}
hexaboards_params = {"key":"Flatness", "vmini": 1.2, "vmaxi": 2.9, "new_angle": 0, "db_table_name": 'hxb_inspect'}
protomodules_params = {"key":"Thick", "vmini": 1.37, "vmaxi": 1.79, "new_angle": 270, "db_table_name": 'proto_inspect'}
modules_params = {"key":"Thick", "vmini": 2.75, "vmaxi": 4.0, "new_angle": 270, "db_table_name": 'module_inspect'}

one_tray_param = {
            'P1Center.X': 142.648,
            'P1Center.Y': 298.465,
            'P2Center.X': 91.899,
            'P2Center.Y': 107.959,
            'P1LEFT.X': 67.688,
            'P1LEFT.Y': 298.445,
            'P2LEFT.X': 16.949,
            'P2LEFT.Y': 107.939,
            'P1RIGHT.X': 217.585,
            'P1RIGHT.Y': 298.455,
            'P2RIGHT.X': 166.848,
            'P2RIGHT.Y': 107.969,
        }

colorClassify = {'-1': Fore.MAGENTA + 'NO INFO' + Fore.BLACK, 
                       '0': Fore.GREEN + 'GREEN' + Fore.BLACK,
                       '1': Fore.YELLOW + 'YELLOW' + Fore.BLACK, 
                       '2': Fore.RED + 'RED' + Fore.BLACK}
classify = {'-1': 'NO INFO',
                         '0': 'GREEN',
                         '1': 'YELLOW',
                         '2': 'RED'}
degrees = [0.03, 0.06, 90]
centers = [0.050, 0.100, 10.0]

header_template = """
{{ ProjectName }}
LastModified: {{ LastModifiedDate }} {{ LastModifiedTime }}
Runtime: {{ RunDate }} {{ RunTime }}
Component ID: {{ ComponentID }}
Operator: {{ Operator }}
Geometry: {{ Geometry }}
Density: {{ Density }}
Sensor size: {{ SensorSize }}
Flatness: {{ Flatness }}
Thickness: {{Thickness}}
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