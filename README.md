# BouncerBot - Your Partner in Lurker-Prevention
### Authored by Shinanygans (shinanygans@proton.me)

This bot will as for a sample media contribution before responding with a link that the user can access.

## Prerequisites

Before you begin, ensure you have met the following requirements:

- **Python 3.10 or higher**: If you don't have Python installed, you can download it from the [official Python website](https://www.python.org/downloads/).

## Installation

Follow these steps to set up your project:

1. Clone this repository to your local machine:

    ```shell
    git clone https://github.com/shnygns/bouncerbot.git
    ```

2. Navigate to the project directory:

    ```shell
    cd bouncerbot
    ```

3. If you prefer using Pipenv:

    - Install Pipenv (if not already installed):

        ```shell
        pip3 install pipenv
        ```

    - Create a virtual environment and install dependencies:

        ```shell
        pipenv install 
        ```
        ...or, so specify the python version overtly:

        ```shell
        pipenv install --python 3.10
        ```


    - Activate the virtual environment:

        ```shell
        pipenv shell
        ```

4. If you prefer using venv and requirements.txt:

    - Create a virtual environment:

        ```shell
        python3 -m venv venv
        ```

    - Activate the virtual environment:

        - On Windows:

            ```shell
            .\venv\Scripts\activate
            ```

        - On macOS and Linux:

            ```shell
            source venv/bin/activate
            ```

    - Install dependencies:

        ```shell
        pip install -r requirements.txt
        ```

5. Make a copy of the template file `sample-config.py` and rename it to `config.py`:

    ```shell
    cp sample-config.py config.py
    ```

6. Open `config.py` and configure the bot token and any other necessary settings.


7. IMPORTANT - Configure named admins in config.py:
If other people find your BouncerBot through a Telegram search and run it in their rooms, THEIR DATA WILL BE STORED IN YOUR DATABASE! This is no bueno. 

To stop this from happening, put your Telegram user_id in the AUTHORIZED_ADMINS list in config.py. If there are user_ids in this list, then only these user_ids will be able to issue bot commands, and the bot will only vacuum up information from chats in which at least one user_id on this list is an admin. Problem solved.

AUTHORIZED_ADMINS = [XXXXXXXXXX, XXXXXXXXXX]


8. Run the script from your virtual environment shell:

    ```shell
    python bouncerbot.py
    ```

## Getting a Bot Token

To run your Telegram bot, you'll need a Bot Token from the Telegram BotFather. Follow these steps to obtain one:

1. Open the Telegram app and search for the "BotFather" bot.

2. Start a chat with BotFather and use the `/newbot` command to create a new bot.

3. Follow the instructions to choose a name and username for your bot.

4. Once your bot is created, BotFather will provide you with a Bot Token. Copy this token.

5. In the `config.py` file, set the `BOT_TOKEN` variable to your Bot Token.




## Usage

Invite this bot to your group as an admin. Make sure the bot's settings in Bot Father give it full privilidges. The bot is active by default.

COMMANDS
/bouncerbot - Toggle name filtering on and off


## Configuration and Features

The config.py file houses the bot token (as a string between quotes), and the list of terms for which a user will be banned if the term appears in his display name. The finished config file should look something like this:

""" BASIC CREDENTIALS """
# BASIC CREDENTIALS - BOT TOKEN
# Gotten from Telegram BotFather
BOT_TOKEN = "XXXXXXXXXXXXXX"  # from BotFather

...

UPLOADS_NEEDED = 0   # Number of videos you want the user to upload before a link is granted
MINUTES_TO_LINK_EXPIRATION = 10  # Link will expire after this many minutes, and the user will need to ask the bot for a different link


### Authorized Admins

AUTHORIZED_ADMINS = [XXXXXXXXXX, XXXXXXXXXX]

If this list is empty, your bot may be used by anyone who is an admin in a chat where the bot is operating. You can fill this list with authorized User IDs (separated by commas, no quotes) that are acceptable for use. 

Only those users listed will be able to command the bot, and the bot will only work in rooms where someone on the list is an admin.


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


## Acknowledgments

This bot was built using the python-telegram-bot library and API wrapper. It also uses tqdm for its progress bars.

One python-telegram-bot example bots - chatmemberbot.py - was the model for the function that detence entering/exiting a group:
https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/chatmemberbot.py 


## Support
This script is provided AS-IS without warranties of any kind. I am exceptionally lazy, and fixes/improvements will proceed in direct proportion to how much I like you.

"Son...you're on your own." --Blazing Saddles



