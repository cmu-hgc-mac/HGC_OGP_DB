from colorama import Fore
baseplates_params = {"key":"Surface", "vmini": 1.2, "vmaxi": 2.2, "new_angle": 0, "db_table_name": 'bp_inspect', "material": 'cf'}
hexaboards_params = {"key":"Flatness", "vmini": 1.2, "vmaxi": 2.9, "new_angle": 0, "db_table_name": 'hxb_inspect'}
protomodules_params = {"key":"Thick", "vmini": 1.37, "vmaxi": 1.79, "new_angle": 270, "db_table_name": 'proto_inspect'}
modules_params = {"key":"Thick", "vmini": 2.75, "vmaxi": 4.0, "new_angle": 270, "db_table_name": 'module_inspect'}

comptable = {'baseplate':{'prefix': 'bp'},'hexaboard':{'prefix': 'hxb'},'protomodule':{'prefix': 'proto'},'module':{'prefix': 'module'}}

default_params = {"PositionID": 1, "Geometry": "Full", "Density": "LD", "TrayNo": 1}

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

pin_mapping = {
    'Full': {'LD': {1: ('p1_center_pin', 'p1O'), 2: ('p2_center_pin', 'p2M')},
             'HD': {1: ('p1_center_pin', 'p1O'), 2: ('p2_center_pin', 'p2M')}},
    'Left': {'LD': {1: ('p1C', 'p1I'), 2: ('p2A', 'p2K')},
             'HD': {1: ('p1F', 'p1P'), 2: ('p2H', 'p2N')}},
    'Right': {'LD': {1: ('p1A', 'p1K'), 2: ('p2C', 'p2I')},
              'HD': {1: ('p1H', 'p1N'), 2: ('p2F', 'p2P')}},
    'Top': {'LD': {1: ('p1D', 'p1O'), 2: ('p2B', 'p2M')},
            'HD': {1: ('p1E', 'p1O'), 2: ('p2G', 'p2M')}},
    'Bottom': {'LD': {1: ('p1B', 'p1M'), 2: ('p2D', 'p2O')},
               'HD': {1: ('p1_center_pin', 'p1M'), 2: ('p2_center_pin', 'p2O')}},
    'Five': {'LD': {1: ('p1_center_pin', 'p1I'), 2: ('p2_center_pin', 'p2K')},
             'HD': {1: ('p1_center_pin', 'p1I'), 2: ('p2_center_pin', 'p2K')}}
}

ADJUSTMENTS = {
    'protomodules': {
        'Full':   {'LD': {1: (0, 0),      2: (0, 0)},      'HD': {1: (0, 0),       2: (0, 0)}},
        'Five':   {'LD': {1: (0, 0),      2: (0, 0)},      'HD': {1: (0, 0),       2: (0, 0)}},
        'Top':    {'LD': {1: (-9.72, 0),  2: (9.72, 0)},   'HD': {1: (-8.44, 0),   2: (8.44, 0)}},
        'Bottom': {'LD': {1: (9.72, 0),   2: (-9.72, 0)},  'HD': {1: (-16, 0),     2: (16, 0)}},
        'Right':  {'LD': {1: (0, 9.72),   2: (0, -9.72)},  'HD': {1: (0, 6.52),    2: (0, -6.52)}},
        'Left':   {'LD': {1: (0, -9.72),  2: (0, 9.72)},   'HD': {1: (0, -6.52),   2: (0, 6.52)}}
    },
    'modules': {
        'Full':   {'LD': {1: (0, 0),      2: (0, 0)},      'HD': {1: (0, 0),       2: (0, 0)}},
        'Five':   {'LD': {1: (0, 0),      2: (0, 0)},      'HD': {1: (0, 0),       2: (0, 0)}},
        'Top':    {'LD': {1: (-8, 0),     2: (8, 8)},      'HD': {1: (-4, 0),      2: (4, 8)}},
        'Bottom': {'LD': {1: (9, 8),      2: (-9, 8)},     'HD': {1: (-15, 0),     2: (15, 0)}},
        'Right':  {'LD': {1: (0, 18),     2: (0, -18)},    'HD': {1: (0, 5),       2: (0, -5)}},
        'Left':   {'LD': {1: (0, -18),    2: (0, 18)},     'HD': {1: (0, -5),      2: (0, 5)}}
    }
}

# DataParser looks for these keys in the metadata
required_keys = ['TrayNo', 'ComponentID', 'Operator', 'Geometry', 'Density', 'Flatness', 'PositionID']
warning_keys = ['Thickness', 'SensorSize']

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