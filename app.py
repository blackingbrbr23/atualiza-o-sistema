from flask import Flask, request, render_template, redirect, url_for
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'static/atualizacoes'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    arquivos = os.listdir(UPLOAD_FOLDER)
    return render_template('index.html', arquivos=arquivos)

@app.route('/upload', methods=['POST'])
def upload():
    f = request.files['arquivo']
    f.save(os.path.join(UPLOAD_FOLDER, f.filename))
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
