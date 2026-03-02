from flask import Blueprint

bp = Blueprint('claims', __name__)

# Import routes to register them
from app.claims import routes
