import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
import matplotlib.pyplot as plt
import io
import base64
import os
from dotenv import load_dotenv
import logging
from pathlib import Path

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')  # Load secret key from .env

# Database setup
BASE_DIR = Path(__file__).parent
DATABASE = os.path.join(BASE_DIR, 'guess_game.db')
DEVELOPER_PASSWORD = os.getenv('DEVELOPER_PASSWORD')  # Load developer password from .env

def init_db():
    """
    Initialize the SQLite database and create the 'guesses' table if it doesn't exist.
    """
    with sqlite3.connect(DATABASE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS guesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                guess INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def reset_db():
    """
    Reset the database by deleting the existing file and reinitializing it.
    """
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
    init_db()

# Initialize the database when the app starts
init_db()

@app.route('/')
def index():
    """
    Render the home page with the current number of participants.
    """
    with sqlite3.connect(DATABASE) as conn:
        count = conn.execute('SELECT COUNT(*) FROM guesses').fetchone()[0]
    return render_template('index.html', count=count)

@app.route('/submit', methods=['POST'])
def submit():
    """
    Handle guess submission and validate the input.
    """
    name = request.form.get('name')
    guess = request.form.get('guess')

    # Validate the guess
    try:
        guess = int(guess)
        if guess < 0 or guess > 100:
            logging.warning(f"Invalid guess range: {guess}")
            return "Please enter a number between 1 and 100.", 400
    except ValueError:
        logging.warning(f"Invalid guess input: {guess}")
        return "Please enter a valid number.", 400

    # Save the data to the database
    with sqlite3.connect(DATABASE) as conn:
        conn.execute('INSERT INTO guesses (name, guess) VALUES (?, ?)', (name, guess))
        conn.commit()
        logging.info(f"New guess recorded: {name} - {guess}")

    # Fetch the count of guesses from the database
    with sqlite3.connect(DATABASE) as conn:
        count = conn.execute('SELECT COUNT(*) FROM guesses').fetchone()[0]

    return render_template('thank_you.html', count=count)

@app.route('/final_result', methods=['GET', 'POST'])
def final_result():
    """
    Handle developer access to the final results page.
    """
    if request.method == 'POST':
        password = request.form.get('password')
        if password == DEVELOPER_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('show_results'))
        else:
            return "Only developers have access to this section. Incorrect password.", 403
    return render_template('final_result.html')

@app.route('/results')
def show_results():
    """
    Display the final results, including charts and the winner.
    """
    if not session.get('authenticated'):
        return "Only developers have access to this section.", 403

    with sqlite3.connect(DATABASE) as conn:
        guesses = [row[0] for row in conn.execute('SELECT guess FROM guesses').fetchall()]

    if not guesses:
        return "No guesses recorded yet."

    average = sum(guesses) / len(guesses)
    two_thirds_avg = (2 / 3) * average

    # Create the original distribution chart
    plt.figure(figsize=(12, 6))

    # Chart 1: Original histogram
    plt.subplot(1, 2, 1)
    plt.hist(guesses, bins=range(1, 101), edgecolor='black', color='skyblue')
    plt.title('Distribution of Guesses')
    plt.xlabel('Guess')
    plt.ylabel('Frequency')

    # Chart 2: Interval-based histogram
    plt.subplot(1, 2, 2)
    bins = range(1, 101, 10)  # Intervals: 1-10, 11-20, ..., 91-100
    plt.hist(guesses, bins=bins, edgecolor='black', color='lightgreen')
    plt.title('Guesses by Intervals')
    plt.xlabel('Guess Intervals')
    plt.ylabel('Frequency')
    plt.xticks(bins, [f'{i}-{i+9}' for i in bins], rotation=45)

    # Save the combined chart to a base64 string
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()

    # Find the winner
    with sqlite3.connect(DATABASE) as conn:
        winner = conn.execute('''
            SELECT name, guess FROM guesses
            ORDER BY ABS(guess - ?) LIMIT 1
        ''', (two_thirds_avg,)).fetchone()

    # Reset the database
    reset_db()

    return render_template('results.html',
                          plot_url=plot_url,
                          average=average,
                          two_thirds_avg=two_thirds_avg,
                          winner=winner)
@app.route('/full')
def show_full():
    with sqlite3.connect(DATABASE) as conn:
        guesses = conn.execute('SELECT * FROM guesses ORDER BY guess DESC').fetchall()
    return render_template('full_result.html', guesses=guesses)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=False, host="0.0.0.0", port=port)
