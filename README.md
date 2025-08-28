# Overview
Python program that log public IP address in SQLite database.  
Only new/change IP is added to DB, if IP is same as last time program was run, then only `last_time_seen` column in table is updated.  

Example of html report:
![Example of html report](/documentation/screenshot/html_report.png)

Made for Raspberry Pi Zero 2 W.  
Raspberry Pi Zero 2 W, at least in my experience get stuck ever few days/weeks, so there is `gap` table to track when it got stuck.  

## Installation
Use [uv](https://docs.astral.sh/uv/) for installing, make sure to have it [installed](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer).  
```shell
# after you have uv
uv tool install git+https://github.com/sasa-buklijas/public_ip_logger
# after this tool is available as public-ip-logger
```

## Usage from CLI 
Just to verify that installation was successful.

```shell
# run
public-ip-logger

# this will make 3x files
# public_ip.db -> what is SQLite DB
# index.html   -> HTML report with IP addresses, first seen, last, duration, etc
# ip_to_sqlite.log -> logs 2x files rotated every 5 days

# to see where are these files located do
public-ip-logger dirs
```

## Crontab
Idea is to run ` public-ip-logger` from crontab every minute

```shell
* * * * * ~/.local/bin/public-ip-logger  > ~/crontab-output-4-public-ip-logger.txt 2>&1
# > ~/crontab-output-4-public-ip-logger.txt 2>&1
# is recommended to see/debug any errors 

# look at index.html via web browser
# you can also server index.html as static webpage with web server (eg. apache, nginx, etc)
```

## Upgrade
```shell
# uv --upgrade will do reinstall ot latest version
uv tool install --upgrade git+https://github.com/sasa-buklijas/public_ip_logger
```

## Uninstall
```shell
uv tool uninstall public-ip-logger
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
-- "reason" is empty when created
-- idea is to populate it manually if user wants eg. "gap do to router reboot"
```

## License  
This project is licensed under the [AGPLv3](LICENSE).
