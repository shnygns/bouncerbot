#! /usr/bin/python
"""
CONFIG.PY

This file stores all Telegram API session information and config settings.
"""

""" BASIC CREDENTIALS """
# BASIC CREDENTIALS - BOT TOKEN
# Gotten from Telegram BotFather
BOT_TOKEN = "XXXXXXX"  

# Path to file for your SQLite database. Default is 'bouncerbot.db'
DATABASE_PATH = "bouncerbot.db"

""" SETTINGS """
# If this list is empty, your bot may be used by anyone who is an admin in a chat where the bot is operating. You can fill this 
# list with authorized User IDs (separated by commas, no quotes) that are acceptable for use. 
# Only those users listed will be able to command the bot, and the bot will only work in rooms where someone on the list is an admin.
AUTHORIZED_ADMINS = [ ]


START_MESSAGE =  ("Just <strong>post or forward a sample video here</strong> so that we know you have material to share.\n\n"
                "The bot will respond with your link!\n"

)

HELP_MESSAGE = ("Type /start to get started.\n\n"
)

SETUP_MESSAGE =("ADMIN SETUP INSTRUCTIONS\n\n"
                "1. Make the bot an admin in a private group you want to protect, and a channel you will use to publicize (avoid posting bot link directly to keep it alive longer).\n\n"
                "2. Use the /cleandb command to see all chats that the bot is in. (If you don't see the group in the reply, post something to the group so the bot can see it.)\n\n"
                "3. Use the /register command to tell the bot which group to protect. Selecting `none` disables the bot. \n\n"
                "4. In your publicizing channel, add a single post to the channel telling people to start a chat with the bot (and remember to give the bot's link).\n\n"
                "5. Publicize the instruction channel to your users. Users can get their one-time link to your protected group by saying `/start` in the bot chat.\n\n"
                "6. Use the /csv command to get a list of all users who have used the bot. If a group nukes, bot will store users in a csv.\n\n"
                
)


UPLOADS_NEEDED = 5
MINUTES_TO_LINK_EXPIRATION = 10