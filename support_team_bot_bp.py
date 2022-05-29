from flask import abort, request, make_response, Blueprint
import os, json, re
from slack_sdk import WebClient

support_client = WebClient(token=os.environ["SUPPORT_BOT_TOKEN"])

support_bot_flow = Blueprint('support_bot_flow', __name__)

# Import Googlesheets API
from googleauthentication import googlesheets_append, googlesheets_massupdate, googlesheets_read, googlesheets_clear, googlesheets_write

# Definitions
def is_request_valid(request):
    is_token_valid = request['token'] == os.environ['SLACK_VERIFICATION_TOKEN_SUPPORT']
    is_team_id_valid = request['team_id'] == os.environ['SLACK_TEAM_ID']

    return is_token_valid and is_team_id_valid

googlesheets_id = os.environ['SUPPORT_GOOGLESHEETS_ID']

def step_1_import(event_ts, response_metadata, channel):
    # Added ability to have hyperlink to slack message, so when someone looks at the database, they can click on the question to shoot them to the question asked.
    user_question = re.sub(r'\<[^)]*\>', '', response_metadata["messages"][0]["text"]).lstrip()
    user_question = user_question.replace('\"', '\'')
    url = 'https://wellhealth.slack.com/archives/'+ channel + "/p" + response_metadata["messages"][0]["ts"].replace(".","")
    user_question_link = '=HYPERLINK("{slack_link}", "{user_question}")'.format(slack_link = url, user_question = user_question)

    response_user = response_metadata['messages'][0]['user']
    googlesheets_append(googlesheets_id, 'database!A2:H', [int(float(event_ts)), channel, response_user, user_question_link, None, None, None])
    pass
    #Need to have a comprehensive way to input into database
def step_1_response(event_channel, event_ts):
    support_client.chat_postMessage(
        channel=event_channel,
        thread_ts = event_ts,
        text = "Hey There! Have you checked these resources?",
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Hey There! Have you checked: \n - The <https://knowledge.wellapp.com|KB Website>\n - In our <https://wellapp.atlassian.net/wiki/spaces/ProductDocs/pages|Confluence Product Page>\n - Our <https://docs.google.com/spreadsheets/d/1y100p75PowMlya0CrRd9_iVy7PId7FCqkyslMjljMII/edit?usp=sharing|Database of Questions>\n - In the Slack Search Bar?"
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "I found an answer!"
                    },
                    "value": "step_2_answer",
                    "action_id": "found-answer"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "No Answer Found"
                        },
                        "value": "step_2_no_answer",
                        "action_id": "not-found-answer"
                    }
                ]
            }
        ]
    )

def flatten_list(_2d_list):
    flat_list = []
    # Iterate through the outer list
    for element in _2d_list:
        if type(element) is list:
            # If the element is of type list, iterate through the sublist
            for item in element:
                flat_list.append(item)
        else:
            flat_list.append(element)
    return flat_list

# Slack Setup
#Event Handler

@support_bot_flow.route('/support/slack_events', methods = ["POST"])
def slack_events():
    # Grab slack information
    slack_event = json.loads(request.data)

    if "challenge" in slack_event:
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
        try:
            event_ts = event["thread_ts"]
        except KeyError:
            event_ts = event["ts"]
        event_channel=event["channel"]

        # Need to read googlesheet everytime for step
        goo_table = googlesheets_read(googlesheets_id, 'database!A1:G')
        # Pain - the above will not scale well as it's not a true database

    # -------------------------------------- #

        if event_type == "app_mention" :
            response_metadata = support_client.conversations_replies(
                channel=event_channel,
                inclusive=True,
                ts = event_ts,
                oldest=0,
                limit=1
            )
            print("Bot Mentioned!")
            step_1_import(event_ts,response_metadata, event_channel)
            step_1_response(event_channel, event_ts)

            return make_response("Answer Sent", 200, {"X-Slack-No-Retry": 1})
        

    return make_response("Unhandled event", 404, {"X-Slack-No-Retry": 1})

@support_bot_flow.route('/support/interactive', methods = ["POST"])
def interactive():
    payload = json.loads(request.form['payload'])
    if payload['type'] == 'block_actions' and payload['actions'][0]['action_id'] == 'found-answer':
        button = "Found an Answer"
        origin_ts = int(float(payload['container']['thread_ts']))
        conversationIDs = flatten_list(googlesheets_read(googlesheets_id, 'database!A2:A'))
        location_id = conversationIDs.index(str(origin_ts))
        googlesheets_clear(googlesheets_id,'database!E{location}'.format(location=location_id+2))
        googlesheets_write(googlesheets_id,'database!E{location}'.format(location=location_id+2), 'yes')
        support_client.chat_update(
            channel=payload['channel']['id'],
            ts=payload['container']['message_ts'],
            text = "Hey there! Have you checked these resources?",
            blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Hey there! Have you checked: \n - The <https://knowledge.wellapp.com|KB Website>\n - In our <https://wellapp.atlassian.net/wiki/spaces/ProductDocs/pages|Confluence Product Page>\n - In the Slack Search Bar?"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "<@{user}> has selected _{button}_.".format(user=payload['user']['id'], button=button)
                        }
                    ]
                }
            ]
        )
        support_client.chat_postMessage(
            channel=payload['channel']['id'],
            thread_ts = payload['container']['thread_ts'],
            text= "Great! Glad there was an answer. Can you fill out the answer that you found here for others?",
            blocks= [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "Great! Glad there was an answer. Can you fill out the answer that you found here for others?"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "input",
                    "block_id": "question_answer",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "plain_text_input-action"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Answer"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Submit"
                            },
                            "value": "submit-answer-1",
                            "action_id": "actionID-found-answer"
                        }
                    ]
                }
            ]
        )

        return make_response("Answer Found", 200, {"X-Slack-No-Retry": 1})

    elif payload['type'] == 'block_actions' and payload['actions'][0]['action_id'] == 'actionID-found-answer':
        message_payload = payload['state']['values']['question_answer']['plain_text_input-action']['value']
        # Splicing message_payload for urls with a trailing _ (this messes up the url)
        try:
            url = re.search("(?P<url>https?://[^\s]+)", message_payload).group("url").rstrip('_')
            message_payload = re.sub("(?P<url>https?://[^\s]+)", url, message_payload) # fix url
            message_payload = message_payload.replace('\"', '\'')
        except:
            message_payload.replace('\"', '\'')

        user_id = payload['user']['id']
        support_client.chat_update(
            channel=payload['channel']['id'],
            ts=payload['container']['message_ts'],
            text= "Great! Glad there was an answer. Can you fill out the answer that you found here for others?",
            blocks= [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "Great! Glad there was an answer. Can you fill out the answer that you found here for others?"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Answer: _{text}_ \n From: _<@{user}>_".format(text=message_payload, user=user_id)
                        }
                    ]
                },
                
            ]
        )

        conversationIDs = flatten_list(googlesheets_read(googlesheets_id, 'database!A2:A'))
        location_id = conversationIDs.index(str(int(float(payload['container']['thread_ts']))))
        googlesheets_clear(googlesheets_id,'database!F{location}:H{location}'.format(location=location_id+2))
        googlesheets_massupdate(googlesheets_id, 'database!F{location}:H{location}'.format(location=location_id+2), ('N/A','N/A',message_payload))

        return make_response("Answer submitted by user", 200, {"X-Slack-No-Retry": 1})
        
    elif payload['type'] == 'block_actions' and payload['actions'][0]['action_id'] == 'not-found-answer':
        button = "Did Not Find an Answer"

        message_block = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "Let's see what we can do. Which feature is this a part of? Please start typing in the product feature."
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select an item"
                        },
                        "options": [],
                        "action_id": "feature_classification"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Product Feature"
                    }
                }
            ]
        # Sorting which channel it is in
        if payload['channel']['id'] == 'C017LNYUTGW': # Support Analytics Questions
            sheetname = 'data_owners'
        else:
            sheetname = 'product_owners'
        google_product_names = googlesheets_read(googlesheets_id,'{sheet}!A2:A'.format(sheet = sheetname))
        product_names = [item for sublist in google_product_names for item in sublist]
        for name in product_names:
            message_template = {
                                "text": {
                                    "type": "plain_text",
                                    "text": "*this is plain_text text*"
                                },
                                "value": "value-0"
                            }
            message_template['text']['text'] = name
            message_template['value'] = name.replace(' ', '_')
            message_block[2]['element']['options'].append(message_template)
    
        support_client.chat_update(
            channel=payload['channel']['id'],
            ts=payload['container']['message_ts'],
            blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Hey There! Have you checked: \n - The <https://knowledge.wellapp.com|KB Website>\n - In our <https://wellapp.atlassian.net/wiki/spaces/ProductDocs/pages|Confluence Product Page>\n - Our <https://docs.google.com/spreadsheets/d/1y100p75PowMlya0CrRd9_iVy7PId7FCqkyslMjljMII/edit?usp=sharing|Database of Questions>\n - In the Slack Search Bar?"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "<@{user}> has selected _{button}_.".format(user=payload['user']['id'], button=button)
                        }
                    ]
                }
            ]
        )

        conversationIDs = flatten_list(googlesheets_read(googlesheets_id, 'database!A2:A'))
        location_id = conversationIDs.index(str(int(float(payload['container']['thread_ts']))))
        googlesheets_clear(googlesheets_id,'database!E{location}'.format(location=location_id+2))
        googlesheets_write(googlesheets_id, 'database!E{location}'.format(location=location_id+2), "no")

        support_client.chat_postMessage(
            channel = payload['channel']['id'],
            thread_ts = payload['container']['thread_ts'],
            text= "What product feature is this problem pertaining to?",
            blocks = message_block
        )
        return make_response("Answer Not Found, Continuing..", 200, {"X-Slack-No-Retry": 1})

    elif payload['type'] == 'block_actions' and payload['actions'][0]['action_id'] == 'feature_classification':
        product_feature = payload['actions'][0]['selected_option']['text']['text']
        user_id = payload['user']['id']

        # Sorting which channel it is in
        if payload['channel']['id'] == 'C017LNYUTGW': # Support Analytics Questions
            sheetname = 'data_owners'
        else:
            sheetname = 'product_owners'
        g_read_po = googlesheets_read(googlesheets_id,'{sheet}!A2:B'.format(sheet=sheetname))
        g_read_si = googlesheets_read(googlesheets_id,'slack_ids!A2:B')
        features = []
        po_names = []
        for row in g_read_po:
            features.append(row[0])
            try:
                po_names.append(row[1])
            except:
                po_names.append(None)

        names = []
        ids = []
        for row in g_read_si:
            names.append(row[0])
            ids.append(row[1])

        product_owner_id = ids[names.index(po_names[features.index(product_feature)])]

        po_name = po_names[features.index(product_feature)]
        conversationIDs = flatten_list(googlesheets_read(googlesheets_id, 'database!A2:A'))
        location_id = conversationIDs.index(str(int(float(payload['container']['thread_ts']))))
        googlesheets_clear(googlesheets_id,'database!F{location}:G{location}'.format(location=location_id+2))
        googlesheets_massupdate(googlesheets_id, 'database!F{location}:G{location}'.format(location=location_id+2), (product_feature, po_name))

        support_client.chat_update(
            channel=payload['channel']['id'],
            ts=payload['container']['message_ts'],
            blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "Let's see what we can do. Which feature is this a part of? Please start typing in the product feature."
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "<@{user}> has selected {product_feature}.".format(user=user_id, product_feature=product_feature)
                        }
                    ]
                }
            ]
        )
        if product_owner_id != 'None':
            support_client.chat_postMessage(
                channel=payload['channel']['id'],
                thread_ts = payload['container']['thread_ts'],
                text = "Pinging <@{product_owner}> for this feature. Do you have an answer to this?".format(product_owner=product_owner_id),
                #Need to add in <@ > when truly done.
                blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Pinging <@{product_owner}> for this feature. Do you have an answer to this?".format(product_owner=product_owner_id)
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "input",
                    "block_id": "question_answer",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "plain_text_input-action"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Answer"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Submit"
                            },
                            "value": "submit-answer-2",
                            "action_id": "actionID-found-answer-2"
                        }
                    ]
                }
            ]
            )
        else:
            conversationIDs = flatten_list(googlesheets_read(googlesheets_id, 'database!A2:A'))
            location_id = conversationIDs.index(str(int(float(payload['container']['thread_ts']))))
            googlesheets_clear(googlesheets_id,'F{location}:G{location}'.format(location=location_id+2))
            support_client.chat_postMessage(
                channel=payload['channel']['id'],
                thread_ts = payload['container']['thread_ts'],
                text = "No product owner was found for this feature. If anyone has an answer please answer below!",
                blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "No product owner was found for this feature. If anyone has an answer please answer below!"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "input",
                    "block_id": "question_answer",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "plain_text_input-action"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Answer"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Submit"
                            },
                            "value": "submit-answer-2",
                            "action_id": "actionID-found-answer-2"
                        }
                    ]
                }
            ]
            )
        return make_response("Pinged Owner", 200, {"X-Slack-No-Retry": 1})

    elif payload['type'] == 'block_actions' and payload['actions'][0]['action_id'] == 'actionID-found-answer-2':
        user_id = payload['user']['id']
        message_payload = payload['state']['values']['question_answer']['plain_text_input-action']['value']
        # Splicing message_payload for urls with a trailing _ (this messes up the url)
        try:
            url = re.search("(?P<url>https?://[^\s]+)", message_payload).group("url").rstrip('_')
            message_payload = re.sub("(?P<url>https?://[^\s]+)", url, message_payload)
            message_payload = message_payload.replace('\"', '\'')
        except:
            message_payload.replace('\"', '\'')

        conversationIDs = flatten_list(googlesheets_read(googlesheets_id, 'database!A2:A'))
        location_id = conversationIDs.index(str(int(float(payload['container']['thread_ts']))))
        googlesheets_clear(googlesheets_id,'database!H{location}'.format(location=location_id+2))
        googlesheets_write(googlesheets_id,'database!H{location}'.format(location=location_id+2), message_payload)
        googlesheets_clear(googlesheets_id,'database!E{location}'.format(location=location_id+2))
        googlesheets_write(googlesheets_id,'database!E{location}'.format(location=location_id+2), 'yes')

        support_client.chat_update(
            channel=payload['channel']['id'],
            ts=payload['container']['message_ts'],
            text= "Pinging <@{user}> for this feature. Do you have an answer to this?".format(user=user_id),
            blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "<@{user}> had an answer, posted below".format(user=user_id)
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Answer: _{text}_ \n From: _<@{user}>_".format(text=message_payload, user=user_id)
                        }
                    ]
                }
            ]
        )

        return make_response("Sent message to Google Spreadsheet.", 200, {"X-Slack-No-Retry": 1})


    else:
        return make_response("Not an understandable command", 200, {"X-Slack-No-Retry": 1})
