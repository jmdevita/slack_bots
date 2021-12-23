import tweepy
import boto3
from boto3.dynamodb.conditions import Key
from flask import request, make_response, abort, Blueprint
from slack_sdk import WebClient

from datetime import datetime, timezone, timedelta
from dateutil import tz
from time import sleep
import os, json

# Load Variables
session = boto3.Session(
    aws_access_key_id=os.environ['AWS_ACCESS_KEY'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    region_name='us-west-1'
)

twitter = tweepy.Client(bearer_token=os.environ['BEARER_TOKEN'])
query = 'from:noodlesbonesday -is:reply -is:retweet'
dynamodb = session.resource('dynamodb')
WEBHOOK_VERIFY_TOKEN = os.environ['WEBHOOK_VERIFY_TOKEN']

# Load Definitions
def create_table(table_name):
    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'date',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'date',
                    'AttributeType': 'N'
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )

        # Wait until the table exists.
        table.meta.client.get_waiter('table_exists').wait(TableName='sprint_information')
        # Print out some data about the table.
        print("Table Made")
    except:
        print('Table Already Created')

def get_bones(date):
    table= dynamodb.Table('noodle_db')

    response = table.query(
        KeyConditionExpression=Key('date').eq(date))

    text = response["Items"][0]['text']

    return text

def post_bones(date, text):
    table= dynamodb.Table('noodle_db')
    table.put_item(
        Item={
                'date': date,
                'text': text
            }
        )

def is_request_valid(request):
    is_token_valid = request['token'] == os.environ['SLACK_VERIFICATION_TOKEN_NOODLE']
    is_team_id_valid = request['team_id'] == os.environ['SLACK_TEAM_ID']

    return is_token_valid and is_team_id_valid

# Load Single-Time Resources
create_table('noodle_db')
noodle_client = WebClient(token=os.environ['NOODLE_BOT_TOKEN'])
noodle_bot = Blueprint('noodle_bot', __name__)

# Load Flask Routes
@noodle_bot.route('/noodle/workday_update', methods=['POST'])
def workday_update():
    post_data = request.get_json()
    print('Received Message')

    try:
        verify_token = post_data['token']
    except KeyError:
        verify_token = "Invalid"
    
    if verify_token == WEBHOOK_VERIFY_TOKEN:
        #Processing
        today = datetime.utcnow().date()
        this_morning = (datetime(today.year, today.month, today.day, tzinfo=tz.tzutc())).isoformat()
        currently = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        today = today.strftime('%m%d%Y')

        value = 0
        for response in tweepy.Paginator(twitter.search_recent_tweets, query=query, start_time=this_morning, end_time=currently, limit=100):
            if response.meta['result_count'] > 0:
                for tweet in response.data:
                    print(tweet.text)
                    if 'no bones' in tweet.text.lower():
                        value -= 1
                    elif 'bones day' in tweet.text.lower():
                        value += 1
                    else:
                        value
        if value > 0:
            text = "Bones"
        elif value < 0:
            text = "No Bones"
        else:
            text = 'No Reading'
        post_bones(int(today), text)
        sleep(5)
        #Posting
        date = post_data['date']
        type = get_bones(date)
        text = "<!here> "
        if type == 'Bones':
            text += "Bones day! Get out there and crush it, take risks, make that one important call, live today to the fullest!"
        elif type == 'No Bones':
            text += "Today is a No Bones Day, be kind to yourself and remember to focus on self care"
        else:
            text += "No Noodle day. Choose your own adventure."

        noodle_client.chat_postMessage(
            channel='C02QBMW1UDU',
            text = text
        )

        return make_response("Accepted", 200)
    
    elif verify_token == "Invalid":
        return make_response("No Token", 401)
    else:
        return make_response("Not Authorized", 401)

@noodle_bot.route('/noodle/mention', methods=['POST'])
def mention():
    slack_event = json.loads(request.data)
    if slack_event['type'] == 'url_verification':
        print("Challenge Token Accepted")
        return make_response(slack_event["challenge"], 200, {"content_type":
                                                             "application/json"
                                                             })

    if not is_request_valid(slack_event):
        print("Not a Valid Request")
        abort(400)

    if "event" in slack_event:
        event = slack_event["event"]
        event_type = event["type"]
        event_ts = event["ts"]
        #try:
        #    event_ts = event["ts"]
        #except KeyError:
        #    event_ts = event["thread_ts"]
        event_channel=event["channel"]
        #event_message = event["text"]
        event_date = datetime.fromtimestamp(slack_event["event_time"]).strftime('%m%d%Y')
        if event_type == "app_mention":
            print("Bot Mentioned!")
            #Processing
            try:
                _type = get_bones(int(event_date))
            except:
                _type = 'No data yet'
            
            if _type == 'Bones':
                text = "Bones day! Get out there and crush it, take risks, make that one important call, live today to the fullest!"
            elif _type == 'No Bones':
                 text = "Today is a No Bones Day, be kind to yourself and remember to focus on self care."
            elif _type == 'No Reading':
                 text = "No Noodle day. Choose your own adventure."
            else:
                text = "I have not seen a post yet with the type of day it was."

            noodle_client.chat_postMessage(
                channel=event_channel,
                thread_ts = event_ts,
                text = text
            )
            
            return make_response("Answer Sent", 200, {"X-Slack-No-Retry": 1})
        

    return make_response("Unhandled event", 404, {"X-Slack-No-Retry": 1})
