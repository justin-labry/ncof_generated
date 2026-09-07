#!/bin/sh

set -eu

for server in \
  nncof-server \
  nnef-server \
  nsmf-server \
  callback-server
do
  log_dir="./${server}/logs"

  if [ -d "$log_dir" ]; then
    echo "Cleaning: $log_dir"
    find "$log_dir" -mindepth 1 -delete
  else
    echo "Skip: $log_dir does not exist"
  fi
done

echo "Log cleanup completed."
