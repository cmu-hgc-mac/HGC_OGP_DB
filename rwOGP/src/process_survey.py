import numpy as np
import pandas as pd
import asyncio, send2trash, glob, re, yaml, os
import matplotlib
matplotlib.use('Agg')
from src.ogp_height_plotter import PlotTool
from src.upload_inspect import DBClient
from src.make_accuracy_plot import make_accuracy_plot
from src.param import *
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
        
        im_dir = pjoin(pdir(self.OGPSurveyFile[0]), 'images')
        if not os.path.exists(im_dir):
            os.makedirs(im_dir)
        self.im_dir = im_dir
        self.tray_dir = yamlconfig.get('ogp_tray_dir')

        print(f'filename to process/upload: {self.OGPSurveyFile}')
        self.client = DBClient(yamlconfig)
        pass

    def __call__(self, component_type):
        """Process and upload OGP Survey files."""
        self.process_and_upload(component_type)
 
    def __getArgs__(self, ex_file, meta_file, comp_type):
        """Get arguments for uploading to database, including the necessary meta data to upload and the image bytes.
        
        Return 
        - db_upload (dict): Dictionary of data to upload to database.
        - db_table_name (str): Name of the table in the database to upload to.
        - modtitle (str): Title of the module."""
        db_upload = {}

        with open(meta_file, 'r') as f:
            metadata = yaml.safe_load(f)

        modtitle = metadata['ComponentID']

        df = pd.read_csv(ex_file)
        plotter = PlotTool(metadata, df, self.tray_dir, pjoin(self.im_dir, comp_type))

        filesuffix = pbase(ex_file).split('.')[0]

        if comp_type == 'baseplates':
            db_upload.update({'bp_name': modtitle})
            component_params = baseplates_params
        elif comp_type == 'hexaboards':
            db_upload.update({'hxb_name':modtitle})
            component_params = hexaboards_params
        elif comp_type == 'protomodules':
            component_params = protomodules_params
            XOffset, YOffset, AngleOff = plotter.get_offsets()
            db_upload.update({'proto_name': modtitle, 'x_offset_mu':np.round(XOffset*1000), 
                              'y_offset_mu':np.round(YOffset*1000), 'ang_offset_deg':np.round(AngleOff,3),
                              "weight": metadata.get('Weight', None)})
        elif comp_type == 'modules':
            component_params = modules_params
            XOffset, YOffset, AngleOff = plotter.get_offsets()
            db_upload.update({'module_name': modtitle, 'x_offset_mu':np.round(XOffset*1000), 
                              'y_offset_mu':np.round(YOffset*1000), 'ang_offset_deg':np.round(AngleOff,3),
                              'weight': metadata.get('Weight', None)})
            # ! what is this block doing?
            try:
                PMoffsets = asyncio.run(self.client.GrabSensorOffsets(modtitle))
                SensorXOffset, SensorYOffset, SensorAngleOff = PMoffsets
                print('Making Accuracy Plot With:', modtitle, SensorXOffset, SensorYOffset, XOffset, YOffset, SensorAngleOff, AngleOff)
                acc_bytes = make_accuracy_plot(modtitle, SensorXOffset, SensorYOffset, int(XOffset*1000), int(YOffset*1000), SensorAngleOff, AngleOff) 
            except Exception as e: 
                print(f" Accruacy Plot: An error pulling PM offsets from pg occurred: {e}")
                print("Accruacy Plot: PM offsets set to 0, 0, 0, due to failed data pull.")
                PMoffsets = [0, 0, 0];
            # ! ============================
        else:
            raise ValueError("Component type not recognized. \
                Currently only supports baseplates, hexaboards, and protomodules. Please change the directory this file belongs to or add customed component type.")

        im_args = {"vmini":component_params['vmini'], "vmaxi":component_params['vmaxi'], 
                   "new_angle": component_params['new_angle'], "savename": pjoin(self.im_dir, comp_type, f"{filesuffix}_heights"),
                   "mod_flat": metadata['Flatness'], "title": metadata['ComponentID'], "show_plot": False}
        
        im_bytes = plotter(**im_args)

        db_upload.update({
            'flatness': metadata['Flatness'], 
            'thickness': np.round(np.mean(plotter.z_points),3), 
            #'max_thickness': np.round(np.max(plotter.z_points),3),
            #'ave_thickness': np.round(np.mean(plotter.z_points),3),
            'x_points':(plotter.x_points).tolist(), 
            'y_points':(plotter.y_points).tolist(), 
            'z_points':(plotter.z_points).tolist(),
            'hexplot':im_bytes, 
            'inspector': metadata['Operator'], 
            'comment':metadata.get("Comment", None)})
        
        db_upload.update(self.getDateTime(metadata))

        db_table_name = component_params['db_table_name']

        return db_upload, db_table_name, modtitle  
    
    def process_and_upload(self, comp_type):
        """Process all OGP Survey files and upload to database.
        
        Parameters:
        - `comp_type` (str): Type of component to process."""
        for ex_file, meta_file in zip(self.OGPSurveyFile, self.MetaFile):
            db_upload, db_table_name, modtitle = self.__getArgs__(ex_file, meta_file, comp_type)
            mappings = np.array([None],dtype=object)
            self.print_db_msg(comp_type, modtitle)
            try:
                asyncio.run(self.client.upload_PostgreSQL(db_table_name, db_upload)) ## python 3.7
            except Exception as e:
                print(f"Exception Encountered: {e}")
                try: 
                    print("Warning: Using python 3.6")
                    (asyncio.get_event_loop()).run_until_complete(self.client.upload_PostgreSQL(db_table_name, db_upload)) ## python 3.6
                except Exception as e:
                    print("ERROR: Could not upload to database.")
                    print(e)
                    print("Check async code in process_survey.py or upload_inspect.py")
                    return
            print(modtitle, 'uploaded!')
            # if trash_file:
                # send2trash.send2trash(ex_file)
            # print(f'Moved {ex_file} to recycle bin.')
        
    @staticmethod
    def print_db_msg(comp_type, modname):
        print('')
        print(f"###### NEW {comp_type} UPLOAD #######")
        print(f"###### FROM: {modname} #######")
        print('')

        print(f'Component type: {comp_type}')

    @staticmethod
    def getDateTime(metadata):
        """Get date and time from metadata."""
        date_inspect = datetime.strptime(metadata['RunDate'], '%m:%d:%y').date()
        time_inspect = datetime.strptime(metadata['RunTime'], '%H:%M:%S').time()
        
        return {"date_inspect": date_inspect, "time_inspect": time_inspect}
        
    
