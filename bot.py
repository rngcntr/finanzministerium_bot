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
    elif get_user(update.message.from_user.username):
        # the user does not have a user tag
        context.bot.send_message(chat_id=update.message.chat_id,
                text="You are already part of the chaos \o/",
                parse_mode=telegram.ParseMode.HTML,
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    else:
        add_user(update.message.from_user.username,
                update.message.from_user.full_name,
                update.message.from_user.id)

        # notify the user
        context.bot.send_message(chat_id=update.message.chat_id,
                text="Bleep blop, I'm a bot.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

def status (update, context):
    relative_finance_list = get_status(update.message.from_user.username)

    # everything is balanced
    if len(relative_finance_list) == 0:
        context.bot.send_message(chat_id=update.message.chat_id,
                text="There are no financial differences with anybody.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

    for relative_finance in relative_finance_list:
        userB = get_user(relative_finance.userB)
        difference = relative_finance.value

        if difference > 0:
            context.bot.send_message(chat_id=update.message.from_user.id,
                    text="You owe " + userB.full_name + " (@" + userB.tag + ") " + str(difference) + " units.",
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        elif difference < 0:
            context.bot.send_message(chat_id=update.message.from_user.id,
                    text=userB.full_name + " (@" + userB.tag + ") owes you " + str(-difference) + " units.",
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))

#
# start a new expense
#
def expense (update, context):
    if update.message.text.strip() == "/expense":
        # normal interaction is used
        current_expense_dict[update.message.from_user.username] = Expense()

        context.bot.send_message(chat_id=update.message.from_user.id,
                text="Who do you share the expense with?",
                reply_markup=telegram.ReplyKeyboardRemove())
        return NAME
    else:
        # quick interaction is used
        current_expense = Expense.from_text(update.message.text)
        if not current_expense:
            context.bot.send_message(chat_id=update.message.from_user.id,
                    text="Please use the following format to enter expenses quickly:\n"
                    "/expense <value> <user_1> <user_2> ... <user_n> <reason>",
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
            return ConversationHandler.END
        else:
            add_expense(current_expense, update.message.from_user.username)
            users = [get_user(user) for user in current_expense.users]
            users.remove(update.message.from_user.username)
            show_expense_result(get_user(update.message.from_user.username), users)
            return ConversationHandler.END

#
# received one (or multiple) users to share the expense with
#
def received_name (update, context):
    entities = update.message.entities

    if (len(entities) == 0):
        # no mentions in message
        context.bot.send_message(chat_id=update.message.from_user.id,
                text="You have to send me a username. Cancelling.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        return ConversationHandler.END
    else:
        entities = list(filter(lambda x: x.type == "mention", entities))
        entities = [update.message.parse_entity(entity).replace("@","") for entity in entities]
        entities = list(filter(lambda x: x != update.message.from_user.username, entities)) # don't share with yourself
        if len(entities) == 0:
            # message element is not a mention
            context.bot.send_message(chat_id=update.message.from_user.id,
                    text="You have to send me at least one registered username who is not you. Cancelling.",
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
            return ConversationHandler.END
        else:
            # there is at least one mentioned user
            users = [get_user(entity) for entity in entities]
            for userB in users:
                if not userB:
                    # the mentioned user is not registered
                    current_expense_dict[update.message.from_user.username] = None
                    context.bot.send_message(chat_id=update.message.from_user.id,
                            text="The user @" + userB.tag + " is not yet registered. Cancelling.",
                            reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
                    return ConversationHandler.END
            # all of the mentioned users are registered
            current_expense_dict[update.message.from_user.username].users = entities
            if len(users) == 1:
                context.bot.send_message(chat_id=update.message.from_user.id,
                        text="Sharing an expense with " + users[0].full_name + ". How much did you spend? (use xxx.xx for decimal values)",
                        reply_markup=telegram.ReplyKeyboardRemove())
            else:
                context.bot.send_message(chat_id=update.message.from_user.id,
                        text="Sharing an expense multiple users. How much did you spend? (use xxx.xx for decimal values)",
                        reply_markup=telegram.ReplyKeyboardRemove())
            return VALUE

#
# received the value of the current expense
#
def received_value (update, context):
    current_expense = current_expense_dict[update.message.from_user.username]

    value_input = update.message.text
    value_decimal = Decimal(sub(r'[^\d\-.]', '', value_input))
    current_expense.value = value_decimal
    context.bot.send_message(chat_id=update.message.from_user.id,
            text="Please provide a reason for this expense.",
            reply_markup=telegram.ReplyKeyboardRemove())

    return REASON

#
# received a reason for the current expense
#
def received_reason (update, context):
    current_expense = current_expense_dict[update.message.from_user.username]

    reason_input = update.message.text
    current_expense.reason = reason_input
    custom_keyboard = [[str(current_expense.value) + " for everybody"], ["Share equally (including yourself)"], ["Share equally (excluding yourself)"], ["Cancel"]]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    context.bot.send_message(chat_id=update.message.from_user.id,
            text="Adding an expense with value "
                + str(current_expense.value)
                + ". How much does everyone have to pay?",
            reply_markup=reply_markup)

    return SHARE

#
# received a share of the current expense for userB
#
def received_share (update, context):
    current_expense = current_expense_dict[update.message.from_user.username]
    users = [get_user(user) for user in current_expense.users]

    share = update.message.text
        
    if share.endswith(" for everybody"):
        context.bot.send_message(chat_id=update.message.from_user.id,
                text="Everybody pays " + str(current_expense.value),
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        for userB in users:
            context.bot.send_message(chat_id=userB.chat_id,
                    text=update.message.from_user.full_name + " has added an expense of " + str(current_expense.value) + " units for the following reason:\n\n" + current_expense.reason,
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        current_expense.value = current_expense.value * len(users)
    elif share == "Share equally (including yourself)":
        context.bot.send_message(chat_id=update.message.from_user.id,
                text="Everybody including you pays " + str(current_expense.value / (len(users) + 1))+ " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        for userB in users:
            context.bot.send_message(chat_id=userB.chat_id,
                    text=update.message.from_user.full_name + " has added an expense of " + str(current_expense.value / (len(users) + 1)) + " units for the following reason:\n\n" + current_expense.reason,
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        current_expense.users.append(update.message.from_user.username)
    elif share == "Share equally (excluding yourself)":
        context.bot.send_message(chat_id=update.message.from_user.id,
                text="Everybody but you pays " + str(current_expense.value / len(users))+ " units.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        for userB in users:
            context.bot.send_message(chat_id=userB.chat_id,
                    text=update.message.from_user.full_name + " has added an expense of " + str(current_expense.value / len(users)) + " units for the following reason:\n\n" + current_expense.reason,
                    reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
    else:
        context.bot.send_message(chat_id=update.message.from_user.id,
                text="I'll simply forget about it.",
                reply_markup=telegram.ReplyKeyboardMarkup(command_keyboard))
        return ConversationHandler.END

    add_expense(current_expense, update.message.from_user.username)
    show_expense_result(get_user(update.message.from_user.username), users)
    current_expense_dict[update.message.from_user.username] = None

    return ConversationHandler.END

#
# shows the updated relative finances after entering a new expense
#
def show_expense_result (userA, users):
    for userB in users:
        difference = get_relative_finance(userA.tag, userB.tag)
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
