from flask import Blueprint

bp = Blueprint('items', __name__)

# Import routes to register them with the blueprint
from app.items import routes
