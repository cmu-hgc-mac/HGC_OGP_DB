import os, yaml, sys, logging
import numpy as np
import pandas as pd

pjoin = os.path.join

from src.parse_data import DataParser
from src.ogp_height_plotter import PlotTool
from src.param import modules_params as component_params
from src.param import pin_mapping
from src.legacy_func import calculate_sensor_alignment
from src.config_utils import setup_logging
from rich.console import Console
from rich.table import Table

def test_angle_calculations(sample_path, comp_type):
    """Compare angle calculations between legacy and new implementation."""
    # Setup the same test data used in both functions
    logging.warning("New Method results ...")
    parser = DataParser(sample_path, 'tests')
    meta, features = parser()

    with open(meta[0], 'r') as f:
        metadata = yaml.safe_load(f)
        
    setup_logging(level=logging.INFO)
    sample_name = os.path.basename(sample_path)
    logging.info(f"Running comparison for {sample_name} with component type {comp_type}")
    feature_df = pd.read_csv(features[0])
    
    # Get results from new implementation (PlotTool)
    PT = PlotTool(metadata, comp_type, feature_df, 'rwOGP/templates/trays', 'tests')
    FD_points = PT.get_FDs()

    FD_x = FD_points[:,0]
    len_non_nan = len(FD_x[~np.isnan(FD_x)])

    hole_xy, slot_xy = PT.get_pin_coordinates()
    position = PT.meta['PositionID']
    
    # Calculate using new method
    centeroff_new, angleoff_new, xoff_new, yoff_new = PT.angle(hole_xy, slot_xy, FD_points)

    logging.warning("Legacy function results ...")
    
    # Prepare data for legacy function
    legacy_points = {
        "Center.X": hole_xy[0],
        "Center.Y": hole_xy[1],
        "OffCenter.X": slot_xy[0],
        "OffCenter.Y": slot_xy[1]
    }
    
    for i, point in enumerate(FD_points[~np.isnan(FD_x)]):
        legacy_points[i] = point
    
    # Calculate using legacy method
    centeroff_legacy, angleoff_legacy, x_off, y_off = calculate_sensor_alignment(
        legacy_points, 
        FDpoints=len_non_nan,
        OffCenterPin="Left" if position == 1 else "Right"
    )
    
    # Compare results using rich table and convert distances to micrometers
    console = Console()
    table = Table(title="Comparison of Angle Calculation Methods")

    # Add columns
    table.add_column("Measurement", style="cyan")
    table.add_column("New", justify="right", style="green")
    table.add_column("Legacy", justify="right", style="yellow")
    table.add_column("Difference", justify="right", style="red")

    # Convert center offsets to micrometers (multiply by 1000)
    centeroff_new_um = centeroff_new * 1000
    centeroff_legacy_um = centeroff_legacy * 1000
    diff_center_um = abs(centeroff_new_um - centeroff_legacy_um)

    # Convert x and y offsets to micrometers
    xoff_new_um = xoff_new * 1000
    yoff_new_um = yoff_new * 1000
    x_off_um = x_off * 1000
    y_off_um = y_off * 1000

    # Add rows
    table.add_row(
        "Center Offset (µm)",
        f"{centeroff_new_um:.1f}",
        f"{centeroff_legacy_um:.1f}",
        f"{diff_center_um:.1f}"
    )
    table.add_row(
        "Angle Offset (deg)",
        f"{angleoff_new:.3f}",
        f"{angleoff_legacy:.3f}",
        f"{abs(angleoff_new-angleoff_legacy):.3f}"
    )
    table.add_row(
        "X Offset (µm)",
        f"{xoff_new_um:.1f}",
        f"{x_off_um:.1f}",
        f"{abs(xoff_new_um-x_off_um):.1f}"
    )
    table.add_row(
        "Y Offset (µm)",
        f"{yoff_new_um:.1f}",
        f"{y_off_um:.1f}",
        f"{abs(yoff_new_um-y_off_um):.1f}"
    )
    # Print the table
    console.print(table)

def test_module_workflow(sample_path, comp_type, tray_dir):
    setup_logging(level=logging.INFO)
    parser = DataParser(sample_path, f'tests/{comp_type}')
    meta, features = parser()

    with open(meta[0], 'r') as f:
        metadata = yaml.safe_load(f)
        
    setup_logging()

    feature_df = pd.read_csv(features[0])
    PT = PlotTool(metadata, comp_type, feature_df, tray_dir, f'tests/{comp_type}')
    
    im_args = {"vmini":component_params['vmini'], "vmaxi":component_params['vmaxi'], 
            "new_angle": component_params['new_angle'], "savename": "ex_heights",
            "mod_flat": metadata['Flatness'], "title": metadata['ComponentID'], "show_plot": True}
    
    PT.get_offsets()
    PT(**im_args)