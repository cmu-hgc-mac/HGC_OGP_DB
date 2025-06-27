import numpy as np
import pandas as pd
import send2trash, yaml, os, logging
import matplotlib
matplotlib.use('Agg')
from src.ogp_height_plotter import PlotTool, grade, ValueMissingError, ValueRangeError
from src.upload_inspect import DBClient
from src.make_accuracy_plot import make_accuracy_plot
from src.param import COMPONENT_PARAMS, COMP_PREFIX
from datetime import datetime

pbase = os.path.basename
pdir = os.path.dirname
pjoin = os.path.join

class SurveyProcessor():
    """Process Parsed OGP Survey CSV files and extract data for plotting and uploading to database."""
    def __init__(self, OGPSurveyFilePath: list, MetaFilePath: list, yamlconfig: dict):
        """Initialize ImageProcessor object.
        
        Parameters:
        - OGPSurveyFilePath (list): (list of) Paths to parsed output csvs of OGP Surveys.
        - MetaFilePath (list): Paths to the metadata file for the OGP Survey files."""
        self.OGPSurveyFile = OGPSurveyFilePath
        self.MetaFile = MetaFilePath

        for i, file in enumerate(self.OGPSurveyFile):
            if not file.endswith('.csv'):
                raise ValueError('Parsed OGP result must be a csv file.')
            self.OGPSurveyFile[i] = file.replace('\\', '/')
        
        im_dir = yamlconfig.get('ogp_image_dir')
        if not os.path.exists(im_dir):
            os.makedirs(im_dir)
        self.im_dir = im_dir
        self.tray_dir = yamlconfig.get('ogp_tray_dir')
        logging.debug(f"Using tray files from directory: {self.tray_dir}")

        self.client = DBClient(yamlconfig)
        pass

    async def __call__(self, component_type) -> tuple[bool, int]:
        """Process and upload OGP Survey files."""
        status, index = await self.process_and_upload(component_type)
        return status, index
 
    async def __getArgs__(self, ex_file, meta_file, comp_type):
        """Get arguments for uploading to database, including the necessary meta data to upload and the image bytes.
        
        Return 
        - db_upload (dict): Dictionary of data to upload to database.
        - component_params (dict): Dictionary of parameters for the component type.
        - comp_type (str): Component folder name."""
        with open(meta_file, 'r') as f:
            metadata = yaml.safe_load(f)
        
        singular_type = comp_type.rstrip('s')
        compID = metadata['ComponentID']

        if singular_type == 'protomodule': 
            compID = compID.replace('ML', 'PL', 1)
            metadata['ComponentID'] = compID
            
        df = pd.read_csv(ex_file)
        plotter = PlotTool(metadata, comp_type, df, self.tray_dir, pjoin(self.im_dir, comp_type))
        filesuffix = pbase(ex_file).split('.')[0]

        logging.info("=" * 100)
        logging.info(f"###### Calculating offsets for {comp_type} {compID} #######")

        
        component_params = COMPONENT_PARAMS[singular_type]
        name_field = f'{COMP_PREFIX[singular_type]}_name'
        db_upload = {name_field: compID}

        if singular_type == 'baseplate' or singular_type == 'hexaboard':
            Offset = metadata.get("Thickness_Offset", 0)
            thickness_list = [metadata.get(f'Thickness{i}', None) for i in range(1, 6)]
            thickness_list = [float(t) for t in thickness_list if t is not None]
            if len(thickness_list) == 0: logging.warning(f"No valid thickness values found in metadata for {compID}.")
            report_thick = np.average(thickness_list)
            logging.info(f"Unconstrained thickness reported by OGP {report_thick} - Offset: {Offset}")
            report_thick -= Offset
            db_upload.update({'flatness': np.round(metadata['Flatness'], 3), 'thickness': np.round(report_thick, 3)})
        elif singular_type == 'protomodule' or singular_type == 'module':
            XOffset, YOffset, AngleOff = plotter.get_offsets()
            db_upload.update({'x_offset_mu':np.round(XOffset*1000), 'y_offset_mu':np.round(YOffset*1000), 'ang_offset_deg':np.round(AngleOff,3),
                              "weight": metadata.get('Weight', None), 'max_thickness': np.round(np.max(plotter.z_points),3), "flatness": np.round(metadata['Flatness'],3),
                             'avg_thickness': np.round(np.mean(plotter.z_points),3), 'grade': grade((XOffset, YOffset), AngleOff)})
            if singular_type == 'module':
                PMoffsets = await self.client.GrabSensorOffsets(compID)
                SensorXOffset, SensorYOffset, SensorAngleOff = PMoffsets
                PCBXOffset, PCBYOffset, PCBAngleOff = int(XOffset*1000), int(YOffset*1000), AngleOff
            else:
                PCBXOffset, PCBYOffset, PCBAngleOff = 0, 0, 0 
                SensorXOffset, SensorYOffset, SensorAngleOff = int(XOffset*1000), int(YOffset*1000), AngleOff
            logging.debug(f"Making Accuracy Plot With Sensor Offsets {SensorXOffset}, {SensorYOffset}, {SensorAngleOff}")
            acc_bytes = make_accuracy_plot(compID, pjoin(self.im_dir, comp_type), SensorXOffset, SensorYOffset, SensorAngleOff, PCBXOffset, PCBYOffset, PCBAngleOff)
            db_upload.update({"offsetplot": acc_bytes})
        else:
            raise ValueError("Component type not recognized. Supporting only baseplate, hexaboard, protomodule, and module.")

        im_args = {"vmini":component_params['vmini'], "vmaxi":component_params['vmaxi'], 
                   "new_angle": component_params['new_angle'], "savename": pjoin(self.im_dir, comp_type, f"{filesuffix}_heights"),
                   "mod_flat": metadata['Flatness'], "title": metadata['ComponentID'], "show_plot": False}
        
        logging.debug(f"###### Generating Image for {compID} #######")
        
        im_bytes = plotter(**im_args)

        db_upload.update({'x_points':(plotter.x_points).tolist(), 'y_points':(plotter.y_points).tolist(), 
            'z_points':(plotter.z_points).tolist(),'hexplot':im_bytes, 'inspector': metadata['Operator'], 'comment':metadata.get("Comment", None)})
        
        db_upload.update(self.getDateTime(metadata))

        return db_upload, component_params, compID  
    
    async def process_and_upload(self, comp_type) -> tuple[bool, int]:
        """Process all OGP Survey files and upload to database.
        
        Parameters:
        - `comp_type` (str): Type of component to process.
        
        Returns:
        - tuple[bool, int]: 
            - bool: True if all files were successfully uploaded, False if any file fails
            - int: Index of the last successfully processed file (-1 if no files were processed)"""
        last_successful_index = -1
        for idx, (ex_file, meta_file) in enumerate(zip(self.OGPSurveyFile, self.MetaFile)):
            try: 
                db_upload, comp_params, compID = await self.__getArgs__(ex_file, meta_file, comp_type)
            except ValueMissingError as e:
                logging.error(f"Error in {ex_file}: {e}")
                return False, last_successful_index
            except ValueRangeError as e:
                logging.error(f"Error in {ex_file}: {e}")
                return False, last_successful_index
            self.print_db_msg(comp_type, compID)
            status = await self.client.link_and_update_table(comp_params, db_upload)
            # status = await self.client.upload_PostgreSQL(comp_params, db_upload)
            if status == False:
                logging.error("No more uploading will be done due to the error. Please double check the data and try again.")
                return False, last_successful_index
            last_successful_index = idx
        return True, last_successful_index  # Return True and last index if all files were processed successfully
                # send2trash.send2trash(ex_file)
            # print(f'Moved {ex_file} to recycle bin.')
        
    @staticmethod
    def print_db_msg(comp_type, modname):
        logging.info(f"###### UPLOADING {comp_type} #######")
        logging.info(f"###### FROM: {modname} #######")

    @staticmethod
    def getDateTime(metadata):
        """Get date and time from metadata."""
        date_inspect = datetime.strptime(metadata['RunDate'], '%m:%d:%y').date()
        time_inspect = datetime.strptime(metadata['RunTime'], '%H:%M:%S').time()
        
        return {"date_inspect": date_inspect, "time_inspect": time_inspect}
        
    
