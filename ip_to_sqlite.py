import io
import time
import logging
import logging.handlers
# pip packages
import dataset
import requests
import humanize

VERSION = '1.0.0'

def get_public_ip():
    url = "https://api.ipify.org/"
    try:
        response = requests.get(url, timeout=5)  # 5-second timeout
        response.raise_for_status()  # Raise HTTP errors (4xx, 5xx)
        return response.text
    except requests.Timeout:
        raise TimeoutError("Request to api.ipify.org timed out.")
    except requests.RequestException as e:
        raise RuntimeError(f"Request failed: {e}")


# to remove and abstract complexity of DB operations
class DB():
    def __init__(self):
        self._db = dataset.connect('sqlite:///public_ip.db')
        self._public_ip_table = self._db['public_ip']

    def add_new_row(self, ip: str, row_time: float):
        return self._public_ip_table.insert(dict(ip=ip, first_time_seen=row_time, last_time_seen=row_time))

    def get_last_row(self):
        results = list(self._public_ip_table.all())
        self._last_row = self._public_ip_table.find_one(order_by='-last_time_seen')
        #logging.debug(f'{results=}')
        #logging.debug(f'{self._last_row=}')
        return self._last_row

    def update_last_time_seen(self, last_time_seen: float):
        return self._public_ip_table.update(dict(id=self._last_row['id'], last_time_seen=last_time_seen), ['id'])

    def get_public_ip_rows(self, limit = None):
        return self._public_ip_table.find(order_by='last_time_seen', _limit=limit)


def public_ip_to_db():
    program_start_time = time.time()
    try:
        current_public_ip = get_public_ip()
    except Exception as e:
        logging.exception(e)
        exit(10)
    response_public_ip_time = time.time()
    logging.info(f'API call took {(response_public_ip_time - program_start_time):.3f} {current_public_ip=}')

    db: DB = DB()
    results = db.get_last_row()

    if results: # NOT first run
        
        last_public_ip = results['ip']
        last_time_seen = results['last_time_seen']
        since_last_check = program_start_time - last_time_seen

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
    from datetime import datetime, timezone

    # Get the current local time with the system's timezone
    current_time = datetime.now().astimezone()
    time_string = current_time.strftime("%Y-%m-%d %H:%M:%S %Z%z")
    html.write(f"<h1>Generated at: {time_string}</h1>\n")

    html.write("<table border='1'>\n")
    columns = ['id', 'IP', 'Start Time', 'End Time', 'Duration', 'Gap', 'Status']
    html.write("<tr>" + "".join(f"<th>{col}</th>" for col in columns) + "</tr>\n")

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
    # Footer
    html.write(f"</table><p>Generated by ip_logger version {VERSION}</p></body></html>\n")

    # Write to file
    with open("index.html", "w") as f:
        f.write(html.getvalue())

    logging.info(f'generate_webpage took {(time.time() - start_time):.3f} seconds')


if __name__ == '__main__':
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
    # Suppress logging from urllib3 library
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    public_ip_to_db()
    generate_webpage()
