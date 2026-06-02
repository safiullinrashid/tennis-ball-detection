import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from backend.app import app

if __name__ == '__main__':
    print("Tennis Ball Detection Server starting on http://localhost:5000")
    print("Open frontend/index.html in a browser")
    app.run(debug=True, host='0.0.0.0', port=5000)