import os, re
from flask import request, Blueprint, make_response
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

whoisthis_client = WebClient(token=os.environ["WIT_BOT_TOKEN"])
whoisthis_bot_flow = Blueprint('whoisthis_bot_flow', __name__)

from googleauthentication import googlesheets_read
wit_googlesheets_id = os.environ['WIT_GOOGLESHEETS_ID']

def is_request_valid(request):
    is_token_valid = request['token'] == os.environ['SLACK_VERIFICATION_TOKEN_WIT']
    is_team_id_valid = request['team_id'] == os.environ['SLACK_TEAM_ID']

    return is_token_valid and is_team_id_valid

@whoisthis_bot_flow.route('/internal/whoisthis', methods=['GET','POST'])
def whoisthis_bot():
    if not is_request_valid(request.form):
        return {"message": "Not Authorized"}, 401

    message = re.sub('[@]', '', request.form["text"])
    for user in whoisthis_client.users_list()['members']:
        if user['is_bot'] == True or user['deleted'] == True:
            pass
        if user['name'] == message:
            full_name = user['profile']['real_name']
            break
    
    try:
        google_info = googlesheets_read(wit_googlesheets_id, 'Employees!A2:D')
        for row in google_info:
            if row[0] == full_name:
                user_info = row
                break
        try:
            user_info
        except NameError:
            try: 
                whoisthis_client.chat_postEphemeral(
                    user= request.form["user_id"],
                    channel=request.form["channel_id"],
                    text = "Could not find user in Lattice, there may be a naming mismatch between Lattice and Slack. Sorry about that!"
                )
            except SlackApiError:
                whoisthis_client.chat_postMessage(
                    channel=request.form["user_id"],
                    text = "Could not find user in Lattice, there may be a naming mismatch between Lattice and Slack. Sorry about that!"
                )
            return make_response("", 200)
    except NameError:
            try:
                whoisthis_client.chat_postEphemeral(
                    user= request.form["user_id"],
                    channel=request.form["channel_id"],
                    text = "Could not find user in Slack, make sure you are just typing in the username with the @ symbol, and nothing else. Sorry about that!"
                )
            except SlackApiError:
                whoisthis_client.chat_postMessage(
                    channel=request.form["user_id"],
                    text = "Could not find user in Slack, make sure you are just typing in the username with the @ symbol, and nothing else. Sorry about that!"
                )
            return make_response("", 200)
    
    try:
        whoisthis_client.chat_postEphemeral(
            user= request.form["user_id"],
            channel=request.form["channel_id"],
            text = "{name} is a {position} \nDepartment: {department}\nStart Date: {start_date}".format(
                name = user_info[0],
                position = user_info[1],
                department = user_info[2],
                start_date = user_info[3]
            )
        )
    except SlackApiError:
        whoisthis_client.chat_postMessage(
            channel=request.form["user_id"],
            text = "{name} is a {position} \nDepartment: {department}\nStart Date: {start_date}".format(
                name = user_info[0],
                position = user_info[1],
                department = user_info[2],
                start_date = user_info[3]
            )
        )
    
    return make_response("", 200)