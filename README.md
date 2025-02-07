# Overview
Python program that log public IP address in SQLite database.  
Made for Raspberry Pi Zero 2 W.  

## Usage
```
git clone https://github.com/sasa-buklijas/ip_logger
cd ip_logger

python -m venv venv-3_11_2
. ./venv-3_11_2/bin/activate

python -m pip install -r requirements.txt

python ip_to_sqlite.py
# this will make 2x files
# public_ip.db -> what is SQLite DB
# index.html   -> HTML report with IP addresses, first seen, last, duration, etc
```
Idea is to run `python ip_to_sqlite.py` in crontab
```
@reboot
* * * * * cd /home/pi/ip_logger && ./venv-3_11_2/bin/python ip_to_sqlite.py

# look at index.html via web browser
# you can also server index.html as static webpage with web server (eg. apache, nginx, etc)
```

## Supported Python Version
Supported Python version is [.python-version](.python-version)  
Others are probably also working, this one is used/tested by myself.

## External Packages
[https://github.com/psf/requests](requests)  
[https://github.com/pudo/dataset](dataset)
[https://github.com/python-humanize/humanize](humanize)

## SQLite database structure
One table:
```
$ sqlite3 public_ip.db ".schema public_ip"

CREATE TABLE public_ip (
	id INTEGER NOT NULL,
	ip TEXT,
	first_time_seen FLOAT,
	last_time_seen FLOAT,
	PRIMARY KEY (id)
);
```



