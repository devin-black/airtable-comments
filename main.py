import requests
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from slack_sdk import WebhookClient

def main():
   #How many days back to show recent comments?
   #https://www.python-engineer.com/posts/run-python-github-actions/
   #Cron for every weekday at 00:00 (UTC): 0 0 * * 1-5
   if datetime.now().weekday() < 5 and datetime.now().weekday() > 0:
      recentHoursBack = 24
      sendToSlack = True
   elif datetime.now().weekday() == 0:
      recentHoursBack = 48
      sendToSlack = True
   else:
      recentHoursBack = 0
      sendToSlack = False
      exit()

   try:
      load_dotenv()
      baseId = os.getenv('BASEID')
      tableId = os.getenv('TABLEID')
      token = os.getenv('TOKEN')
      webhook_url = os.getenv('WEBHOOK_URL')
   except:
      print("Error loading env file")
   else:
      if not baseId or not tableId or not token:
         print("Env file found but error loading variables")
         exit()

   #API header
   headers = {
      "Authorization": f"Bearer {token}"
   }


   #Get record IDs
   allRecords = []

   recordsUrl = f"https://api.airtable.com/v0/{baseId}/{tableId}"
   records = requests.get(recordsUrl, headers=headers)
   records = records.json()
   allRecords.extend(records['records'])

   offset = records['offset']

   #Now paginate
   while True:
      recordsUrl = f"https://api.airtable.com/v0/{baseId}/{tableId}?pageSize=100&offset={offset}"
      records = requests.get(recordsUrl, headers=headers)
      records = records.json()
      allRecords.extend(records['records'])

      try:
         offset = records['offset']
      except KeyError:
         break

   recordIds = []
   newRecords = {}

   print(f"Retrieved {len(allRecords)} records")

   for record in allRecords:
      #Grab ID for later to use for comments
      recordIds.append(record["id"])
      
   print("Successfully retrieved record IDs")

   #Get comments
   allComments = []
   for recordId in recordIds:
      commentsUrl = f"https://api.airtable.com/v0/{baseId}/{tableId}/{recordId}/comments?pageSize=100"
      comments = requests.get(commentsUrl, headers=headers)
      comments = comments.json()
      try:
         comments = comments["comments"][0]
      except IndexError:
         #If no comments
         continue

      #Just take what we need
      commentPretty = {}
      commentPretty['id'] = comments['id']
      commentPretty['author'] = comments['author']['name']
      commentPretty['createdTime'] = comments['createdTime']
      commentPretty['text'] = comments['text']

      #Add the record ID
      commentPretty['recordId'] = recordId

      allComments.append(commentPretty)
      print(f"Retrieved comment for record {recordId}")

   print(f"Retrieved {len(allComments)} comments")

   #Add record info to comments
   allCommentsWithRecordId = []
   for comment in allComments:
      for record in allRecords:
         if record['id'] == comment['recordId']:
            comment['recordName'] = record["fields"]["Record Name"]
            comment['phase'] = record["fields"]["Phase"]
            allCommentsWithRecordId.append(comment)

   allComments = allCommentsWithRecordId

   print("Successfully retrieved comments")

   #Now find recent comments:
   oneDayAgo = datetime.now() - timedelta(hours=recentHoursBack)
   recentComments = [
      comment for comment in allComments if 
      datetime.fromisoformat(comment["createdTime"][:-1]) > oneDayAgo
   ]

   #Package up comments and send to Slack'
   webhook = WebhookClient(webhook_url)

   if sendToSlack and len(recentComments) > 0:
      response = webhook.send(text="Airtable comments summary", blocks=[
         {
            "type": "section",
            "text": {
               "type": "mrkdwn",
               "text": f"_Airtable comments from the last {recentHoursBack} hours:_"
            }
         }
      ])
      for comment in recentComments:
         #make date a little prettier
         formattedDate = datetime.strptime(comment['createdTime'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime("%b %d %Y %H:%M:%S")

         payload = f"""
         On *{comment['recordName']}* (Phase: {comment['phase']})\nBy {comment['author']} at {formattedDate} (UTC)
         ```{comment['text']}```
         """
         

         response = webhook.send(blocks=[
            {
               "type": "section",
               "text": {
                  "type": "mrkdwn",
                  "text": payload
               }
            }
         ])

   print("Done")

if __name__ == "__main__":
   main()