#!/bin/sh

host=${SERVER_NAME:-localhost}

/usr/bin/wget --header "Host: ${host}" --quiet --spider localhost:8080
