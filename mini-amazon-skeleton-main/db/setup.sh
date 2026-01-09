#!/bin/bash

mypath=`realpath "$0"`
mybase=`dirname "$mypath"`
cd "$mybase"

datadir="${1:-generate/}"
if [ ! -d $datadir ] ; then
    echo "$datadir does not exist under $mybase"
    exit 1
fi

source ../.flaskenv
dbname=$DB_NAME

PGPASSWORD="$DB_PASSWORD" dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" --if-exists "$dbname"
PGPASSWORD="$DB_PASSWORD" createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$dbname"

PGPASSWORD="$DB_PASSWORD" psql -X -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$dbname" -f create.sql
cd $datadir
PGPASSWORD="$DB_PASSWORD" psql -X -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$dbname" -f "$mybase/load.sql"
