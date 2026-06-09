import json
from api.main import app

def dump_openapi(path='openapi.json'):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(app.openapi(), f, indent=2)

if __name__ == '__main__':
    dump_openapi()
    print('OpenAPI schema written to openapi.json')
