import simplejson
import telegram
import logging
from expense import *
from file_handler import *
from telegram import MessageEntity, User
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, Filters
from decimal import Decimal
from re import sub

NAME, VALUE, REASON, SHARE = range(4)

user_dict = {}
chat_dict = {}
relative_finance_dict = {}
current_expense_dict = {}

command_keyboard = [["/expense", "/status"]]

def main ():
    bot = init_bot(read_token("secret_token"))

    updater = Updater(token=read_token("secret_token"), use_context=True)
    dispatcher = updater.dispatcher

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

    # Add handler for /start command
    start_handler = CommandHandler("start", start)
    dispatcher.add_handler(start_handler)

    # Add handler for /status command
    status_handler = CommandHandler("status", status)
    dispatcher.add_handler(status_handler)

    # Add handler for /expense command
    expense_handler = ConversationHandler(
            entry_points=[CommandHandler('expense', expense)],
            states={
                NAME: [MessageHandler(Filters.text & Filters.entity(MessageEntity.MENTION),
                    received_name,
                    pass_user_data=True),
                    ],
                VALUE: [MessageHandler(Filters.text,
                    received_value,
                    pass_user_data=True),
                    ],
                REASON: [MessageHandler(Filters.text,
                    received_reason,
                    pass_user_data=True),
                    ],
                SHARE: [MessageHandler(Filters.text,
                    received_share,
                    pass_user_data=True),
                    ],
                },
            fallbacks=[CommandHandler("cancel", cancel)]
            )
    dispatcher.add_handler(expense_handler)

    global user_dict
    global chat_dict
    global relative_finance_dict

    user_dict = load_dict("storage/user_dict.json")
    chat_dict = load_dict("storage/chat_dict.json")
    relative_finance_dict = load_dict("storage/relative_finance_dict.json")

    # Add handler for plaintext
    # failure_handler = MessageHandler(Filters.text, failure)
    # dispatcher.add_handler(failure_handler)

    # Start the bot
    updater.start_polling()

def init_bot (secret_token):
    bot = telegram.Bot(token=secret_token)
    return bot

def start (update, context):
    user_dict["@" + update.message.from_user.username] = {"id": update.message.from_user.id,
            "username": update.message.from_user.username,
            "full_name": update.message.from_user.full_name}
    chat_dict["@" + update.message.from_user.username] = update.message.chat_id

    write_dict(user_dict, "storage/user_dict.json")
    write_dict(chat_dict, "storage/chat_dict.json")

    # initialize finance dict for new users
    if not ("@" + update.message.from_user.username) in relative_finance_dict:
        relative_finance_dict["@" + update.message.from_user.username] = {}

    context.bot.send_message(chat_id=update.message.chat_id,
            text="Bleep blop, I'm a bot.",
            reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

def status (update, context):
    output_lines = 0

    # search for me -> other
    userA = user_dict["@" + update.message.from_user.username]
    for userB in [user_dict[u] for u in relative_finance_dict["@" + update.message.from_user.username]]:
        difference = relative_finance_dict["@" + userA["username"]]["@" + userB["username"]]
        if difference > 0:
            context.bot.send_message(chat_id=update.message.chat_id,
                    text="You owe " + userB["full_name"] + " (@" + userB["username"] + ") " + str(difference) + " units.",
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
            output_lines += 1
        elif difference < 0:
            context.bot.send_message(chat_id=chat_dict["@" + userB["username"]],
                    text=userB["full_name"] + " (@" + userB["username"] + ") owes you " + str(-difference) + " units.",
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

            output_lines += 1

    # search for other -> me
    for userA in [user_dict[u] for u in relative_finance_dict]:
        if userA != user_dict["@" + update.message.from_user.username]:
            userB = user_dict["@" + update.message.from_user.username]

            if "@" + userB["username"] in relative_finance_dict["@" + userA["username"]]:
                difference = relative_finance_dict["@" + userA["username"]]["@" + userB["username"]]
                if difference > 0:
                    context.bot.send_message(chat_id=chat_dict["@" + userB["username"]],
                            text=userA["full_name"] + " (@" + userA["username"] + ") owes you " + str(difference) + " units.",
                            reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
                    output_lines += 1
                elif difference < 0:
                    context.bot.send_message(chat_id=update.message.chat_id,
                            text="You owe " + userA["full_name"] + " (@" + userA["username"] + ") " + str(-difference) + " units.",
                            reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
                    output_lines += 1

    # everything is balanced
    if output_lines == 0:
        context.bot.send_message(chat_id=update.message.chat_id,
                text="There are no financial differences with anybody.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))


def expense (update, context):
    current_expense_dict[update.message.from_user.id] = Expense()
    current_expense_dict[update.message.from_user.id].userA = {"id": update.message.from_user.id,
            "username": update.message.from_user.username,
            "full_name": update.message.from_user.full_name}
    context.bot.send_message(chat_id=update.message.chat_id,
            text="Who do you share the expense with?",
            reply_markup=telegram.ReplyKeyboardRemove())
    return NAME

def received_name (update, context):
    entities = update.message.entities

    if (len(entities) == 0):
        context.bot.send_message(chat_id=update.message.chat_id,
                text="You have to send me a username. Cancelling.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        return ConversationHandler.END
    elif (entities[0].type != "mention"):
        context.bot.send_message(chat_id=update.message.chat_id,
                text="You have to send me a username. Cancelling.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        return ConversationHandler.END
    else:
        username_string = update.message.parse_entity(entities[0])
        if not username_string in user_dict:
            current_expense_dict[update.message.from_user] = None
            context.bot.send_message(chat_id=update.message.chat_id,
                    text="This user is not yet registered. Cancelling.",
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
            return ConversationHandler.END
        else:
            expense_partner = user_dict[username_string]
            current_expense_dict[update.message.from_user.id].userB = expense_partner
            context.bot.send_message(chat_id=update.message.chat_id,
                    text="Sharing an expense with " + expense_partner["full_name"] + ". How much did you spend? (use xxx.xx for decimal values)",
                    reply_markup=telegram.ReplyKeyboardRemove())
            return VALUE

def received_value (update, context):
    value_input = update.message.text
    value_decimal = Decimal(sub(r'[^\d\-.]', '', value_input))
    current_expense_dict[update.message.from_user.id].value = value_decimal
    context.bot.send_message(chat_id=update.message.chat_id,
            text="Please tell "
                + current_expense_dict[update.message.from_user.id].userB["full_name"]
                + " a reason for this expense.",
            reply_markup=telegram.ReplyKeyboardRemove())
    return REASON

def received_reason (update, context):
    reason_input = update.message.text
    current_expense_dict[update.message.from_user.id].reason = reason_input
    custom_keyboard = [["100%", "50%", "Cancel"]]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    context.bot.send_message(chat_id=update.message.chat_id,
            text="Adding an expense with value "
                + str(current_expense_dict[update.message.from_user.id].value)
                + ". How much does "
                + current_expense_dict[update.message.from_user.id].userB["full_name"]
                + " have to pay?",
            reply_markup=reply_markup)
    return SHARE

def received_share (update, context):
    share = update.message.text
    current_expense = current_expense_dict[update.message.from_user.id]
        
    userA = current_expense.userA
    userB = current_expense.userB
    reason = current_expense.reason
    value = current_expense.value

    if share == "100%":
        context.bot.send_message(chat_id=update.message.chat_id,
                text=userB["full_name"] + " pays everything.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=chat_dict["@" + userB["username"]],
                text=userA["full_name"] + " has added an expense of " + str(value) + " units for the following reason:\n\n" + reason,
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    elif share == "50%":
        value = value / 2
        context.bot.send_message(chat_id=update.message.chat_id,
                text="You share your expense equally with " + userB["full_name"] + ".",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=chat_dict["@" + userB["username"]],
                text=userA["full_name"] + " has added an expense of " + str(value) + " units for the following reason:\n\n" + reason,
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    else:
        context.bot.send_message(chat_id=update.message.chat_id,
                text="I'll simply forget about it.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        return ConversationHandler.END

    # relative finance is always in lesicographical order
    if userA["username"] < userB["username"]:
        if not ("@" + userB["username"]) in relative_finance_dict["@" + userA["username"]]:
            relative_finance_dict["@" + userA["username"]]["@" + userB["username"]] = -value
        else:
            old_value = Decimal(relative_finance_dict["@" + userA["username"]]["@" + userB["username"]])
            relative_finance_dict["@" + userA["username"]]["@" + userB["username"]] = old_value - value
        difference = relative_finance_dict["@" + userA["username"]]["@" + userB["username"]]
    else:
        if not ("@" + userA["username"]) in relative_finance_dict["@" + userB["username"]]:
            relative_finance_dict["@" + userB["username"]]["@" + userA["username"]] = value
        else:
            old_value = Decimal(relative_finance_dict["@" + userB["username"]]["@" + userA["username"]])
            relative_finance_dict["@" + userB["username"]]["@" + userA["username"]] = old_value + value
        difference = -relative_finance_dict["@" + userB["username"]]["@" + userA["username"]]

    write_dict(relative_finance_dict, "storage/relative_finance_dict.json")

    # A owes B and you are A
    if ((difference > 0) and (update.message.from_user.id != userB)):
        context.bot.send_message(chat_id=update.message.chat_id,
                text="You owe " + userB["full_name"] + " " + str(difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=chat_dict["@" + userB["username"]],
                text=userA["full_name"] + " owes you " + str(difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    # A owes B and you are B
    elif ((difference > 0) and (update.message.from_user.id == userB)):
        context.bot.send_message(chat_id=update.message.chat_id,
                text=userB["full_name"] + " owes you " + str(difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=chat_dict["@" + userB["username"]],
                text="You owe " + userA["full_name"] + " " + str(difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    # B owes A and you are A
    elif ((difference < 0) and (update.message.from_user.id != userB)):
        context.bot.send_message(chat_id=update.message.chat_id,
                text=userB["full_name"] + " owes you " + str(-difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=chat_dict["@" + userB["username"]],
                text="You owe " + userA["full_name"] + " " + str(-difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    # B owes A and you are B
    elif ((difference < 0) and (update.message.from_user.id == userB)):
        context.bot.send_message(chat_id=update.message.chat_id,
                text="You owe " + userB["full_name"] + " " + str(-difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=chat_dict["@" + userB["username"]],
                text=userA["full_name"] + " owes you " + str(-difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    # A and B are balanced
    else:
        context.bot.send_message(chat_id=update.message.chat_id,
                text="You and " + userB["full_name"] + " are now balanced.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=chat_dict["@" + userB["username"]],
                text="You and " + userA["full_name"] + " are now balanced.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

    current_expense_dict[update.message.from_user.id] = None
    return ConversationHandler.END

def cancel (update, context):
    context.bot.send_message(chat_id=update.message.chat_id,
            text="I'll simply forget about it.",
            reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

def failure (update, context):
    context.bot.send_message(chat_id=update.message.chat_id,
            text="I don't understand human language.\n<i>(at least I pretend...)</i>",
            parse_mode=telegram.ParseMode.HTML,
            reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

if __name__ == '__main__':
    main()
