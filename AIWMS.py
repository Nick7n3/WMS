import telebot
from telebot import types
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt

# Initialize the bot with your token
API_TOKEN = 'ApiToken'
bot = telebot.TeleBot(API_TOKEN)

# Connect to SQLite database
conn = sqlite3.connect('cargo.db', check_same_thread=False)
cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS cargo
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, arr_date TEXT, lea_date TEXT, volume INTEGER)''')
conn.commit()

# In-memory storage for admin status
admin_enabled = False

total_volume = 0

num_users = 0 
# Define warehouse capacity
WAREHOUSE_CAPACITY = 1000  # Example capacity in cubic meters

# Function to clean expired data
def clean_expired_data():
    today = datetime.now().strftime("%d.%m.%Y")
    cursor.execute("DELETE FROM cargo WHERE lea_date < ?", (today,))
    conn.commit()

# Start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to AIWMS! \nPlease enter the starting date of storing (dd.mm.yyyy):")

@bot.message_handler(commands=['MakeRequest'])
def send_welcome(message):
    bot.reply_to(message, "Please enter the starting date of storing (dd.mm.yyyy):")    

# Enable admin command
@bot.message_handler(commands=['EnableAdmin'])
def enable_admin(message):
    global admin_enabled
    admin_enabled = True
    bot.reply_to(message, "Admin mode enabled. You can now use /get and /status.")



@bot.message_handler(commands=['status'])
def send_dashboard(message):
        if admin_enabled:
            clean_expired_data()
            # Retrieve the total volume of all cargo
            cursor.execute("SELECT volume FROM cargo")
            total_volume = cursor.fetchone()[0]


            # Retrieve the number of users
            cursor.execute("SELECT COUNT(*) FROM cargo")
            num_users = cursor.fetchone()[0]


            # Create the dashboard
            plt.figure(figsize=(8, 6))

            # Plot the total volume of cargo
            plt.subplot(2, 1, 1)
            plt.bar(['Total Volume'], [total_volume])
            plt.title('Total Volume of Cargo')
            plt.ylabel('Volume (m^3)')

            # Plot the number of users
            plt.subplot(2, 1, 2)
            plt.bar(['Number of Users'], [num_users])
            plt.title('Number of Users')
            plt.ylabel('Count')

            plt.tight_layout()

            # Save the dashboard as a photo
            plt.savefig('dashboard.png')

            with open('dashboard.png', 'rb') as photo:
                bot.send_photo(message.chat.id, photo)


# Get command
@bot.message_handler(commands=['get'])
def get_requests(message):
    if admin_enabled:
        clean_expired_data()
        cursor.execute("SELECT * FROM cargo")
        rows = cursor.fetchall()
        if rows:
            response = "Stored Requests:\n"
            for row in rows:
                response += f"ID: {row[0]}, Arrival: {row[1]}, Leaving: {row[2]}, Volume: {row[3]}\n"
            bot.reply_to(message, response)
        else:
            bot.reply_to(message, "No requests found.")
    else:
        bot.reply_to(message, "You do not have permission to use this command.")

# Handle text messages
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_data = message.text.split()
    
    # Check if the message is a date
    try:
        datetime.strptime(user_data[0], "%d.%m.%Y")
        bot.reply_to(message, "Enter the volume of the cargo:")
        bot.register_next_step_handler(message, handle_volume, user_data[0])
    except ValueError:
        bot.reply_to(message, "Please enter a valid date in the format dd.mm.yyyy.")

def handle_volume(message, arr_date):
    try:
        volume = int(message.text)
        bot.reply_to(message, "When does the cargo leave the warehouse? (dd.mm.yyyy):")
        bot.register_next_step_handler(message, handle_leaving_date, arr_date, volume)
    except ValueError:
        bot.reply_to(message, "Please enter a valid number for the volume.")

def handle_leaving_date(message, arr_date, volume):
    try:
        lea_date = datetime.strptime(message.text, "%d.%m.%Y").strftime("%d.%m.%Y")

        # Calculate the total volume already stored for the given period
        cursor.execute("SELECT SUM(volume) FROM cargo WHERE lea_date >= ? AND arr_date <= ?", (arr_date, lea_date))
        current_volume = cursor.fetchone()[0] or 0

        # Check if adding the new volume exceeds the warehouse capacity
        if current_volume + volume > WAREHOUSE_CAPACITY:
            bot.reply_to(message, "Storing is not possible for the given dates due to capacity limits.\n/MakeRequest")
        else:
            cursor.execute("INSERT INTO cargo (arr_date, lea_date, volume) VALUES (?, ?, ?)", (arr_date, lea_date, volume))
            conn.commit()
            
            # Display stored request with 'Accept' button
            msg = bot.send_message(message.chat.id, f"Stored request:\nArrival Date: {arr_date}\nLeaving Date: {lea_date}\nVolume: {volume}\nTo make another request enter: /MakeRequest")
            bot.register_next_step_handler(msg, lambda m: m)



    except ValueError:
        bot.reply_to(message, "Please enter a valid date in the format dd.mm.yyyy.")

# Handle callback query from the 'Accept' button
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "accept":
        # Delete the last two messages
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.delete_message(call.message.chat.id, call.message.message_id - 1)
        
        # Confirm the request is written
        bot.send_message(call.message.chat.id, "Request is written!")



# Run the bot
if __name__ == "__main__":
    clean_expired_data()
    bot.polling(none_stop=True)