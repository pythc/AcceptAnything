from dataclasses import dataclass
from urllib.request import Request
from flask import Flask, jsonify
from pydantic import BaseModel

@dataclass
class Summary:
    method: str
    value: int

class ModelSummary(BaseModel):
    method: str
    value: int

def request_summary(value: int):
    return Summary(Request('https://example.invalid/').get_method(), value * 2)

def model_summary(value: int):
    return ModelSummary(method=Request('https://example.invalid/').get_method(), value=value * 2)

app = Flask(__name__)

@app.get('/')
def index():
    return '<h1>验收校准</h1>'

@app.get('/large')
def large():
    return jsonify(data='x' * (2 * 1024 * 1024), tail='完整末尾')
