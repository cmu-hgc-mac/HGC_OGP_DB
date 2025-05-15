import os, yaml, sys, asyncio, logging
import argparse
from rich_argparse import RichHelpFormatter

pjoin = os.path.join

file_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = pjoin(file_dir, 'rwOGP')
if src_dir not in sys.path:
    sys.path.append(src_dir)

from src.auto_upload import InventoryUpdater
from src.config_utils import load_config, create_default_config, update_credentials, update_directorys, verify_config, setup_logging
from src.invent_utils import invent_print, clear_invent

program_descriptions = """This program is used to automatically upload results to the OGP database. 
It is designed to be run from the command line.  
The program will read the configuration file and use the information to connect to the OGP database and upload the results. 
The program will also update the inventory file to reflect the results that have been uploaded.

Running without any arguments will process and upload all new surveys to the OGP database."""

async def main_func(comp_type):
    """Main function to run the program."""
    settings = load_config()
    if settings is None:
        logging.error("Program will now exit. Please update the configuration file and run the program again.")
        create_default_config()
        return
    else:
        config_path = settings['config_path']
        invent_path = settings['inventory_path']
        logging.debug(f"Using configuration file: {config_path} to create database client.")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        status, message = verify_config(config)
        if not status:
            logging.warning(message)
            return
    
    updater = InventoryUpdater(invent_path, config, comp_type)
    await updater()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=program_descriptions,
        prog="OGP Auto Uploader",
        formatter_class=RichHelpFormatter
    )

    parser.add_argument("--print", action='store_true', help="Print the current inventory.")
    parser.add_argument("--clear", action='store_true', help="Clear the current inventory. Note that these do not delete the OGP output files. They only remove the files from being marked as uploaded in the inventory.")
    parser.add_argument("--updatedb", action='store_true', help="Update the credentials in the configuration file.")
    parser.add_argument("--updatedir", action='store_true', help="Update the directory paths for OGP outputs/processing in the configuration file.")
    parser.add_argument("--type", type=str, default='', help="Specify the type of component to process and upload. If not specified, all components will be processed.")
    parser.add_argument("--debug", action='store_true', help="Print debug messages.")
    parser.add_argument("--disable", action='store_true', help="Disable the program from uploading.")

    args = parser.parse_args()

    if args.debug:
        setup_logging(logging.DEBUG)
    else:
        setup_logging(logging.WARNING)
    
    if args.print:
        invent_print()
        sys.exit(0)
    if args.clear:
        logging.info("Clearing the current inventory...")
        clear_invent()
        sys.exit(0)
    if args.updatedb:
        logging.info("Updating credentials...")
        result = asyncio.run(update_credentials())
        sys.exit(0)
    if args.updatedir:
        logging.info("Updating directory paths...")
        result = asyncio.run(update_directorys())
        sys.exit(0)

    asyncio.run(main_func(args.type))
