import logging
import os
import sys
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from slack_sdk import WebhookClient

logging.basicConfig(level=logging.INFO)


def request_api(url: str, headers: dict, timeout: int = 10) -> requests.Response:
    for i in range(3):
        try:
            response = requests.get(url=url, headers=headers, timeout=timeout)
            return response
        except requests.exceptions.Timeout:
            if i == 2:
                logging.error("Request timed out 3 times. Quitting.")
                sys.exit()
            else:
                logging.warning("Request timed out. Trying again...")


def main():
    # How many days back to show recent comments?
    if datetime.now().weekday() < 5 and datetime.now().weekday() > 0:
        recent_hours_back = 24
    elif datetime.now().weekday() == 0:
        recent_hours_back = 48
    else:
        logging.error("Not a valid day. Quitting.")
        sys.exit()

    # Get env vars — first try OS, then try .env
    base_id = os.environ.get("BASE_ID")
    table_id = os.environ.get("TABLE_ID")
    token = os.environ.get("TOKEN")
    webhook_url = os.environ.get("WEBHOOK_URL")

    if not all([base_id, table_id, token, webhook_url]):
        logging.info("No env vars from OS. Trying .env file.")
        load_dotenv()
        base_id = os.environ.get("BASE_ID")
        table_id = os.environ.get("TABLE_ID")
        token = os.environ.get("TOKEN")
        webhook_url = os.environ.get("WEBHOOK_URL")

    if not all([base_id, table_id, token, webhook_url]):
        logging.error("Could not retrieve required environment variables. Quitting")
        sys.exit()

    # API header
    headers = {"Authorization": f"Bearer {token}"}

    # Get record IDs
    all_records = []

    records_url = f"https://api.airtable.com/v0/{base_id}/{table_id}"

    records = request_api(url=records_url, headers=headers)

    records = records.json()
    all_records.extend(records["records"])

    offset = records["offset"]

    # Now paginate
    while True:
        records_url = f"https://api.airtable.com/v0/{base_id}/{table_id}?pageSize=100&offset={offset}"

        records = request_api(url=records_url, headers=headers)

        records = records.json()
        all_records.extend(records["records"])

        try:
            offset = records["offset"]
        except KeyError:
            break

    record_ids = []

    logging.info(f"Retrieved {len(all_records)} records")

    for record in all_records:
        # Grab ID for later to use for comments
        record_ids.append(record["id"])

    logging.info("Successfully retrieved record IDs")

    # Get comments
    all_comments = []
    for record_id in record_ids:
        comments_url = f"https://api.airtable.com/v0/{base_id}/{table_id}/{record_id}/comments?pageSize=100"

        comments = request_api(url=comments_url, headers=headers)

        comments = comments.json()
        try:
            comments = comments["comments"][0]
        except IndexError:
            # If no comments
            continue

        # Just take what we need
        comment_pretty = {}
        comment_pretty["id"] = comments["id"]
        comment_pretty["author"] = comments["author"]["name"]
        comment_pretty["createdTime"] = comments["createdTime"]
        comment_pretty["text"] = comments["text"]

        # Add the record ID
        comment_pretty["recordId"] = record_id

        all_comments.append(comment_pretty)
        logging.info(f"Retrieved comment for record {record_id}")

    logging.info(f"Retrieved {len(all_comments)} comments")

    # Add record info to comments
    all_comments_with_record_id = []
    for comment in all_comments:
        for record in all_records:
            if record["id"] == comment["recordId"]:
                comment["recordName"] = record["fields"]["Record Name"]
                comment["phase"] = record["fields"]["Phase"]
                all_comments_with_record_id.append(comment)

    all_comments = all_comments_with_record_id

    logging.info("Successfully added record info to comments")

    # Now find recent comments:
    one_day_ago = datetime.now() - timedelta(hours=recent_hours_back)
    recent_comments = [
        comment
        for comment in all_comments
        if datetime.fromisoformat(comment["createdTime"][:-1]) > one_day_ago
    ]

    # Package up comments and send to Slack'
    webhook = WebhookClient(webhook_url)

    if recent_comments:
        webhook.send(
            text="Airtable comments summary",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"_Airtable comments from the last {recent_hours_back} hours:_",
                    },
                }
            ],
        )
        for comment in recent_comments:
            # make date a little prettier
            formatted_date = datetime.strptime(
                comment["createdTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).strftime("%b %d %Y %H:%M:%S")

            payload = f"""
         On *{comment['recordName']}* (Phase: {comment['phase']})\nBy {comment['author']} at {formatted_date} (UTC)
         ```{comment['text']}```
         """

            webhook.send(
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn", "text": payload}}
                ]
            )

            logging.info("Done")
            sys.exit(0)

    else:
        logging.warning("No recent comments to send. Quitting.")
        sys.exit()


if __name__ == "__main__":
    main()
