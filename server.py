from waitress import serve
from app import app  # Substitua 'app' pelo nome da sua instância Flask ou Django

if __name__ == "__main__":
    serve(app, host='0.0.0.0', port=8080) # Ou a porta que você preferir