#!/bin/bash
# Check if venv exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the bot
python bot.py
