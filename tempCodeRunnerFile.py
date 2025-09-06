from sqlalchemy import or_
import pytz
from werkzeug.security import generate_password_hash, check_password_hash

from datetime import datetime, timedelta, time, timezone
from functools import wraps
import uuid
import csv
from io import StringIO
import json
from collections import Counter, OrderedDict
import math

# --- AI IMPORTS AND SETUP ---
from dotenv import load_dotenv
import google.generativeai as genai
