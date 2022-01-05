import json
import os
import requests
import threading

from flask import Flask
from flask import request
from slack import WebClient

CHECK_INTERVAL = 10.0

# SLACK_TOKEN = os.getenv('SLACK_TOKEN')
SLACK_TOKEN = 'xoxb-842063672404-2923114979617-QJt0Ta57JlPmTxjuLP1iESW8'

if SLACK_TOKEN is None:
    print('SLACK_TOKEN is not defined in environment variables')
    exit(1)

SLACK_CLIENT = WebClient(SLACK_TOKEN)

URL_SEARCH = 'https://restaurant-api.wolt.com/v1/search?sort=releveancy&lat=32.06694006621747&lon=34.784552827477455&q=%s'
URL_REST_INFO = 'https://restaurant-api.wolt.com/v3/venues/slug/%s'

# SCHEDULED_CHECKS = {"U01NMJ7JTV4":"benz-brothers-ibn-gabirol"}
SCHEDULED_CHECKS={}

app = Flask(__name__)


def send_message(user_id, text):
    SLACK_CLIENT.chat_postMessage(
        channel=user_id,
        text=text,
        response_type="in_channel"
    )


def check():
    print("checking")
    if SCHEDULED_CHECKS:
        print(f'Processing {str(len(SCHEDULED_CHECKS))} jobs...', flush=True)

        users_to_delete = []

        for user_id in SCHEDULED_CHECKS:
            try:
                response = requests.get(URL_REST_INFO % SCHEDULED_CHECKS[user_id])

                # response.raise_for_status()

                result = response.json()['results'][0]

                # Prefer Hebrew name
                try:
                    rest_name = list(filter(lambda x: x["lang"] == "he", result["name"]))[
                        0]["value"]
                except:
                    rest_name = list(filter(lambda x: x["lang"] == "en", result["name"]))[
                        0]["value"]
                    print("errrorrr")

                is_online = result['online']

                if is_online:
                    order_url = result['public_url']

                    send_message(
                        user_id,
                        f'Yay! :sunglasses: *{rest_name}* is available for orders <{order_url}|here>.'
                    )

                    users_to_delete.append(user_id)
            except Exception as e:
                print(f'Unable to process job (User ID: {user_id}, Slug: {SCHEDULED_CHECKS[user_id]}: {str(e)}',
                      flush=True)

                send_message(
                    user_id,
                    'Woops, something went wrong on our side! :scream_cat: Please reschedule your notification.'
                )

                users_to_delete.append(user_id)

        for user_id in users_to_delete:
            del SCHEDULED_CHECKS[user_id]

        print(f'Done ({str(len(users_to_delete))})', flush=True)

    else:
        print("SCHEDULED_CHECKS:",SCHEDULED_CHECKS)
    t = threading.Timer(CHECK_INTERVAL, check)
    t.daemon = True
    t.start()


def find_restaurant(query):
    response = requests.get(URL_SEARCH % query)

    response.raise_for_status()

    results = response.json()['results']

    ret = []

    for result in results[:10]:
        # Prefer Hebrew name
        try:
            rest_name = list(filter(lambda x: x["lang"] == "he", result["value"]["name"]))[
                0]["value"]
        except:
            rest_name = list(filter(lambda x: x["lang"] == "en", result["value"]["name"]))[
                0]["value"]

        slug = result['value']['slug']

        ret.append((rest_name, slug))

    return ret



@app.route('/scheduled',methods=['GET'])
def getter_test():
    return SCHEDULED_CHECKS

@app.route('/testing', methods=['POST'])
def what():
    user_id = request.form['user_id']
    command = request.form['command']
    text = request.form['text']
    channel_id = request.form['channel_id']
    response = requests.get(URL_SEARCH % text)

    response.raise_for_status()
    return request

@app.route('/', methods=['POST'])
def regular_callback():
    user_id = request.form['user_id']
    command = request.form['command']
    text = request.form['text']
    channel_id = request.form['channel_id']

    if command == '/wolt':
        if text == 'cancel':
            if user_id in SCHEDULED_CHECKS:
                del SCHEDULED_CHECKS[user_id]

            return 'I removed your scheduled notification! :smile: Type `/wolt [restaurant_name]` to start again!'

        if user_id in SCHEDULED_CHECKS:
            return 'It seems there is already a scheduled notification set for you :cry:. Type `/wolt cancel` to cancel it!'

        try:
            results = find_restaurant(text)
        except:
            return "Oops, something went wrong! :cry: Please try again."

        if not results:
            return "I didn't find any results matching this restaurant name :cry:. Try to be more specific! '" + text + "'"

        attachments = [
            {
                "fallback": "If you could read this message, you'd be choosing something fun to do right now.",
                "color": "#3AA3E3",
                "attachment_type": "default",
                "callback_id": "game_selection",
                "actions": [
                    {
                        "name": "rest_list",
                        "text": "Pick a restaurant...",
                        "type": "select",
                        "options": [

                        ]
                    }
                ]
            }
        ]

        for result in results:
            attachments[0]['actions'][0]['options'].append(
                {
                    "text": result[0],
                    "value": f'{result[0]};{result[1]}'
                },
            )

        return {
            'text': "Choose a restaurant from the list and I will notify you when it's available for orders!",
            'attachments': attachments
        }


@app.route("/interactive_callback", methods=["POST"])
def interactive_callback():
    payload = json.loads(request.form['payload'])
    user_id = payload['user']['id']
    user_name = payload['user']['name']
    pair = payload['actions'][0]['selected_options'][0]['value'].split(';')
    rest_name = pair[0]
    slug = pair[1]

    SCHEDULED_CHECKS[user_id] = slug

    print(f"Scheduled new notification for user '{user_name} for restaurant {rest_name} ({slug})", flush=True)

    return f'Awesome! I will notify you as soon as {rest_name} is available for orders! :smile:'

check()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)