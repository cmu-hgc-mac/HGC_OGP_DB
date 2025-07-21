import sys, asyncpg, logging
sys.path.append('../')

from src.param import COMP_PREFIX

class MissingEntryException(Exception):
    pass

def get_query_read(component_type, part_name = None, limit=15) -> str:
    """Get the query to read from the database.

    Returns:
    - query (str): Formatted query string.
    """
    prefix = COMP_PREFIX[component_type]
    if part_name is None:
        query = f"""SELECT {prefix}_name FROM {prefix}_inspect ORDER BY {prefix}_row_no DESC LIMIT {limit};"""
    else:
        query = f"""SELECT hexplot FROM {prefix}_inspect WHERE {prefix}_name = '{part_name}'"""
    return query

def get_query_write(table_name, column_names) -> str:
    """Get the query to write to the database.
    
    Returns:
    - query (str): Formatted query string."""
    pre_query = f""" INSERT INTO {table_name} ({', '.join(column_names)}) VALUES """
    data_placeholder = ', '.join(['${}'.format(i) for i in range(1, len(column_names)+1)])
    query = f"""{pre_query} {'({})'.format(data_placeholder)}"""
    return query

def get_query_write_link(comp_params, db_dict) -> tuple[str, str, str, list]:
    """Get queries to link a component to its mother table and write to the database.
    Parameters:
    - comp_params (dict): Component parameters including prefix and mother table info.
    - db_dict (dict): Data to be uploaded to the database.
    Returns:
    - pre_query (str): Query to verify component exists in mother table.
    - comp_name_val (str): Component name/ID value.
    - query (str): Main insertion query.
    - column_values (list): Values to be inserted.

    Raises:
    - MissingEntryException: If component ID column is not in the data."""

    # Extract basic parameters
    prefix = comp_params['prefix']
    mother_table = comp_params['mother_table']
    table_name = f"{prefix}_inspect"

    # Define column names
    number_col = f"{prefix}_no"
    comp_name_col = f"{prefix}_name"
    column_names = list(db_dict.keys())
    column_values = list(db_dict.values())

    # Verify component name exists in data
    if comp_name_col not in column_names:
        raise MissingEntryException(
            f"Component ID not provided in data. Column names must contain {comp_name_col}."
        )

    # Get component name value and its position in the data
    comp_name_val = db_dict[comp_name_col]
    comp_name_position = f"${column_names.index(comp_name_col) + 1}"

    # Generate the existence check query
    pre_query = f"""
    SELECT EXISTS (
        SELECT 1
        FROM {mother_table}
        WHERE {comp_name_col} = $1
    );"""

    placeholders = [f"${i + 1}" for i in range(len(column_names))]
    query = f"""
    INSERT INTO {table_name} ({number_col}, {', '.join(column_names)})
    SELECT {mother_table}.{number_col}, {', '.join(placeholders)}
    FROM {mother_table}
    WHERE {mother_table}.{comp_name_col} = {comp_name_position};
    """
    # WHERE REPLACE({mother_table}.{comp_name_col}, '-', '_') = {comp_name_position};
    return pre_query, comp_name_val, query, column_values

class DBClient():
    def __init__(self, config):
        """Initialize the database client.
        Parameters:
        - config: a loaded yaml configuration object."""
        self.host = config['host']
        self.database = config['database']
        self.user = config['user']
        self.password = config['password']

        self._connect_params = {
            'host': self.host,
            'database': self.database,
            'user': self.user,
            'password': self.password}

    async def fetch_PostgreSQL(self, query):
        conn = await asyncpg.connect(**self._connect_params)
        value = await conn.fetch(query)
        await conn.close()
        return value

    async def request_PostgreSQL(self, component_type, bp_name = None):
        """Request data from the database."""
        result = await self.fetch_PostgreSQL(get_query_read(component_type, bp_name))
        return result

    async def upload_PostgreSQL(self, comp_params, db_upload_data) -> bool:
        """Upload data to the database. Return True if successful, False otherwise.

        Parameters:
        - table_name (str): Name of the table to upload data to.
        - db_upload_data (dict): Dictionary containing the data to upload."""
        try:
            conn = await asyncpg.connect(**self._connect_params)
            logging.debug('Connection successful. \n')
            table_name = comp_params['db_table_name']

            schema_name = 'public'
            table_exists_query = """
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = $1 
                AND table_name = $2
            );
            """
            logging.debug(f"Attempting to upload to Table {table_name}...")
            table_exists = await conn.fetchval(table_exists_query, schema_name, table_name)  ### Returns True/False
            if table_exists:
                query = get_query_write(table_name, db_upload_data.keys())
                await conn.execute(query, *db_upload_data.values())
                logging.info(f'Data successfully uploaded to the {table_name}!')
                return True
            else:
                logging.warning(f'Table {table_name} does not exist in the database. Please create the table before uploading data.')
                return False
        except Exception as e:
            logging.error(f"Error encountered when uploading to the database: {e}")
            return False
        finally: 
            await conn.close()

    async def link_and_update_table(self, comp_params, db_upload_data) -> bool:
        """Link the component to the mother table and update the database. Return True if successful, False otherwise."""
        conn = await asyncpg.connect(**self._connect_params)
        try:
            prequery, name, query, values = get_query_write_link(comp_params, db_upload_data)
            logging.debug("Executing pre-query...")
            status = await conn.fetchval(prequery, name)
            if not status:
                logging.warning(f"Component {name} not found in the mother table {comp_params['mother_table']}.")
                await self.upload_PostgreSQL(comp_params, db_upload_data)
                logging.info(f"Component {name} uploaded without linking to the mother table.")
            else:
                await conn.execute(query, *values)
                logging.info('Data successfully uploaded!')
            return True
        except Exception as e:
            logging.error(f"Error encountered when linking to the mother table: {e}")
            return False
        
    async def GrabSensorOffsets(self, name: str) -> tuple[float, float, float]:
        """Grab the sensor offsets (PM offset numbers) from the database.
        
        Parameters:
        - name (str): Name of the prototype module.

        Returns:
        - tuple[float, float, float]: x_offset, y_offset, angle_offset for the module."""
        conn = None
        try:
            conn = await asyncpg.connect(**self._connect_params)
            query = """SELECT x_offset_mu, y_offset_mu, ang_offset_deg
                        FROM proto_inspect
                        WHERE LOWER(proto_name) = LOWER($1)
                        ORDER BY proto_row_no DESC
                        LIMIT 1;"""
            # Order by row number descending to get the most recent entry
            row = await conn.fetchrow(query, name.replace('ML', 'PL', 1))
            return row['x_offset_mu'], row['y_offset_mu'], row['ang_offset_deg']
        except Exception as e:
            logging.error("Error encountered when grabbing Protomodule offsets from database.")
            logging.error("Accuracy Plot: PM offsets set to 0, 0, 0, due to failed data pull.")
            logging.error(e)
            return 0.0, 0.0, 0.0
        finally:
            if conn:
                await conn.close()
