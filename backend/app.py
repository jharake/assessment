from flask import Flask, request, jsonify, render_template,redirect, url_for

import sqlite3
from openai import OpenAI

app = Flask(__name__)

# Initialize OpenAI
OPENAI_API_KEY = "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"
client = OpenAI(api_key=OPENAI_API_KEY)

def init_db():
    with sqlite3.connect("library.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'available'  -- New column for book status
            )
        """)
        conn.commit()

def check_out_book(book_id):
    with sqlite3.connect("library.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE books SET status = 'borrowed' WHERE id = ? AND status = 'available'", (book_id,))
        if cursor.rowcount > 0:
            conn.commit()
            return f"✅ Book with ID {book_id} has been checked out."
        return "❌ Book is already borrowed or does not exist."

def check_in_book(book_id):
    with sqlite3.connect("library.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE books SET status = 'available' WHERE id = ? AND status = 'borrowed'", (book_id,))
        if cursor.rowcount > 0:
            conn.commit()
            return f"✅ Book with ID {book_id} has been returned."
        return "❌ Book is already available or does not exist."

# Functions to interact with the database
def add_book(title, author):
    with sqlite3.connect("library.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO books (title, author) VALUES (?, ?)", (title, author))
        conn.commit()
        return f"✅ Book '{title}' by {author} added."

def delete_book(book_id):
    with sqlite3.connect("library.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
        if cursor.rowcount > 0:
            conn.commit()
            return f"✅ Book with ID {book_id} deleted."
        return "❌ Book not found."

def update_book(book_id, new_title, new_author):
    with sqlite3.connect("library.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE books SET title = ?, author = ? WHERE id = ?",
            (new_title, new_author, book_id)
        )
        if cursor.rowcount > 0:
            conn.commit()
            return f"✅ Updated book with ID {book_id} to '{new_title}' by {new_author}."
        return "❌ Book not found."

def list_books():
    with sqlite3.connect("library.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM books")
        books = cursor.fetchall()
        return [{"id": row[0], "title": row[1], "author": row[2], "status": row[3]} for row in books]

# OpenAI Tool Definitions
tools = [
    {
        "type": "function",
        "name": "add_book",
        "description": "Add a new book to the library.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of the book"},
                "author": {"type": "string", "description": "Author of the book"}
            },
            "required": ["title", "author"]
        }
    },
    {
        "type": "function",
        "name": "delete_book",
        "description": "Delete a book from the library.",
        "parameters": {
            "type": "object",
            "properties": {
                "book_id": {"type": "integer", "description": "ID of the book to delete"}
            },
            "required": ["book_id"]
        }
    },
    {
        "type": "function",
        "name": "update_book",
        "description": "Update the title and author of an existing book.",
        "parameters": {
            "type": "object",
            "properties": {
                "book_id": {"type": "integer", "description": "ID of the book to update"},
                "new_title": {"type": "string", "description": "New title of the book"},
                "new_author": {"type": "string", "description": "New author of the book"}
            },
            "required": ["book_id", "new_title", "new_author"]
        }
    }
]

# Route for AI-powered library management
@app.route("/", methods=["GET", "POST"])
def index():
    chat_history = []
    bot_response = ""

    if request.method == "POST":
        user_message = request.form.get("message", "")
        chat_history.append({"role": "user", "content": user_message})

        # Get book list context
        books = list_books()
        books_context = "\n".join([f"{book['id']}. {book['title']} by {book['author']}" for book in books])
        context_message = {
            "role": "system",
            "content": f"Current books in the library:\n{books_context}"
        }

        # Send user input to OpenAI with the book list context
        input_message = [context_message] + [{"role": "user", "content": user_message}]

        response = client.responses.create(
            model="gpt-4o-mini",
            input=input_message,
            tools=tools
        )

        output = response.output

        for item in output:
            if hasattr(item, "name"):
                tool_name = item.name
                args = eval(item.arguments)
                if tool_name == "add_book":
                    bot_response = add_book(args["title"], args["author"])
                elif tool_name == "delete_book":
                    bot_response = delete_book(args["book_id"])
                elif tool_name == "update_book":
                    bot_response = update_book(args["book_id"], args["new_title"], args["new_author"])
            else:
                bot_response = item.content[0].text if hasattr(item, "content") else "I didn't understand that."

        chat_history.append({"role": "bot", "content": bot_response})

    return render_template("index.html", chat_history=chat_history, library=list_books())

@app.route('/search', methods=['GET'])
def search_books():
    query = request.args.get('query', '').strip().lower()
    filter_by = request.args.get('filter_by', 'title')  # Default to searching by title

    # Fetch books from the database
    books = list_books()

    # Filter books based on the query and filter_by criteria
    if filter_by == 'title':
        filtered_books = [book for book in books if query in book['title'].lower()]
    elif filter_by == 'author':
        filtered_books = [book for book in books if query in book['author'].lower()]
    elif filter_by == 'status':
        filtered_books = [book for book in books if query in book['status'].lower()]
    else:
        filtered_books = books  # If no valid filter is provided, return all books

    return render_template("index.html", chat_history=[], library=filtered_books)


@app.route('/api/books', methods=['POST'])
def api_add_book():
    data = request.form
    title = data.get("title")
    author = data.get("author")
    if title and author:
        add_book(title, author)
        return redirect(url_for('index'))  # Redirect to the main page
    return jsonify(error="Title and author are required."), 400

@app.route('/api/books/<int:book_id>', methods=['POST'])
def api_update_or_delete_book(book_id):
    method = request.form.get("_method")
    if method == "DELETE":
        delete_book(book_id)
        return redirect(url_for('index'))  # Redirect to the main page
    elif method == "PUT":
        title = request.form.get("title")
        author = request.form.get("author")
        if title and author:
            update_book(book_id, title, author)
            return redirect(url_for('index'))  # Redirect to the main page
        return jsonify(error="Title and author are required."), 400
    return jsonify(error="Invalid method."), 400

@app.route('/api/books/<int:book_id>/checkout', methods=['POST'])
def api_check_out_book(book_id):
    message = check_out_book(book_id)
    return redirect(url_for('index'))  # Redirect to the main page

@app.route('/api/books/<int:book_id>/checkin', methods=['POST'])
def api_check_in_book(book_id):
    message = check_in_book(book_id)
    return redirect(url_for('index'))  # Redirect to the main page

# Initialize database and run app
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
