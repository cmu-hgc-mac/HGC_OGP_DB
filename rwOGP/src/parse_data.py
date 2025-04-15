import os, yaml, logging
from ttp import ttp
import pandas as pd
from io import StringIO
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from src.param import default_params, pin_mapping
from src.parser_template import header_template, data_template, required_keys, warning_keys

pjoin = os.path.join
pbase = os.path.basename

class ParserKeyException(Exception):
    pass

class DataParser():
    """Parse data file(s) using TTP template. 
    Output metadata, which contains info such as geometry and density, and feature results, which are dataframes containing the parsed data."""
    def __init__(self, data_file, output_dir):
        """Initialize DataParser object.
        
        Parameters:
        - data_file (str/list[str]): Path(s) to the data output file by OGP surveys to be parsed.
        - output_dir (str): Path to the output directory of the parsed data."""
        if isinstance(data_file, str):
            data_file = [data_file]
        
        self.data_file = data_file
        self.output_dir = output_dir

        input_parent = os.path.dirname(data_file[0])
        self.backup_dir = pjoin(input_parent, '.backup')

        if input_parent == self.output_dir:
            raise ParserKeyException("Input and output directories of the DataParser cannot be the same.")
        
        try:
            if not os.path.exists(output_dir):
                logging.debug(f"Creating parsed output directory: {output_dir}")
                os.makedirs(output_dir)
            
            if not os.path.exists(self.backup_dir):
                logging.debug(f"Creating backup directory: {self.backup_dir}")
                os.makedirs(self.backup_dir)
            
        except OSError as e:
            raise ParserKeyException(f"Error creating output directory: {e}")
    
    def __call__(self) -> tuple:
        """Parse data file produced by default OGP template. Create metadata file and output feature results to a csv file.
        
        Return 
        - gen_meta (list): List of metadata files generated.
        - gen_features (list): List of feature files generated."""
        gen_meta = []
        gen_features = []
        logging.info("=== Parsing OGP Data ===")
        for filename in self.data_file:
            self.header_results = {}
            with open(filename, 'r') as f:
                self.data = f.read()
            logging.info(f"Parsing data file: {pbase(filename)}")

            backup_file = pjoin(self.backup_dir, pbase(filename))
            if not os.path.exists(backup_file):
                with open(backup_file, 'w') as f:
                    f.write(self.data)
            
            self.read_temp_sep()
            try:
                output_filename = self.output_meta()
            except ParserKeyException as e:
                logging.error(f"Error in parsing metadata: {e} for {filename}")
                continue
            self.output_features(f'{output_filename}.csv')

            gen_features.append(pjoin(self.output_dir, f'{output_filename}.csv'))
            gen_meta.append(pjoin(self.output_dir, f'{output_filename}_meta.yaml'))
        return gen_meta, gen_features

    def read_temp_sep(self, header_template=header_template, feature_template=data_template, delimiter='---'):
        """Read data file produced with header and feature templates separated by a delimiter."""
        parts = self.data.split(delimiter)
        
        assert len(parts) == 2, 'Exactly One delimiter is required'
        parser = ttp(data=parts[0], template=header_template)
        parser.parse()
        header_results = parser.result(structure="flat_list")
        parser = ttp(data=parts[1], template=feature_template)
        parser.parse()
        feature_results = parser.result(format='csv', structure="flat_list")

        self.header_results = {}
        for header in header_results:
            self.header_results.update(header)

        self.feature_results = pd.read_csv(StringIO(feature_results[0])).drop_duplicates()
        
        return header_results, feature_results
    
    def output_features(self, output_filename):
        """Output feature results to a csv file."""
        self.feature_results.to_csv(pjoin(self.output_dir, output_filename), index=False)
    
    def output_meta(self) -> str:
        """Output metadata to a file, with filename based on ComponentID and Operator.
        
        Return 
        - filename (str): Filename prefix of the metadata file."""
        header_dict = self.header_results

        header_dict = self.check_missing_keys(header_dict)
        header_dict = self.check_types(header_dict)
        header_dict = self.check_missing_mappings(header_dict)
        header_dict = self.check_illegal_chars(header_dict)

        filename = f"{header_dict['ComponentID']}_{header_dict['Operator']}"
        meta_file = f'{filename}_meta.yaml'
        with open(f'{self.output_dir}/{meta_file}', 'w') as f:
            yaml.dump(header_dict, f, default_flow_style=False)
        return filename
    
    def check_missing_keys(self, header_dict):
        """Check for missing keys in the parsed header. 
        If missing, adopt default values for the missing keys or exit the program."""
        missing_keys = set(required_keys) - set(header_dict.keys())
        if missing_keys or set(warning_keys) - set(header_dict.keys()):
            console = Console()
            warning_text = Text()

            if missing_keys:
                warning_text.append(f"\nMissing required keys:\n", style="red")
                for key in missing_keys:
                    warning_text.append(f"• {key}\n", style="red dim")

                header_dict = self.adopt_default(header_dict)
                console.print(Panel(
                    warning_text,
                    title="[red]Error[/red]",
                    border_style="red",
                    expand=False
                ))

                user_input = input("Do you want to enter values for the missing keys? (y/n): ")
                if user_input.lower() != 'y':
                    raise ParserKeyException(f"Missing keys not resolved! Exiting...")
                else:
                    for key in missing_keys:
                        value = input(f"Enter value for {key}: ")
                        header_dict[key] = value
            elif logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
                success_text = Text()
                success_text.append(f"All required keys detected for {header_dict['ComponentID']}!\n", style="green")

                # Create table data
                table_data = [[key, str(value)] for key, value in header_dict.items()]
                table = Table(show_header=True, header_style="bold green")
                table.add_column("Key", style="dim")
                table.add_column("Value")

                for row in table_data:
                    table.add_row(*row)

                console.print(Panel(success_text, title="[green]Success[/green]", border_style="green", expand=False))
                console.print(table)

            # Handle optional keys
            missing_optional = set(warning_keys) - set(header_dict.keys())
            if missing_optional and logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
                warning_text = Text()
                warning_text.append(f"DataParser did not parse all the optional keys for {header_dict['ComponentID']} due to mismatching in naming or missing data.\n", style="yellow")
                warning_text.append("\nMissing optional keys:\n", style="yellow")
                for key in missing_optional:
                    warning_text.append(f"• {key}\n", style="yellow dim")

                console.print(Panel(
                    warning_text,
                    title="[yellow]Warning[/yellow]",
                    border_style="yellow",
                    expand=False
                ))
            elif logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
                success_text = Text()
                success_text.append(f"All optional keys for {header_dict['ComponentID']} were successfully parsed.\n", style="green")

                console.print(Panel(
                    success_text,
                    title="[green]Success[/green]",
                    border_style="green",
                    expand=False
                ))
        
        return header_dict
    
    def check_illegal_chars(self, header_dict):
        """Remove all illegal characters from the header_dict."""
        illegal_chars = ['/', '\\', ':', '*', '?', '<', '>', '|']
        filename_fields = ['ComponentID', 'Operator']
    
        for field in filename_fields:
            has_illegal = any(char in header_dict[field] for char in illegal_chars)
            if has_illegal:
                original = header_dict[field]
                logging.warning(f"Unconventional character(s) detected in {field}: {original}")
                found_chars = [char for char in illegal_chars if char in original]
                logging.warning(f"Found illegal characters: {found_chars}")
                user_in = input("Would you want to remove these characters? If not the parsing might not continue correctly. (y/n): ")
                if user_in.lower() == 'y':
                    cleaned_value = original
                    for char in illegal_chars:
                        cleaned_value = cleaned_value.replace(char, '')
                        header_dict[field] = cleaned_value
    
        return header_dict
    
    def check_missing_mappings(self, header_dict):
        """Check for missing mappings in the parsed header. 
        If unrecognized in pin mapping, adopt default values for the missing keys or exit the program."""
        Geometry = header_dict['Geometry']
        density = header_dict['Density']
        if pin_mapping.get(Geometry) is None:
            logging.warning(f"Geometry {Geometry} not recognized. Default to Full.")
            user_input = input("Do you want to adopt the default values for Geometry? (y/n): ")
            if user_input.lower() != 'y':
                raise ParserKeyException("Exiting... Please check the Geometry value or update the pin mapping in param.py.")
            header_dict['Geometry'] = 'Full'
            Geometry = 'Full'
        if pin_mapping.get(Geometry).get(density) is None:
            logging.warning(f"Density {density} not recognized for Geometry {Geometry}. Default to LD.")
            user_input = input("Do you want to adopt the default values for Density? (y/n): ")
            if user_input.lower() != 'y':
                raise ParserKeyException("Exiting... Please check the Density value or update the pin mapping in param.py.")
            header_dict['Density'] = 'LD'
        return header_dict

    def check_types(self, header_dict):
        """If the data types in header_dict are not correct, convert the types to the correct ones."""
        header_dict['PositionID'] = int(header_dict['PositionID'])
        header_dict['TrayNo'] = int(header_dict['TrayNo'])
        header_dict['Density'] = str(header_dict['Density']).upper()
        header_dict['Geometry'] = str(header_dict['Geometry']).capitalize()
        header_dict['Flatness'] = float(header_dict['Flatness'])
        if header_dict.get("Thickness") is not None:
            header_dict['Thickness'] = float(header_dict['Thickness'])
        if header_dict.get("Thickness_Offset") is not None:
            header_dict['Thickness_Offset'] = float(header_dict['Thickness_Offset'])
        return header_dict
        
    def adopt_default(self, header_dict):
        """Adopt default values for the missing keys."""
        for key in set(required_keys) - set(header_dict.keys()):
            logging.info(f"Default value {default_params[key]} will be adopted for missing key: ", key)
            header_dict[key] = default_params[key]
        return header_dict
    
    @staticmethod
    def get_xyz(df: pd.DataFrame, filterKwd=[]) -> pd.DataFrame:
        """Get X, Y, Z coordinates from the dataframe."""
        if filterKwd: regex_pattern = '|'.join(filterKwd)
        df = df[~df['FeatureName'].str.contains(regex_pattern, case=False, na=False)]
        return df.dropna(subset=['X_coordinate', 'Y_coordinate', 'Z_coordinate'])
    
    @staticmethod
    def get_feature_from_df(df: 'pd.DataFrame', feature_name, filterType=None, filterKwd=[]) -> pd.Series:
        """Get feature from the dataframe.
        
        Parameters:
        - df (pd.DataFrame): Dataframe containing the parsed data.
        - feature_name (str): Name of the feature to be extracted."""
        assert feature_name in df.columns, 'Feature not found'

        if filterType is None: filtered_df = df
        else: filtered_df = df[df['FeatureType'] == filterType]

        return filtered_df[feature_name].dropna()
    