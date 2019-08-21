from json import JSONEncoder, JSONDecoder
import json

class User:
    tag = None
    full_name = None
    chat_id = None

class UserEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__

class UserDecoder(JSONDecoder):
    def from_json(json_object):
        input_user = Expense();
        if "tag" in json_object:
            input_user.tag = json_object["tag"]
        if "full_name" in json_object:
            input_user.full_name = json_object["full_name"]
        if "chat_id" in json_object:
            input_user.chat_id = json_object["chat_id"]
