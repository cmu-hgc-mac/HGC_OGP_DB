import os, subprocess, json, sys, logging
from .parse_data import DataParser, ParserKeyException
from .process_survey import SurveyProcessor
from rich.table import Table
from rich.console import Console

pexist = os.path.exists
pjoin = os.path.join

class InventoryUpdater():
    """Update the inventory of OGP results and upload new files to the database."""
    def __init__(self, inventory_path, config_yaml, comp_type='', dryrun=False):
        self.dryrun = dryrun

        """Initialize the file uploader.
        
        Parameters
        - `inventory_path`: path to the inventory json file."""
        self.inventory_p = inventory_path
        self.config = config_yaml
        self.checkdir = self.config.get('ogp_survey_dir')
        self.parsed_dir = self.config.get('ogp_parsed_dir')
        self.comp_type = comp_type
        self.dryrun = dryrun
        logging.debug(f"Reading inventory from: {self.inventory_p}")
        logging.debug(f"Parsing OGP survey files from directory: {self.checkdir}")
        logging.debug(f"Saving parsed data to directory: {self.parsed_dir}")

    def display_file_changes(self, new_inventory, removed_inventory, successful_uploads):
        """Display a table of file changes using rich.Table"""
        console = Console()
        table = Table(title="OGP Survey File Changes Summary")
        
        # Add columns
        table.add_column("Component Type", style="cyan")
        table.add_column("New Files", style="green")
        table.add_column("Removed Files", style="red")
        table.add_column("Successfully Uploaded", style="blue")

        # Get all unique component types
        all_components = set(list(new_inventory.keys()) + 
                           list(removed_inventory.keys()) + 
                           list(successful_uploads.keys()))

        # Add rows for each component
        for component in sorted(all_components):
            new_files = new_inventory.get(component, [])
            removed_files = removed_inventory.get(component, [])
            uploaded_files = successful_uploads.get(component, [])
            
            table.add_row(
                component,
                "\n".join(new_files) if new_files else "-",
                "\n".join(removed_files) if removed_files else "-",
                "\n".join(uploaded_files) if uploaded_files else "-"
            )

        # Add summary row
        table.add_row(
            "Total",
            str(sum(len(files) for files in new_inventory.values())),
            str(sum(len(files) for files in removed_inventory.values())),
            str(sum(len(files) for files in successful_uploads.values())),
            style="bold"
        )

        # Print the table
        console.print("\n")
        console.print(table)
        console.print("\n")
    
    async def __call__(self):
        if not pexist(self.inventory_p):
            self.__deal_empty()
            return
            
        with open(self.inventory_p, 'r') as f:
            self.inventory = json.load(f)
        
        new_files, removed_files = self.__check_inventory()
        self.__update_removed(removed_files)
        status = await self.upload_and_update(new_files)
        
        if status:
            logging.info("===All new files were successfully processed and uploaded to the database.===")
        else:
            logging.error("Some files failed to upload to the database.\n")

    def __update_removed(self, removed_invent):
        for subdir, files in removed_invent.items():
            if subdir in self.inventory:
                self.inventory[subdir] = [file for file in self.inventory[subdir] if file not in files]
                if not self.inventory[subdir]:
                    del self.inventory[subdir]
        
        with open(self.inventory_p, 'w') as f:
            json.dump(self.inventory, f)
        
        logging.warning("\n=== Inventory Update Alert ===")
        logging.warning(f"Removed {sum(len(files) for files in removed_invent.values())} files from inventory")

    def __update_inven(self, success_invent):
        """Update the inventory with the successfully uploaded files."""
        for subdir, files in success_invent.items():
            if subdir not in self.inventory:
                self.inventory[subdir] = files
            else:
                self.inventory[subdir].extend(files)
                self.inventory[subdir] = list(dict.fromkeys(self.inventory[subdir]))
        
        with open(self.inventory_p, 'w') as f:
            json.dump(self.inventory, f)
        
        logging.info("\n=== Inventory Update Alert ===")
        logging.info(f"Successfully updated inventory with {sum(len(files) for files in success_invent.values())} new files")

    def __create_new(self) -> dict:
        """Create a new inventory dictionary. 
        With structure like {subdir:[files]} 
        
        Return
        - dictionary of subdirectories and their corresponding txt files."""
        txt_files_by_subdir = {}
        for item in os.listdir(self.checkdir):
            subdir_path = pjoin(self.checkdir, item)
            if os.path.isdir(subdir_path):
                txt_files = [
                    file for file in os.listdir(subdir_path)
                    if file.endswith('.txt') and not file.startswith('.')
                ]
                
                if txt_files:
                    txt_files_by_subdir[item] = txt_files

        return txt_files_by_subdir
    
    async def __deal_empty(self) -> bool:
        """Check if inventory is empty and prompt user to upload all existing OGP results to database.
        
        Return 
        - bool: whether all existing OGP results are uploaded to database."""
        txt_files_by_subdir = self.__create_new()

        with open(self.inventory_p, 'w') as f:
            json.dump(txt_files_by_subdir, f)

        logging.info("Initialize Inventory of OGP results for the first time...Would you like to process and upload all the existing OGP results to database? (Y/N)")
        choice = input().strip().lower()

        if choice == 'y':
            logging.info("Uploading all existing OGP results to database...")

            # --- DRY RUN PATCH ---
            if self.dryrun:
                logging.warning("[DRY RUN] Skipping upload of initial inventory.")
                return True
            # ----------------------

            # Real upload
            return await self.upload_files(txt_files_by_subdir)

        else:
            logging.info("Exiting...")
            return False

    
    def __check_inventory(self) -> tuple[dict, dict]:
        """Check for changes in the inventory of OGP results.
        If self.comp_type is specified, only check that specific subdirectory.

        Returns:
        - dict: Subdirectories and their corresponding new files to be processed.
        - dict: Subdirectories and their corresponding removed files.
        """
        logging.info("\n=== Checking for OGP Survey File Changes ===")
        new_inventory = self.__create_new()
        old_inventory = self.inventory.copy()
        changed_inventory = {}
        removed_inventory = {}

        total_new_files = 0
        total_removed_files = 0
        new_subdirs = []

        if self.comp_type:
            if self.comp_type in new_inventory:
                new_inventory = {self.comp_type: new_inventory[self.comp_type]}
            else:
                new_inventory = {}
                logging.info("No new files to process for component type:", self.comp_type)
                sys.exit()
            if self.comp_type in old_inventory:
                old_inventory = {self.comp_type: old_inventory[self.comp_type]}
            else:
                old_inventory = {}

        for subdir, files in new_inventory.items():
            if subdir not in old_inventory:
                new_subdirs.append(subdir)
                changed_inventory[subdir] = files
                total_new_files += len(files)
            else:
                new_files = set(files) - set(old_inventory[subdir])
                removed_files = set(old_inventory[subdir]) - set(files)
                if new_files or removed_files:
                    logging.info(f"\nChanges in subdirectory '{subdir}':")
                    if new_files:
                        logging.info(f"  + Added: {', '.join(sorted(new_files))}")
                        total_new_files += len(new_files)
                    if removed_files:
                        logging.info(f"  - Removed: {', '.join(sorted(removed_files))}")
                        total_removed_files += len(removed_files)

                if new_files:
                    changed_inventory[subdir] = list(new_files)
                if removed_files:
                    removed_inventory[subdir] = list(removed_files)
        
        # check for removed subdirectories
        for subdir in old_inventory:
            if subdir not in new_inventory:
                removed_inventory[subdir] = old_inventory[subdir]
                total_removed_files += len(old_inventory[subdir])

        return changed_inventory, removed_inventory
    
    async def upload_and_update(self, invent) -> bool:
        """Parse, postprocess and upload files to the database.
        
        Parameters
        - `invent`: dictionary of {subdir:[files]} to be uploaded. subdir should be names of components, e.g. baseplate, modules, etc.
        
        Returns
        - `bool`: True if all files were successfully processed & uploaded, False otherwise.
        """
        status = True 
        for subdir, files in invent.items():
            inputs = [pjoin(self.checkdir, subdir, file) for file in files]
            if inputs:
                parse_output_dir = pjoin(self.parsed_dir, subdir)
                dp = DataParser(inputs, parse_output_dir)
                try: 
                    gen_meta, gen_features = dp()
                except ParserKeyException as e:
                    sys.exit()
                uploader = SurveyProcessor(gen_features, gen_meta, self.config)
                # Always run SurveyProcessor so tables and calculations happen
                if self.dryrun:
                    # Run SurveyProcessor ONCE to show geometry
                    await uploader(subdir)

                    logging.warning(f"[DRY RUN] Skipping upload for {subdir}.")
                    success = True
                    indx = len(files) - 1

                else:
                    # Normal mode: run SurveyProcessor ONCE and upload
                    success, indx = await uploader(subdir)




                successful_uploads = {}
                if success:
                    successful_uploads[subdir] = files
                elif indx != -1:
                    successful_files = files[:indx+1]
                    if successful_files:  # Only add if there were successful uploads
                        successful_uploads[subdir] = successful_files
                    logging.warning(f"Failed to upload file: {inputs[indx + 1]}")
                    status = False
                else:
                    status = False
                    logging.warning(f"Failed to upload files from {subdir}")
                
                if successful_uploads: 
                    logging.info("These files were successfully uploaded:", successful_uploads)
                    self.__update_inven(successful_uploads)
            else:
                logging.warning(f"No files from {subdir} to process/upload to database.")
            
        # Only show upload summary in real mode
        if invent and not self.dryrun:
            self.display_file_changes(invent, {}, successful_uploads)

        return status

        
    def run_on_new_files(self, files, action):
        """Run the action on each file in the list of files
        
        Parameters
        - `files`: list of files to run the action on, without parent directory prefix."""
        for file in files:
            subprocess.Popen(['python', action, os.path.join(self.checkdir, file)])
    
    @staticmethod
    def deal_corrupt(json_path):
        """Deal with corrupt json files.
        
        Parameters
        - `json_path`: path to the corrupt json file."""
        with open(json_path, 'r') as f:
            try:
                data = json.load(f)
                return data
            except json.JSONDecodeError:
                logging.error(f"Corrupt json file: {json_path}. Please remove the file and run the program again.")
