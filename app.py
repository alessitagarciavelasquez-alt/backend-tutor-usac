from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

app = Flask(_name_)
CORS(app)

# Configuración SQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///estudiante.db'
db = SQLAlchemy(app)

class Historial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50)) # Resumen, Mapa, etc.
    contenido = db.Column(db.Text)
    fecha = db.Column(db.DateTime, server_default=db.func.now())

with app.app_context():
    db.create_all()

@app.route('/guardar', methods=['POST'])
def guardar():
    data = request.json
    nuevo = Historial(tipo=data['tipo'], contenido=data['contenido'])
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({"mensaje": "Guardado en SQL exitosamente"})

if _name_ == "_main_":
    app.run()
