import io
import time
import random
import tomllib
import ipaddress
import logging
import logging.handlers
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError
# pip packages
import ping3
import dataset
import requests
import humanize
#from tenacity import retry, stop_after_attempt, wait_fixed

VERSION = '1.1.7'

#@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))  # 2 attempts, 2 seconds between retries
def get_public_ip() -> str:
    IPIFY = 'https://api.ipify.org/'
    AWS = 'https://checkip.amazonaws.com'
    ICANHAZIP = 'https://icanhazip.com/'
    IFCONFIG = 'https://ifconfig.me/'
    IPINFO = 'https://ipinfo.io/ip'
    external_api = (IPIFY, AWS, ICANHAZIP, IFCONFIG, IPINFO, )
    #external_api = (IPINFO,)   # just for developer , when adding new enteral API for IP, to test is 
    external_ip = '__UNKNOWN_IP__'

    eairo = random.sample(external_api, k=len(external_api)) # external_api_in_random_order
    for url in eairo:
        try:
            response = requests.get(url, timeout=5)  # 5-second timeout
            response.raise_for_status()  # Raise HTTP errors (4xx, 5xx)
            if url in (IPIFY, IFCONFIG, IPINFO, ):
                #logging.debug(f'{response.text=} {response.text.strip()=}')
                external_ip = response.text
                break
            elif url in (AWS, ICANHAZIP, ):
                #logging.debug(f'{response.text=} {response.text.strip()=}')
                external_ip = response.text.strip()
                break
            else:
                logging.error(f'Unknown {url=} {response.text=}')
                raise ValueError(f'Unknown {url=} {response.text=}')
        except requests.Timeout:
            logging.error(f'Request to {url=} timed out.')
        except requests.RequestException as e:
            logging.error(f'Request to {url=} error {e=}')

    # all 5x API failed for some reason
    if external_ip == '__UNKNOWN_IP__':
        local_router_ping_result = ping3.ping('192.168.1.1') # Local Router, check if it is working
        logging.warning(f'{local_router_ping_result=}')

        ping_result = ping3.ping('8.8.8.8') # Google DNS, check if internet is working
        logging.warning(f'{ping_result=}')
        if ping_result is None: # If timed out (no reply), returns None
            logging.warning('No internet access or Google down.')

    logging.info(f'{url=} {external_ip=}')
    try:
        ipaddress.IPv4Address(external_ip)
        return external_ip
    except ipaddress.AddressValueError:
        logging.error(f'Not valid {external_ip=}')
        raise ValueError('Failed to retrieve external IP')


# to remove and abstract complexity of DB operations
class DB():
    def __init__(self):
        self._db = dataset.connect('sqlite:///public_ip.db')
        self._public_ip_table = self._db['public_ip']
        self._error_table = self._db['errors']
        self._gap_table = self._db['gap']

    def add_new_row(self, ip: str, row_time: float):
        return self._public_ip_table.insert(dict(ip=ip, first_time_seen=row_time, last_time_seen=row_time))

    def get_last_row(self):
        #results = list(self._public_ip_table.all())
        #logging.debug(f'{results=}')
        self._last_row = self._public_ip_table.find_one(order_by='-last_time_seen')
        #logging.debug(f'{self._last_row=}')
        return self._last_row

    def update_last_time_seen(self, last_time_seen: float):
        return self._public_ip_table.update(dict(id=self._last_row['id'], last_time_seen=last_time_seen), ['id'])

    def get_public_ip_rows(self, limit = None):
        return self._public_ip_table.find(order_by='last_time_seen', _limit=limit)

    def insert_gap(self, start, end):
        self._gap_table.insert(dict(start=start, end=end, reason=''))

    def get_gap_rows(self, limit = None):
        return self._gap_table.find(order_by='-end', _limit=limit)

    def number_of_gap_rows(self):
        return self._gap_table.count()

    def number_of_error_rows(self):
        return self._error_table.count()

    def get_error_rows(self, limit = None):
        return self._error_table.find(order_by='-unix_time_stamp', _limit=limit)

    def add_error(self, uts: float, error: str):
        self._error_table.insert(dict(unix_time_stamp=uts, error=error))

    def close(self):
        self._db.close()


def public_ip_to_db():
    program_start_time = time.time()
    try:
        current_public_ip = get_public_ip()
    except Exception as e:
        db = DB()
        db.add_error(program_start_time, str(e))
        db.close()
        #logging.debug(f'{e=} --- {str(e)=}')
        logging.exception(e)
        return False
    #finally:
    #    if get_public_ip.statistics['attempt_number'] != 1:
    #        logging.warning(f'{get_public_ip.statistics=}')
    response_public_ip_time = time.time()
    
    logging.info(f'API call took {(response_public_ip_time - program_start_time):.3f} {current_public_ip=}')

    db: DB = DB()
    results = db.get_last_row()

    if results: # NOT first run
        
        last_public_ip = results['ip']
        last_time_seen = results['last_time_seen']
        since_last_check = program_start_time - last_time_seen

        #logging.debug(f'{last_time_seen=} {since_last_check=}')
        # I am running this on Raspberry Pi Zero 2 W, ever minute from crontab
        # Raspberry Pi Zero 2 W was not designed to run 24/7, usually it get stuck ever few days
        # this is just table to track when it got stuck
        if since_last_check > 180:  # expected 60 seconds on average, gave 40 as buffer 
            logging.warning(f'{since_last_check=:.2f}')
            db.insert_gap(last_time_seen, program_start_time)

        if current_public_ip == last_public_ip: # IP same
            logging.info(f'ip same {current_public_ip} == {last_public_ip}, {since_last_check:.1f} seconds since last run.')

            rows_updated = db.update_last_time_seen(program_start_time)
            if rows_updated != 1:
                logging.error(f'SOME PROBLEM, EXPECTED 1 ROW UPDATED, but {rows_updated=}')
        else:   # if IP changed
            logging.info(f'ip NOT same {current_public_ip} != {last_public_ip}')

            primary_key_id = db.add_new_row(current_public_ip , program_start_time)
            if primary_key_id > 1:
                    logging.error(f'SOME PROBLEM, EXPECTED > 1 for primary_key_id, but {primary_key_id=}')

    else:   # first run, no data in DB
        logging.info('First run')
        primary_key_id = db.add_new_row(current_public_ip , program_start_time)
        if primary_key_id != 1:
                logging.error(f'SOME PROBLEM, EXPECTED 1 for primary_key_id, but {primary_key_id=}')

    # to flush SQLite WAL
    db.close()

    # 2x spaces for better output
    logging.info(f'public_ip_to_db  took {(time.time() - program_start_time):.3f} seconds')


def generate_webpage():
    start_time = time.time()

    # DB access
    db: DB = DB()
    rows_oldest_first = db.get_public_ip_rows()

    # Use StringIO to efficiently build the HTML in memory
    html = io.StringIO()
    html.write("<html><head><title>IP Logger</title></head><body>\n")
    from datetime import datetime

    # Get the current local time with the system's timezone
    current_time = datetime.now().astimezone()
    time_string = current_time.strftime("%Y-%m-%d %H:%M:%S %Z%z")
    html.write(f"<h1>Generated at: {time_string}</h1>\n")

    html.write("<h2>Public IP</h2><table border='1'>\n")
    columns = ['id', 'IP', 'Start Time', 'End Time', 'Duration', 'Gap', 'Status']
    html.write("<tr>" + "".join(f"<th>{col}</th>" for col in columns) + "</tr>\n")

    # public_ip table
    table_rows_oldest_first = []
    previous_last_time_seen = None
    previous_ip = None
    # rows_oldest_first because of gap calculation
    for row in rows_oldest_first:
        #logging.debug(row)
        first_time_seen = datetime.fromtimestamp(row['first_time_seen']).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z%z")
        last_time_seen = datetime.fromtimestamp(row['last_time_seen']).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z%z")
        duration = humanize.precisedelta(row['last_time_seen'] - row['first_time_seen'])

        if previous_last_time_seen:
            # if gape is more 90 seconds, that crontab was not successfully run every minute
            gap = row['first_time_seen'] - previous_last_time_seen
            if gap < 90:
                status = 'ok'
            else:
                status = 'STRANGE'
            # humanize for better display on webpage
            gap = humanize.precisedelta(row['first_time_seen'] - previous_last_time_seen)
        else:   # not possible to calculate for first row
            status = '-'
            gap = '-'
        previous_last_time_seen = row['last_time_seen'] # mut use row, to have it as float

        # check if previous IP same, that should not happen
        if previous_ip == row['ip']:
            logging.warning(f'{previous_ip} == {row["ip"]}, should not happen')
            status += ' SAME IP AS BEFORE'
        previous_ip == row['ip']
        
        # add it to list
        data = [row['id'], row['ip'], first_time_seen, last_time_seen, duration, gap, status]
        table_rows_oldest_first.append(("<tr>" + "".join(f"<td>{val}</td>" for val in data) + "</tr>\n"))
    # need to reversed, because we want newest on the top(as first row in table)
    html.write("".join(reversed(table_rows_oldest_first)))
    html.write("</table>")

    # error table
    error_rows = db.number_of_error_rows()
    if error_rows > 0:
        html.write("<h2>Error</h2><table border='1'>\n")
        columns = ['id', 'Time', 'Error']
        html.write("<tr>" + "".join(f"<th>{col}</th>" for col in columns) + "</tr>\n")
        for row in db.get_error_rows():
            #logging.debug(f'{row=}')
            utc = datetime.fromtimestamp(row['unix_time_stamp']).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z%z")
            error = row['error']
            html.write("<tr>" + "".join(f"<td>{val}</td>" for val in [row['id'], utc, error]) + "</tr>\n")
        html.write("</table>")

    # gap table
    gap_rows = db.number_of_gap_rows()
    #logging.debug(f'{gap_rows=}')
    if gap_rows > 0:
        html.write("<h2>Gap</h2><table border='1'>\n")
        columns = ['id', 'Start Time', 'End Time', 'Gap Duration', 'Reason']
        html.write("<tr>" + "".join(f"<th>{col}</th>" for col in columns) + "</tr>\n")
        for row in db.get_gap_rows():
            #logging.debug(f'{row=}')
            start = datetime.fromtimestamp(row['start']).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z%z")
            end = datetime.fromtimestamp(row['end']).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z%z")
            duration = humanize.precisedelta(row['end'] - row['start'])
            html.write("<tr>" + "".join(f"<td>{val}</td>" for val in [row['id'], start, end, duration, row['reason']]) + "</tr>\n")
        html.write("</table>")

    # Footer
    html.write(f"<p>Generated by ip_logger version {VERSION}</p></body></html>\n")

    # Write to file
    with open("index.html", "w") as f:
        f.write(html.getvalue())

    # to flush SQLite WAL
    db.close()

    logging.info(f'generate_webpage took {(time.time() - start_time):.3f} seconds')


def get_version():
    package_name = "public-ip-logger"

    # First try installed metadata
    try:
        return version(package_name)
    except PackageNotFoundError:
        # Fallback: read pyproject.toml in the same folder
        pyproject = Path(__file__).with_name("pyproject.toml")
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            return data["project"]["version"]
        except Exception:
            return "unknown"


def main():
    # set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        #format='%(asctime)s:%(msecs)03d|%(filename)14s|%(lineno)4d|%(levelname)10s|%(name)s|%(message)s',
        format='%(asctime)s:%(msecs)03d|%(lineno)4d|%(levelname)10s|%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.handlers.TimedRotatingFileHandler(
                'ip_to_sqlite.log',
                when = 'D',
                interval = 4,       # rotate logs ever 4 days
                backupCount = 1,    # 2x files
            ),
            logging.StreamHandler()
        ]
    )

    program = Path(__file__).stem
    version = get_version()

    try:
        logging.info(f'{program} v{version} ---START---')
        public_ip_to_db()
        generate_webpage()
    except Exception as e:
        logging.exception(e)
    finally:
        logging.info(f'{program} v{version} ----END----')


if __name__ == '__main__':
    main()
