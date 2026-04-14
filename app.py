import os
from flask import Flask
# ... otros imports ...

app = Flask(_name_)

# Configuración segura para Render
basedir = os.path.abspath(os.path.dirname(_file_))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'estudiante.db')
