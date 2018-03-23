import os
import time
import re
from slackclient import SlackClient
from mapbox import Geocoder, Static
import json


# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))

# instantiate Mapbox clients
geocoder = Geocoder()
static = Static()

# mapbot's user ID in Slack: value is assigned after the bot starts up
mapbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
command = "locate"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == mapbot_id:
                return message, event["channel"]
    return None, None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(command, channel):
    """
        Executes bot command if the command is known
    """
    # Default response is help text for the user
    default_response = "Not sure what you mean. Try *{}*.".format(command)

    # Finds and executes the given command, filling in response
    response = None

    if command.startswith("locate"):
        query_list = command.split(" ")
        query = " ".join(query_list[1:])
        response = get_coords(query)

    if command.startswith("map"):
        query_list = command.split(" ")
        query = " ".join(query_list[1:])
        response, attachment = get_static_map(query)

    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response,
        attachments=attachment
    )

def get_static_map(query):
    latlon = get_coords(query)
    if latlon:
        response = static.image('mapbox.satellite', lon=latlon[0], lat=latlon[1], z=12)
        if response.status_code:
            with open('/tmp/map.png', 'wb') as output:
                _ = output.write(response.content)
            return "Success!", get_attachments()
        else:
            return "Sorry, we're having trouble finding {query}".format(query=query)
    else:
        return "Sorry, we're having trouble finding {query}".format(query=query)

def get_attachments():
    image_url = "http://www.catster.com/wp-content/uploads/2017/08/A-fluffy-cat-looking-funny-surprised-or-concerned.jpg"
    return [{"title": "Cat", "image_url": image_url}]

def get_coords(query):
    response = geocoder.forward(query)
    if response.status_code:
        first = response.geojson()['features'][0]
        return first['geometry']['coordinates']
    else:
        return None

if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Mapbot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        mapbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")