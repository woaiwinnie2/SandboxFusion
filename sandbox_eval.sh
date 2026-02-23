#!/bin/bash
# Script to test the sandbox by running 'ls' in bash
# http://localhost:8080/run_code

echo "🔍 Sending 'ls -R . /Workspace' t
o sandbox..."

curl -s -X POST "http://localhost:8080/run_code" \
     -H "Content-Type: application/json" \
     -d '{
           "code": "ls -R ./Workspace",
           "language": "bash",
           "files": {
             "Workspace/test": ""
           }
         }'
