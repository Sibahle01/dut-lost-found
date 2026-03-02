from flask import Blueprint

bp = Blueprint('notifications', __name__)

# Import routes to register them
from app.notifications import routes
