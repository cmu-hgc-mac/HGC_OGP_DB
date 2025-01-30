# Package for OGP + Database: rwOGP
This package is intended to be used to read and write data from the OGP to a local database. The package is divided into two parts: 
1. CLI tool for automatic upload of data from the OGP to the local database. (`python rwOGP/main.py`)
2. GUI to read data from the local database to the OGP. (`python rwOGP/startGUI.py`)

## Getting started
Set the output template of all OGP survey programs to be [OGP_template.txt](https://github.com/cmu-hgc-mac/HGC_OGP_DB/blob/main/rwOGP/templates/OGP_template.txt) file.
Make changes to the user input routine of every OGP survey program, as demonstrated below.
![OGP1](https://github.com/user-attachments/assets/d897793d-df3a-48fc-a04e-fd160cbf312f)
![OGP2](https://github.com/user-attachments/assets/eab83325-0726-4e05-b881-7defcc6751c2)
![OGP3](https://github.com/user-attachments/assets/d5837b11-1ceb-4c6b-adc1-87542269f7a0)

### Method 1: Run Python directly
Clone the repository and install the required packages:
```
git clone git@github.com:cmu-hgc-mac/HGC_OGP_DB.git
```
Run the following command to postprocess and upload the OGP survey results to the database:
```
cd HGC_OGP_DB
python rwOGP/main.py
```
To inspect data from database
```
python rwOGP/startGUI.py
```

For more information on how to use the CLI tool, run:
```python rwOGP/main.py --help```
The following options are available: to clear the database, to upload a specific file, to upload all files, and to view the database.

### Method 2: Install as a package (Under Development)
In Python 3.6 or greater on the OGP computer: 
```
pip install git+https://github.com/cmu-hgc-mac/HGC_OGP_DB.git
```
Then run in terminal
```
uploadOGPresults
```
If run for the first time, this prompts user to enter a secure folder/directory to create a configuration file containing information about database connection and OGP survey results. Modify the configuration file to include the correct information.

Running this command after will automatically postprocess and upload the OGP survey results to the database.

## How to use:
This GUI contains two tabs: 'View Plots' and 'Upload Files'. Run `python rwOGP/startGUI.py` to start the GUI.
- View plots shows plots data from the OGP. (TBD: Change limit on number of files) 
- Upload Files lets the user upload .XLS output files containing OGP meaurements to the local db.
  - The **watch directory** _must contain_ the following subdirectories for the GUI to work:
    - baseplates
    - hexaboards
    - protomodules
    - modules
  - The OGP inspection files _must be configured to write to these locations_ by default type.
    - The .XLS files must be saved with the ID of the component and will be used as the part ID in the db.

![OGP_GUI](https://github.com/murthysindhu/HGC_DB_postgres/assets/58646122/dbeddf4c-2dc8-4da7-8f26-f916d1c69b74)

## Developer's Notes:
## Troubleshooting
### Missing entries (data or header or the entire txt file)
1. Check if OGP survey program is properly named. Spaces are very likely to cause parsing issues and therefore should be avoided. 
Correct Example: `CMU_OGP_module_survey_2024`
2. Check if the routines are reporting results to Files. Turn Results for (X, Y, Z) on, and change the system setting to Link Results to Files. Do this for user input variables as well.
3. Check if the file output routine has filter applied. Uncheck the option.

### Template change
- If the template is changed, how data is parsed from the OGP output files will also need to be modified accordingly in `src/param.py`.
- The meta data needs to follow the format: 
  ```
  LastModified: {ProjectLastModified}		
  Runtime: {RunDateTime}
  ```
  Otherwise [ttp](https://ttp.readthedocs.io/en/latest/) package will have trouble parsing the data.
  

## Using pgAdmin4 to view tables (Instructions to follow)
Install [postgreSQL-15 with pgAdmin4](https://www.pgadmin.org/download/) on your computers. Make sure you add ```psql``` to your path.


