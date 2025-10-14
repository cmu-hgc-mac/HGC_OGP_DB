import os, yaml
from os.path import join as pjoin
import logging
from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme

DEFAULT_CONFIG = {
        'host': 'localhost',
        'database': 'hgcdb',
        'user': 'ogp_user',
        'password': 'hgcalpass',
        'inst_code': 'CM',
        'institution_name': 'Carnegie Mellon University',
        'ogp_survey_dir': '/path/to/ogp/survey/directory',
        'ogp_parsed_dir': '/path/to/ogp/parsed/directory',
        'ogp_tray_dir': '/path/to/ogp/tray/directory',
        'ogp_image_dir': '/path/to/ogp/image/directory',
        'dry_run_kwd': 'dummy'
    }

def setup_logging(level=logging.INFO, show_time=True, show_path=False):
    """Set up logging with rich formatting and styling."""
    # Custom theme for rich
    custom_theme = Theme({
        "logging.level.debug": "dim cyan italic",  # Make debug messages italic, dimmed and cyan
        "logging.level.info": "green",
        "logging.level.warning": "yellow bold",
        "logging.level.error": "red",
        "logging.level.critical": "red bold reverse",
    })
    
    console = Console(theme=custom_theme)
    
    class CustomRichHandler(RichHandler):
        def render_message(self, record, message):
            if record.levelno == logging.DEBUG:
                # Add special formatting for debug messages
                return f"🔍 {message}"  # Prefix debug messages with a magnifying glass
            return message

    rich_handler = CustomRichHandler(
        console=console,
        show_time=show_time,
        show_path=show_path,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=False  # Disable markup interpretation
    )

    # Set format pattern
    logging.basicConfig(
        level=level,
        format="%(message)s",  # Include logger name
        datefmt="[%X]",
        handlers=[rich_handler],
        force=True  # Force reconfiguration
    )
    logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
    
    # Return a logger for the module
    return logging.getLogger(__name__)

def log_process_status(process_name, status, data=None):
    """
    Helper function for consistent process logging with rich formatting.
    
    Parameters
    ----------
    process_name : str
        Name of the process being logged
    status : str
        Status of the process ('start', 'complete', 'error', 'warning')
    data : Any, optional
        Additional data to log (e.g., error message, warning details)
    
    Examples
    --------
    >>> logger = logging.getLogger(__name__)
    >>> log_process_status(logger, "data processing", "start")
    >>> try:
    >>>     # do something
    >>>     log_process_status(logger, "data processing", "complete")
    >>> except Exception as e:
    >>>     log_process_status(logger, "data processing", "error", e)
    """
    if status == "start":
        logging.info(f"[bold blue]Starting[/bold blue] {process_name}...")
    elif status == "complete":
        logging.info(f"[bold green]Completed[/bold green] {process_name}")
    elif status == "error":
        logging.error(f"[bold red]Error[/bold red] in {process_name}")
        if data:
            # Log the exception with traceback
            if isinstance(data, Exception):
                logging.exception(f"Details for {process_name} error:", exc_info=data)
            else:
                logging.error(f"Error details: {data}")
    elif status == "warning":
        logging.warning(f"[bold yellow]Warning[/bold yellow] in {process_name}: {data}")


SETTINGS_FILE = pjoin(os.path.expanduser('~'), ".my-cli-tool", "settings.yaml")

def read_config_files():
    """Helper function to read both settings and config files."""
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = yaml.safe_load(f)
            config_file = settings['config_path']
        with open(config_file, 'r') as f:
            current_config = yaml.safe_load(f)
        return settings, config_file, current_config
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Error reading configuration files: {e}")
        return None, None, None

def write_config_file(config_file, config_data):
    """Helper function to write configuration data to file."""
    try:
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)
        return True
    except (IOError, yaml.YAMLError) as e:
        logging.error(f"Error updating configuration file: {e}")
        return False

def validate_directory(dir_path):
    """Validate and create directory if user confirms."""
    dir_path = os.path.expanduser(dir_path)
    dir_path = os.path.abspath(dir_path)
    
    if not os.path.exists(dir_path):
        logging.warning(f"\nDirectory does not exist: {dir_path}")
        create = input("Would you like to create it? (y/n): ").strip().lower()
        if create == 'y':
            try:
                os.makedirs(dir_path, exist_ok=True)
                logging.info(f"Created directory: {dir_path}")
            except OSError as e:
                logging.error(f"Error creating directory: {e}")
                return None
        else:
            return None
    
    if not os.access(dir_path, os.W_OK):
        logging.warning(f"Warning: No write permission for directory: {dir_path}")
        proceed = input("Continue anyway? (y/n): ").strip().lower()
        if proceed != 'y':
            return None
    
    return dir_path

async def verify_db_credentials(host, database, user, password):
    """Helper function to verify database credentials."""
    import asyncpg
    conn = None
    logging.debug(f"Connecting to database {database} at {host} using provided credentials ...")
    try:
        conn = await asyncpg.connect(
            host=host,
            database=database,
            user=user,
            password=password
        )
        return True
    except Exception as e:
        logging.error(f"Authentication failed: {e}")
        return False
    finally:
        if conn is not None:
            await conn.close()

def get_config_location():
    """Get the configuration file location based on user preference."""
    print("Do you want to create the config file at a custom location? (y/n)")
    choice = input().strip().lower()

    home_dir = os.path.expanduser('~')

    if choice == 'y':
        logging.info("Please enter the directory where you want to create the config file:")
        custom_path = os.path.expanduser(input().strip())
        if os.path.isdir(custom_path):
            return pjoin(custom_path, "rwOGP_DBconfig.yaml")
    else:
        config_dir = pjoin(home_dir, '.config')
        os.makedirs(config_dir, exist_ok=True)
        return pjoin(config_dir, 'rwOGP_DBconfig.yaml')


def verify_config(current_config):
    """
    Verify that the configuration file has all required keys and valid directory paths.
    Returns (bool, list): A tuple containing:
        - Boolean indicating if config is valid
        - List of error messages if any
    """
    errors = []
    
    # Required directory paths
    dir_keys = {
        'ogp_survey_dir': 'OGP survey files',
        'ogp_parsed_dir': 'parsed OGP data',
        'ogp_tray_dir': 'tray information',
        'ogp_image_dir': 'OGP images'
    }
    
    # Check directory paths
    for key, desc in dir_keys.items():
        if key not in current_config:
            errors.append(f"Missing directory configuration for {desc}")
            continue
            
        dir_path = current_config[key]
        if not dir_path:
            errors.append(f"Empty path for {desc}")
            continue
            
        # Expand path
        dir_path = os.path.expanduser(dir_path)
        dir_path = os.path.abspath(dir_path)
        
        if not os.path.exists(dir_path):
            errors.append(f"Directory does not exist: {dir_path} ({desc})")
        elif not os.path.isdir(dir_path):
            errors.append(f"Path is not a directory: {dir_path} ({desc})")
        elif not os.access(dir_path, os.W_OK):
            errors.append(f"No write permission for directory: {dir_path} ({desc})")
    
    is_valid = len(errors) == 0
    return is_valid, errors

async def update_directorys():
    """Update directory paths in the configuration file.
    
    Updates the following directory configurations:
    - ogp_survey_dir: Directory containing OGP survey files
    - ogp_parsed_dir: Directory for parsed OGP data
    - ogp_tray_dir: Directory for tray information
    - ogp_image_dir: Directory for OGP images
    """
    _, config_file, current_config = read_config_files()
    if not current_config:
        return False

    # Directory configurations to update
    dir_configs = {
        'ogp_survey_dir': 'OGP survey files',
        'ogp_parsed_dir': 'parsed OGP data',
        'ogp_tray_dir': 'tray information',
        'ogp_image_dir': 'OGP images'
    }

    def set_default_path(key):
        """Set and save default path for a directory."""
        default_path = '/path/to/ogp/' + key.replace('ogp_', '').replace('_dir', '')
        current_config[key] = default_path
        if write_config_file(config_file, current_config):
            logging.info(f"Using default path: {default_path}. You can update this later using the directory update menu.")
            return True
        logging.error("Failed to save configuration file")
        return False

    def handle_directory_setup(key, desc, max_attempts=3):
        """Handle the directory setup process with validation and saving."""
        for attempt in range(max_attempts):
            new_path = input(f"Enter path for {desc}: ").strip()

            if not new_path:
                logging.error("Path cannot be empty. Please enter a valid path.")
                continue

            validated_path = validate_directory(new_path)
            if validated_path:
                current_config[key] = validated_path
                if write_config_file(config_file, current_config):
                    logging.info(f"Successfully set {desc} to: {validated_path}")
                    return True
                logging.warning("Failed to save configuration file")
                return False

            if attempt < max_attempts - 1:
                if input("Would you like to try another path? (y/n): ").strip().lower() != 'y':
                    return set_default_path(key)

        logging.error("Max attempts reached. Skipping directory setup.")
        return set_default_path(key)

    # Display current configuration
    logging.info("\nCurrent directory configurations:")
    missing_dirs = []
    for key, desc in dir_configs.items():
        if key not in current_config:
            missing_dirs.append(key)
        else:
            logging.info(f"{desc}: {current_config[key]}")

    # Handle missing directories
    if missing_dirs:
        logging.warning("\nThe following required directories were missing from config and have been added with default values:")
        for key in missing_dirs:
            logging.warning(f"\nSetting up {dir_configs[key]} directory")
            if not handle_directory_setup(key, dir_configs[key]):
                return False

    # Menu for directory updates
    print("\nWhich directory would you like to update?")
    for i, (_, desc) in enumerate(dir_configs.items(), 1):
        print(f"{i}. {desc}")
    print("5. All directories")
    print("6. Cancel")

    choice = input("Enter your choice (1-6): ").strip()

    if choice == '6':
        print("Operation cancelled.")
        return False

    if choice == '5':  # Update all directories
        for key, desc in dir_configs.items():
            if not handle_directory_setup(key, desc):
                return False
        return True

    if choice in ['1', '2', '3', '4']:
        key = list(dir_configs.keys())[int(choice) - 1]
        return handle_directory_setup(key, dir_configs[key])

    print("Invalid choice!")
    return False

async def update_credentials():
    """Update database credentials and/or database connection details after authenticating with current ones."""
    import getpass
    import asyncpg

    settings, config_file, current_config = read_config_files()
    if not current_config:
        return False

    def update_config_file(host, database, user, password):
        """Helper function to update configuration file."""
        try:
            current_config['host'] = host
            current_config['database'] = database
            current_config['user'] = user
            current_config['password'] = password
            with open(config_file, 'w') as f:
                yaml.dump(current_config, f, default_flow_style=False)
            return True
        except (IOError, yaml.YAMLError) as e:
            print(f"Error updating configuration file: {e}")
            return False

    if not await verify_db_credentials(
        current_config['host'],
        current_config['database'],
        current_config['user'],
        current_config['password']
    ):
        return False

    print("\nWhat would you like to update?")
    print("1. Database credentials only")
    print("2. Database, user, and password")
    print("3. Host, database, user, and password")
    choice = input("Enter your choice (1/2/3): ").strip()

    new_host = current_config['host']
    new_database = current_config['database']
    
    if choice == '3':
        print("\nEnter new database connection details:")
        new_host = input(f"New host [{current_config['host']}]: ").strip()
        if not new_host:
            new_host = current_config['host']
        
        new_database = input(f"New database name [{current_config['database']}]: ").strip()
        if not new_database:
            new_database = current_config['database']
    elif choice == '2':
        new_database = input(f"New database name [{current_config['database']}]: ").strip()
        if not new_database:
            new_database = current_config['database']
    elif choice != '1':
        print("Invalid choice!")
        return False

    print("\nEnter new credentials:")
    new_user = input("New username: ").strip()
    new_password = getpass.getpass("New password: ").strip()
    confirm_password = getpass.getpass("Confirm password: ").strip()

    if new_password != confirm_password:
        logging.error("Passwords do not match!")
        return False

    if not await verify_db_credentials(new_host, new_database, new_user, new_password):
        return False

    if not update_config_file(new_host, new_database, new_user, new_password):
        return False

    logging.info("Configuration updated successfully!")
    return True

def create_settings_file(config_file):
    """Create settings file with config and inventory paths."""
    home_dir = os.path.expanduser('~')
    settings_dir = pjoin(home_dir, '.my-cli-tool')
    os.makedirs(settings_dir, exist_ok=True)
    
    inventory_path = pjoin(settings_dir, 'inventory.json')
    settings = {
        'config_path': config_file,
        'inventory_path': inventory_path
    }
    with open(SETTINGS_FILE, 'w') as f:
        yaml.dump(settings, f)

def create_default_config():
    """Create a default YAML configuration file and a SETTINGS file, then open it for editing."""
    config_file = get_config_location()
    
    print("Creating default configuration file...")
    with open(config_file, 'w') as f:
        yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)

    print(f"Configuration file created at {config_file}")
    
    editor = os.environ.get('EDITOR', 'vim')  # Default to vim if no EDITOR is set
    
    print("\nWould you like to edit the configuration file now? (y/n)")
    if input().strip().lower() == 'y':
        try:
            os.system(f'{editor} {config_file}')
            print("\nConfiguration file has been updated.")
        except Exception as e:
            print(f"\nError opening editor: {e}")
            print("Please update the configuration file manually!")
    else:
        print("\nPlease update the configuration file with the correct database connection information!")

    create_settings_file(config_file)

def load_config():
    """Load the configuration file from the default location."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return yaml.safe_load(f)
    return None
