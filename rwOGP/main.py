import os, yaml, sys, asyncio, logging, glob, argparse
from datetime import datetime
from rich_argparse import RichHelpFormatter
from rich.table import Table
from rich.console import Console

pjoin = os.path.join

file_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = pjoin(file_dir, 'rwOGP')
if src_dir not in sys.path:
    sys.path.append(src_dir)

from src.auto_upload import InventoryUpdater
from src.config_utils import load_config, create_default_config, update_credentials, update_directorys, verify_config, setup_logging
from src.invent_utils import invent_print, clear_invent
from src.workflow_tester import test_module_workflow, test_angle_calculations

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

def test_workflow():
    settings = load_config()
    if settings is None:
        logging.error("Program will now exit. Please run without arguments first!")
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
    
    check_dir = config.get('ogp_survey_dir')
    comp_types = ["protomodules", "modules"]
    console = Console()
    console.print("[bold cyan]Select component type:[/bold cyan]")
    console.print(f"[bold green]0[/bold green]: protomodules")
    console.print(f"[bold yellow]1[/bold yellow]: modules")
    while True:
        try:
            selection = int(input(f"Enter 0 for protomodules or 1 for modules: ").strip())
            if 0 <= selection < len(comp_types):
                comp_type = comp_types[selection]
                break
            else:
                logging.error("Invalid selection. Please try again.")
        except ValueError:
            logging.error("Please enter a valid number.")
    check_dir = pjoin(check_dir, comp_type)
    # Find files in check_dir, sort by modification time (descending)
    files = sorted(glob.glob(pjoin(check_dir, "*.txt")),
        key=os.path.getmtime, reverse=True)[:5]

    if not files:
        logging.warning("No files found in the directory. Exiting test mode.")
        return

    table = Table(title="[bold magenta]Select a file to test[/bold magenta]", show_header=True, header_style="bold blue")
    table.add_column("Index", justify="center", style="bold green")
    table.add_column("File Name", justify="left", style="yellow")
    table.add_column("Last Modified", justify="center", style="cyan")

    for idx, file_path in enumerate(files):
        last_modified = os.path.getmtime(file_path)
        last_modified_str = (
            f"{last_modified:.0f}" if last_modified is None
            else
            f"{datetime.fromtimestamp(last_modified).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        row_style = "on grey15" if idx % 2 == 0 else ""
        table.add_row(f"[bold green]{idx}[/bold green]", f"[yellow]{os.path.basename(file_path)}[/yellow]", f"[cyan]{last_modified_str}[/cyan]", style=row_style)

    console = Console()
    console.print(table)

    while True:
        try:
            selection = int(input(f"Enter the index of the file to test (0-{len(files)-1}): ").strip())
            if 0 <= selection < len(files):
                selected_file = files[selection]
                break
            else:
                logging.error("Invalid selection. Please try again.")
        except ValueError:
            logging.error("Please enter a valid number.")

    test_module_workflow(selected_file, comp_type, config.get('ogp_tray_dir'))

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
    parser.add_argument("--type", type=str, default='', help="Specify the type of component to process and upload [baseplates/hexaboards/protomodules/modules]. If not specified, all components will be processed.")
    parser.add_argument("--debug", action='store_true', help="Print debug messages.")
    parser.add_argument("--disable", action='store_true', help="Disable the program from uploading.")
    parser.add_argument("--test", action='store_true', help="Run the program in test mode on a selected file.")

    args = parser.parse_args()

    if args.debug:
        setup_logging(logging.INFO)
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
    if args.test:
        logging.info("Running in test mode...")
        test_workflow()
        sys.exit(0)

    asyncio.run(main_func(args.type))
