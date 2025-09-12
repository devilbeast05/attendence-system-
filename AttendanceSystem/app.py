from attendance import create_app, init_db

app = create_app()

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
