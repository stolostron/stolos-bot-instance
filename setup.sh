#!/bin/bash
set -e

echo "cve-bot-instance" > /home/botuser/app/.instance-id

# Instance-specific packages go here:
# dnf --disableplugin=subscription-manager --disablerepo='*' --enablerepo='ubi-*' install -y --nodocs <package>
# pip3.12 install <package>
# npm install -g <package>

echo "Instance setup complete: cve-bot-instance"
