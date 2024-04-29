#! /usr/bin/python

"""
BouncerBot - Your Partner in Lurker-Prevention
Authored by Shinanygans (shinanygans@proton.me)

This bot will as for a sample media contribution before responding with a link that the user can access.
"""

import logging
import re
import sys
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta, timezone
import traceback
import pytz
import asyncio
import csv
from collections import OrderedDict
from functools import wraps
from telegram import Update, ChatMember, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType, ParseMode
from telegram.error import RetryAfter, Forbidden, TimedOut, BadRequest, NetworkError
from telegram.ext import (
    ChatMemberHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackContext,
    Application
)
from db_utils import Database
from config import (
    BOT_TOKEN,
    AUTHORIZED_ADMINS,
    START_MESSAGE,
    MINUTES_TO_LINK_EXPIRATION,
    UPLOADS_NEEDED,
    HELP_MESSAGE,
    SETUP_MESSAGE
)



# Configure logging
when = 'midnight'  # Rotate logs at midnight (other options include 'H', 'D', 'W0' - 'W6', 'MIDNIGHT', or a custom time)
interval = 1  # Rotate daily
backup_count = 7  # Retain logs for 7 days
log_handler = TimedRotatingFileHandler('app.log', when=when, interval=interval, backupCount=backup_count)
log_handler.suffix = "%Y-%m-%d"  # Suffix for log files (e.g., 'my_log.log.2023-10-22')

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        log_handler,
    ]
)

# Create a separate handler for console output with a higher level (WARNING)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)  # Set the level to WARNING or higher
console_formatter = logging.Formatter("BOUNCERBOT: %(message)s")
console_handler.setFormatter(console_formatter)

# Attach the console handler to the root logger
logging.getLogger().addHandler(console_handler)


# Global variables
bouncerbot = None
app = None
db = Database()
utc_timezone = pytz.utc
cached_active_chats = {}


# Custom decorator function to check if the requesting user is authorized (use for commands).
def authorized_admin_check(handler_function):
    @wraps(handler_function)
    async def wrapper(update: Update, context: CallbackContext):
        try:
            user_id = update.effective_user.id
            if AUTHORIZED_ADMINS and user_id not in AUTHORIZED_ADMINS:
                return 
            else:
                return await handler_function(update, context)

        except Exception as e:
            logging.warning(f"An error occured in authorized_admin_check(): {e}")
            return
    return wrapper


def private_bot_chat_check(handler_function):
    @wraps(handler_function)
    async def wrapper(update: Update, context: CallbackContext):
        try:
            chat_type = update.effective_chat.type
            if chat_type != ChatType.PRIVATE:
                return
            else:
                return await handler_function(update, context)
        except Exception as e:
            logging.warning(f"An error occured in private_bot_chat_check(): {e}")
            return
    return wrapper


def parse_date_from_db(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=utc_timezone) if date_str else None


def parse_user_tuple_list_from_db(user_tuple_list):
    user_dict = {}
    for user in user_tuple_list:
        user_id = user[0]
        full_name = user[1]
        username = user[2]
        last_accessed_bot = parse_date_from_db(user[3])
        last_uploaded_video = parse_date_from_db(user[4])
        number_videos_uploaded = user[5]
        access_granted = parse_date_from_db(user[6])
        invite_link = user[7]
        link_used = parse_date_from_db(user[8])
        chat_id = user[9]

        user_dict[user_id] = {
            'full_name': full_name,
            'username': username,
            'last_accessed_bot': last_accessed_bot,
            'last_uploaded_video': last_uploaded_video,
            'number_videos_uploaded': number_videos_uploaded,
            'access_granted': access_granted,
            'chat_id': chat_id,
            'invite_link': invite_link,
            'link_used': link_used
        }
    return user_dict


def create_keyboard_from_active_chats():
    buttons = []
    button_names={}
    active_chats = db.return_all_active_chats()
    for chat_id, chat_title in active_chats.items():
        buttons.append(InlineKeyboardButton(chat_title, callback_data=f"activechats_{chat_id}"))
        button_names[chat_id] = chat_title

    buttons.append(InlineKeyboardButton("None", callback_data="activechats_None"))

    # Create a two-column layout for the buttons
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]

    # Create an inline keyboard markup
    reply_markup = InlineKeyboardMarkup(keyboard)

    return reply_markup, button_names


async def list_active_chats():
    response_text = "ACTIVE CHATS:\n\n"
    active_chats = db.return_all_active_chats()
    for chat_id, chat_title in active_chats.items():
        response_text += f"{chat_id} - {chat_title}\n"
    return response_text


async def create_one_time_invite_link() -> str:
    # Create a new invite link that can only be used once
    destination_chat_id = db.lookup_setting("destination_chat_id")
    if destination_chat_id is None:
        return None
    expire_time = int((datetime.now() + timedelta(minutes=MINUTES_TO_LINK_EXPIRATION)).timestamp()) if MINUTES_TO_LINK_EXPIRATION else None
    invite_creation_response = await bouncerbot.create_chat_invite_link(int(destination_chat_id), member_limit=1, expire_date=expire_time)
    invite_link = invite_creation_response.invite_link
    return invite_link


def extract_callback_data(data):
    callback_data = data.split("_")
    return callback_data[0], callback_data[1]


def handle_choice(choice, button_names):
    if choice == "None":
        message_text = f"Destination group set to <strong>None</strong>."
        db.update_settings("destination_chat_id", None)
    else:
        try:
            choice_int = int(choice)
            message_text = f"Destination group set to <strong>{button_names[choice_int]}</strong>."
            db.update_settings("destination_chat_id", choice_int)
        except:
            message_text = "Invalid action."
    return message_text


async def request_invite_link(update: Update, context: CallbackContext) -> str:
    # Get the chat ID
    user_id = update.effective_user.id

    # Create a one-time invite link
    invite_link = await create_one_time_invite_link()
    if invite_link is None:
        response_text = "Currently, there is no active chat to link to. Please check back later."
    else:
        response_text = f"Here is your one-time invite link: {invite_link}"

    # Send the invite link to the user
    await context.bot.send_message(chat_id=user_id, text=response_text)
    return invite_link


async def send_confirmation_and_delete_original(bot, chat_id, user_id, message_id, message_text):
    await bot.send_message(chat_id=chat_id, text=message_text, parse_mode=ParseMode.HTML)
    await asyncio.sleep(3)
    await bot.delete_message(chat_id=user_id, message_id=message_id)
    return


async def track_used_link(update: Update, context: CallbackContext):
    # if this is a 'join by invite link' event, update.chat_member.invite_link will contain the invite link used

    # Early return if the update is not a 'join by invite link' event
    if update.chat_member.invite_link is None:
        return

    link_used = update.chat_member.invite_link.invite_link
    new_member = update.chat_member.new_chat_member.user
    db_user = db.lookup_invite_link(link_used)
    link_in_db = db_user is not None
   
    if link_in_db:
        db.record_link_used(new_member.id)
        logging.warning(f"Invite link {link_used} was used by {new_member.full_name} (ID: {new_member.id})")
        
    return


# @private_bot_chat_check handled at task creation
async def handle_message(update: Update, context: CallbackContext) -> None:
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        if chat_id not in cached_active_chats.keys():
            chat_title = update.effective_chat.title
            cached_active_chats[chat_id] = chat_title
            db.record_active_chat(chat_id, chat_title)
            logging.warning(f"Chat {chat_id} ({chat_title}) added to active_chats.")

        if update.effective_message.video:
            num_uploads = db.record_video_upload(user_id)
            if num_uploads >= UPLOADS_NEEDED:
                invite_link = await request_invite_link(update, context)
                db.record_access_granted(user_id, invite_link)


    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f"An error occurred in handle_message(): {e}\n{tb}")
    return


def get_user_details(update) -> tuple:
    user_id = update.effective_user.id
    full_name = update.effective_user.full_name
    username = update.effective_user.username
    return user_id, full_name, username


async def send_no_active_chat_message(context, user_id, full_name) -> None:
    response_text = f"Welcome back, {full_name}! You have already been granted access. Currently, there is no active chat to link to. Please check back later."
    await context.bot.send_message(
        chat_id=user_id,
        text=f"<i style='color:#808080;'>{response_text}</i>",
        parse_mode=ParseMode.HTML
    ) 
    return


async def generate_start_command_response_text(db_user, num_uploads, user_id, full_name, destination_chat_id, chat_title) -> str:

    async def generate_existing_link_response_text(full_name, invite_link, link_creation_time):
        response_text = f"Welcome back, {full_name}! You have already been granted access. Here is your invite link:\n{invite_link}\n\n"
        if MINUTES_TO_LINK_EXPIRATION:
            # time_remaining equals the number of minutes reflected in MINUTES_TO_LINK_EXPIRATION, minus the elapsed time beteween now and the link creation time
            time_remaining = timedelta(minutes=MINUTES_TO_LINK_EXPIRATION) - (datetime.now(timezone.utc) - link_creation_time)
            total_minutes = int(time_remaining.total_seconds() / 60)
            hours, minutes = divmod(total_minutes, 60)
            if hours > 0:
                response_text += f"This link will expire in {hours} {'hours' if hours > 1 else 'hour'}. and {minutes} {'minutes' if minutes > 1 else 'minute'}."
            elif total_minutes == 0:
                response_text += f"This link will expire in less than one minute."
            else:
                response_text += f"This link will expire in {minutes} {'minutes' if minutes > 1 else 'minute'}."
        return response_text


    async def generate_new_link_response_text(user_id, full_name):
        invite_link = await create_one_time_invite_link()
        if invite_link is None:
            response_text = f"Welcome back, {full_name}! You have already been granted access. Currently, there is no active chat to link to. Please check back later."
        else:
            db.record_access_granted(user_id, invite_link)
            response_text = f"Welcome back, {full_name}! You have already been granted access. Here is your invite link:\n{invite_link}\n\n"
            if MINUTES_TO_LINK_EXPIRATION:
                response_text += f"This link will expire in {MINUTES_TO_LINK_EXPIRATION} minutes."
        return response_text


    response_text = f"💥 <strong>Welcome to {chat_title}</strong> 💥\n\n"
    response_text += START_MESSAGE

    # If user is in the database, check if they have an invite link and if it has been used
    if db_user is not None:
        db_user_dict = parse_user_tuple_list_from_db([db_user])
        access_granted_timestamp = db_user_dict[user_id]['access_granted']
        invite_link = db_user_dict[user_id]['invite_link']
        link_used = db_user_dict[user_id]['link_used']
        link_chat_id = db_user_dict[user_id]['chat_id']

        #If an invite link exists, has not been used, has not expired, and is for the correct chat, generate a response with the existing link:
        if invite_link and not link_used and (datetime.now(timezone.utc) - access_granted_timestamp) < timedelta(minutes=MINUTES_TO_LINK_EXPIRATION) and link_chat_id == destination_chat_id:
            response_text = await generate_existing_link_response_text(full_name, invite_link, access_granted_timestamp)

        #If the existing link has expired, or there is no existing link but the obligation has been met, generate a new link
        elif num_uploads >= UPLOADS_NEEDED:
            response_text = await generate_new_link_response_text(user_id, full_name)
        #If there is no existing link and the obligation has not been met, inform the user of their progress
        else:
            response_text += f"\n\nYou have uploaded {num_uploads} out of {UPLOADS_NEEDED} required media files." if UPLOADS_NEEDED >0 else ""
    
    return response_text


#############  INACTIVE CHAT HANDLING #############


async def find_inactive_chats():
    db_chats = db.return_all_active_chats()
    active_chats = []
    inactive_chats = []
    for chat_id, chat_title in db_chats.items(): 
        try:
            await bouncerbot.get_chat(chat_id)  # Test to see if chat is active
            active_chats.append(chat_id)
        except (BadRequest, Forbidden) as e:
            logging.warning(f"Chat {chat_id} ({chat_title}) is not accessible. Removing from active_chats.")
            inactive_chats.append(chat_id)
            await clean_inactive_chats(chat_id)
    return active_chats, inactive_chats


async def clean_inactive_chats(chat_id: int):
    try:
        db_users = db.return_users_for_chat(chat_id)
        db_user_dict = parse_user_tuple_list_from_db(db_users)
        chat_title = db.lookup_active_chat_title_with_id(chat_id)
        await write_users_to_csv(db_user_dict, chat_title)
        
        db.delete_users_for_chat(chat_id)
        db.delete_active_chat(chat_id)
        logging.warning(f"Chat {chat_id} ({chat_title}) removed from active chats and all user data deleted.")
    except Exception as e:
        logging.warning(f"An error occurred in clean_inactive_chats(): {e}")
    return


async def create_readable_current_date_for_filenames():
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


#############  CSV PROCESSING FUNCTIONS #############


async def write_users_to_csv(users_dict, chat_title):
    if not users_dict:
        return None  # Return None if the dictionary is empty

    date_string = datetime.now().strftime("%Y%m%d_%H-%M")  # You can adjust the date format as needed
    safe_chat_title = sanitize_filename(chat_title)
    file_path = f'users_{safe_chat_title}_{date_string}.csv'
    
    # Determine the fieldnames from the keys of the first user entry
    # Assuming all dictionaries have the same structure
    if users_dict:
        first_user_key = next(iter(users_dict))
        fieldnames = list(users_dict[first_user_key].keys())

    with open(file_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for user_id, data in users_dict.items():
            writer.writerow(data)  # Write data directly since fieldnames are dynamically set

    return file_path


def sanitize_filename(filename):
    # Define a regex pattern to match any disallowed file name characters
    # Spaces are also included in the pattern to replace them with underscores
    pattern = r'[\\/*?:"<>|\s]+'
    # Replace these characters with underscores
    safe_filename = re.sub(pattern, '_', filename)
    return safe_filename


#############  COMMAND HANDLING FUNCTIONS  #############

@private_bot_chat_check
async def start_command(update: Update, context: CallbackContext) -> None:
    """Send a message with information about the bot's available commands."""
    try:
        user_id, full_name, username = get_user_details(update)
        destination_chat_id = db.lookup_setting("destination_chat_id")
        db.record_bot_user(user_id, full_name, username, destination_chat_id)
        db_user = db.lookup_user(user_id)
        num_uploads = 0
        destination_chat_id = db.lookup_setting("destination_chat_id")
        chat = await bouncerbot.get_chat(destination_chat_id) if destination_chat_id else None

        if not chat:
            await send_no_active_chat_message(context, user_id, full_name)
            return

        chat_title = chat.title if chat else "None"
        chat_id = chat.id if chat else "None"
        if db_user[5] is not None:
            num_uploads = db_user[5]

        response_text = await generate_start_command_response_text(db_user, num_uploads, user_id, full_name, chat_id, chat_title)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=f"<i style='color:#808080;'>{response_text}</i>",
            parse_mode=ParseMode.HTML
        )  
    except Exception as e:
        tb = traceback.format_exc()
        _, _, exc_traceback = sys.exc_info()
        logging.error(f"An error occurred in {exc_traceback.tb_frame.f_code.co_name} line: {exc_traceback.tb_lineno}: {e}\n{tb}")
    return


@private_bot_chat_check
async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message with information about the bot's available commands."""
    # If the user_id is in AUTHORIZED_ADMINS, send the setup message. Otherwise, send the help message
    try:
        user_id = update.effective_user.id
        response_text = SETUP_MESSAGE if user_id in AUTHORIZED_ADMINS else HELP_MESSAGE
        await context.bot.send_message(
            chat_id=user_id,
            text=response_text,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        tb = traceback.format_exc()
        _, _, exc_traceback = sys.exc_info()
        logging.error(f"An error occurred in {exc_traceback.tb_frame.f_code.co_name} line: {exc_traceback.tb_lineno}: {e}\n{tb}")
    return


async def post_active_chats_in_message(update: Update, context: CallbackContext):
    try:
        user_id=update.effective_user.id
        response_text = await list_active_chats()
        await app.bot.send_message(chat_id=user_id, text=response_text)
    except Exception as e:
        tb = traceback.format_exc()
        _, _, exc_traceback = sys.exc_info()
        logging.error(f"An error occurred in {exc_traceback.tb_frame.f_code.co_name} line: {exc_traceback.tb_lineno}: {e}\n{tb}")
    return


async def register_destination_chat(update: Update, context: CallbackContext):
    try:
        issuer_user_id = update.effective_user.id
        reply_markup, button_names = create_keyboard_from_active_chats()
        menu_message = await context.bot.send_message(
            chat_id=issuer_user_id,
            text="Select the group that you want to let users through to:",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        # Save the message ID for later reference
        context.user_data['menu_message_id'] = menu_message.message_id
        context.user_data['button_names'] = button_names


    except Exception as e:
        tb = traceback.format_exc()
        _, _, exc_traceback = sys.exc_info()
        logging.error(f"An error occurred in {exc_traceback.tb_frame.f_code.co_name} line: {exc_traceback.tb_lineno}: {e}\n{tb}")
    return

# Callback function for handling button clicks
async def button_click(update, context):
    try:
        query = update.callback_query
        chat_id = query.message.chat_id
        user_id = query.from_user.id
        message_id = context.user_data['menu_message_id'] 
        button_names = context.user_data['button_names']

        # Extract the callback_data
        action, choice = extract_callback_data(query.data)

        if action != "activechats":
            return

        # Check the action and perform the corresponding operation
        message_text = handle_choice(choice, button_names)

        try:
            # Send a confirmation message and delete the original message
            await send_confirmation_and_delete_original(context.bot, chat_id, user_id, message_id, message_text)
        except BadRequest as e:
            logging.error(f" Error with register_destination_chat() confirmation messages: {e}")

    except Exception as e:
        tb = traceback.format_exc()
        _, _, exc_traceback = sys.exc_info()
        logging.error(f"An error occurred in {exc_traceback.tb_frame.f_code.co_name} line: {exc_traceback.tb_lineno}: {e}\n{tb}")
    return


async def export_all_users_to_csv(update: Update, context: CallbackContext):
    try:
        db_users = db.return_all_users()
        db_user_dict = parse_user_tuple_list_from_db(db_users)

        chat_users = {}
        for user_id, data in db_user_dict.items():
            chat_id = data['chat_id']
            chat_users.setdefault(chat_id, {})[user_id] = data

        for chat_id, users in chat_users.items():
            sorted_users = sorted(
                users.items(),
                key=lambda x: x[1]['last_accessed_bot'] if x[1]['last_accessed_bot'] is not None else datetime.min.replace(tzinfo=utc_timezone),
                reverse=True
            )
            chat_title = db.lookup_active_chat_title_with_id(chat_id)
            file_path = await write_users_to_csv({uid: dat for uid, dat in sorted_users}, chat_title)
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))

    except Exception as e:
        tb = traceback.format_exc()
        _, _, exc_traceback = sys.exc_info()
        logging.error(f"An error occurred in {exc_traceback.tb_frame.f_code.co_name} line: {exc_traceback.tb_lineno}: {e}\n{tb}")
    return


async def clean_database(update: Update, context: CallbackContext):
    try:
        _, inactive_chats = await find_inactive_chats()
        for chat_id in inactive_chats:
            await clean_inactive_chats(chat_id)
        await post_active_chats_in_message(update, context)
    except Exception as e:
        tb = traceback.format_exc()
        _, _, exc_traceback = sys.exc_info()
        logging.error(f"An error occurred in {exc_traceback.tb_frame.f_code.co_name} line: {exc_traceback.tb_lineno}: {e}\n{tb}")
    return

'''
async def drop_table(update: Update, context: CallbackContext):
    # Get the chat ID
    chat_id = update.effective_chat.id
    try:
        db.drop_table()
        db._ensure_schema()
        response_text = "Table dropped successfully!"
        await context.bot.send_message(chat_id=chat_id, text=response_text)
    except Exception as e:
        tb = traceback.format_exc()
        _, _, exc_traceback = sys.exc_info()
        logging.error(f"An error occurred in {exc_traceback.tb_frame.f_code.co_name} line: {exc_traceback.tb_lineno}: {e}\n{tb}")
    return
'''

#############  ASYNCIO TASK FUNCTIONS  #############


async def handle_message_loop(update: Update, context: CallbackContext):
    asyncio.create_task(handle_message(update, context))
    return


@private_bot_chat_check
@authorized_admin_check
async def clean_database_loop(update: Update, context: CallbackContext):
    asyncio.create_task(clean_database(update, context))
    return

@private_bot_chat_check
@authorized_admin_check
async def register_destination_chat_loop(update: Update, context: CallbackContext):
    asyncio.create_task(register_destination_chat(update, context))
    return


@private_bot_chat_check
@authorized_admin_check
async def export_loop(update: Update, context: CallbackContext):
    asyncio.create_task(export_all_users_to_csv(update, context))
    return


async def post_init(application: Application):
    asyncio.create_task(cache_chats_on_startup())


async def cache_chats_on_startup():
    db_chats = db.return_all_active_chats()
    for chat_id, chat_title in db_chats.items(): 
        try:
            await bouncerbot.get_chat(chat_id)  # Test to see if chat is active
            cached_active_chats[chat_id] = chat_title
        except (BadRequest, Forbidden) as e:
            logging.warning(f"Chat {chat_id} ({chat_title}) is not accessible. Removing from active_chats.")
            await clean_inactive_chats(chat_id)
    return

#############  MAIN FUNCTION  #############

def main() -> None:
    global bouncerbot
    global app

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("csv", export_loop))
    application.add_handler(CommandHandler("cleandb", clean_database_loop))
    application.add_handler(CommandHandler("register", register_destination_chat_loop))
    # application.add_handler(CommandHandler("drop", drop_table))
    application.add_handler(ChatMemberHandler(track_used_link, ChatMemberHandler.CHAT_MEMBER))
    application.add_handler(CallbackQueryHandler(button_click, pattern='^activechats_.*'))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message_loop))

    try:
        bouncerbot = application.bot
        app = application

        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()