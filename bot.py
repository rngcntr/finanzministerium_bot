import simplejson
import telegram
import logging
from expense import *
from db_handler import *
from file_handler import *
from telegram import MessageEntity, User
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, Filters
from decimal import Decimal
from re import sub

NAME, VALUE, REASON, SHARE = range(4)

current_expense_dict = {}

start_keyboard = [["/start"]]
command_keyboard = [["/expense", "/status"]]

#
# main function
#
def main ():
    initialize_database()

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

    # Add handler for plaintext
    # failure_handler = MessageHandler(Filters.text, failure)
    # dispatcher.add_handler(failure_handler)

    # Start the bot
    updater.start_polling()

#
# start a bot with the given secret token
#
def init_bot (secret_token):
    bot = telegram.Bot(token=secret_token)
    return bot

#
# start the bot
#
def start (update, context):
    if not update.message.from_user.username:
        # the user does not have a user tag
        context.bot.send_message(chat_id=update.message.chat_id,
                text="You don't seem to have a user tag.\n"
                "Tags begin with an @ symbol and are needed in order to mention other users."
                " You can create your own tag inside the Telegram settings.\n"
                "Once you created a tag, come back and press /start",
                parse_mode=telegram.ParseMode.HTML,
                reply_markup=telegram.ReplyKeyboardMarkup(start_keyboard))
    else:
        add_user(update.message.from_user.username,
                update.message.from_user.full_name,
                update.message.from_user.id)

        # notify the user
        context.bot.send_message(chat_id=update.message.chat_id,
                text="Bleep blop, I'm a bot.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

def status (update, context):
    userA = get_user(update.message.from_user.username)
    relative_finance_list = get_status(userA.tag)

    # everything is balanced
    if len(relative_finance_list) == 0:
        context.bot.send_message(chat_id=update.message.chat_id,
                text="There are no financial differences with anybody.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

    for relative_finance in relative_finance_list:
        userB = get_user(relative_finance.userB)
        difference = relative_finance.value

        if difference > 0:
            context.bot.send_message(chat_id=userA.chat_id,
                    text="You owe " + userB.full_name + " (@" + userB.tag + ") " + str(difference) + " units.",
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        elif difference < 0:
            context.bot.send_message(chat_id=userA.chat_id,
                    text=userB.full_name + " (@" + userB.tag + ") owes you " + str(-difference) + " units.",
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

#
# start a new expense
#
def expense (update, context):
    userA = get_user(update.message.from_user.username)
    current_expense_dict[userA.tag] = Expense()
    current_expense_dict[userA.tag].userA = userA.tag

    context.bot.send_message(chat_id=userA.chat_id,
            text="Who do you share the expense with?",
            reply_markup=telegram.ReplyKeyboardRemove())
    return NAME

#
# received one (or multiple) users to share the expense with
#
def received_name (update, context):
    userA = get_user(update.message.from_user.username)
    entities = update.message.entities

    if (len(entities) == 0):
        # no mentions in message
        context.bot.send_message(chat_id=userA.chat_id,
                text="You have to send me a username. Cancelling.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        return ConversationHandler.END
    elif (entities[0].type != "mention"):
        # message element is not a mention
        context.bot.send_message(chat_id=userA.chat_id,
                text="You have to send me a username. Cancelling.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        return ConversationHandler.END
    else:
        # there is at least one mentioned user
        userB_string = update.message.parse_entity(entities[0]).replace("@", "")
        userB = get_user(userB_string)
        if not userB:
            # the mentioned user is not registered
            current_expense_dict[userA.tag] = None
            context.bot.send_message(chat_id=userA.chat_id,
                    text="This user is not yet registered. Cancelling.",
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
            return ConversationHandler.END
        else:
            # the mentioned user is registered
            current_expense_dict[userA.tag].userB = userB.tag
            context.bot.send_message(chat_id=userA.chat_id,
                    text="Sharing an expense with " + userB.full_name + ". How much did you spend? (use xxx.xx for decimal values)",
                    reply_markup=telegram.ReplyKeyboardRemove())
            return VALUE

#
# received the value of the current expense
#
def received_value (update, context):
    userA = get_user(update.message.from_user.username)
    current_expense = current_expense_dict[userA.tag]
    userB = get_user(current_expense.userB)

    value_input = update.message.text
    value_decimal = Decimal(sub(r'[^\d\-.]', '', value_input))
    current_expense.value = value_decimal
    context.bot.send_message(chat_id=userA.chat_id,
            text="Please tell "
                + userB.full_name
                + " a reason for this expense.",
            reply_markup=telegram.ReplyKeyboardRemove())

    return REASON

#
# received a reason for the current expense
#
def received_reason (update, context):
    userA = get_user(update.message.from_user.username)
    current_expense = current_expense_dict[userA.tag]
    userB = get_user(current_expense.userB)

    reason_input = update.message.text
    current_expense.reason = reason_input
    custom_keyboard = [["100%", "50%", "Cancel"]]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    context.bot.send_message(chat_id=userA.chat_id,
            text="Adding an expense with value "
                + str(current_expense.value)
                + ". How much does "
                + userB.full_name
                + " have to pay?",
            reply_markup=reply_markup)

    return SHARE

#
# received a share of the current expense for userB
#
def received_share (update, context):
    userA = get_user(update.message.from_user.username)
    current_expense = current_expense_dict[userA.tag]
    userB = get_user(current_expense.userB)
    reason = current_expense.reason
    value = current_expense.value

    share = update.message.text
        
    if share == "100%":
        context.bot.send_message(chat_id=userA.chat_id,
                text=userB.full_name + " pays everything.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=userB.chat_id,
                text=userA.full_name + " has added an expense of " + str(value) + " units for the following reason:\n\n" + reason,
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    elif share == "50%":
        value = value / 2
        current_expense.value = value
        context.bot.send_message(chat_id=userA.chat_id,
                text="You share your expense equally with " + userB.full_name + ".",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=userB.chat_id,
                text=userA.full_name + " has added an expense of " + str(value) + " units for the following reason:\n\n" + reason,
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    else:
        context.bot.send_message(chat_id=userA.chat_id,
                text="I'll simply forget about it.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        return ConversationHandler.END

    add_expense(current_expense)

    difference = get_relative_finance(current_expense.userA, current_expense.userB)
    # userA owes userB difference units

    # A owes B
    if difference > 0:
        context.bot.send_message(chat_id=userA.chat_id,
                text="You owe " + userB.full_name + " " + str(difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=userB.chat_id,
                text=userA.full_name + " owes you " + str(difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    # B owes A 
    elif difference < 0:
        context.bot.send_message(chat_id=userA.chat_id,
                text=userB.full_name + " owes you " + str(-difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=userB.chat_id,
                text="You owe " + userA.full_name + " " + str(-difference) + " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    # A and B are balanced
    else:
        context.bot.send_message(chat_id=userA.chat_id,
                text="You and " + userB.full_name + " are now balanced.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        context.bot.send_message(chat_id=userB.chat_id,
                text="You and " + userA.full_name + " are now balanced.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

    current_expense_dict[userA.tag] = None
    return ConversationHandler.END

#
# cancel a previously started expense
#
def cancel (update, context):
    context.bot.send_message(chat_id=update.message.chat_id,
            text="I'll simply forget about it.",
            reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

#
# send failure message for non control commands
#
def failure (update, context):
    context.bot.send_message(chat_id=update.message.chat_id,
            text="I don't understand human language.\n<i>(at least I pretend...)</i>",
            parse_mode=telegram.ParseMode.HTML,
            reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

if __name__ == '__main__':
    main()
