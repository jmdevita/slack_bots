import os, json, re
from datetime import datetime, timedelta

from googleauthentication import googlesheets_append, googlesheets_read, googlesheets_write, googlesheets_clear

# Sendgrid Imports
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from bs4 import BeautifulSoup

# Slack Imports
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
    # This section is for the Looker Bot (Adding a User)

    if payload['type'] == 'block_actions' and payload['container']['type'] == 'message':
        button_action = payload['actions'][0]['action_id']
        # Approve Button Pressed
        if button_action == "action-approval":
            # this button payload contains a list of which rows were approved, where [0] is row 2 in the googlesheet
            button_payload = json.loads(payload['actions'][0]['value'])
            user_name = payload['user']['username']
            g_names = [item for sublist in googlesheets_read(googlesheets_id, 'backlog!A2:A') for item in sublist]
            approved_names = list( g_names[i] for i in button_payload )

            text = ', '.join(approved_names)

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
            g_db = googlesheets_read(googlesheets_id, 'backlog!A2:A')
            for index, val in enumerate(g_db):
                if index in button_payload:
                    googlesheets_clear(googlesheets_id, 'backlog!F{num}'.format(num = str(index + 2)))
                    googlesheets_write(googlesheets_id, 'backlog!F{num}'.format(num = str(index + 2)), user_name)
            
            return make_response('Support Authenticated', 200)
        
        # Delete Button Pressed
        elif button_action == "action-delete":
            looker_client.chat_delete(
                channel=payload['channel']['id'],
                ts=payload['container']['message_ts']
            )
            
            return make_response('Message Deleted', 200)
        else:
            return make_response('No Actionable Method', 400)

    elif payload['type'] == 'shortcut' and payload['callback_id'] == 'looker_add_user':
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
                                "text": "Date to be Added"
                            }
                        }
                    ],
                    "type": "modal",
                    "callback_id": "looker_add_user"
                }

        # Changing date
        message['blocks'][3]['element']['initial_date'] = datetime.today().strftime('%Y-%m-%d')
        looker_client.views_open(
            trigger_id = payload['trigger_id'],
            view=message
        )
        
        return make_response("", 200)
    elif payload['type'] == 'view_submission' and payload['view']['callback_id'] == 'looker_add_user':
        email = payload['view']['state']['values']['email_address']['plain_text_input-action']['value']
        group = payload['view']['state']['values']['group_name']['group_option']['selected_option']['text']['text'].lower()
        _date = payload['view']['state']['values']['date_select']['datepicker-action']['selected_date']
        requestor_name = payload['user']['username']
        requestor_id = payload['user']['id']
        
        # Fix Date
        date_formatted = datetime.strptime(_date, '%Y-%m-%d').strftime('%m/%d/%Y')
        # Celery Task
        add_user_google.delay(googlesheets_id, email, requestor_name, requestor_id, group, date_formatted)
        
        looker_client.chat_postMessage(
            channel=requestor_id,
            text= "These users -- {email} -- are added to the queue. Please check if their contracted seats are updated in the database. They will be added to *{group}'s* analytics group once approved and if there are enough seats. Expect about an hour for approval and you will be notified if the user group may be full, the contract is unavailable, or if the user is added. Please contact <@U01HR2FE9RC> if there was a mistake.".format(email=email, group=group.title())
        )
        return make_response("", 200)

# This section is the Contracted Seats (User Account) Lookup Shortcut

    elif payload['type'] == "shortcut" and payload['callback_id'] == 'check_contract':
        message = {
            "title": {
                "type": "plain_text",
                "text": "Look up Contracted Seats"
            },
            "submit": {
                "type": "plain_text",
                "text": "Submit"
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Want to find out how many seats an account is contracted? Or see if we have a contract at all?"
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
                }
            ],
            "type": "modal",
            "callback_id": "check_contract"
        }

        looker_client.views_open(
            trigger_id = payload['trigger_id'],
            view=message
        )
        return make_response("", 200)

    elif payload['type'] == "view_submission" and payload['view']['callback_id'] == 'check_contract':
        # Read from payload the group
        group = payload['view']['state']['values']['group_name']['group_option']['selected_option']['text']['text'].lower()
        requestor_id = payload['user']['id']
        # Read contract_info section from google sheet
        contract_info_g = googlesheets_read(googlesheets_id, "contract_info!A2:C")
        contract_found = False
        for row in contract_info_g:
            if group == row[0].lower(): # Compares group name to contract_info group name to grab looker seats
                contract_user_count = int(row[2])

                contract_found = True
        # This will read
        print(contract_found)
        if contract_found == True:
            looker_groups_g = googlesheets_read(googlesheets_id, "looker_groups!A2:D")
            for row in looker_groups_g:
                if group == row[0].lower(): # Compares group name to looker_group name to grab seats
                    looker_user_count = int(row[2])

            # The contract_user_count will ALWAYS be met since the contract found variable is true
            if contract_user_count < looker_user_count:
                looker_client.chat_postMessage(
                    channel=requestor_id,
                    text= "This account, {group}, can NOT add more users in looker. Please use the other shortcut to add users.\nContracted Users: {contract_user_count}\nCurrent Looker Users: {looker_user_count}".format(group=group.title(), looker_user_count=looker_user_count, contract_user_count=contract_user_count)
                )
            else:
                looker_client.chat_postMessage(
                    channel=requestor_id,
                    text= "This account, {group}, can add more users in looker. Please contact and assign a ticket to the relevant CEM.\nContracted Users: {contract_user_count}\nCurrent Looker Users: {looker_user_count}".format(group=group.title(), looker_user_count=looker_user_count, contract_user_count=contract_user_count)
                )

        elif contract_found == False:
            looker_client.chat_postMessage(
                channel=requestor_id,
                text= "This account, {group}, does not have a contract in place with a number of users. Please contact your Sales & Finance team to get contracted seats. After, please contact the Data team to update the sheet.".format(group=group.title())
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
        # Adding logic to account for users that have met contract quota or no contract was found
        if post_data['fail_reason'] == "Max Users Met" and not post_data['reset']:
            looker_client.chat_postMessage(
                channel=post_data['slack_id'],
                text= "ERROR: User -- {email} -- was not added to Looker. The contracted amount of total users have been met. If the client is interested in adjusting their contract please consult the Sales team.".format(email=email)
            )
            return make_response("", 200)
        elif post_data['fail_reason'] == "No Contract Found" and not post_data['reset']:
            looker_client.chat_postMessage(
                channel=post_data['slack_id'],
                text= "ERROR: User -- {email} -- was not added to Looker. There is no contract found for this account, please contact the Finance team or provide the contract details to the Data team.\
                       If the customer does not have a looker license limit, please assign to the support queue to add customer user and @ Craig Wason and @ Jessica Edge in the internal feed, support will add the users via admin console".format(email=email)
            )
            return make_response("", 200)
        else:
            analytics_new_account_link = os.environ['ANALYTICS_BASE_LINK']
            
            if post_data['reset']: # Due to inconsistency of making an account
                reset_link = analytics_new_account_link + "/password/reset/" + re.findall("([^\/]+$)", post_data['reset_link'])[0]
            else:
                reset_link = analytics_new_account_link + "/account/setup/" + re.findall("([^\/]+$)", post_data['reset_link'])[0]
            # Post message via Sendgrid and send slack user a verification response.
            SENDGRID_API_KEY = os.environ['SENDGRID_API_KEY']
            from_email = os.environ['SENDGRID_EMAIL']
            with open('welcome_email.html', 'r') as f:
                contents = f.read()
                html_welcome_email = BeautifulSoup(contents, 'html.parser')

            html_welcome_email.find(class_='lkrButton')['href'] = reset_link # This is where we add in password reset code
            message = Mail(
                from_email=from_email,
                to_emails= email,
                subject='Welcome to WELL Analytics Plus',
                html_content=str(html_welcome_email))
            try:
                sg = SendGridAPIClient(SENDGRID_API_KEY)
                sg.send(message) # Sending email with login link
                
                # Message looker user that email was successful
                looker_client.chat_postMessage(
                    channel=post_data['slack_id'],
                    text= "User -- {email} -- was added to Looker. An email from {from_email} has been sent to them.".format(email=email, from_email=from_email)
                )
            except Exception as e:
                print(e.message)
                # Should have a logging component here instead of these print statements
                looker_client.chat_postMessage(
                    channel=post_data['slack_id'],
                    text= "User -- {email} -- was added not sent an email due to a SendGrid error. Please send them an email with their login link: {reset_link}".format(email=email, reset_link=reset_link)
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
                channel= 'C02TH2Y07RA',
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
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Delete Message"
                                },
                                "value": "delete",
                                "action_id": "action-delete"
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