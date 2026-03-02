from flask import Blueprint

bp = Blueprint('admin', __name__)

# Import routes to register them
from app.admin import routes
