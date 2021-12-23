from flask import abort, request, make_response, Blueprint
import os, json
from slack_sdk import WebClient

support_client = WebClient(token=os.environ["SUPPORT_BOT_TOKEN"])

support_bot_flow = Blueprint('support_bot_flow', __name__)

# Import Googlesheets API
from googleauthentication import googlesheets_append, googlesheets_read

# Definitions
def is_request_valid(request):
    is_token_valid = request['token'] == os.environ['SLACK_VERIFICATION_TOKEN_SUPPORT']
    is_team_id_valid = request['team_id'] == os.environ['SLACK_TEAM_ID']

    return is_token_valid and is_team_id_valid

googlesheets_id = os.environ['GOOGLESHEETS_ID']

def step_1_import(event_ts, response_metadata):
    #googlesheets_append(googlesheets_id, 'database!A2:G', [event_ts, 1, None, response_metadata["messages"][0]["text"], None, None])
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
                    "text": "Hey There! Have you checked: \n - The <https://support.wellapp.com/|Support Website>\n - In our <https://wellapp.atlassian.net/wiki/spaces/ProductDocs/pages|Confluence Product Page>\n - In the Slack Search Bar?"
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
                            "text": "Yup, no luck"
                        },
                        "value": "step_2_no_answer",
                        "action_id": "not-found-answer"
                    }
                ]
            }
        ]
    )

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
            event_ts = event["ts"]
        except KeyError:
            event_ts_2 = event["thread_ts"]
        event_channel=event["channel"]
        event_message = event["text"]

        # Need to read googlesheet everytime for step
        goo_table = googlesheets_read(googlesheets_id, 'database!A1:G')
        # Pain - the above will not scale well as it's not a true database

    # -------------------------------------- #

        if event_type == "app_mention":
            response_metadata = support_client.conversations_replies(
                channel=event_channel,
                inclusive=True,
                ts = event_ts,
                oldest=0,
                limit=1
            )
            print("Bot Mentioned!")
            step_1_import(event_ts,response_metadata)
            step_1_response(event_channel, event_ts)

            return make_response("Answer Sent", 200, {"X-Slack-No-Retry": 1})
        

    return make_response("Unhandled event", 404, {"X-Slack-No-Retry": 1})

@support_bot_flow.route('/support/interactive', methods = ["POST"])
def interactive():
    payload = json.loads(request.form['payload'])

    if payload['type'] == 'block_actions' and payload['actions'][0]['action_id'] == 'found-answer':
        button = "Found an Answer"
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
                            "text": "Hey there! Have you checked: \n - The <https://support.wellapp.com/|Support Website>\n - In our <https://wellapp.atlassian.net/wiki/spaces/ProductDocs/pages|Confluence Product Page>\n - In the Slack Search Bar?"
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

        return make_response("Answer submitted by user", 200, {"X-Slack-No-Retry": 1})
        
    elif payload['type'] == 'block_actions' and payload['actions'][0]['action_id'] == 'not-found-answer':
        button = "Did Not Find an Answer"

        message_block = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "Darn! Let's see what we can do. Which feature is this a part of? Please start typing in the product feature."
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

        google_product_names = googlesheets_read(googlesheets_id,'product_owners!A2:A')
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
                            "text": "Hey There! Have you checked: \n - The <https://support.wellapp.com/|Support Website>\n - In our <https://wellapp.atlassian.net/wiki/spaces/ProductDocs/pages|Confluence Product Page>\n - In the Slack Search Bar?"
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
            channel = payload['channel']['id'],
            thread_ts = payload['container']['thread_ts'],
            text= "What product feature is this problem pertaining to?",
            blocks = message_block
        )
        return make_response("Answer Not Found, Continuing..", 200, {"X-Slack-No-Retry": 1})

    elif payload['type'] == 'block_actions' and payload['actions'][0]['action_id'] == 'feature_classification':
        product_feature = payload['actions'][0]['selected_option']['text']['text']
        user_id = payload['user']['id']
        g_read_po = googlesheets_read(googlesheets_id,'product_owners!A2:B')
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

        product_owner_id = ids[names.index(po_names[features.index('WELL Core Analytics')])]

        support_client.chat_update(
            channel=payload['channel']['id'],
            ts=payload['container']['message_ts'],
            blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "Darn! Let's see what we can do. Which feature is this a part of? Please start typing in the product feature."
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
                text = "Pinging the {product_owner} for this feature. Do you have an answer to this?".format(product_owner=product_owner_id),
                #Need to add in <@ > when truly done.
                blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "Pinging the {product_owner} for this feature. Do you have an answer to this?".format(product_owner=product_owner_id)
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
            support_client.chat_postMessage(
                channel=payload['channel']['id'],
                thread_ts = payload['container']['thread_ts'],
                text = "No product owner was found for this feature.".format(product_owner=product_owner_id)
            )
        return make_response("Pinged Owner", 200, {"X-Slack-No-Retry": 1})

    elif payload['type'] == 'block_actions' and payload['actions'][0]['action_id'] == 'actionID-found-answer-2':
        #Update googlesheet here
        user_id = payload['user']['id']
        message_payload = payload['state']['values']['question_answer']['plain_text_input-action']['value']
        support_client.chat_update(
            channel=payload['channel']['id'],
            ts=payload['container']['message_ts'],
            text= "Pinging the {user} for this feature. Do you have an answer to this?".format(user=user_id),
            blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": "Pinging the {user} for this feature. Do you have an answer to this?".format(user=user_id)
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
