from database.db_handling import FLASK_HOST
from . import app

if __name__ == '__main__':
    app.run(host=FLASK_HOST)