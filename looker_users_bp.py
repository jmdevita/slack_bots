import os, json
from datetime import datetime, timedelta, date, time

from googleauthentication import googlesheets_append, googlesheets_read, googlesheets_write, googlesheets_clear

from slack_sdk import WebClient
from flask import abort, Blueprint, request, make_response
from flask_celery_app import flaskapp, add_user_google
looker_client = WebClient(token=os.environ['LOOKER_BOT_TOKEN'])
looker_bot = Blueprint('looker_bot', __name__)

googlesheets_id = os.environ['LOOKER_GOOGLESHEETS_ID']
WEBHOOK_VERIFY_TOKEN = os.environ['LOOKER_WEBHOOK_VERIFY_TOKEN']

def is_request_valid(request):
    payload = json.loads(request.form['payload'])
    is_api_app_id_valid = payload['api_app_id'] == os.environ['LOOKER_API_APP_ID']
    is_team_id_valid = payload['team']['id'] == os.environ['SLACK_TEAM_ID']
    is_type_valid = payload['type'] == 'block_suggestion'
    return is_api_app_id_valid and is_team_id_valid and is_type_valid

def is_request_valid_2(request):
    is_team_id_valid = json.loads(request.form['payload'])['user']['team_id'] == os.environ['SLACK_TEAM_ID']
    return is_team_id_valid

def is_request_valid_3(request):
    payload = json.loads(request.form['payload'])
    is_team_id_valid = payload['user']['team_id'] == os.environ['SLACK_TEAM_ID']
    is_type_valid = payload['type'] == 'shortcut' or payload['type'] == 'block_actions' or payload['type'] == 'view_submission'
    return is_team_id_valid and is_type_valid

# Looker Routes
@looker_bot.route('/looker/shortcut', methods=['POST'])
def shortcut():
    if not is_request_valid_3(request):
        print("Request not valid 1")
        abort(400)
    
    payload = json.loads(request.form['payload'])

    if payload['type'] == 'block_actions' and payload['container']['type'] != 'view':
        button_payload = payload['actions'][0]['value']
        user_name = payload['user']['username']

        text = []
        for id in button_payload:
            g_names = [item for sublist in googlesheets_read(googlesheets_id, 'backlog!A2:A') for item in sublist]
        text = ', '.join(g_names)

        looker_client.chat_update(
            channel=payload['channel']['id'],
            ts=payload['container']['message_ts'],
            blocks= [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text + ' have been approved.'
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "<@{user}> has approved these individuals.".format(user=user_name)
                        }
                    ]
                }
            ]
        )
        # Make this celery app
        g_db = googlesheets_read(googlesheets_id, 'backlog!A2:F')
        for index, val in enumerate(g_db):
            if str(index) in button_payload:
                googlesheets_clear(googlesheets_id, 'backlog!F{num}'.format(num = str(index + 2)))
                googlesheets_write(googlesheets_id, 'backlog!F{num}'.format(num = str(index + 2)), user_name)
        
        return make_response('Support Authenticated', 200)

    elif payload['type'] != 'view_submission':
        message = {
                    "title": {
                        "type": "plain_text",
                        "text": "Add a User"
                    },
                    "submit": {
                        "type": "plain_text",
                        "text": "Submit"
                    },
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "email_address",
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "plain_text_input-action"
                            },
                            "label": {
                                "type": "plain_text",
                                "text": "User Email"
                            }
                        },
                        {
                            "type": "section",
                            "block_id": "group_name",
                            "text": {
                                "type": "mrkdwn",
                                "text": "User Group"
                            },
                            "accessory": {
                                "action_id": "group_option",
                                "type": "external_select",
                                "placeholder": {
                                    "type": "plain_text",
                                    "text": "Type Here"
                                },
                                "min_query_length": 3
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "Can't find your user group? Submit a ticket <https://wellapp.atlassian.net/jira/software/c/projects/WELLBI/boards/80|here>."
                            }
                        },
                        {
                            "type": "input",
                            "block_id": "date_select",
                            "element": {
                                "type": "datepicker",
                                "initial_date": "2021-11-26",
                                "placeholder": {
                                    "type": "plain_text",
                                    "text": "Select a date"
                                },
                                "action_id": "datepicker-action"
                            },
                            "label": {
                                "type": "plain_text",
                                "text": "Date to be Added (must be day after today at the earliest)"
                            }
                        }
                    ],
                    "type": "modal"
                }

        # Changing date
        message['blocks'][3]['element']['initial_date'] = (datetime.today()+timedelta(days=1)).strftime('%Y-%m-%d')
        looker_client.views_open(
            trigger_id = payload['trigger_id'],
            view=message,
        )
        
        return make_response("", 200)
    elif payload['type'] == 'view_submission':
        email = payload['view']['state']['values']['email_address']['plain_text_input-action']['value']
        group = payload['view']['state']['values']['group_name']['group_option']['selected_option']['text']['text'].lower()
        _date = payload['view']['state']['values']['date_select']['datepicker-action']['selected_date']
        requestor_name = payload['user']['username']
        requestor_id = payload['user']['id']
        
        # Celery Task
        add_user_google.delay(googlesheets_id, email, requestor_name, requestor_id, group, _date)
        
        looker_client.chat_postMessage(
            channel=requestor_id,
            text= "These users -- {email} -- are added to the queue. They will be added to *{group}'s* analytics group. You will get a follow up message when the user is added. Generally users are added at 5am PST every day. Please contact <@U01HR2FE9RC> if there was a mistake.".format(email=email, group=group)
        )
        return make_response("", 200)
    else:
        return make_response("", 200)

@looker_bot.route('/looker/select_menu', methods=['POST'])
def select_menu():
    if not is_request_valid(request):
        print("Request is not valid 3")
        abort(400)

    payload = json.loads(request.form['payload'])
    value = payload['value'].lower()

    google_list = googlesheets_read(googlesheets_id, "looker_groups!A2:A")
    name_list = [item.lower() for sublist in google_list for item in sublist]

    message = {
        "options": [
        ]
    }

    for name in name_list:
        if value in name:
            message_template = {'text': {'type': 'plain_text', 'text': '*this is plain_text text*'}, 'value': 'value-3'}
            message_template['text']['text'] = name.title()
            message_template['value'] = name.replace(' ', '_').replace("'","")
            message['options'].append(message_template.copy())

    response = flaskapp.response_class(
        response=json.dumps(message),
        status=200,
        mimetype='application/json'
)

    return response

@looker_bot.route('/looker/user_added', methods=['POST'])
def user_added():
    print('Recieved Message')
    post_data = request.get_json()
    try:
        verify_token = post_data['token']
    except KeyError:
        verify_token = "INVALID"
    if verify_token == os.environ['LOOKER_WEBHOOK_TOKEN']:
        email = post_data['user_email']
        reset_link = post_data['reset_link']

        looker_client.chat_postMessage(
            channel=post_data['slack_id'],
            text= "User -- {email} -- was added to Looker. Their reset link is: {reset_link}".format(email=email, reset_link=reset_link)
        )
        return make_response("", 200)
    elif verify_token == "INVALID":
        return {"message": "No Token"}, 401
    else:
        return {"message": "Not Authorized"}, 401

# User for getting support sign off
@looker_bot.route('/looker/support_message', methods=['POST'])
def support_message():
    # This will wait for matillion job to schedule
    post_data = request.get_json()
    try:
        verify_token = post_data['token']
    except KeyError:
        verify_token = "INVALID"
    if verify_token == WEBHOOK_VERIFY_TOKEN:

        g_db = googlesheets_read(googlesheets_id, 'backlog!A2:F')

        _date = datetime.today()

        message_list = []
        rows = []
        num = 0
        for row in g_db:
            google_date = datetime.strptime(row[4], '%m/%d/%Y')
            if google_date <= _date and row[5] == 'FALSE':
                message_list.append("{email} to the *{group_name}* analytics group| Requested by _{requested_by}_".format(email=row[0], group_name=row[3], requested_by=row[1].title()))
                rows.append(num)
            num += 1
        message_text = "\n".join(message_list)
        if rows:
            looker_client.chat_postMessage(
                channel= 'G01JCPP0SJZ',
                text= "New users to be added to Looker, needs approval!",
                blocks= [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "These are the list of users that are requested to be added to Looker \n -------------------- \n" + message_text + "\n A reminder that users can be removed by deleting them from <https://docs.google.com/spreadsheets/d/10b1-9fr67GS8bHnsHfCEmc2WJk0xyL9ByP3gh_mHXpM/edit#gid=36461416|this document>."
                        }
                    },
                            {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Approve"
                                },
                                "value": "{rows}".format(rows=rows),
                                "action_id": "action-approval"
                            }
                        ]
                    }
                ]
            )
            return make_response("Support Message Sent", 200)
        else:
            return make_response("Support Message not Sent, no users", 200)
    elif verify_token == "INVALID":
        return {"message": "No Token"}, 401
    else:
        return {"message": "Not Authorized"}, 401