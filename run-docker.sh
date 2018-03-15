#!/usr/bin/env bash

echo "running mithra locally for development and testing"
echo "You'll want to run docker-logs in anther window see what's going on"
echo "================================================================================"
echo ""
echo "building js..."

cd js
yarn build
cd ..

echo "================================================================================"
echo ""
echo "running docker compose..."

docker-compose up -d --build
