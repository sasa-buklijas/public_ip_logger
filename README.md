# Overview
Python program that log public IP address in SQLite database.  
Only new/change IP is added to DB, if IP is same as last time program was run, then only `last_time_seen` column in table is updated.  
Made for Raspberry Pi Zero 2 W.  
Raspberry Pi Zero 2 W, at least in my experience get stuck ever few days/weeks, so there is `gap` table to track when it got stuck.  

## Usage

Best to use [uv](https://docs.astral.sh/uv/), make sure to have it [installed](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer).  

```shell
# get code
git clone https://github.com/sasa-buklijas/public_ip_logger

# get in directory
cd public_ip_logger

# run script
uv run python ip_to_sqlite.py

# this will make 2x files
# public_ip.db -> what is SQLite DB
# index.html   -> HTML report with IP addresses, first seen, last, duration, etc
```
Idea is to run `python ip_to_sqlite.py` in crontab
```
* * * * * cd /home/pi/public_ip_logger && ./.venv/bin/python ip_to_sqlite.py

# look at index.html via web browser
# you can also server index.html as static webpage with web server (eg. apache, nginx, etc)
```

## Supported Python Version
Supported Python version is [.python-version](.python-version)  
Others are probably also working, this one is used/tested by myself.

## External Packages
See [pyproject.toml](pyproject.toml) file in `dependencies` section.  

## SQLite database structure
3x tables:
```sql
$ sqlite3 public_ip.db ".schema"

-- for public IP
CREATE TABLE public_ip (
        id INTEGER NOT NULL, 
        ip TEXT, 
        first_time_seen FLOAT, 
        last_time_seen FLOAT, 
        PRIMARY KEY (id)
);

-- if there are some errors in resolving public IP
-- useful for debug and to troubleshot Raspberry Pi 
CREATE TABLE errors (
        id INTEGER NOT NULL, 
        unix_time_stamp FLOAT, 
        error TEXT, 
        PRIMARY KEY (id)
);

-- there are gaps larger than 2 minutes
-- useful for debug and to troubleshot Raspberry Pi
CREATE TABLE IF NOT EXISTS "gap" (
        "id"    INTEGER NOT NULL,
        "start" FLOAT,
        "end"   FLOAT,
        "reason"        TEXT,
        PRIMARY KEY("id")
);

```



