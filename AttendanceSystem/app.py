from attendance import create_app, init_db
from flask import redirect, url_for

# Initialize the database first
init_db()

app = create_app()

# Add a root route to redirect to portal selection page
@app.route('/')
def index():
    return redirect('/portal')

# Add a new route for portal selection
@app.route('/portal')
def portal_selection():
    return redirect(url_for('admin.portal_selection'))

if __name__ == "__main__":
    app.run(debug=True)