# Airtable Comments Summary

This Python script retrieves comments from Airtable and summarizes them, sending them to Slack.

By default it runs on weekdays and sends a summary of the last 24 hours, except on Monday where it sends the last 48.

## Required Libraries

This script requires the following libraries:
- requests
- slack_sdk
- dotenv

To install these libraries, run the following command:
`pip install requests slack_sdk python-dotenv`

## Environment Variables

This script uses the following environment variables:
For Airtable:
- BASE_ID
- TABLE_ID
- TOKEN

For Slack:
- WEBHOOK_URL

You can set these environment variables in one of two ways:
1. Set the environment variables in your shell environment.
2. Add the environment variables to a `.env` file in the same directory as the script. (see `env.example`, which you can rename to `.env`)

## Usage

To run the script:
`python airtable_comments_summary.py`

## Scheduling
- Including is a `github-actions.yml` file which has a GitHub Action that runs the script every weekday via cron. 

## Todo
- Make scheduling more flexible. Currently it runs on weekdays and sends a summary of the last 24 hours, except on Monday where it sends the last 48. This should be configurable.