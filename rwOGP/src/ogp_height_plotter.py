import numpy as np
import pandas as pd
import os, re, yaml, sys
import matplotlib.pyplot as plt
import matplotlib.colors as cls
from src.parse_data import DataParser
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from src.param import pin_mapping, plot2d_dim, ADJUSTMENTS, angle_lookup, ANGLE_CALC_CONFIG

pjoin = os.path.join

class ValueMissingError(Exception):
    pass

class ValueRangeError(Exception):
    pass

class MeasurementResults:
    def __init__(self):
        self.console = Console()
        self.fiducial_points = []
        self.pin_info = []
        self.offsets = []
        self.height_stats = []

    def add_fiducial(self, fd_number, x, y):
        self.fiducial_points.append([f'FD{fd_number}', f'{x:.3f}', f'{y:.3f}'])

    def add_pin(self, pin_type, x, y, description):
        self.pin_info.append([pin_type, f'{x:.3f}', f'{y:.3f}', description])

    def add_offset(self, measurement, value, unit):
        self.offsets.append([measurement, f'{value:.3f}', unit])

    def add_height_stat(self, measurement, value, unit='mm'):
        self.height_stats.append([measurement, f'{value:.3f}', unit])

    def display(self):
        # Fiducial Points Table
        if self.fiducial_points:
            rprint("[bold blue]Fiducial Points:[/bold blue]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("FD Number", style="cyan")
            table.add_column("X (mm)", style="green")
            table.add_column("Y (mm)", style="green")
            for row in self.fiducial_points:
                table.add_row(*row)
            self.console.print(table)
            print()  # Add a newline

        # Pin Information Table
        if self.pin_info:
            rprint("[bold blue]Pin Information:[/bold blue]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Pin Type", style="cyan")
            table.add_column("X (mm)", style="green")
            table.add_column("Y (mm)", style="green")
            table.add_column("Description", style="yellow")
            for row in self.pin_info:
                table.add_row(*row)
            self.console.print(table)
            print()  # Add a newline

        # Offsets Table
        if self.offsets:
            rprint("[bold blue]Measurement Offsets:[/bold blue]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Measurement", style="cyan")
            table.add_column("Value", style="green")
            table.add_column("Unit", style="yellow")
            for row in self.offsets:
                table.add_row(*row)
            self.console.print(table)
            print()  # Add a newline

        # Height Statistics Table
        if self.height_stats:
            rprint("[bold blue]Height Statistics:[/bold blue]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Measurement", style="cyan")
            table.add_column("Value", style="green")
            table.add_column("Unit", style="yellow")
            for row in self.height_stats:
                table.add_row(*row)
            self.console.print(table)

class PlotTool:
    def __init__(self, meta, component_type, features: 'pd.DataFrame', tray_dir, save_dir=None):
        """
        Parameters
        - `meta`: metadata of the features, including Tray ID, Operator, and Component ID
        - `component_type`: type of the component, either 'protomodules' or 'modules'
        - `features`: dataframe of features to plot
        - `save_dir`: directory to save the plots to"""
        self.save_dir = save_dir
        self.meta = meta
        self.comp_type = component_type.rstrip('s')
        self.tray_dir = tray_dir
        #! this is a hack
        self.features = DataParser.get_xyz(features, ['Tray'])
        self.x_points = self.features['X_coordinate']
        self.y_points = self.features['Y_coordinate']
        self.z_points = self.features['Z_coordinate']
        self.results = MeasurementResults()

        self.__check_save_dir()
    
    def __call__(self, **args):
        """Plot the 2D height map of the given data."""
        centerxy = self.get_center_for_plot()
        im_bytes = self.plot2d(self.x_points, self.y_points, self.z_points, centerxy, **args)
        return im_bytes
     
    def __check_save_dir(self):
        if self.save_dir is not None:
            if not os.path.exists(self.save_dir):
                print(f"Directory {self.save_dir} does not exist.")
                print("Creating save directory:", self.save_dir)
                os.makedirs(self.save_dir)
    
    def get_center_for_plot(self) -> int:
        """Get the index of the fiducial center in the dataframe by taking the average of the x and y coordinates."""
        center_x = (max(self.x_points) + min(self.x_points)) / 2
        center_y = (max(self.y_points) + min(self.y_points)) / 2
        print(f"Center = ({center_x:.3f}, {center_y:.3f}) mm")
        return (center_x, center_y)
    
    @staticmethod
    def _prepare_coordinates(x, y, centerxy, rotate, new_angle):
        """Prepare and transform coordinates."""
        center_x, center_y = centerxy
        x = x - center_x
        y = y - center_y

        assert rotate >= 0 and rotate < len(x), "The specified index for rotation has to be within the range of the data."
        if rotate != 0:
            rotate_angle = vec_angle(x[rotate-1], y[rotate-1]) if rotate != 0 else 0
            for i in range(len(x)):
                x[i], y[i] = vec_rotate(x[i], y[i], rotate_angle, new_angle)
        
        return x, y
    
    @staticmethod
    def _create_stats_text(mean_h, std_h, max_h, min_h, mod_flat=None):
        """Create statistics text for the plot."""
        base_stats = [
            f'mean: {mean_h:.3f} mm',
            f'std:     {std_h:.3f} mm',
            '',
            f'height: {mean_h:.3f} mm',
            f'       $+$ ({max_h - mean_h:.3f}) mm',
            f'       $-$ ({mean_h - min_h:.3f}) mm',
            '',
            f'$\Delta$H = {max_h - min_h:.3f} mm',
            '',
            f'maxH: {max_h:.3f} mm',
            f'minH:  {min_h:.3f} mm'
        ]
        
        if mod_flat is not None:
            base_stats.extend(['', f'flatness: {mod_flat:.3f}'])
        
        return '\n'.join(base_stats)
    
    @staticmethod
    def _save_plot_output(fig, savename):
        """Save plot to file and return bytes.
        
        Parameters
        ----------
        fig : matplotlib.figure.Figure
            The figure object to save
        savename : str
            Path where to save the figure
            
        Returns
        -------
        bytes
            The figure data in bytes format
        """
        from io import BytesIO
        buffer = BytesIO()
        fig.savefig(savename, bbox_inches='tight')
        fig.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        image_bytes = buffer.read()
        buffer.close()
        plt.close(fig)
        return image_bytes
    
    @staticmethod
    def plot2d(x, y, zheight, centerxy, vmini, vmaxi, new_angle, title, savename, mod_flat, show_plot, value=1, rotate=0):
        """Plot 2D height map of the given data.
        [... existing docstring ...]
        """
        mean_h, std_h, max_h, min_h = PlotTool._calculate_height_stats(zheight)
        
        x, y = PlotTool._prepare_coordinates(x, y, centerxy, rotate, new_angle)
        
        # Create plot
        fig = plt.figure(dpi=150, figsize=(9,5))
        axs = fig.add_subplot(111)
        axs.set_aspect('equal')
        
        # Plot data
        axs.hexbin(x, y, zheight, gridsize=20, vmin=vmini, vmax=vmaxi, cmap=plt.cm.coolwarm)
        norm = cls.Normalize(vmin=vmini, vmax=vmaxi)
        sm = plt.cm.ScalarMappable(norm=norm, cmap=plt.cm.coolwarm)
        cb = plt.colorbar(sm, ax=axs)
        cb.minorticks_on()
        
        # Set plot properties
        axs.set_xlabel("x (mm)")
        axs.set_ylabel("y (mm)")
        axs.minorticks_on()
        axs.set_xlim(plot2d_dim)
        axs.set_ylim(plot2d_dim)
        cb.set_label("Height (mm)")
        axs.set_title(title)
        
        # Add statistics text
        textstr = PlotTool._create_stats_text(mean_h, std_h, max_h, min_h, mod_flat)
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        axs.text(1.3, 1.0, textstr, transform=axs.transAxes, fontsize=10, verticalalignment='top', bbox=props)

        for xi, yi, zi in zip(x, y, zheight):
            axs.text(xi, yi, f"{zi:.2f}", fontsize=8, color='black', ha='center', va='bottom')
        
        if show_plot:
            plt.show()
            plt.close(fig)
            return None
            
        return PlotTool._save_plot_output(fig, savename)
    
    def get_FD_center(self, fd_indices, FDPoints):
        """Get the center of the fiducial points.

        Parameters
        ----------
        fd_indices : list
            Indices of fiducial points to use for center calculation
        FDPoints : np.ndarray
            Array of fiducial points with shape (n,2) where each row is (x,y)

        Returns
        -------
        np.ndarray
            Center point coordinates (x,y)
        """
        points_to_average = FDPoints[fd_indices]
        if np.any(np.isnan(points_to_average)):
            print(f"NaN values found in FD points {[i+1 for i in fd_indices]} used for default calculation.")
            userinput = input(f"Would you like to continue with the available points? (y/n): ")
            if userinput.lower() != 'y':
                raise ValueMissingError("Exiting... Please check the FD points and try again.")
            else:
                points_to_average = FDPoints[~np.isnan(FDPoints).any(axis=1)]
        FDCenter = np.mean(points_to_average, axis=0)
        return FDCenter

    def angle(self, holeXY:tuple, slotXY:tuple, FDPoints:np.array):
        """Calculate the angle and offset of the sensor from the tray fiducials.
        
        Parameters
        - `holeXY`: the location of the pin that corresponds to the HOLE in the base plate. the center pin for Full, LD/HD.
        - `slotXY`: the location of the pin that corresponds to the SLOT in the base plate. the offcenter pin for Full, LD/HD.
        - `FDPoints`: array of fiducial points: 2, 4, 6, or 8, FD points are accepted

        Return
        - `CenterOffset`: offset of the sensor from the tray center
        - `AngleOffset`: angle of the sensor from the tray fiducials
        - `XOffset`: x-offset of the sensor from the tray center
        - `YOffset`: y-offset of the sensor from the tray center"""

        geometry, density, position, CompType = self.meta['Geometry'], self.meta['Density'], self.meta['PositionID'], self.comp_type

        holeX, holeY = holeXY
        slotX, slotY = slotXY

        pinX = slotX - holeX     #X component of a vector pointing from hole to slot
        pinY = slotY - holeY     #Y component "" ""

        Hole = np.array([holeX, holeY])
        print(f'pinX: {pinX}  &  pinY: {pinY}')

        # Get the angle calculation function from the lookup dictionary
        density_dict = angle_lookup.get(geometry, {})
        position_dict = density_dict.get(density, density_dict.get('default', {}))
        angle_func = position_dict.get(position)

        if angle_func is None:
            raise ValueError(f"No angle calculation defined for geometry={geometry}, density={density}, position={position}")

        angle_Pin = angle_func(pinX, pinY)

        print(f'Pin Angle: {angle_Pin}')
    
        if density == 'HD':
            if geometry == 'Full':
                fd_indices = [0, 1, 2, 3] # FD1, FD2, FD3, FD4
            else:
                fd_indices = [0, 2] # FD1 and FD3
            FDCenter = self.get_FD_center(fd_indices, FDPoints)
        if density == 'LD':
            if geometry == 'Full':
                if CompType == 'module':
                    fd_indices = [2, 5] # FD3 and FD6
                elif CompType == 'protomodule':
                    fd_indices = [0, 1, 2, 3] # FD1, FD2, FD3, FD4
            else:
                fd_indices = [0, 2] # FD1 and FD3
            FDCenter = self.get_FD_center(fd_indices, FDPoints)

        adjustmentX, adjustmentY = ADJUSTMENTS[CompType][geometry][density][position]
        print(f'Adjustment X: ', adjustmentX, 'Adjustment Y: ', adjustmentY)
        
        XOffset = FDCenter[0]-Hole[0]-adjustmentX
        YOffset = FDCenter[1]-Hole[1]-adjustmentY
        print(f"Hole Vs FDCenter: {Hole} vs {FDCenter}")

        print(f"Assembly Survey X Offset: {XOffset:.3f} mm.")
        print(f"Assembly Survey Y Offset: {YOffset:.3f} mm. \n")

        CenterOffset = np.sqrt(XOffset**2 + YOffset**2)

        FD3to1 = FDPoints[0] - FDPoints[2]  #Vector from FD3 to FD1
        
        try:
            config = ANGLE_CALC_CONFIG[geometry]
            if isinstance(config, dict):
                config = config[density] if density in config else config
                if isinstance(config, dict):
                    config = config[position]

            angle_FD3to1 = config(FD3to1, FDPoints, CompType) # Angle of FD3 to FD1
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid configuration for geometry={geometry}, density={density}, position={position}")
        
        AngleOffset = angle_FD3to1 - angle_Pin

        return CenterOffset, AngleOffset, XOffset, YOffset

    def get_FDs(self) -> np.array:
        """Get the fiducial points from the features dataframe, ordered by the FD number.
        If none of the FDs are found, return False.
        
        Return 
        - `FD_points`: 8 by 2 array of fiducial points, empty points are filled with np.nan"""
        FD_points = self.features[self.features['FeatureName'].str.contains('FD')].copy()
        FD_points.loc[:, 'FD_number'] = FD_points['FeatureName'].apply(lambda x: int(re.search(r'FD(\d+)', x).group(1)) if re.search(r'FD(\d+)', x) else 0)
        FD_names = FD_points['FeatureName'].values
        FD_numbers = FD_points['FD_number'].values
        x_y_coords = FD_points[['X_coordinate', 'Y_coordinate']].values
        num_FDs = len(x_y_coords)
        if not num_FDs in {2, 4, 6, 8}:
            print("The number of fiducial points measured must be 2, 4, 6, or 8.")
            print(f"Measured {len(FD_names)} FDs:", FD_names)
            print("This program looks for keyword 'FD' in file output. Make sure you rename your routine to include 'FD' in the name.")
            raise ValueMissingError("Exiting... Please check the FD points and try again.")
        
        sort_indices = np.argsort(FD_numbers)
        FD_points = x_y_coords[sort_indices]
        print(f"Found {num_FDs} fiducial points: {FD_names}")

        FD_array = np.full((8,2), np.nan)
        for i, (x,y) in zip(FD_numbers, FD_points):
            print(f"FD{i}: ({x:.3f}, {y:.3f})")
            FD_array[i-1] = [x,y]

        return FD_array

    def get_offsets(self):
        """Get the offsets of the sensor from the tray fiducials.
        
        Return 
        - `XOffset`: x-offset of the sensor from the tray center
        - `YOffset`: y-offset of the sensor from the tray center
        - `AngleOff`: angle of the sensor from the tray fiducials"""
        PositionID, Geometry, density, TrayNo = self.meta['PositionID'], self.meta['Geometry'], self.meta['Density'], self.meta['TrayNo']

        TrayFile = pjoin(self.tray_dir, f"Tray{TrayNo}.yaml") 
        print(f"Using Tray {TrayNo} info...")
        
        print(f"Geometry: {Geometry}; Density: {density}; PositionID: {PositionID}; Comp_Type: {self.comp_type}")

        with open(TrayFile, 'r') as f:
            trayinfo = yaml.safe_load(f)

        HolePin, SlotPin = pin_mapping.get(Geometry, {}).get(density, {}).get(PositionID, ('', ''))

        if HolePin == '' or SlotPin == '':
            print(f"Could not find the HolePin and SlotPin for the given Geometry: {Geometry} and Density: {density}.")

        HolePin_xy = tuple(trayinfo[f'{HolePin}_xy'])  
        SlotPin_xy = tuple(trayinfo[f'{SlotPin}_xy'])

        FD_points = self.get_FDs()
        
        plotFD(FD_points, HolePin_xy, SlotPin_xy, True, pjoin(self.save_dir, f"{self.meta['ComponentID']}_FDpoints.png"))
        
        print(f'Calculating Angle and Offsets with:  {HolePin} @: {HolePin_xy} & {SlotPin} @: {SlotPin_xy} \n')
        

        CenterOff, AngleOff, XOffset, YOffset = self.angle(HolePin_xy, SlotPin_xy, FD_points)

        if PositionID == 1:
            NEWY = XOffset*-1;
            NEWX = YOffset; 
        elif PositionID == 2:
            NEWY = XOffset;
            NEWX = YOffset*-1; 
        
        print(f"Rotational Offset is {AngleOff:.5f} degrees; Center Offset is {CenterOff:.3f} mm")

        if abs(AngleOff) > 20:
            raise ValueRangeError("The calculated angle offset is too large. Check the fiducial points and the sensor position (Pos 1 vs. 2)")
        if abs(XOffset) > 5 or abs(YOffset) > 5:
            raise ValueRangeError("The calculated offset is too large. Check the fiducial points and the sensor position (Pos 1 vs. 2)")

        return NEWX, NEWY, AngleOff
    
    @staticmethod
    def _calculate_height_stats(zheight):
        """Calculate basic height statistics."""
        mean_h = np.mean(zheight)
        std_h = np.std(zheight)
        max_h = max(zheight)
        min_h = min(zheight)

        print(f"Average Height = {mean_h:.3f} mm; Maximum Height = {max_h:.3f} mm; Minimum Height = {min_h:.3f} mm")
        print(f"Height = {mean_h:.3f} + ({max_h - mean_h:.3f}) - ({mean_h - min_h:.3f}) mm. \n")

        return mean_h, std_h, max_h, min_h

def vec_angle(x,y):
    angle_arctan = np.degrees(np.arctan2(y,x))
    return angle_arctan

def vec_rotate(old_x, old_y, old_angle, new_angle = 120):
    """Rotate a vector by a given angle.

    Parameters
    - `old_x`: x-coordinate of the vector
    - `old_y`: y-coordinate of the vector
    - `old_angle`: angle of the vector
    - `new_angle`: angle to rotate the vector to"""
    rad = np.radians(new_angle - old_angle)
    new_x = old_x*np.cos(rad)-old_y*np.sin(rad)
    new_y = old_x*np.sin(rad)+old_y*np.cos(rad)
    return new_x, new_y
    
def plotFD(FDpoints:np.array, holeXY:tuple, slotXY:tuple, save=False, save_name='') -> None:
    """Plot the fiducial points and the center of the sensor.
    
    Parameters
    - `FDpoints`: array of fiducial points
    - `holeXY`: HOLE in the BP. The center pin for Full, LD/HD.
    - `slotXY`: SLOT in the BP. The offcenter pin for Full, LD/HD.
    - `save`: whether to save the plot. Incompatible with showing the plot.
    - `save_name`: name to save the plot as"""
    CenterX, CenterY = holeXY
    OffX, OffY = slotXY

    plt.figure()
    FDnames = ['FD1', 'FD2', 'FD3', 'FD4', 'FD5', 'FD6', 'FD7', 'FD8']
    plt.plot(FDpoints[:,0], FDpoints[:,1], 'ro', ms=2)
    plt.plot(CenterX, CenterY, 'ro', ms=2)
    plt.annotate('CenterPin', (CenterX, CenterY))
    plt.plot(OffX, OffY, 'bo', ms=2)
    plt.annotate('OffcenterPin', (OffX, OffY))
    plt.arrow(OffX, OffY, CenterX-OffX, CenterY-OffY, lw=0.5, color='g')
    for i, (x, y) in enumerate(FDpoints):
        if not np.isnan(x) and not np.isnan(y):
            plt.annotate(FDnames[i], (x, y))
    
    plt.xlim(50,350)
    plt.xlabel("x [mm]")
    plt.ylabel("y [mm]")

    plt.title("Fiducial Points")
    if save:
        plt.savefig(save_name)
        print("Saved FD plot to", save_name)
    else: plt.show()
    plt.close()

def grade(CenterOffset, AngleOff):
    """Quality Control for modules
    
    Parameters
    - `CenterOffset`: offset of the sensor from the tray center. In mm
    - `AngleOff`: angle of the sensor from the tray fiducials. In degrees
    """
    '''
    QC designation for different measurements
    Measurement      |         GREEN          |        YELLOW         |          RED          |
    _________________|________________________|_______________________|_______________________|
    Angle of Plac.   |0 < abs(x - 90.) <= 0.03 |0.03 < abs(x - 90.) <= .06| 0.06 < abs(x - 90.)<90| 
    Placement        |      0 < x <= 0.05     |    0.05 < x <= 0.1    |      0.1 < x <= 10.   | 
    Height           |0 < abs(x - Nom) <= 0.05|0.05 <abs(x - Nom)<=0.1|0.1 < abs(x - Nom)<=10.| 
    Max Hght from Nom|      0 < x <= 0.05     |    0.05 < x <= 0.1    |    0.1 < x <= 10.     | 
    Min Hght ffrom Nom|      0 < x <= 0.05     |    0.05 < x <= 0.1    |    0.1 < x <= 10.     | 
    
#     '''
    X_Offset, Y_Offset = CenterOffset
    X_Offset *= 1000
    Y_Offset *= 1000
    
    if X_Offset <= 50 and Y_Offset <= 50 and AngleOff <= 0.02:
        return "A"
    elif X_Offset <= 100 and Y_Offset <= 100 and AngleOff <= 0.04:
        return "B"
    else:
        return "C"
